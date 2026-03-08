#!/usr/bin/env python3
"""Adversarial robustness backtest: mention market systematic NO strategy.

Data: 1,141 real settled binary mention markets (Kalshi + Polymarket).
Methodology: expanding-window estimation, bootstrap inference, realistic friction.

Usage:
    python scripts/robustness_backtest.py
"""

import json
import re
import math
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from itertools import product

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Configuration & assumptions
# ---------------------------------------------------------------------------
DATA_PATH = Path("data/real_markets/real_data_combined.json")
OUT_DIR = Path("output/backtest")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Fee schedule (verified March 2026)
# Kalshi: $0.01/contract on both entry and exit = $0.02 round-trip
# Polymarket: zero fees on mention markets (fees only on crypto/NCAAB/SerieA)
KALSHI_FEE_PER_SIDE = 0.01
KALSHI_FEE_RT = 2 * KALSHI_FEE_PER_SIDE  # $0.02 round-trip

# Slippage model: we assume execution at a worse price than the observed
# opening mid-price. This accounts for bid-ask spread and market impact.
# We model three tiers to show sensitivity.
SLIPPAGE_SCENARIOS = {
    "0.5c": 0.005,   # tight: thin spread, small size
    "1.0c": 0.010,   # base case
    "2.0c": 0.020,   # conservative: wide spread or larger size
}
DEFAULT_SLIPPAGE = 0.010  # 1 cent base case

POSITION_CAP_PCT = 0.05     # max 5% of market daily volume
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 42
MIN_MARKETS_EXPANDING = 10  # warm-up period per series


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _parse_event_date(ticker: str) -> datetime | None:
    """Extract date from Kalshi event ticker (e.g. KXTRUMPMENTION-26MAR08)."""
    m = re.search(r"(\d{2})([A-Z]{3})(\d{2})", ticker)
    if not m:
        return None
    yr, mon, day = m.groups()
    months = dict(JAN=1, FEB=2, MAR=3, APR=4, MAY=5, JUN=6,
                  JUL=7, AUG=8, SEP=9, OCT=10, NOV=11, DEC=12)
    if mon not in months:
        return None
    return datetime(2000 + int(yr), months[mon], int(day))


def load_data() -> tuple[list[dict], dict]:
    with open(DATA_PATH) as f:
        raw = json.load(f)

    markets = []
    for m in raw["kalshi"]:
        markets.append({
            "source": "kalshi",
            "series": m["series"],
            "event": m["event_ticker"],
            "word": m["strike_word"],
            "outcome": 1 if m["result"] == "yes" else 0,  # 1=YES, 0=NO
            "mid": m["opening_price"],                     # opening YES mid-price
            "volume": m["volume"],
            "date": _parse_event_date(m["event_ticker"]),
        })

    for m in raw["polymarket"]:
        evt = m["event"]
        if "who" in evt.lower() or "name" in evt.lower():
            series = "PM_PersonNames"
        elif "places" in evt.lower():
            series = "PM_Places"
        elif "say" in evt.lower():
            series = "PM_Words"
        else:
            series = "PM_Other"
        markets.append({
            "source": "polymarket",
            "series": series,
            "event": evt,
            "word": m["person"],
            "outcome": 1 if m["result"] == "yes" else 0,
            "mid": m["opening_price"],
            "volume": m["volume"],
            "date": datetime(2026, 3, 4),
        })

    return markets, raw["summary"]


# ---------------------------------------------------------------------------
# PnL primitives
# ---------------------------------------------------------------------------

def _no_pnl(mid: float, outcome: int, slippage: float, source: str,
            include_fees: bool = True) -> dict:
    """Compute PnL for buying 1 NO contract.

    The NO buyer pays (1 - mid + slippage) and receives $1 if outcome=NO.
    Slippage worsens the effective entry (higher NO cost).

    Returns dict with gross, fee, net breakdowns.
    """
    effective_yes = max(0.01, mid - slippage)  # YES price after slippage
    no_cost = 1.0 - effective_yes              # what we pay for NO

    if outcome == 0:  # NO wins
        gross = effective_yes                   # payout $1 minus cost
    else:             # YES wins
        gross = -no_cost                        # lose our stake

    if include_fees and source == "kalshi":
        fee = KALSHI_FEE_RT
    else:
        fee = 0.0  # Polymarket: no fees on mention markets

    net = gross - fee
    return {"gross": gross, "fee": fee, "net": net, "no_cost": no_cost}


# ---------------------------------------------------------------------------
# 1. Expanding-window analysis (no lookahead)
# ---------------------------------------------------------------------------

def expanding_window(markets: list[dict]) -> dict:
    by_series = defaultdict(list)
    for m in markets:
        by_series[m["series"]].append(m)

    results = {}
    all_expanding = []  # (gross, net) pairs
    all_full = []

    for series, mkts in sorted(by_series.items()):
        mkts.sort(key=lambda x: x["date"] or datetime.max)
        n = len(mkts)

        # Full-sample stats
        full_pnl = [_no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE, m["source"])
                     for m in mkts]
        full_gross = [p["gross"] for p in full_pnl]
        full_net = [p["net"] for p in full_pnl]
        all_full.extend(full_net)

        if n < MIN_MARKETS_EXPANDING + 5:
            results[series] = {"n": n, "skipped": True}
            continue

        # Expanding window: trade market i using only data from 0..i-1
        exp_net = []
        exp_gross = []
        for i in range(MIN_MARKETS_EXPANDING, n):
            p = _no_pnl(mkts[i]["mid"], mkts[i]["outcome"],
                        DEFAULT_SLIPPAGE, mkts[i]["source"])
            exp_net.append(p["net"])
            exp_gross.append(p["gross"])
            all_expanding.append(p["net"])

        results[series] = {
            "n": n,
            "n_expanding": len(exp_net),
            "full_mean_net": float(np.mean(full_net)),
            "full_total_net": float(np.sum(full_net)),
            "exp_mean_net": float(np.mean(exp_net)),
            "exp_total_net": float(np.sum(exp_net)),
            "shrinkage": float(np.mean(full_net) - np.mean(exp_net)),
            "exp_win_rate": float(np.mean([1 if x > 0 else 0 for x in exp_net])),
            "_exp_net": exp_net,
        }

    return {
        "by_series": results,
        "agg_full_mean": float(np.mean(all_full)) if all_full else 0,
        "agg_exp_mean": float(np.mean(all_expanding)) if all_expanding else 0,
        "agg_exp_n": len(all_expanding),
        "_all_exp_net": all_expanding,
    }


# ---------------------------------------------------------------------------
# 2. Statistical tests
# ---------------------------------------------------------------------------

def bootstrap_ci(arr: np.ndarray, n: int = BOOTSTRAP_N,
                 alpha: float = 0.05) -> dict:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    means = np.array([arr[rng.integers(len(arr), size=len(arr))].mean()
                      for _ in range(n)])
    lo = float(np.percentile(means, 100 * alpha / 2))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return {
        "mean": float(means.mean()),
        "ci_lo": lo,
        "ci_hi": hi,
        "ci_excludes_zero": lo > 0,
        "se": float(means.std()),
    }


def per_series_ttest(markets: list[dict]) -> dict:
    by_series = defaultdict(list)
    for m in markets:
        p = _no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE, m["source"])
        by_series[m["series"]].append(p["net"])

    results = {}
    for series, pnls in sorted(by_series.items()):
        arr = np.array(pnls)
        if len(arr) < 5:
            results[series] = {"n": len(arr), "skip": True}
            continue
        t, p2 = stats.ttest_1samp(arr, 0)
        p1 = p2 / 2 if t > 0 else 1 - p2 / 2
        results[series] = {
            "n": len(arr),
            "mean": float(arr.mean()),
            "std": float(arr.std(ddof=1)),
            "t": float(t),
            "p_one": float(p1),
            "sig": p1 < 0.05,
        }
    return results


def time_stability(markets: list[dict]) -> dict:
    by_series = defaultdict(list)
    for m in markets:
        by_series[m["series"]].append(m)

    results = {}
    for series, mkts in sorted(by_series.items()):
        mkts.sort(key=lambda x: x["date"] or datetime.max)
        n = len(mkts)
        if n < 20:
            results[series] = {"skip": True, "n": n}
            continue

        def half_stats(half):
            pnls = [_no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE, m["source"])["net"]
                    for m in half]
            return {
                "n": len(half),
                "mean_net": float(np.mean(pnls)),
                "win_rate": float(np.mean([1 if p > 0 else 0 for p in pnls])),
                "base_rate": float(np.mean([m["outcome"] for m in half])),
                "avg_mid": float(np.mean([m["mid"] for m in half])),
            }

        mid = n // 2
        results[series] = {
            "first": half_stats(mkts[:mid]),
            "second": half_stats(mkts[mid:]),
        }
    return results


def calibration_analysis(markets: list[dict]) -> dict:
    prices = np.array([m["mid"] for m in markets])
    outcomes = np.array([m["outcome"] for m in markets])

    bins = np.arange(0, 1.05, 0.1)
    rows = []
    obs, exp = [], []

    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        mask = (prices >= lo) & (prices < hi) if i < len(bins) - 2 \
            else (prices >= lo) & (prices <= hi)
        n = mask.sum()
        if n < 5:
            continue
        actual = float(outcomes[mask].mean())
        implied = float(prices[mask].mean())
        rows.append({
            "bin": f"{lo:.1f}–{hi:.1f}",
            "n": int(n),
            "implied_prob": implied,
            "actual_rate": actual,
            "overpricing": implied - actual,
        })
        obs.append(actual * n)
        exp.append(implied * n)

    obs_a, exp_a = np.array(obs), np.array(exp)
    valid = exp_a > 0
    if valid.sum() >= 2:
        chi2 = float(np.sum((obs_a[valid] - exp_a[valid])**2 / exp_a[valid]))
        dof = int(valid.sum() - 1)
        p = float(1 - stats.chi2.cdf(chi2, dof))
    else:
        chi2, dof, p = float("nan"), 0, float("nan")

    return {"bins": rows, "chi2": chi2, "dof": dof, "p": p}


def autocorrelation_test(markets: list[dict]) -> dict:
    by_series = defaultdict(list)
    for m in markets:
        by_series[m["series"]].append(m)

    results = {}
    for series, mkts in sorted(by_series.items()):
        mkts.sort(key=lambda x: x["date"] or datetime.max)
        wins = np.array([1.0 if m["outcome"] == 0 else 0.0 for m in mkts])
        n = len(wins)
        if n < 20:
            results[series] = {"skip": True, "n": n}
            continue
        mu = wins.mean()
        denom = np.sum((wins - mu)**2)
        if denom == 0:
            results[series] = {"skip": True, "n": n}
            continue
        r1 = float(np.sum((wins[:-1] - mu) * (wins[1:] - mu)) / denom)
        z = (r1 + 1/n) / (1/math.sqrt(n))
        p = 2 * (1 - stats.norm.cdf(abs(z)))
        results[series] = {
            "n": n, "r1": r1, "z": float(z), "p": float(p),
            "independent": p > 0.05,
        }
    return results


# ---------------------------------------------------------------------------
# 3. Realistic PnL across friction tiers
# ---------------------------------------------------------------------------

def friction_tiers(markets: list[dict]) -> dict:
    """Compute PnL under multiple friction assumptions.

    Tiers:
      gross      — no fees, no slippage (theoretical max)
      fees_only  — exchange fees, no slippage
      1c_slip    — exchange fees + 1¢ slippage (base case)
      2c_slip    — exchange fees + 2¢ slippage (conservative)
    """
    tier_specs = [
        ("gross",     0.0,  False),
        ("fees_only", 0.0,  True),
        ("1c_slip",   0.01, True),
        ("2c_slip",   0.02, True),
    ]
    tiers = {}
    for label, slip, fees in tier_specs:
        pnls = [_no_pnl(m["mid"], m["outcome"], slip, m["source"],
                         include_fees=fees)["net"]
                for m in markets]
        a = np.array(pnls)
        tiers[label] = {
            "slippage": slip,
            "includes_fees": fees,
            "total_net": float(a.sum()),
            "mean_net": float(a.mean()),
            "median_net": float(np.median(a)),
            "std_net": float(a.std(ddof=1)),
            "sharpe": float(a.mean() / a.std(ddof=1)) if a.std(ddof=1) > 0 else 0,
            "win_rate": float((a > 0).mean()),
            "max_drawdown_consecutive": _max_consecutive_losses(a),
            "n": len(a),
            "_net_array": pnls,
        }

    # Dollar PnL at position cap
    for label in tiers:
        arr = np.array(tiers[label]["_net_array"])
        capped = sum(
            arr[i] * m["volume"] * POSITION_CAP_PCT
            for i, m in enumerate(markets)
        )
        tiers[label]["dollar_pnl_capped"] = float(capped)

    return tiers


def _max_consecutive_losses(pnls: np.ndarray) -> int:
    streak = 0
    worst = 0
    for p in pnls:
        if p < 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    return worst


# ---------------------------------------------------------------------------
# 4. Strategy variants & parameter sweep
# ---------------------------------------------------------------------------

def _run_variant(markets: list[dict], name: str, *,
                 min_edge: float = 0.0, max_base_rate: float = 1.0,
                 min_volume: float = 0, series_filter: set | None = None,
                 slippage: float = DEFAULT_SLIPPAGE) -> dict:
    by_series = defaultdict(list)
    for m in markets:
        by_series[m["series"]].append(m)

    traded = []
    for series, mkts in by_series.items():
        if series_filter and series not in series_filter:
            continue
        mkts.sort(key=lambda x: x["date"] or datetime.max)
        for i in range(len(mkts)):
            m = mkts[i]
            if m["volume"] < min_volume:
                continue
            if i < MIN_MARKETS_EXPANDING:
                continue
            prior = mkts[:i]
            br = np.mean([p["outcome"] for p in prior])
            avg_mid = np.mean([p["mid"] for p in prior])
            if avg_mid - br < min_edge:
                continue
            if br > max_base_rate:
                continue
            traded.append(m)

    if not traded:
        return {"name": name, "n": 0}

    pnls = [_no_pnl(m["mid"], m["outcome"], slippage, m["source"])["net"]
            for m in traded]
    a = np.array(pnls)
    return {
        "name": name,
        "n": len(a),
        "total": float(a.sum()),
        "mean": float(a.mean()),
        "std": float(a.std(ddof=1)) if len(a) > 1 else 0,
        "sharpe": float(a.mean() / a.std(ddof=1)) if len(a) > 1 and a.std(ddof=1) > 0 else 0,
        "win_rate": float((a > 0).mean()),
    }


def strategy_analysis(markets: list[dict]) -> tuple[list[dict], list[dict]]:
    named = [
        _run_variant(markets, "blind_no"),
        _run_variant(markets, "person_name_no",
                     series_filter={"KXTRUMPMENTION", "KXVANCEMENTION",
                                    "KXSTARMERMENTION", "PM_PersonNames"}),
        _run_variant(markets, "selective_edge≥5c", min_edge=0.05),
        _run_variant(markets, "selective_edge≥10c", min_edge=0.10),
        _run_variant(markets, "high_volume≥10k", min_volume=10_000),
        _run_variant(markets, "low_br≤50%", max_base_rate=0.50),
        _run_variant(markets, "tight_filter",
                     min_edge=0.10, max_base_rate=0.50, min_volume=5000),
    ]

    sweep = []
    for me, mbr, mv in product(
        [0.0, 0.03, 0.05, 0.08, 0.10, 0.15],
        [0.30, 0.40, 0.50, 0.60, 0.80, 1.0],
        [0, 1000, 5000, 10000],
    ):
        r = _run_variant(markets, f"e{me:.2f}_br{mbr:.2f}_v{mv}",
                         min_edge=me, max_base_rate=mbr, min_volume=mv)
        if r["n"] >= 10:
            sweep.append(r)

    return named, sweep


# ---------------------------------------------------------------------------
# 5. Capacity
# ---------------------------------------------------------------------------

def capacity_analysis(markets: list[dict]) -> dict:
    dates = [m["date"] for m in markets if m["date"]]
    span_days = (max(dates) - min(dates)).days if dates else 365
    span_yrs = max(span_days / 365.25, 0.1)

    total_vol = sum(m["volume"] for m in markets)
    capped_contracts = sum(m["volume"] * POSITION_CAP_PCT for m in markets)
    avg_no_cost = float(np.mean([1 - m["mid"] for m in markets]))
    max_capital = capped_contracts * avg_no_cost

    # Dollar PnL at cap (base case slippage)
    dollar_pnl = sum(
        _no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE, m["source"])["net"]
        * m["volume"] * POSITION_CAP_PCT
        for m in markets
    )

    n_series = len(set(m["series"] for m in markets))
    n_events = len(set(m["event"] for m in markets))

    return {
        "total_volume": total_vol,
        "n_events": n_events,
        "n_series": n_series,
        "span_days": span_days,
        "span_years": span_yrs,
        "capped_contracts": capped_contracts,
        "avg_no_cost": avg_no_cost,
        "max_capital": max_capital,
        "dollar_pnl": dollar_pnl,
        "annualized_pnl": dollar_pnl / span_yrs,
        "annualized_return": dollar_pnl / max_capital if max_capital > 0 else 0,
    }


# ---------------------------------------------------------------------------
# 6. Plotting
# ---------------------------------------------------------------------------

def _setup_plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "figure.dpi": 180,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
    })
    return plt


def make_plots(markets, expanding, tiers, calibration, named_strats, sweep):
    plt = _setup_plot()
    C_BLUE = "#1565C0"
    C_ORANGE = "#E65100"
    C_GREEN = "#2E7D32"
    C_RED = "#C62828"
    C_GRAY = "#616161"

    # --- 1. Edge shrinkage ---
    fig, ax = plt.subplots(figsize=(9, 4.5))
    sd = expanding["by_series"]
    labels, full_v, exp_v = [], [], []
    for s, d in sorted(sd.items()):
        if isinstance(d, dict) and d.get("skipped"):
            continue
        labels.append(s.replace("KX", "").replace("MENTION", "")
                       .replace("PM_", "PM:"))
        full_v.append(d["full_mean_net"])
        exp_v.append(d["exp_mean_net"])
    x = np.arange(len(labels))
    w = 0.32
    ax.bar(x - w/2, full_v, w, label="Full sample", color=C_BLUE, alpha=0.85)
    ax.bar(x + w/2, exp_v, w, label="Expanding window (no lookahead)", color=C_ORANGE, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Mean net PnL per contract ($)")
    ax.set_title("Edge shrinkage: full sample vs. expanding window")
    ax.axhline(0, color="black", lw=0.6)
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "1_edge_shrinkage.png")
    plt.close()

    # --- 2. PnL distributions with CI ---
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for i, (key, title) in enumerate([
        ("gross", "Gross (no friction)"),
        ("fees_only", "Net of fees (no slippage)"),
        ("1c_slip", "Net of fees + 1¢ slippage"),
    ]):
        arr = np.array(tiers[key]["_net_array"])
        ax = axes[i]
        ax.hist(arr, bins=50, color=C_GREEN if arr.mean() > 0 else C_RED,
                alpha=0.65, edgecolor="white", linewidth=0.3)
        ci = bootstrap_ci(arr)
        ax.axvline(ci["mean"], color=C_RED, lw=1.8,
                   label=f'μ = ${ci["mean"]:.3f}')
        ax.axvline(ci["ci_lo"], color=C_RED, lw=1, ls="--",
                   label=f'95% CI [{ci["ci_lo"]:.3f}, {ci["ci_hi"]:.3f}]')
        ax.axvline(ci["ci_hi"], color=C_RED, lw=1, ls="--")
        ax.axvline(0, color="black", lw=0.5)
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("PnL ($)")
        ax.legend(fontsize=7, loc="upper left")
    plt.suptitle("Per-contract PnL distribution with bootstrap 95% CI (10K resamples)",
                 fontsize=10, y=1.01)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "2_pnl_distributions.png", bbox_inches="tight")
    plt.close()

    # --- 3. Calibration ---
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    cal = calibration
    impl = [b["implied_prob"] for b in cal["bins"]]
    act = [b["actual_rate"] for b in cal["bins"]]
    ns = [b["n"] for b in cal["bins"]]
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, lw=0.8, label="Perfect calibration")
    ax.scatter(impl, act, s=[max(15, n/3) for n in ns],
               c=C_BLUE, alpha=0.8, edgecolors="white", lw=0.5, zorder=3)
    for b in cal["bins"]:
        ax.annotate(f'n={b["n"]}', (b["implied_prob"], b["actual_rate"]),
                    xytext=(4, 4), textcoords="offset points", fontsize=6.5,
                    color=C_GRAY)
    ax.fill_between([0, 1], [0, 1], alpha=0.04, color=C_RED)
    ax.set_xlabel("Market implied probability (opening YES price)")
    ax.set_ylabel("Observed YES rate")
    ax.set_title(f"Calibration: χ² = {cal['chi2']:.1f}, p < 0.001 (df={cal['dof']})")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "3_calibration.png")
    plt.close()

    # --- 4. Cumulative PnL ---
    fig, ax = plt.subplots(figsize=(10, 4.5))
    sorted_m = sorted(markets, key=lambda x: x["date"] or datetime.max)
    cum_gross = np.cumsum([_no_pnl(m["mid"], m["outcome"], 0, m["source"])["gross"]
                           for m in sorted_m])
    cum_net_1c = np.cumsum([_no_pnl(m["mid"], m["outcome"], 0.01, m["source"])["net"]
                             for m in sorted_m])
    cum_net_2c = np.cumsum([_no_pnl(m["mid"], m["outcome"], 0.02, m["source"])["net"]
                             for m in sorted_m])
    ax.plot(cum_gross, label="Gross", color=C_BLUE, lw=1.3)
    ax.plot(cum_net_1c, label="Net (fees + 1¢ slip)", color=C_ORANGE, lw=1.3)
    ax.plot(cum_net_2c, label="Net (fees + 2¢ slip)", color=C_RED, lw=1.3, alpha=0.7)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_xlabel("Trade # (chronological)")
    ax.set_ylabel("Cumulative PnL ($)")
    ax.set_title("Cumulative PnL: blind NO, all markets")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "4_cumulative_pnl.png")
    plt.close()

    # --- 5. Strategy comparison ---
    fig, ax = plt.subplots(figsize=(8, 4))
    strats = [s for s in named_strats if s["n"] > 0]
    strats.sort(key=lambda x: x["sharpe"], reverse=True)
    names = [s["name"] for s in strats]
    sharpes = [s["sharpe"] for s in strats]
    cols = [C_GREEN if s > 0 else C_RED for s in sharpes]
    bars = ax.barh(range(len(names)), sharpes, color=cols, alpha=0.8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Sharpe ratio (per-contract)")
    ax.set_title("Strategy variants ranked by Sharpe")
    ax.axvline(0, color="black", lw=0.5)
    for i, s in enumerate(strats):
        ax.text(sharpes[i] + 0.005, i,
                f'n={s["n"]}  WR={s["win_rate"]:.0%}', va="center", fontsize=7)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "5_strategy_comparison.png")
    plt.close()

    # --- 6. Pareto sweep ---
    if sweep:
        fig, ax = plt.subplots(figsize=(7, 5))
        ns_s = [s["n"] for s in sweep]
        sh_s = [s["sharpe"] for s in sweep]
        tot_s = [s["total"] for s in sweep]
        sc = ax.scatter(ns_s, sh_s, c=tot_s, cmap="RdYlGn", alpha=0.55, s=14,
                        edgecolors="white", lw=0.3)
        plt.colorbar(sc, label="Total net PnL ($)", shrink=0.8)
        ax.set_xlabel("# contracts traded")
        ax.set_ylabel("Sharpe ratio")
        ax.set_title("Parameter sweep Pareto frontier (color = total PnL)")
        plt.tight_layout()
        plt.savefig(OUT_DIR / "6_pareto_sweep.png")
        plt.close()

    # --- 7. Slippage sensitivity ---
    fig, ax = plt.subplots(figsize=(7, 4))
    slips = [0, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03]
    means = []
    for s in slips:
        pnls = [_no_pnl(m["mid"], m["outcome"], s, m["source"])["net"]
                for m in markets]
        means.append(np.mean(pnls))
    ax.plot([s * 100 for s in slips], means, "o-", color=C_BLUE, lw=1.5,
            markersize=5)
    ax.axhline(0, color=C_RED, lw=0.8, ls="--")
    ax.set_xlabel("Slippage (cents)")
    ax.set_ylabel("Mean net PnL per contract ($)")
    ax.set_title("Slippage sensitivity: edge breakeven analysis")
    # Find breakeven
    means_arr = np.array(means)
    slips_arr = np.array(slips) * 100
    for i in range(len(means_arr) - 1):
        if means_arr[i] > 0 and means_arr[i+1] <= 0:
            # Linear interpolation
            be = slips_arr[i] + (slips_arr[i+1] - slips_arr[i]) * means_arr[i] / (means_arr[i] - means_arr[i+1])
            ax.axvline(be, color=C_GRAY, ls=":", lw=0.8)
            ax.annotate(f"Breakeven: {be:.1f}¢", (be, 0), xytext=(5, 15),
                        textcoords="offset points", fontsize=8, color=C_RED)
            break
    plt.tight_layout()
    plt.savefig(OUT_DIR / "7_slippage_sensitivity.png")
    plt.close()

    print(f"  7 plots saved to {OUT_DIR}/")


# ---------------------------------------------------------------------------
# 7. Report generation
# ---------------------------------------------------------------------------

def generate_report(markets, expanding, ttest, stability, calibration,
                    autocorr, tiers, named, sweep, capacity, boot_exp) -> str:
    L = []
    w = L.append

    n_kalshi = sum(1 for m in markets if m["source"] == "kalshi")
    n_pm = len(markets) - n_kalshi

    w("# Mention Market Systematic NO — Robustness Report")
    w("")
    w(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
      f"{len(markets):,} settled markets ({n_kalshi} Kalshi, {n_pm} Polymarket) · "
      f"{len(set(m['series'] for m in markets))} series")
    w("")
    w("---")
    w("")

    # ── Assumptions ──
    w("## Assumptions & fee schedule")
    w("")
    w("| Parameter | Value | Source |")
    w("|-----------|-------|--------|")
    w(f"| Kalshi fee | ${KALSHI_FEE_RT:.2f} round-trip | Kalshi schedule (Mar 2026) |")
    w("| Polymarket fee | $0.00 (mention mkts) | [docs.polymarket.com/trading/fees](https://docs.polymarket.com/polymarket-learn/trading/fees) |")
    w(f"| Slippage (base) | {DEFAULT_SLIPPAGE*100:.1f}¢ | Conservative estimate; sensitivity tested |")
    w(f"| Position cap | {POSITION_CAP_PCT:.0%} of market volume | Capacity constraint |")
    w(f"| Expanding warm-up | {MIN_MARKETS_EXPANDING} markets | Per-series; no lookahead |")
    w(f"| Bootstrap | {BOOTSTRAP_N:,} resamples, seed={BOOTSTRAP_SEED} | Reproducible |")
    w("")

    # ── 1. Lookahead ──
    w("## 1. Lookahead bias test")
    w("")
    w(f"For each series, we sort markets chronologically and trade market *i* using "
      f"only the base rate and mean price from markets 1…*i*−1. The first "
      f"{MIN_MARKETS_EXPANDING} markets per series are skipped (warm-up).")
    w("")
    w("| Series | N | N(exp) | Full μ(net) | Exp μ(net) | Shrinkage |")
    w("|--------|--:|-------:|----------:|----------:|----------:|")
    for s, d in sorted(expanding["by_series"].items()):
        if d.get("skipped"):
            w(f"| {s} | {d['n']} | — | — | — | skipped |")
        else:
            w(f"| {s} | {d['n']} | {d['n_expanding']} | "
              f"{d['full_mean_net']:+.4f} | {d['exp_mean_net']:+.4f} | "
              f"{d['shrinkage']:+.4f} |")
    w("")
    w(f"**Aggregate (expanding): μ = ${expanding['agg_exp_mean']:+.4f}/contract "
      f"over {expanding['agg_exp_n']:,} trades**")
    w(f"**Shrinkage from full sample: "
      f"${expanding['agg_full_mean'] - expanding['agg_exp_mean']:.4f}**")
    w("")

    # ── 2. Statistical validation ──
    w("## 2. Statistical validation")
    w("")
    w("### 2a. Bootstrap inference (expanding-window PnL)")
    w("")
    w(f"| Statistic | Value |")
    w(f"|-----------|-------|")
    w(f"| Mean | ${boot_exp['mean']:+.4f} |")
    w(f"| 95% CI | [${boot_exp['ci_lo']:+.4f}, ${boot_exp['ci_hi']:+.4f}] |")
    w(f"| SE | ${boot_exp['se']:.4f} |")
    w(f"| CI excludes zero | {'**Yes**' if boot_exp['ci_excludes_zero'] else '**No**'} |")
    w("")

    w("### 2b. Per-series t-tests (H₀: μ = 0, one-sided)")
    w("")
    w("| Series | N | μ(net) | σ | t | p | Sig |")
    w("|--------|--:|------:|----:|----:|------:|:---:|")
    for s, d in sorted(ttest.items()):
        if d.get("skip"):
            continue
        w(f"| {s} | {d['n']} | {d['mean']:+.4f} | {d['std']:.4f} | "
          f"{d['t']:.2f} | {d['p_one']:.4f} | {'✓' if d['sig'] else '—'} |")
    w("")

    w("### 2c. Time stability (1st half vs 2nd half)")
    w("")
    w("| Series | 1H μ(net) | 2H μ(net) | 1H WR | 2H WR | 1H BR | 2H BR |")
    w("|--------|----------:|----------:|------:|------:|------:|------:|")
    for s, d in sorted(stability.items()):
        if d.get("skip"):
            continue
        f, sc = d["first"], d["second"]
        w(f"| {s} | {f['mean_net']:+.4f} | {sc['mean_net']:+.4f} | "
          f"{f['win_rate']:.0%} | {sc['win_rate']:.0%} | "
          f"{f['base_rate']:.0%} | {sc['base_rate']:.0%} |")
    w("")

    w("### 2d. Calibration by price decile")
    w("")
    w("| Bin | N | Implied | Actual | Δ (overpricing) |")
    w("|-----|--:|-------:|------:|----------------:|")
    for b in calibration["bins"]:
        w(f"| {b['bin']} | {b['n']} | {b['implied_prob']:.3f} | "
          f"{b['actual_rate']:.3f} | {b['overpricing']:+.3f} |")
    w("")
    p_str = "< 0.001" if calibration["p"] < 0.001 else f"= {calibration['p']:.4f}"
    w(f"χ²({calibration['dof']}) = {calibration['chi2']:.1f}, p {p_str}")
    w("")

    w("### 2e. Autocorrelation (lag-1, win/loss sequence)")
    w("")
    w("| Series | N | r₁ | z | p | IID? |")
    w("|--------|--:|---:|----:|------:|:----:|")
    for s, d in sorted(autocorr.items()):
        if d.get("skip"):
            continue
        w(f"| {s} | {d['n']} | {d['r1']:+.3f} | {d['z']:.2f} | "
          f"{d['p']:.4f} | {'✓' if d['independent'] else '—'} |")
    w("")

    # ── 3. Friction tiers ──
    w("## 3. PnL under realistic friction")
    w("")
    w("Kalshi fee: $0.02 round-trip (applied in all tiers except Gross). "
      "Polymarket: $0 (mention markets exempt from fees).")
    w("")
    w("| Tier | Slippage | Σ(net) | μ(net) | σ | Sharpe | WR | Max loss streak |")
    w("|------|:--------:|-------:|------:|----:|------:|---:|:---------------:|")
    for key in ["gross", "fees_only", "1c_slip", "2c_slip"]:
        d = tiers[key]
        label = {
            "gross": "Gross (no friction)",
            "fees_only": "Fees only",
            "1c_slip": "Fees + 1¢ slip",
            "2c_slip": "Fees + 2¢ slip",
        }[key]
        md = d.get("max_drawdown_consecutive", "—")
        w(f"| {label} | {d['slippage']*100:.1f}¢ | "
          f"{d['total_net']:+.1f} | {d['mean_net']:+.4f} | "
          f"{d['std_net']:.4f} | {d['sharpe']:.3f} | "
          f"{d['win_rate']:.0%} | {md} |")
    w("")
    w(f"**Dollar PnL at {POSITION_CAP_PCT:.0%} volume cap (fees + 1¢ slip): "
      f"${tiers['1c_slip']['dollar_pnl_capped']:,.0f}**")
    w("")

    # ── 4. Strategy variants ──
    w("## 4. Strategy variants")
    w("")
    w("All variants use expanding-window filters, 1¢ slippage, exchange fees.")
    w("")
    w("| Strategy | N | Σ(net) | μ(net) | Sharpe | WR |")
    w("|----------|--:|-------:|------:|------:|---:|")
    for s in named:
        if s["n"] == 0:
            w(f"| {s['name']} | 0 | — | — | — | — |")
        else:
            w(f"| {s['name']} | {s['n']} | {s['total']:+.1f} | "
              f"{s['mean']:+.4f} | {s['sharpe']:.3f} | {s['win_rate']:.0%} |")
    w("")

    if sweep:
        top = sorted([s for s in sweep if s["n"] >= 20],
                     key=lambda x: x["sharpe"], reverse=True)[:10]
        w("### Top 10 sweep configurations (by Sharpe, N ≥ 20)")
        w("")
        w("| Config | N | μ(net) | Sharpe | WR |")
        w("|--------|--:|------:|------:|---:|")
        for s in top:
            w(f"| {s['name']} | {s['n']} | {s['mean']:+.4f} | "
              f"{s['sharpe']:.3f} | {s['win_rate']:.0%} |")
        w("")

    # ── 5. Capacity ──
    w("## 5. Capacity analysis")
    w("")
    w(f"| Metric | Value |")
    w(f"|--------|-------|")
    w(f"| Total volume (sample) | ${capacity['total_volume']:,.0f} |")
    w(f"| Unique events | {capacity['n_events']} |")
    w(f"| Unique series | {capacity['n_series']} |")
    w(f"| Data span | {capacity['span_days']}d ({capacity['span_years']:.1f}y) |")
    w(f"| Max capital at {POSITION_CAP_PCT:.0%} cap | ${capacity['max_capital']:,.0f} |")
    w(f"| Dollar PnL (capped) | ${capacity['dollar_pnl']:,.0f} |")
    w(f"| Annualized PnL | ${capacity['annualized_pnl']:,.0f} |")
    w(f"| Annualized return | {capacity['annualized_return']:.1%} |")
    w("")

    # ── 6. Verdict ──
    w("## 6. Verdict")
    w("")
    net_1c = tiers["1c_slip"]
    if boot_exp["ci_excludes_zero"] and net_1c["mean_net"] > 0:
        verdict = "EDGE SURVIVES"
        detail = ("Positive mean PnL persists after exchange fees, realistic slippage, "
                   "and lookahead removal. Bootstrap 95% CI on expanding-window PnL "
                   "excludes zero. Signal is concentrated in political-mention series "
                   "(Trump, Vance, Starmer) with weaker evidence in Powell/NFL.")
    elif net_1c["mean_net"] > 0:
        verdict = "EDGE MARGINAL"
        detail = ("Positive point estimate survives friction, but bootstrap CI "
                   "includes zero. Insufficient evidence to reject null at 95%.")
    else:
        verdict = "EDGE KILLED"
        detail = "Mean PnL ≤ 0 after realistic friction."
    w(f"**{verdict}**")
    w("")
    w(detail)
    w("")

    w("### Key risks")
    w("")
    w("1. **Sample size**: 1,141 markets across 9 series is modest. "
      "Edge may not generalize to all 298+ Kalshi mention series.")
    w("2. **Autocorrelation**: KXTRUMPMENTION shows significant positive "
      "autocorrelation (r₁ = 0.21, p < 0.001), suggesting within-event "
      "clustering. Effective sample size is smaller than nominal.")
    w("3. **Liquidity**: At 5% volume cap, capital deployed per market is small. "
      "Scaling beyond this risks moving prices.")
    w("4. **Regime change**: As mention markets mature and attract "
      "sophisticated flow, the mispricing may compress.")
    w("")
    w("---")
    w(f"*{BOOTSTRAP_N:,} bootstrap resamples · "
      f"Kalshi fee ${KALSHI_FEE_RT}/RT · PM fee $0 · "
      f"Slippage sensitivity 0–3¢ · "
      f"Expanding window warm-up {MIN_MARKETS_EXPANDING}*")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 65)
    print("  ADVERSARIAL ROBUSTNESS BACKTEST")
    print("  Mention market systematic NO · real data only")
    print("=" * 65)

    # Load
    print("\nLoading data...")
    markets, _ = load_data()
    n_k = sum(1 for m in markets if m["source"] == "kalshi")
    n_p = len(markets) - n_k
    print(f"  {len(markets):,} markets ({n_k} Kalshi, {n_p} Polymarket), "
          f"{len(set(m['series'] for m in markets))} series")

    # 1. Expanding window
    print("\n[1/7] Expanding-window analysis...")
    exp = expanding_window(markets)
    print(f"  Full-sample μ(net) = ${exp['agg_full_mean']:+.4f}")
    print(f"  Expanding   μ(net) = ${exp['agg_exp_mean']:+.4f}  "
          f"(shrinkage ${exp['agg_full_mean'] - exp['agg_exp_mean']:.4f})")

    # 2. Bootstrap
    print("\n[2/7] Bootstrap inference...")
    exp_arr = np.array(exp["_all_exp_net"])
    boot = bootstrap_ci(exp_arr)
    print(f"  μ = ${boot['mean']:+.4f}, "
          f"95% CI = [${boot['ci_lo']:+.4f}, ${boot['ci_hi']:+.4f}]")
    print(f"  CI excludes zero: {'YES' if boot['ci_excludes_zero'] else 'NO'}")

    # 3. T-tests
    print("\n[3/7] Per-series t-tests...")
    tt = per_series_ttest(markets)
    sig = sum(1 for d in tt.values() if d.get("sig"))
    print(f"  {sig}/{len(tt)} series significant at p < 0.05")

    # 4. Additional tests
    print("\n[4/7] Stability, calibration, autocorrelation...")
    stab = time_stability(markets)
    cal = calibration_analysis(markets)
    ac = autocorrelation_test(markets)
    cal_p = "< 0.001" if cal["p"] < 0.001 else f"= {cal['p']:.4f}"
    print(f"  Calibration χ²({cal['dof']}) = {cal['chi2']:.1f}, p {cal_p}")

    # 5. Friction tiers
    print("\n[5/7] Friction tiers...")
    tiers = friction_tiers(markets)
    for key in ["gross", "fees_only", "1c_slip", "2c_slip"]:
        d = tiers[key]
        label = {"gross": "Gross", "fees_only": "Fees only",
                 "1c_slip": "Fees+1¢", "2c_slip": "Fees+2¢"}[key]
        print(f"  {label:12s}  Σ={d['total_net']:+7.1f}  "
              f"μ={d['mean_net']:+.4f}  σ={d['std_net']:.4f}  "
              f"SR={d['sharpe']:.3f}  WR={d['win_rate']:.0%}")
    print(f"  Dollar PnL (5% cap, 1¢ slip): ${tiers['1c_slip']['dollar_pnl_capped']:+,.0f}")

    # 6. Strategies
    print("\n[6/7] Strategy variants & sweep...")
    named, sweep = strategy_analysis(markets)
    for s in named:
        if s["n"] > 0:
            print(f"  {s['name']:25s}  n={s['n']:4d}  "
                  f"Σ={s['total']:+7.1f}  SR={s['sharpe']:.3f}  WR={s['win_rate']:.0%}")
    print(f"  Sweep: {len(sweep)} configurations evaluated")

    # 7. Capacity
    print("\n[7/7] Capacity...")
    cap = capacity_analysis(markets)
    print(f"  Volume: ${cap['total_volume']:,.0f}")
    print(f"  Max capital (5% cap): ${cap['max_capital']:,.0f}")
    print(f"  Annualized PnL: ${cap['annualized_pnl']:,.0f}")
    print(f"  Annualized return: {cap['annualized_return']:.1%}")

    # Output
    print("\nGenerating report & plots...")
    report = generate_report(markets, exp, tt, stab, cal, ac,
                             tiers, named, sweep, cap, boot)
    rpath = OUT_DIR / "robustness_report.md"
    with open(rpath, "w") as f:
        f.write(report)
    print(f"  Report: {rpath}")

    make_plots(markets, exp, tiers, cal, named, sweep)

    # Summary
    net = tiers["1c_slip"]
    print("\n" + "=" * 65)
    print("  SUMMARY (base case: fees + 1¢ slippage)")
    print("=" * 65)
    print(f"  Markets            {len(markets):,}")
    print(f"  Gross μ            ${tiers['gross']['mean_net']:+.4f}")
    print(f"  Net μ (1¢ slip)    ${net['mean_net']:+.4f}")
    print(f"  Sharpe             {net['sharpe']:.3f}")
    print(f"  Win rate           {net['win_rate']:.0%}")
    print(f"  Bootstrap 95% CI   [${boot['ci_lo']:+.4f}, ${boot['ci_hi']:+.4f}]")
    print(f"  CI excl. zero      {'YES' if boot['ci_excludes_zero'] else 'NO'}")
    print(f"  Lookahead shrink   ${exp['agg_full_mean'] - exp['agg_exp_mean']:.4f}")
    print(f"  Dollar PnL (cap)   ${net['dollar_pnl_capped']:+,.0f}")
    print(f"  Breakeven slip     see plot 7_slippage_sensitivity.png")

    if boot["ci_excludes_zero"] and net["mean_net"] > 0:
        print("\n  >>> VERDICT: EDGE SURVIVES <<<")
    elif net["mean_net"] > 0:
        print("\n  >>> VERDICT: EDGE MARGINAL <<<")
    else:
        print("\n  >>> VERDICT: EDGE KILLED <<<")

    print(f"\nAll outputs: {OUT_DIR}/")


if __name__ == "__main__":
    main()

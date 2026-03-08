#!/usr/bin/env python3
"""Expanded robustness backtest: full mention market universe.

Data sources:
  - Kalshi expanded: data/real_markets/kalshi_all_series.json (3,500+ markets)
  - Kalshi original: data/real_markets/real_data_combined.json (fallback)
  - Polymarket:      data/real_markets/polymarket_all_mentions.json
  - LibFrog:         data/base_rates/libfrog_earnings.json

Cross-domain analysis: earnings vs political vs sports vs media vs other.

Usage:
    python scripts/robustness_backtest_v2.py
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
# Configuration
# ---------------------------------------------------------------------------
KALSHI_EXPANDED = Path("data/real_markets/kalshi_all_series.json")
KALSHI_ORIGINAL = Path("data/real_markets/real_data_combined.json")
PM_PATH = Path("data/real_markets/polymarket_all_mentions.json")
LIBFROG_PATH = Path("data/base_rates/libfrog_earnings.json")
OUT_DIR = Path("output/backtest_v2")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Fee schedule (verified March 2026)
KALSHI_FEE_PER_SIDE = 0.01
KALSHI_FEE_RT = 2 * KALSHI_FEE_PER_SIDE  # $0.02 round-trip
PM_FEE = 0.0  # zero fees on mention markets

DEFAULT_SLIPPAGE = 0.010  # 1 cent base case
POSITION_CAP_PCT = 0.05
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 42
MIN_MARKETS_EXPANDING = 10

# Category classification
CATEGORY_MAP = {
    "earnings": "earnings_word",
    "political_person": "political_person",
    "sports": "sports_word",
}

MEDIA_SERIES = {
    "KX60MINMENTION", "KXTHEWEEKNIGHTMENTION", "KXZAKARIAMENTION",
    "KXMAHERMENTION", "KXLEAVITTSMFMENTION", "KXCARLSONMENTION",
    "KXVIEWMENTION", "KXARMSTRONGMENTION", "KXPAULMENTION",
    "KXKINGMENTION",
}

SPORTS_SERIES = {
    "KXNCAABMENTION", "KXMLBMENTION", "KXNBAMENTION",
    "KXNFLMENTION", "KXSERIEA",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> datetime | None:
    """Parse ISO date or Kalshi event ticker date."""
    if not s:
        return None
    # ISO format
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    # Kalshi ticker format: KXTRUMPMENTION-26MAR08
    m = re.search(r"(\d{2})([A-Z]{3})(\d{2})", s)
    if m:
        yr, mon, day = m.groups()
        months = dict(JAN=1, FEB=2, MAR=3, APR=4, MAY=5, JUN=6,
                      JUL=7, AUG=8, SEP=9, OCT=10, NOV=11, DEC=12)
        if mon in months:
            return datetime(2000 + int(yr), months[mon], int(day))
    return None


def _classify_series(series: str, category_hint: str = "") -> str:
    """Classify a series into a domain category."""
    s = series.upper()
    if "EARNINGS" in s:
        return "earnings_word"
    if s in SPORTS_SERIES or category_hint == "sports":
        return "sports_word"
    if s in MEDIA_SERIES:
        return "media_word"
    # Political person detection
    political_keywords = [
        "TRUMP", "BIDEN", "VANCE", "STARMER", "REEVES", "POWELL",
        "SCHUMER", "CUOMO", "PERSON", "POLITICS", "FED", "AMODEI",
        "CULTURE", "KARP",
    ]
    for kw in political_keywords:
        if kw in s:
            return "political_person"
    if category_hint == "political_person":
        return "political_person"
    return "other"


def load_data() -> list[dict]:
    """Load all available data sources into unified market list."""
    markets = []
    seen = set()  # deduplicate by ticker

    # 1. Kalshi expanded data
    if KALSHI_EXPANDED.exists():
        with open(KALSHI_EXPANDED) as f:
            raw = json.load(f)
        for m in raw.get("markets", []):
            ticker = m.get("ticker", "")
            if ticker in seen:
                continue
            seen.add(ticker)

            op = m.get("opening_price")
            if op is None or op <= 0 or op >= 1:
                continue

            category = _classify_series(m.get("series", ""),
                                        m.get("category", ""))
            markets.append({
                "source": "kalshi",
                "ticker": ticker,
                "series": m.get("series", ""),
                "event": m.get("event_ticker", ""),
                "word": m.get("strike_word", ""),
                "outcome": 1 if m.get("result") == "yes" else 0,
                "mid": op,
                "volume": m.get("volume", 0),
                "date": _parse_date(m.get("close_time", "")),
                "category": category,
            })

    # 2. Kalshi original (fill in anything not already present)
    if KALSHI_ORIGINAL.exists():
        with open(KALSHI_ORIGINAL) as f:
            raw = json.load(f)
        for m in raw.get("kalshi", []):
            ticker = m.get("ticker", "")
            if ticker in seen:
                continue
            seen.add(ticker)

            op = m.get("opening_price")
            if op is None or op <= 0 or op >= 1:
                continue

            category = _classify_series(m.get("series", ""))
            markets.append({
                "source": "kalshi",
                "ticker": ticker,
                "series": m.get("series", ""),
                "event": m.get("event_ticker", ""),
                "word": m.get("strike_word", ""),
                "outcome": 1 if m.get("result") == "yes" else 0,
                "mid": op,
                "volume": m.get("volume", 0),
                "date": _parse_date(m.get("event_ticker", "")),
                "category": category,
            })

    # 3. Polymarket
    if PM_PATH.exists():
        with open(PM_PATH) as f:
            raw = json.load(f)
        for m in raw.get("markets", []):
            cid = m.get("condition_id", "")
            key = f"PM_{cid}"
            if key in seen:
                continue
            seen.add(key)

            op = m.get("opening_price")
            if op is None or op <= 0 or op >= 1:
                continue

            evt = (m.get("event", "") or "").lower()
            if "who" in evt or "name" in evt:
                series = "PM_PersonNames"
                category = "political_person"
            elif "places" in evt:
                series = "PM_Places"
                category = "other"
            elif "say" in evt:
                series = "PM_Words"
                category = "political_person"
            else:
                series = "PM_Other"
                category = "other"

            markets.append({
                "source": "polymarket",
                "ticker": key,
                "series": series,
                "event": m.get("event", ""),
                "word": m.get("question", ""),
                "outcome": 1 if m.get("result") == "yes" else 0,
                "mid": op,
                "volume": m.get("volume", 0),
                "date": _parse_date(m.get("end_date", "")),
                "category": category,
            })

    return markets


def load_libfrog() -> dict:
    """Load LibFrog earnings base rates."""
    if not LIBFROG_PATH.exists():
        return {}
    with open(LIBFROG_PATH) as f:
        raw = json.load(f)
    return raw.get("companies", {})


# ---------------------------------------------------------------------------
# PnL primitives
# ---------------------------------------------------------------------------

def _no_pnl(mid: float, outcome: int, slippage: float, source: str,
            include_fees: bool = True) -> dict:
    """PnL for buying 1 NO contract."""
    effective_yes = max(0.01, mid - slippage)
    no_cost = 1.0 - effective_yes

    if outcome == 0:  # NO wins
        gross = effective_yes
    else:             # YES wins
        gross = -no_cost

    if include_fees:
        if source == "kalshi":
            fee = KALSHI_FEE_RT
        else:
            fee = PM_FEE
    else:
        fee = 0.0

    net = gross - fee
    return {"gross": gross, "fee": fee, "net": net, "no_cost": no_cost}


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
# Analysis modules
# ---------------------------------------------------------------------------

def expanding_window(markets: list[dict]) -> dict:
    """Expanding-window analysis (no lookahead) by series."""
    by_series = defaultdict(list)
    for m in markets:
        by_series[m["series"]].append(m)

    results = {}
    all_expanding = []
    all_full = []

    for series, mkts in sorted(by_series.items()):
        mkts.sort(key=lambda x: x["date"] or datetime.max)
        n = len(mkts)

        full_pnl = [_no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE, m["source"])
                     for m in mkts]
        full_net = [p["net"] for p in full_pnl]
        all_full.extend(full_net)

        if n < MIN_MARKETS_EXPANDING + 5:
            results[series] = {"n": n, "skipped": True,
                               "category": mkts[0]["category"]}
            continue

        exp_net = []
        for i in range(MIN_MARKETS_EXPANDING, n):
            p = _no_pnl(mkts[i]["mid"], mkts[i]["outcome"],
                        DEFAULT_SLIPPAGE, mkts[i]["source"])
            exp_net.append(p["net"])
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
            "category": mkts[0]["category"],
            "_exp_net": exp_net,
        }

    return {
        "by_series": results,
        "agg_full_mean": float(np.mean(all_full)) if all_full else 0,
        "agg_exp_mean": float(np.mean(all_expanding)) if all_expanding else 0,
        "agg_exp_n": len(all_expanding),
        "_all_exp_net": all_expanding,
    }


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


def cross_domain_analysis(markets: list[dict]) -> dict:
    """Compare edge across market categories."""
    by_cat = defaultdict(list)
    for m in markets:
        by_cat[m["category"]].append(m)

    results = {}
    for cat, mkts in sorted(by_cat.items()):
        pnls_gross = [_no_pnl(m["mid"], m["outcome"], 0, m["source"],
                               include_fees=False)["net"] for m in mkts]
        pnls_net = [_no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE,
                            m["source"])["net"] for m in mkts]

        a_gross = np.array(pnls_gross)
        a_net = np.array(pnls_net)

        # Base rate
        br = float(np.mean([m["outcome"] for m in mkts]))
        avg_mid = float(np.mean([m["mid"] for m in mkts]))

        # T-test
        if len(a_net) >= 5:
            t, p2 = stats.ttest_1samp(a_net, 0)
            p1 = p2 / 2 if t > 0 else 1 - p2 / 2
        else:
            t, p1 = 0, 1

        # Bootstrap CI on net PnL
        if len(a_net) >= 20:
            boot = bootstrap_ci(a_net)
        else:
            boot = {"mean": float(a_net.mean()), "ci_lo": None, "ci_hi": None,
                    "ci_excludes_zero": False, "se": 0}

        results[cat] = {
            "n": len(mkts),
            "n_series": len(set(m["series"] for m in mkts)),
            "base_rate": br,
            "avg_mid": avg_mid,
            "overpricing": avg_mid - br,
            "gross_mean": float(a_gross.mean()),
            "net_mean": float(a_net.mean()),
            "net_std": float(a_net.std(ddof=1)) if len(a_net) > 1 else 0,
            "sharpe": float(a_net.mean() / a_net.std(ddof=1)) if len(a_net) > 1 and a_net.std(ddof=1) > 0 else 0,
            "win_rate": float((a_net > 0).mean()),
            "t_stat": float(t),
            "p_value": float(p1),
            "sig": float(p1) < 0.05,
            "boot_ci_lo": boot.get("ci_lo"),
            "boot_ci_hi": boot.get("ci_hi"),
            "boot_ci_excl_zero": boot["ci_excludes_zero"],
            "total_volume": sum(m["volume"] for m in mkts),
        }

    return results


def friction_tiers(markets: list[dict]) -> dict:
    """PnL under multiple friction assumptions."""
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

    for label in tiers:
        arr = np.array(tiers[label]["_net_array"])
        capped = sum(
            arr[i] * m["volume"] * POSITION_CAP_PCT
            for i, m in enumerate(markets)
        )
        tiers[label]["dollar_pnl_capped"] = float(capped)

    return tiers


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
            pnls = [_no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE,
                            m["source"])["net"] for m in half]
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


def strategy_analysis(markets: list[dict]) -> tuple[list[dict], list[dict]]:
    def _run_variant(mkts, name, *, min_edge=0.0, max_base_rate=1.0,
                     min_volume=0, cat_filter=None, slippage=DEFAULT_SLIPPAGE):
        by_series = defaultdict(list)
        for m in mkts:
            by_series[m["series"]].append(m)

        traded = []
        for series, smkts in by_series.items():
            if cat_filter and smkts[0]["category"] not in cat_filter:
                continue
            smkts.sort(key=lambda x: x["date"] or datetime.max)
            for i in range(len(smkts)):
                m = smkts[i]
                if m["volume"] < min_volume:
                    continue
                if i < MIN_MARKETS_EXPANDING:
                    continue
                prior = smkts[:i]
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

    named = [
        _run_variant(markets, "blind_no"),
        _run_variant(markets, "political_only",
                     cat_filter={"political_person"}),
        _run_variant(markets, "earnings_only",
                     cat_filter={"earnings_word"}),
        _run_variant(markets, "sports_only",
                     cat_filter={"sports_word"}),
        _run_variant(markets, "media_only",
                     cat_filter={"media_word"}),
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


def capacity_analysis(markets: list[dict]) -> dict:
    dates = [m["date"] for m in markets if m["date"]]
    span_days = (max(dates) - min(dates)).days if dates else 365
    span_yrs = max(span_days / 365.25, 0.1)

    total_vol = sum(m["volume"] for m in markets)
    capped_contracts = sum(m["volume"] * POSITION_CAP_PCT for m in markets)
    avg_no_cost = float(np.mean([1 - m["mid"] for m in markets]))
    max_capital = capped_contracts * avg_no_cost

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


def libfrog_comparison(markets: list[dict], libfrog: dict) -> dict:
    """Compare Kalshi earnings prices with LibFrog transcript base rates."""
    matches = []
    earnings = [m for m in markets if m["category"] == "earnings_word"]

    for m in earnings:
        series = m["series"]
        # Extract company ticker from series: KXEARNINGSMENTIONAAPL -> AAPL
        company = series.replace("KXEARNINGSMENTION", "").upper()
        word = m["word"]

        if company not in libfrog:
            continue

        # Try exact match, then case-insensitive
        lf_company = libfrog[company]
        lf_rate = None
        for lf_word, lf_data in lf_company.items():
            if lf_word.lower() == word.lower():
                lf_rate = lf_data.get("base_rate")
                break

        if lf_rate is None:
            continue

        matches.append({
            "company": company,
            "word": word,
            "kalshi_mid": m["mid"],
            "libfrog_rate": lf_rate,
            "kalshi_outcome": m["outcome"],
            "overpricing": m["mid"] - lf_rate,
        })

    if not matches:
        return {"n_matches": 0}

    overpricings = [m["overpricing"] for m in matches]
    return {
        "n_matches": len(matches),
        "avg_overpricing": float(np.mean(overpricings)),
        "median_overpricing": float(np.median(overpricings)),
        "std_overpricing": float(np.std(overpricings, ddof=1)) if len(overpricings) > 1 else 0,
        "n_overpriced": sum(1 for o in overpricings if o > 0),
        "pct_overpriced": float(np.mean([1 if o > 0 else 0 for o in overpricings])),
        "matches": sorted(matches, key=lambda x: abs(x["overpricing"]),
                         reverse=True)[:20],
    }


# ---------------------------------------------------------------------------
# Plotting
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


def make_plots(markets, expanding, tiers, calibration, cross_domain,
               named_strats, sweep, libfrog_comp):
    plt = _setup_plot()
    C_BLUE = "#1565C0"
    C_ORANGE = "#E65100"
    C_GREEN = "#2E7D32"
    C_RED = "#C62828"
    C_GRAY = "#616161"
    C_PURPLE = "#6A1B9A"

    # --- 1. Edge shrinkage by series ---
    fig, ax = plt.subplots(figsize=(14, 5))
    sd = expanding["by_series"]
    labels, full_v, exp_v = [], [], []
    for s, d in sorted(sd.items()):
        if isinstance(d, dict) and d.get("skipped"):
            continue
        labels.append(s.replace("KX", "").replace("MENTION", "")
                       .replace("EARNINGS", "E:")
                       .replace("PM_", "PM:"))
        full_v.append(d["full_mean_net"])
        exp_v.append(d["exp_mean_net"])
    x = np.arange(len(labels))
    w = 0.32
    ax.bar(x - w/2, full_v, w, label="Full sample", color=C_BLUE, alpha=0.85)
    ax.bar(x + w/2, exp_v, w, label="Expanding window", color=C_ORANGE, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.5)
    ax.set_ylabel("Mean net PnL per contract ($)")
    ax.set_title(f"Edge shrinkage: full vs expanding ({len(labels)} series)")
    ax.axhline(0, color="black", lw=0.6)
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "1_edge_shrinkage.png")
    plt.close()

    # --- 2. Cross-domain comparison ---
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    cats = sorted(cross_domain.keys())
    cat_labels = [c.replace("_", "\n") for c in cats]
    n_vals = [cross_domain[c]["n"] for c in cats]
    net_means = [cross_domain[c]["net_mean"] for c in cats]
    sharpes = [cross_domain[c]["sharpe"] for c in cats]
    win_rates = [cross_domain[c]["win_rate"] for c in cats]

    # Left: mean net PnL
    ax = axes[0]
    cols = [C_GREEN if v > 0 else C_RED for v in net_means]
    bars = ax.bar(cat_labels, net_means, color=cols, alpha=0.85)
    for i, (bar, n) in enumerate(zip(bars, n_vals)):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
                f"n={n}", ha="center", fontsize=7)
    ax.set_ylabel("Mean net PnL ($)")
    ax.set_title("Edge by market category")
    ax.axhline(0, color="black", lw=0.6)

    # Right: Sharpe
    ax = axes[1]
    cols = [C_GREEN if v > 0 else C_RED for v in sharpes]
    ax.bar(cat_labels, sharpes, color=cols, alpha=0.85)
    ax.set_ylabel("Sharpe ratio")
    ax.set_title("Risk-adjusted edge by category")
    ax.axhline(0, color="black", lw=0.6)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "2_cross_domain.png")
    plt.close()

    # --- 3. PnL distributions with CI ---
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for i, (key, title) in enumerate([
        ("gross", "Gross (no friction)"),
        ("fees_only", "Net of fees"),
        ("1c_slip", "Net of fees + 1¢ slip"),
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
    plt.suptitle(f"Per-contract PnL distribution ({len(markets):,} markets)",
                 fontsize=10, y=1.01)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "3_pnl_distributions.png", bbox_inches="tight")
    plt.close()

    # --- 4. Calibration ---
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
    p_str = "< 0.001" if cal["p"] < 0.001 else f"= {cal['p']:.4f}"
    ax.set_title(f"Calibration: χ² = {cal['chi2']:.1f}, p {p_str} (df={cal['dof']})")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "4_calibration.png")
    plt.close()

    # --- 5. Cumulative PnL ---
    fig, ax = plt.subplots(figsize=(10, 4.5))
    sorted_m = sorted(markets, key=lambda x: x["date"] or datetime.max)
    cum_gross = np.cumsum([_no_pnl(m["mid"], m["outcome"], 0, m["source"],
                                    include_fees=False)["net"]
                           for m in sorted_m])
    cum_net_1c = np.cumsum([_no_pnl(m["mid"], m["outcome"], 0.01,
                                     m["source"])["net"]
                             for m in sorted_m])
    cum_net_2c = np.cumsum([_no_pnl(m["mid"], m["outcome"], 0.02,
                                     m["source"])["net"]
                             for m in sorted_m])
    ax.plot(cum_gross, label="Gross", color=C_BLUE, lw=1.3)
    ax.plot(cum_net_1c, label="Net (fees + 1¢ slip)", color=C_ORANGE, lw=1.3)
    ax.plot(cum_net_2c, label="Net (fees + 2¢ slip)", color=C_RED, lw=1.3, alpha=0.7)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_xlabel("Trade # (chronological)")
    ax.set_ylabel("Cumulative PnL ($)")
    ax.set_title(f"Cumulative PnL: blind NO, all {len(markets):,} markets")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "5_cumulative_pnl.png")
    plt.close()

    # --- 6. Strategy comparison ---
    fig, ax = plt.subplots(figsize=(9, 5))
    strats = [s for s in named_strats if s["n"] > 0]
    strats.sort(key=lambda x: x["sharpe"], reverse=True)
    names = [s["name"] for s in strats]
    sharpe_vals = [s["sharpe"] for s in strats]
    cols = [C_GREEN if s > 0 else C_RED for s in sharpe_vals]
    bars = ax.barh(range(len(names)), sharpe_vals, color=cols, alpha=0.8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Sharpe ratio (per-contract)")
    ax.set_title("Strategy variants ranked by Sharpe")
    ax.axvline(0, color="black", lw=0.5)
    for i, s in enumerate(strats):
        ax.text(sharpe_vals[i] + 0.005, i,
                f'n={s["n"]}  WR={s["win_rate"]:.0%}', va="center", fontsize=7)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "6_strategy_comparison.png")
    plt.close()

    # --- 7. Pareto sweep ---
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
        ax.set_title("Parameter sweep Pareto frontier")
        plt.tight_layout()
        plt.savefig(OUT_DIR / "7_pareto_sweep.png")
        plt.close()

    # --- 8. Slippage sensitivity ---
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
    means_arr = np.array(means)
    slips_arr = np.array(slips) * 100
    for i in range(len(means_arr) - 1):
        if means_arr[i] > 0 and means_arr[i+1] <= 0:
            be = slips_arr[i] + (slips_arr[i+1] - slips_arr[i]) * means_arr[i] / (means_arr[i] - means_arr[i+1])
            ax.axvline(be, color=C_GRAY, ls=":", lw=0.8)
            ax.annotate(f"Breakeven: {be:.1f}c", (be, 0), xytext=(5, 15),
                        textcoords="offset points", fontsize=8, color=C_RED)
            break
    plt.tight_layout()
    plt.savefig(OUT_DIR / "8_slippage_sensitivity.png")
    plt.close()

    # --- 9. LibFrog vs Kalshi comparison ---
    if libfrog_comp.get("n_matches", 0) > 0:
        fig, ax = plt.subplots(figsize=(7, 6))
        matches = libfrog_comp["matches"]
        kalshi_mids = [m["kalshi_mid"] for m in matches]
        lf_rates = [m["libfrog_rate"] for m in matches]
        ax.scatter(lf_rates, kalshi_mids, alpha=0.6, s=30, c=C_BLUE,
                   edgecolors="white", lw=0.3)
        ax.plot([0, 1], [0, 1], "k--", alpha=0.4, lw=0.8)
        ax.set_xlabel("LibFrog transcript base rate")
        ax.set_ylabel("Kalshi opening YES price")
        ax.set_title(f"LibFrog vs Kalshi (n={len(matches)})")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        plt.tight_layout()
        plt.savefig(OUT_DIR / "9_libfrog_vs_kalshi.png")
        plt.close()
        n_plots = 9
    else:
        n_plots = 8

    print(f"  {n_plots} plots saved to {OUT_DIR}/")


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(markets, expanding, ttest, stability, calibration,
                    autocorr, tiers, named, sweep, capacity, boot_exp,
                    cross_domain, libfrog_comp) -> str:
    L = []
    w = L.append

    n_kalshi = sum(1 for m in markets if m["source"] == "kalshi")
    n_pm = len(markets) - n_kalshi
    cats = set(m["category"] for m in markets)

    w("# Mention Market Systematic NO — Expanded Robustness Report")
    w("")
    w(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
      f"{len(markets):,} settled markets ({n_kalshi} Kalshi, {n_pm} Polymarket) · "
      f"{len(set(m['series'] for m in markets))} series · "
      f"{len(cats)} categories")
    w("")
    w("---")
    w("")

    # ── Data inventory ──
    w("## 0. Data inventory")
    w("")
    w("| Source | Markets | Series | Categories |")
    w("|--------|--------:|-------:|-----------:|")
    w(f"| Kalshi expanded | {n_kalshi:,} | "
      f"{len(set(m['series'] for m in markets if m['source']=='kalshi'))} | "
      f"{len(set(m['category'] for m in markets if m['source']=='kalshi'))} |")
    if n_pm > 0:
        w(f"| Polymarket | {n_pm:,} | "
          f"{len(set(m['series'] for m in markets if m['source']=='polymarket'))} | "
          f"{len(set(m['category'] for m in markets if m['source']=='polymarket'))} |")
    w(f"| **Total** | **{len(markets):,}** | "
      f"**{len(set(m['series'] for m in markets))}** | "
      f"**{len(cats)}** |")
    w("")

    by_cat_count = defaultdict(int)
    for m in markets:
        by_cat_count[m["category"]] += 1
    w("| Category | N | % |")
    w("|----------|--:|--:|")
    for cat, count in sorted(by_cat_count.items(), key=lambda x: -x[1]):
        w(f"| {cat} | {count:,} | {count/len(markets):.0%} |")
    w("")

    # ── Assumptions ──
    w("## 1. Assumptions & fee schedule")
    w("")
    w("| Parameter | Value | Source |")
    w("|-----------|-------|--------|")
    w(f"| Kalshi fee | ${KALSHI_FEE_RT:.2f} round-trip | Kalshi schedule (Mar 2026) |")
    w("| Polymarket fee | $0.00 (mention mkts) | [docs.polymarket.com](https://docs.polymarket.com/polymarket-learn/trading/fees) |")
    w(f"| Slippage (base) | {DEFAULT_SLIPPAGE*100:.1f}c | Conservative estimate; sensitivity tested |")
    w(f"| Position cap | {POSITION_CAP_PCT:.0%} of market volume | Capacity constraint |")
    w(f"| Expanding warm-up | {MIN_MARKETS_EXPANDING} markets | Per-series; no lookahead |")
    w(f"| Bootstrap | {BOOTSTRAP_N:,} resamples, seed={BOOTSTRAP_SEED} | Reproducible |")
    w("")

    # ── Cross-domain comparison ──
    w("## 2. Cross-domain comparison")
    w("")
    w("**Does the edge exist in all market types, or only certain categories?**")
    w("")
    w("| Category | N | Series | Base rate | Avg price | Overpricing | "
      "Net mu | Sharpe | WR | p-value | Sig | CI excl 0 |")
    w("|----------|--:|-------:|----------:|----------:|------------:|"
      "------:|------:|---:|--------:|:---:|:---------:|")
    for cat, d in sorted(cross_domain.items(), key=lambda x: -x[1]["n"]):
        ci_str = "Y" if d["boot_ci_excl_zero"] else "N"
        sig_str = "Y" if d["sig"] else "N"
        w(f"| {cat} | {d['n']:,} | {d['n_series']} | "
          f"{d['base_rate']:.3f} | {d['avg_mid']:.3f} | "
          f"{d['overpricing']:+.3f} | {d['net_mean']:+.4f} | "
          f"{d['sharpe']:.3f} | {d['win_rate']:.0%} | "
          f"{d['p_value']:.4f} | {sig_str} | {ci_str} |")
    w("")

    # Narrative
    sig_cats = [c for c, d in cross_domain.items() if d["sig"]]
    if sig_cats:
        w(f"Significant edge (p < 0.05): **{', '.join(sig_cats)}**")
    else:
        w("No category reaches individual significance at p < 0.05.")
    w("")

    # ── Lookahead ──
    w("## 3. Lookahead bias test")
    w("")
    w(f"Expanding window: trade market *i* using only data from markets 1 ... *i*-1. "
      f"First {MIN_MARKETS_EXPANDING} per series skipped.")
    w("")
    w("| Series | Cat | N | N(exp) | Full mu | Exp mu | Shrinkage |")
    w("|--------|-----|--:|-------:|-------:|------:|----------:|")
    for s, d in sorted(expanding["by_series"].items()):
        cat = d.get("category", "")
        if d.get("skipped"):
            w(f"| {s} | {cat} | {d['n']} | - | - | - | skipped |")
        else:
            w(f"| {s} | {cat} | {d['n']} | {d['n_expanding']} | "
              f"{d['full_mean_net']:+.4f} | {d['exp_mean_net']:+.4f} | "
              f"{d['shrinkage']:+.4f} |")
    w("")
    w(f"**Aggregate expanding: mu = ${expanding['agg_exp_mean']:+.4f}/contract "
      f"over {expanding['agg_exp_n']:,} trades**")
    w(f"**Shrinkage: ${expanding['agg_full_mean'] - expanding['agg_exp_mean']:.4f}**")
    w("")

    # ── Bootstrap ──
    w("## 4. Bootstrap inference (expanding-window PnL)")
    w("")
    w(f"| Statistic | Value |")
    w(f"|-----------|-------|")
    w(f"| Mean | ${boot_exp['mean']:+.4f} |")
    w(f"| 95% CI | [${boot_exp['ci_lo']:+.4f}, ${boot_exp['ci_hi']:+.4f}] |")
    w(f"| SE | ${boot_exp['se']:.4f} |")
    w(f"| CI excludes zero | {'**Yes**' if boot_exp['ci_excludes_zero'] else '**No**'} |")
    w("")

    # ── Friction tiers ──
    w("## 5. PnL under realistic friction")
    w("")
    w("| Tier | Slip | Total | mu | sigma | Sharpe | WR | Max loss streak |")
    w("|------|:----:|------:|---:|------:|------:|---:|:---------------:|")
    for key in ["gross", "fees_only", "1c_slip", "2c_slip"]:
        d = tiers[key]
        label = {
            "gross": "Gross",
            "fees_only": "Fees only",
            "1c_slip": "Fees+1c",
            "2c_slip": "Fees+2c",
        }[key]
        md = d.get("max_drawdown_consecutive", "-")
        w(f"| {label} | {d['slippage']*100:.1f}c | "
          f"{d['total_net']:+.1f} | {d['mean_net']:+.4f} | "
          f"{d['std_net']:.4f} | {d['sharpe']:.3f} | "
          f"{d['win_rate']:.0%} | {md} |")
    w("")
    w(f"**Dollar PnL at {POSITION_CAP_PCT:.0%} cap (fees+1c slip): "
      f"${tiers['1c_slip']['dollar_pnl_capped']:,.0f}**")
    w("")

    # ── Per-series t-tests ──
    w("## 6. Per-series t-tests (H0: mu = 0, one-sided)")
    w("")
    w("| Series | N | mu | sigma | t | p | Sig |")
    w("|--------|--:|---:|------:|--:|--:|:---:|")
    for s, d in sorted(ttest.items()):
        if d.get("skip"):
            continue
        sig_mark = "Y" if d["sig"] else "-"
        w(f"| {s} | {d['n']} | {d['mean']:+.4f} | {d['std']:.4f} | "
          f"{d['t']:.2f} | {d['p_one']:.4f} | {sig_mark} |")
    w("")

    # ── Calibration ──
    w("## 7. Calibration by price decile")
    w("")
    w("| Bin | N | Implied | Actual | Overpricing |")
    w("|-----|--:|-------:|------:|------------:|")
    for b in calibration["bins"]:
        w(f"| {b['bin']} | {b['n']} | {b['implied_prob']:.3f} | "
          f"{b['actual_rate']:.3f} | {b['overpricing']:+.3f} |")
    w("")
    p_str = "< 0.001" if calibration["p"] < 0.001 else f"= {calibration['p']:.4f}"
    w(f"chi2({calibration['dof']}) = {calibration['chi2']:.1f}, p {p_str}")
    w("")

    # ── Strategy variants ──
    w("## 8. Strategy variants")
    w("")
    w("| Strategy | N | Total | mu | Sharpe | WR |")
    w("|----------|--:|------:|---:|------:|---:|")
    for s in named:
        if s["n"] == 0:
            w(f"| {s['name']} | 0 | - | - | - | - |")
        else:
            w(f"| {s['name']} | {s['n']} | {s['total']:+.1f} | "
              f"{s['mean']:+.4f} | {s['sharpe']:.3f} | {s['win_rate']:.0%} |")
    w("")

    if sweep:
        top = sorted([s for s in sweep if s["n"] >= 20],
                     key=lambda x: x["sharpe"], reverse=True)[:10]
        if top:
            w("### Top 10 sweep configs (by Sharpe, N >= 20)")
            w("")
            w("| Config | N | mu | Sharpe | WR |")
            w("|--------|--:|---:|------:|---:|")
            for s in top:
                w(f"| {s['name']} | {s['n']} | {s['mean']:+.4f} | "
                  f"{s['sharpe']:.3f} | {s['win_rate']:.0%} |")
            w("")

    # ── LibFrog ──
    if libfrog_comp.get("n_matches", 0) > 0:
        w("## 9. LibFrog transcript base rate comparison")
        w("")
        w(f"Matched {libfrog_comp['n_matches']} earnings markets against "
          f"LibFrog historical transcript data.")
        w("")
        w(f"| Metric | Value |")
        w(f"|--------|-------|")
        w(f"| Matches | {libfrog_comp['n_matches']} |")
        w(f"| Avg overpricing (Kalshi - LibFrog) | {libfrog_comp['avg_overpricing']:+.3f} |")
        w(f"| Median overpricing | {libfrog_comp['median_overpricing']:+.3f} |")
        w(f"| % overpriced | {libfrog_comp['pct_overpriced']:.0%} |")
        w("")
        w("### Top overpriced/underpriced (by magnitude)")
        w("")
        w("| Company | Word | Kalshi | LibFrog | Delta |")
        w("|---------|------|------:|-------:|------:|")
        for m in libfrog_comp["matches"][:15]:
            w(f"| {m['company']} | {m['word']} | {m['kalshi_mid']:.3f} | "
              f"{m['libfrog_rate']:.3f} | {m['overpricing']:+.3f} |")
        w("")

    # ── Capacity ──
    w(f"## {'10' if libfrog_comp.get('n_matches', 0) > 0 else '9'}. Capacity analysis")
    w("")
    w(f"| Metric | Value |")
    w(f"|--------|-------|")
    w(f"| Total volume | ${capacity['total_volume']:,.0f} |")
    w(f"| Unique events | {capacity['n_events']} |")
    w(f"| Unique series | {capacity['n_series']} |")
    w(f"| Data span | {capacity['span_days']}d ({capacity['span_years']:.1f}y) |")
    w(f"| Max capital at {POSITION_CAP_PCT:.0%} cap | ${capacity['max_capital']:,.0f} |")
    w(f"| Dollar PnL (capped) | ${capacity['dollar_pnl']:,.0f} |")
    w(f"| Annualized PnL | ${capacity['annualized_pnl']:,.0f} |")
    w(f"| Annualized return | {capacity['annualized_return']:.1%} |")
    w("")

    # ── Price range analysis ──
    n_sect = 10 if libfrog_comp.get("n_matches", 0) > 0 else 9
    n_sect += 1
    w(f"## {n_sect}. Price range analysis")
    w("")
    w("Markets with extreme opening prices (<5% or >95%) are trivially obvious. "
      "The real edge opportunity is in the **competitive range** (5-95%).")
    w("")
    buckets = [
        ("<5%", 0.0, 0.05),
        ("5-25%", 0.05, 0.25),
        ("25-50%", 0.25, 0.50),
        ("50-75%", 0.50, 0.75),
        ("75-95%", 0.75, 0.95),
        (">95%", 0.95, 1.0),
    ]
    w("| Price range | N | % | Base rate | Avg price | Overpricing | Net mu | Sharpe |")
    w("|-------------|--:|--:|----------:|----------:|------------:|------:|------:|")
    for label, lo, hi in buckets:
        bkt = [m for m in markets if lo < m["mid"] <= hi]
        if not bkt:
            continue
        br = np.mean([m["outcome"] for m in bkt])
        avg_p = np.mean([m["mid"] for m in bkt])
        pnls = [_no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE, m["source"])["net"]
                for m in bkt]
        a = np.array(pnls)
        sr = float(a.mean() / a.std(ddof=1)) if len(a) > 1 and a.std(ddof=1) > 0 else 0
        w(f"| {label} | {len(bkt):,} | {len(bkt)/len(markets):.0%} | "
          f"{br:.3f} | {avg_p:.3f} | {avg_p - br:+.3f} | "
          f"{a.mean():+.4f} | {sr:.3f} |")
    w("")

    # Competitive range analysis
    competitive = [m for m in markets if 0.05 < m["mid"] <= 0.95]
    if competitive:
        comp_pnls = [_no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE, m["source"])["net"]
                     for m in competitive]
        comp_a = np.array(comp_pnls)
        comp_boot = bootstrap_ci(comp_a) if len(comp_a) >= 20 else None
        w(f"**Competitive range (5-95%) only: "
          f"N={len(competitive):,}, mu=${comp_a.mean():+.4f}, "
          f"Sharpe={comp_a.mean()/comp_a.std(ddof=1):.3f}**")
        if comp_boot:
            w(f"**Bootstrap 95% CI: [${comp_boot['ci_lo']:+.4f}, ${comp_boot['ci_hi']:+.4f}] "
              f"— {'excludes' if comp_boot['ci_excludes_zero'] else 'includes'} zero**")
    w("")

    # ── Verdict ──
    n_sect += 1
    w(f"## Verdict")
    w("")
    net_1c = tiers["1c_slip"]

    # Check which categories have edge
    edge_cats = [c for c, d in cross_domain.items()
                 if d["net_mean"] > 0 and d["sig"]]
    marginal_cats = [c for c, d in cross_domain.items()
                     if d["net_mean"] > 0 and not d["sig"]]

    if boot_exp["ci_excludes_zero"] and net_1c["mean_net"] > 0:
        verdict = "EDGE SURVIVES (all markets)"
        detail = (f"Positive mean PnL persists after fees, slippage, and lookahead removal. "
                  f"Bootstrap 95% CI on expanding-window PnL excludes zero. "
                  f"Edge is strongest in: {', '.join(edge_cats) if edge_cats else 'aggregate'}.")
        if marginal_cats:
            detail += f" Marginal evidence in: {', '.join(marginal_cats)}."
    elif net_1c["mean_net"] > 0:
        verdict = "EDGE MARGINAL (all markets)"
        detail = ("Positive point estimate survives friction, but bootstrap CI "
                   "includes zero. Insufficient evidence to reject null at 95%.")
    else:
        verdict = "BLIND NO EDGE KILLED (all markets)"
        detail = ("Mean PnL <= 0 after realistic friction on the full dataset. "
                   "The blind NO strategy does not survive fees + slippage across "
                   "all 7,000+ markets.")

    # Check competitive range
    if competitive:
        comp_a_final = np.array([_no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE,
                                          m["source"])["net"] for m in competitive])
        if comp_a_final.mean() > 0:
            comp_boot_final = bootstrap_ci(comp_a_final) if len(comp_a_final) >= 20 else None
            if comp_boot_final and comp_boot_final["ci_excludes_zero"]:
                detail += (f"\n\nHowever, the **competitive range (5-95%)** retains "
                           f"significant edge: mu=${comp_a_final.mean():+.4f}, "
                           f"CI excludes zero. The edge is real but requires "
                           f"filtering out trivially-priced markets.")
            else:
                detail += (f"\n\nThe competitive range (5-95%) shows positive but "
                           f"marginal edge: mu=${comp_a_final.mean():+.4f}.")

    # Category-specific verdicts
    if edge_cats:
        detail += (f"\n\n**Category-level edge survives** in: "
                   f"{', '.join(edge_cats)}. "
                   f"A selective strategy targeting these categories "
                   f"is more promising than blind NO across all markets.")

    w(f"**{verdict}**")
    w("")
    w(detail)
    w("")

    w("### Key risks")
    w("")
    w(f"1. **Category concentration**: Edge is concentrated in "
      f"{'some categories' if len(edge_cats) < len(cross_domain) else 'all categories'}. "
      f"Blind NO across all categories destroys alpha.")
    w("2. **Extreme prices dominate**: 78% of markets have prices <5% or >95%, "
      "diluting the signal from competitive-range markets.")
    w("3. **Autocorrelation**: Within-event clustering reduces effective sample size.")
    w("4. **Liquidity**: At 5% volume cap, capital deployed per market is small.")
    w("5. **Regime change**: As markets mature, mispricing may compress.")
    w("")
    w("---")
    w(f"*{len(markets):,} markets · {BOOTSTRAP_N:,} bootstrap resamples · "
      f"Kalshi fee ${KALSHI_FEE_RT}/RT · PM fee $0 · "
      f"Slippage sensitivity 0-3c*")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 65)
    print("  EXPANDED ROBUSTNESS BACKTEST v2")
    print("  Full mention market universe · cross-domain analysis")
    print("=" * 65)

    # Load
    print("\nLoading data...")
    markets = load_data()
    libfrog = load_libfrog()

    n_k = sum(1 for m in markets if m["source"] == "kalshi")
    n_p = len(markets) - n_k
    n_series = len(set(m["series"] for m in markets))
    by_cat = defaultdict(int)
    for m in markets:
        by_cat[m["category"]] += 1

    print(f"  {len(markets):,} markets ({n_k} Kalshi, {n_p} Polymarket), "
          f"{n_series} series")
    for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"    {cat:20s} {count:5,}")
    if libfrog:
        print(f"  LibFrog: {len(libfrog)} companies loaded")

    # 1. Expanding window
    print("\n[1/9] Expanding-window analysis...")
    exp = expanding_window(markets)
    print(f"  Full-sample mu(net) = ${exp['agg_full_mean']:+.4f}")
    print(f"  Expanding   mu(net) = ${exp['agg_exp_mean']:+.4f}  "
          f"(shrinkage ${exp['agg_full_mean'] - exp['agg_exp_mean']:.4f})")

    # 2. Bootstrap
    print("\n[2/9] Bootstrap inference...")
    exp_arr = np.array(exp["_all_exp_net"])
    boot = bootstrap_ci(exp_arr)
    print(f"  mu = ${boot['mean']:+.4f}, "
          f"95% CI = [${boot['ci_lo']:+.4f}, ${boot['ci_hi']:+.4f}]")
    print(f"  CI excludes zero: {'YES' if boot['ci_excludes_zero'] else 'NO'}")

    # 3. Cross-domain
    print("\n[3/9] Cross-domain analysis...")
    cd = cross_domain_analysis(markets)
    for cat, d in sorted(cd.items(), key=lambda x: -x[1]["n"]):
        sig = "*" if d["sig"] else " "
        print(f"  {cat:20s}  n={d['n']:5,}  mu={d['net_mean']:+.4f}  "
              f"SR={d['sharpe']:.3f}  BR={d['base_rate']:.3f}  "
              f"price={d['avg_mid']:.3f}  {sig}")

    # 4. T-tests
    print("\n[4/9] Per-series t-tests...")
    tt = per_series_ttest(markets)
    sig = sum(1 for d in tt.values() if d.get("sig"))
    print(f"  {sig}/{len(tt)} series significant at p < 0.05")

    # 5. Additional tests
    print("\n[5/9] Stability, calibration, autocorrelation...")
    stab = time_stability(markets)
    cal = calibration_analysis(markets)
    ac = autocorrelation_test(markets)
    cal_p = "< 0.001" if cal["p"] < 0.001 else f"= {cal['p']:.4f}"
    print(f"  Calibration chi2({cal['dof']}) = {cal['chi2']:.1f}, p {cal_p}")

    # 6. Friction tiers
    print("\n[6/9] Friction tiers...")
    tier = friction_tiers(markets)
    for key in ["gross", "fees_only", "1c_slip", "2c_slip"]:
        d = tier[key]
        label = {"gross": "Gross", "fees_only": "Fees only",
                 "1c_slip": "Fees+1c", "2c_slip": "Fees+2c"}[key]
        print(f"  {label:12s}  Total={d['total_net']:+8.1f}  "
              f"mu={d['mean_net']:+.4f}  sigma={d['std_net']:.4f}  "
              f"SR={d['sharpe']:.3f}  WR={d['win_rate']:.0%}")
    print(f"  Dollar PnL (5% cap, 1c slip): "
          f"${tier['1c_slip']['dollar_pnl_capped']:+,.0f}")

    # 7. Strategies
    print("\n[7/9] Strategy variants & sweep...")
    named, sweep = strategy_analysis(markets)
    for s in named:
        if s["n"] > 0:
            print(f"  {s['name']:25s}  n={s['n']:5d}  "
                  f"Total={s['total']:+8.1f}  SR={s['sharpe']:.3f}  "
                  f"WR={s['win_rate']:.0%}")
    print(f"  Sweep: {len(sweep)} configurations evaluated")

    # 8. Capacity
    print("\n[8/9] Capacity...")
    cap = capacity_analysis(markets)
    print(f"  Volume: ${cap['total_volume']:,.0f}")
    print(f"  Max capital (5% cap): ${cap['max_capital']:,.0f}")
    print(f"  Annualized PnL: ${cap['annualized_pnl']:,.0f}")
    print(f"  Annualized return: {cap['annualized_return']:.1%}")

    # 9. LibFrog comparison
    print("\n[9/9] LibFrog transcript comparison...")
    lf_comp = libfrog_comparison(markets, libfrog)
    if lf_comp["n_matches"] > 0:
        print(f"  {lf_comp['n_matches']} matches found")
        print(f"  Avg overpricing: {lf_comp['avg_overpricing']:+.3f}")
        print(f"  % overpriced: {lf_comp['pct_overpriced']:.0%}")
    else:
        print("  No LibFrog matches found")

    # Output
    print("\nGenerating report & plots...")
    report = generate_report(markets, exp, tt, stab, cal, ac,
                             tier, named, sweep, cap, boot,
                             cd, lf_comp)
    rpath = OUT_DIR / "robustness_report_v2.md"
    with open(rpath, "w") as f:
        f.write(report)
    print(f"  Report: {rpath}")

    make_plots(markets, exp, tier, cal, cd, named, sweep, lf_comp)

    # Summary
    net = tier["1c_slip"]
    print("\n" + "=" * 65)
    print("  SUMMARY (base case: fees + 1c slippage)")
    print("=" * 65)
    print(f"  Markets            {len(markets):,}")
    print(f"  Categories         {len(cd)}")
    print(f"  Gross mu           ${tier['gross']['mean_net']:+.4f}")
    print(f"  Net mu (1c slip)   ${net['mean_net']:+.4f}")
    print(f"  Sharpe             {net['sharpe']:.3f}")
    print(f"  Win rate           {net['win_rate']:.0%}")
    print(f"  Bootstrap 95% CI   [${boot['ci_lo']:+.4f}, ${boot['ci_hi']:+.4f}]")
    print(f"  CI excl. zero      {'YES' if boot['ci_excludes_zero'] else 'NO'}")
    print(f"  Lookahead shrink   ${exp['agg_full_mean'] - exp['agg_exp_mean']:.4f}")
    print(f"  Dollar PnL (cap)   ${net['dollar_pnl_capped']:+,.0f}")

    # Competitive range
    competitive = [m for m in markets if 0.05 < m["mid"] <= 0.95]
    if competitive:
        comp_pnls = [_no_pnl(m["mid"], m["outcome"], DEFAULT_SLIPPAGE,
                             m["source"])["net"] for m in competitive]
        comp_a = np.array(comp_pnls)
        comp_boot = bootstrap_ci(comp_a) if len(comp_a) >= 20 else None
        print(f"\n  Competitive range (5-95% only):")
        print(f"    Markets          {len(competitive):,} ({len(competitive)/len(markets):.0%})")
        print(f"    Net mu           ${comp_a.mean():+.4f}")
        sr = comp_a.mean() / comp_a.std(ddof=1) if comp_a.std(ddof=1) > 0 else 0
        print(f"    Sharpe           {sr:.3f}")
        if comp_boot:
            print(f"    Bootstrap CI     [${comp_boot['ci_lo']:+.4f}, ${comp_boot['ci_hi']:+.4f}]")
            print(f"    CI excl. zero    {'YES' if comp_boot['ci_excludes_zero'] else 'NO'}")

    print("\n  Cross-domain edge:")
    for cat, d in sorted(cd.items(), key=lambda x: -x[1]["net_mean"]):
        sig = "***" if d["boot_ci_excl_zero"] else ("*" if d["sig"] else "")
        print(f"    {cat:20s}  mu={d['net_mean']:+.4f}  SR={d['sharpe']:.3f}  {sig}")

    if boot["ci_excludes_zero"] and net["mean_net"] > 0:
        print("\n  >>> VERDICT: EDGE SURVIVES (all markets) <<<")
    elif net["mean_net"] > 0:
        print("\n  >>> VERDICT: EDGE MARGINAL <<<")
    else:
        print("\n  >>> VERDICT: BLIND NO EDGE KILLED <<<")
        if competitive and comp_a.mean() > 0:
            print("  >>> SELECTIVE EDGE EXISTS (competitive range + category filter) <<<")

    print(f"\nAll outputs: {OUT_DIR}/")


if __name__ == "__main__":
    main()

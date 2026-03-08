#!/usr/bin/env python3
"""Adversarial robustness backtest for mention market NO strategy.

Uses ONLY real settled market data from Kalshi and Polymarket.
Tests whether the YES-overpricing edge survives fees, slippage,
lookahead removal, and statistical scrutiny.

Usage:
    python scripts/robustness_backtest.py
"""

import json
import re
import sys
import math
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from itertools import product

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_PATH = Path("data/real_markets/real_data_combined.json")
OUT_DIR = Path("output/backtest")
OUT_DIR.mkdir(parents=True, exist_ok=True)

KALSHI_FEE = 0.01          # $0.01 per contract
POLYMARKET_FEE = 0.02       # 2% on settlement winnings
SLIPPAGE_CENTS = 0.015      # 1.5 cents midpoint assumption
POSITION_CAP_PCT = 0.05     # max 5% of market volume
BOOTSTRAP_N = 10_000
MIN_MARKETS_EXPANDING = 10  # skip first N per series for expanding window

# ---------------------------------------------------------------------------
# Data loading & date parsing
# ---------------------------------------------------------------------------

def parse_event_date(event_ticker: str) -> datetime | None:
    """Extract date from Kalshi event ticker like KXTRUMPMENTION-26MAR08."""
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", event_ticker)
    if m:
        yr, mon, day = m.groups()
        month_map = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
        }
        if mon in month_map:
            return datetime(2000 + int(yr), month_map[mon], int(day))
    # Try other patterns like KXNFLMENTION-26JAN18HOUNE
    m2 = re.search(r"-(\d{2})([A-Z]{3})(\d{2})", event_ticker)
    if m2:
        yr, mon, day = m2.groups()
        month_map = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
        }
        if mon in month_map:
            return datetime(2000 + int(yr), month_map[mon], int(day))
    return None


def load_data():
    """Load and normalize all markets into a flat list of dicts."""
    with open(DATA_PATH) as f:
        raw = json.load(f)

    markets = []

    for m in raw["kalshi"]:
        dt = parse_event_date(m["event_ticker"])
        markets.append({
            "source": "kalshi",
            "series": m["series"],
            "event": m["event_ticker"],
            "word": m["strike_word"],
            "result": 1 if m["result"] == "yes" else 0,
            "opening_price": m["opening_price"],
            "volume": m["volume"],
            "date": dt,
        })

    for m in raw["polymarket"]:
        # Polymarket SOTU markets all happened on the same date
        series = "PM_SOTU_2026"
        evt = m["event"]
        if "who" in evt.lower() or "name" in evt.lower():
            series = "PM_PersonNames"
        elif "places" in evt.lower():
            series = "PM_Places"
        elif "say" in evt.lower():
            series = "PM_Words"

        markets.append({
            "source": "polymarket",
            "series": series,
            "event": evt,
            "word": m["person"],
            "result": 1 if m["result"] == "yes" else 0,
            "opening_price": m["opening_price"],
            "volume": m["volume"],
            "date": datetime(2026, 3, 4),  # SOTU date
        })

    return markets, raw["summary"]


# ---------------------------------------------------------------------------
# Core PnL calculations
# ---------------------------------------------------------------------------

def no_pnl_gross(opening_price: float, result: int) -> float:
    """Gross PnL from buying 1 NO contract at opening price.
    NO price = 1 - opening_price (for YES).
    If result=0 (NO wins): profit = opening_price
    If result=1 (YES wins): loss = -(1 - opening_price)
    """
    if result == 0:
        return opening_price       # win: collect YES price
    else:
        return -(1 - opening_price)  # lose: paid NO price


def apply_fees(gross_pnl: float, opening_price: float, result: int, source: str) -> float:
    """Apply exchange fees to gross PnL."""
    if source == "kalshi":
        return gross_pnl - KALSHI_FEE
    else:  # polymarket
        if result == 0:  # won
            winnings = opening_price  # settlement payout
            fee = winnings * POLYMARKET_FEE
            return gross_pnl - fee
        else:
            return gross_pnl  # no fee on loss for PM


def apply_slippage(opening_price: float) -> float:
    """Return worse execution price (higher NO cost = lower effective YES price)."""
    return max(0.01, opening_price - SLIPPAGE_CENTS)


def position_size(volume: float) -> float:
    """Max contracts = 5% of market volume."""
    return volume * POSITION_CAP_PCT


# ---------------------------------------------------------------------------
# 1. Expanding-window base rates (kill lookahead)
# ---------------------------------------------------------------------------

def expanding_window_analysis(markets: list[dict]) -> dict:
    """For each series, sort chronologically and compute expanding-window edge."""
    results = {}
    series_markets = defaultdict(list)
    for m in markets:
        series_markets[m["series"]].append(m)

    all_expanding_pnl = []
    all_fullsample_pnl = []

    for series, mkts in series_markets.items():
        # Sort by date (None dates go last)
        mkts.sort(key=lambda x: x["date"] or datetime.max)

        n = len(mkts)
        if n < MIN_MARKETS_EXPANDING + 5:
            results[series] = {"n": n, "skipped": True, "reason": "too few markets"}
            continue

        # Full-sample stats
        full_prices = [m["opening_price"] for m in mkts]
        full_results = [m["result"] for m in mkts]
        full_base_rate = np.mean(full_results)
        full_avg_price = np.mean(full_prices)
        full_edge = full_avg_price - full_base_rate

        # Expanding window: for market i, base_rate from markets 0..i-1
        expanding_edges = []
        expanding_pnl = []
        expanding_correct = []

        for i in range(MIN_MARKETS_EXPANDING, n):
            prior_results = [mkts[j]["result"] for j in range(i)]
            prior_base_rate = np.mean(prior_results)
            prior_avg_price = np.mean([mkts[j]["opening_price"] for j in range(i)])

            current = mkts[i]
            # Edge known at time of trade
            edge_at_trade = prior_avg_price - prior_base_rate
            expanding_edges.append(edge_at_trade)

            # Actual PnL
            pnl = no_pnl_gross(current["opening_price"], current["result"])
            expanding_pnl.append(pnl)
            expanding_correct.append(1 if current["result"] == 0 else 0)
            all_expanding_pnl.append(pnl)

        for m in mkts:
            all_fullsample_pnl.append(no_pnl_gross(m["opening_price"], m["result"]))

        expanding_mean_pnl = np.mean(expanding_pnl)
        full_mean_pnl = np.mean([no_pnl_gross(m["opening_price"], m["result"]) for m in mkts])

        results[series] = {
            "n": n,
            "n_expanding": len(expanding_pnl),
            "skipped_first": MIN_MARKETS_EXPANDING,
            "full_sample_base_rate": full_base_rate,
            "full_sample_avg_price": full_avg_price,
            "full_sample_edge": full_edge,
            "full_sample_mean_pnl": full_mean_pnl,
            "expanding_mean_pnl": expanding_mean_pnl,
            "expanding_win_rate": np.mean(expanding_correct),
            "expanding_mean_edge": np.mean(expanding_edges),
            "edge_shrinkage": full_mean_pnl - expanding_mean_pnl,
            "expanding_pnl_array": expanding_pnl,
        }

    return {
        "by_series": results,
        "total_expanding_mean_pnl": np.mean(all_expanding_pnl) if all_expanding_pnl else 0,
        "total_full_mean_pnl": np.mean(all_fullsample_pnl) if all_fullsample_pnl else 0,
        "total_expanding_n": len(all_expanding_pnl),
    }


# ---------------------------------------------------------------------------
# 2. Statistical validation
# ---------------------------------------------------------------------------

def bootstrap_ci(pnl_array: np.ndarray, n_boot: int = BOOTSTRAP_N, ci: float = 0.95) -> tuple:
    """Bootstrap confidence interval for mean PnL."""
    rng = np.random.default_rng(42)
    boot_means = np.array([
        np.mean(rng.choice(pnl_array, size=len(pnl_array), replace=True))
        for _ in range(n_boot)
    ])
    alpha = (1 - ci) / 2
    lo = np.percentile(boot_means, alpha * 100)
    hi = np.percentile(boot_means, (1 - alpha) * 100)
    return float(lo), float(np.mean(boot_means)), float(hi)


def per_series_ttest(markets: list[dict]) -> dict:
    """One-sample t-test: is mean per-market PnL > 0 for each series?"""
    series_pnl = defaultdict(list)
    for m in markets:
        pnl = no_pnl_gross(m["opening_price"], m["result"])
        series_pnl[m["series"]].append(pnl)

    results = {}
    for series, pnls in series_pnl.items():
        arr = np.array(pnls)
        if len(arr) < 5:
            results[series] = {"n": len(arr), "skip": True}
            continue
        t_stat, p_two = stats.ttest_1samp(arr, 0)
        p_one = p_two / 2 if t_stat > 0 else 1 - p_two / 2
        results[series] = {
            "n": len(arr),
            "mean_pnl": float(np.mean(arr)),
            "std_pnl": float(np.std(arr, ddof=1)),
            "t_stat": float(t_stat),
            "p_value_one_sided": float(p_one),
            "significant_005": p_one < 0.05,
        }
    return results


def time_stability(markets: list[dict]) -> dict:
    """Split each series into first/second half and compare edges."""
    series_markets = defaultdict(list)
    for m in markets:
        series_markets[m["series"]].append(m)

    results = {}
    for series, mkts in series_markets.items():
        mkts.sort(key=lambda x: x["date"] or datetime.max)
        n = len(mkts)
        if n < 20:
            results[series] = {"n": n, "skip": True}
            continue

        mid = n // 2
        first_half = mkts[:mid]
        second_half = mkts[mid:]

        def half_stats(half):
            pnls = [no_pnl_gross(m["opening_price"], m["result"]) for m in half]
            return {
                "n": len(half),
                "mean_pnl": float(np.mean(pnls)),
                "win_rate": float(np.mean([1 if m["result"] == 0 else 0 for m in half])),
                "avg_price": float(np.mean([m["opening_price"] for m in half])),
                "base_rate": float(np.mean([m["result"] for m in half])),
            }

        results[series] = {
            "first_half": half_stats(first_half),
            "second_half": half_stats(second_half),
        }
    return results


def calibration_test(markets: list[dict]) -> dict:
    """Bin markets by opening price decile, compare predicted vs actual YES rate."""
    prices = np.array([m["opening_price"] for m in markets])
    results_arr = np.array([m["result"] for m in markets])

    # Create decile bins
    bins = np.arange(0, 1.05, 0.1)
    bin_labels = [f"{bins[i]:.1f}-{bins[i+1]:.1f}" for i in range(len(bins)-1)]

    observed = []
    expected = []
    counts = []
    bin_data = []

    for i in range(len(bins) - 1):
        mask = (prices >= bins[i]) & (prices < bins[i+1])
        if i == len(bins) - 2:  # last bin includes upper bound
            mask = (prices >= bins[i]) & (prices <= bins[i+1])
        n = mask.sum()
        if n < 5:
            continue
        actual_rate = results_arr[mask].mean()
        predicted_rate = prices[mask].mean()  # market price = implied probability
        observed.append(actual_rate * n)
        expected.append(predicted_rate * n)
        counts.append(n)
        bin_data.append({
            "bin": bin_labels[i],
            "n": int(n),
            "predicted": float(predicted_rate),
            "actual": float(actual_rate),
            "overpricing": float(predicted_rate - actual_rate),
        })

    # Chi-squared test
    obs = np.array(observed)
    exp = np.array(expected)
    # Use manual chi-squared to handle expected zeros
    valid = exp > 0
    if valid.sum() >= 2:
        chi2 = np.sum((obs[valid] - exp[valid])**2 / exp[valid])
        dof = valid.sum() - 1
        p_val = 1 - stats.chi2.cdf(chi2, dof)
    else:
        chi2, dof, p_val = float("nan"), 0, float("nan")

    return {
        "bins": bin_data,
        "chi2": float(chi2),
        "dof": int(dof),
        "p_value": float(p_val),
        "markets_overpriced_in_all_bins": all(b["overpricing"] > 0 for b in bin_data),
    }


def autocorrelation_test(markets: list[dict]) -> dict:
    """Test for autocorrelation in wins/losses (are they independent?)."""
    series_markets = defaultdict(list)
    for m in markets:
        series_markets[m["series"]].append(m)

    results = {}
    for series, mkts in series_markets.items():
        mkts.sort(key=lambda x: x["date"] or datetime.max)
        wins = np.array([1 if m["result"] == 0 else 0 for m in mkts], dtype=float)
        n = len(wins)
        if n < 20:
            results[series] = {"n": n, "skip": True}
            continue

        # Lag-1 autocorrelation
        mean_w = wins.mean()
        numer = np.sum((wins[:-1] - mean_w) * (wins[1:] - mean_w))
        denom = np.sum((wins - mean_w)**2)
        if denom == 0:
            r1 = 0
        else:
            r1 = numer / denom

        # Under null (iid), r1 ~ N(-1/n, 1/n) for large n
        z = (r1 - (-1/n)) / (1/math.sqrt(n))
        p_val = 2 * (1 - stats.norm.cdf(abs(z)))

        results[series] = {
            "n": n,
            "lag1_autocorr": float(r1),
            "z_stat": float(z),
            "p_value": float(p_val),
            "independent_005": p_val > 0.05,
        }
    return results


# ---------------------------------------------------------------------------
# 3. Realistic PnL
# ---------------------------------------------------------------------------

def compute_pnl_tiers(markets: list[dict]) -> dict:
    """Compute gross, net-of-fees, and net-of-fees+slippage PnL."""
    gross_pnls = []
    fee_pnls = []
    full_pnls = []
    capped_pnls = []

    for m in markets:
        price = m["opening_price"]
        result = m["result"]
        source = m["source"]
        vol = m["volume"]

        # Gross
        g = no_pnl_gross(price, result)
        gross_pnls.append(g)

        # Net of fees
        f = apply_fees(g, price, result, source)
        fee_pnls.append(f)

        # Net of fees + slippage
        slipped_price = apply_slippage(price)
        g_slip = no_pnl_gross(slipped_price, result)
        f_slip = apply_fees(g_slip, slipped_price, result, source)
        full_pnls.append(f_slip)

        # With position cap
        max_contracts = position_size(vol)
        capped_pnls.append(f_slip * max_contracts)

    gross_arr = np.array(gross_pnls)
    fee_arr = np.array(fee_pnls)
    full_arr = np.array(full_pnls)
    capped_arr = np.array(capped_pnls)

    def tier_stats(arr, label):
        return {
            "label": label,
            "total_pnl": float(arr.sum()),
            "mean_pnl": float(arr.mean()),
            "median_pnl": float(np.median(arr)),
            "std_pnl": float(arr.std(ddof=1)),
            "sharpe": float(arr.mean() / arr.std(ddof=1)) if arr.std(ddof=1) > 0 else 0,
            "win_rate": float((arr > 0).mean()),
            "n": len(arr),
        }

    return {
        "gross": tier_stats(gross_arr, "Gross"),
        "net_fees": tier_stats(fee_arr, "Net of Fees"),
        "net_fees_slippage": tier_stats(full_arr, "Net of Fees + Slippage"),
        "capped_dollar_pnl": {
            "total": float(capped_arr.sum()),
            "mean": float(capped_arr.mean()),
        },
        "arrays": {
            "gross": gross_pnls,
            "net_fees": fee_pnls,
            "net_fees_slippage": full_pnls,
        },
    }


# ---------------------------------------------------------------------------
# 4. Strategy variants & parameter sweep
# ---------------------------------------------------------------------------

def evaluate_strategy(markets: list[dict], name: str,
                      min_edge: float = 0.0,
                      max_base_rate: float = 1.0,
                      min_volume: float = 0,
                      series_filter: set | None = None) -> dict:
    """Evaluate a strategy variant with given filters."""
    # For expanding-window, we need series-level base rates
    series_markets = defaultdict(list)
    for m in markets:
        series_markets[m["series"]].append(m)

    traded = []
    for series, mkts in series_markets.items():
        if series_filter and series not in series_filter:
            continue
        mkts.sort(key=lambda x: x["date"] or datetime.max)

        for i in range(len(mkts)):
            m = mkts[i]
            if m["volume"] < min_volume:
                continue

            # Expanding window base rate
            if i < MIN_MARKETS_EXPANDING:
                continue
            prior = mkts[:i]
            br = np.mean([p["result"] for p in prior])
            avg_p = np.mean([p["opening_price"] for p in prior])
            edge = avg_p - br

            if edge < min_edge:
                continue
            if br > max_base_rate:
                continue

            traded.append(m)

    if not traded:
        return {"name": name, "n_traded": 0}

    pnls = []
    for m in traded:
        price = apply_slippage(m["opening_price"])
        g = no_pnl_gross(price, m["result"])
        f = apply_fees(g, price, m["result"], m["source"])
        pnls.append(f)

    arr = np.array(pnls)
    return {
        "name": name,
        "n_traded": len(traded),
        "total_pnl": float(arr.sum()),
        "mean_pnl": float(arr.mean()),
        "std_pnl": float(arr.std(ddof=1)) if len(arr) > 1 else 0,
        "sharpe": float(arr.mean() / arr.std(ddof=1)) if len(arr) > 1 and arr.std(ddof=1) > 0 else 0,
        "win_rate": float((arr > 0).mean()),
    }


def run_strategy_variants(markets: list[dict]) -> list[dict]:
    """Run named strategy variants + parameter sweep."""
    results = []

    # Named strategies
    results.append(evaluate_strategy(markets, "blind_no"))
    results.append(evaluate_strategy(markets, "person_name_no",
                                     series_filter={"KXTRUMPMENTION", "KXVANCEMENTION",
                                                    "KXSTARMERMENTION", "PM_PersonNames"}))
    results.append(evaluate_strategy(markets, "selective_edge05",
                                     min_edge=0.05))
    results.append(evaluate_strategy(markets, "selective_edge10",
                                     min_edge=0.10))
    results.append(evaluate_strategy(markets, "high_volume_only",
                                     min_volume=10000))
    results.append(evaluate_strategy(markets, "low_base_rate",
                                     max_base_rate=0.50))

    # Parameter sweep
    sweep_results = []
    min_edges = [0.0, 0.03, 0.05, 0.08, 0.10, 0.15]
    max_base_rates = [0.30, 0.40, 0.50, 0.60, 0.80, 1.0]
    min_volumes = [0, 1000, 5000, 10000]

    for me, mbr, mv in product(min_edges, max_base_rates, min_volumes):
        name = f"sweep_e{me:.2f}_br{mbr:.2f}_v{mv}"
        r = evaluate_strategy(markets, name, min_edge=me,
                              max_base_rate=mbr, min_volume=mv)
        if r["n_traded"] > 0:
            sweep_results.append(r)

    return results, sweep_results


# ---------------------------------------------------------------------------
# 5. Capacity analysis
# ---------------------------------------------------------------------------

def capacity_analysis(markets: list[dict]) -> dict:
    """Estimate capital capacity from real data."""
    total_volume = sum(m["volume"] for m in markets)
    total_capped_volume = sum(position_size(m["volume"]) for m in markets)

    # Average NO price
    avg_no_price = np.mean([1 - m["opening_price"] for m in markets])
    max_capital_deployed = total_capped_volume * avg_no_price

    # Net PnL per dollar deployed
    pnls_per_contract = []
    for m in markets:
        price = apply_slippage(m["opening_price"])
        g = no_pnl_gross(price, m["result"])
        f = apply_fees(g, price, m["result"], m["source"])
        pnls_per_contract.append(f)

    mean_pnl = np.mean(pnls_per_contract)

    # Total dollar PnL at 5% cap
    total_dollar_pnl = sum(
        pnls_per_contract[i] * position_size(markets[i]["volume"])
        for i in range(len(markets))
    )

    # Count unique events/series
    unique_events = len(set(m["event"] for m in markets))
    unique_series = len(set(m["series"] for m in markets))

    # Annualize: our data spans roughly how long?
    dates = [m["date"] for m in markets if m["date"]]
    if dates:
        span_days = (max(dates) - min(dates)).days
    else:
        span_days = 365
    span_years = max(span_days / 365, 0.1)

    # Known Kalshi mention series = 298 per user spec
    # We have 6 series — extrapolation factor
    series_multiplier = 298 / unique_series if unique_series > 0 else 1

    return {
        "total_volume_usd": total_volume,
        "avg_no_price": float(avg_no_price),
        "total_capped_contracts": total_capped_volume,
        "max_capital_at_5pct": max_capital_deployed,
        "mean_net_pnl_per_contract": float(mean_pnl),
        "total_dollar_pnl_capped": total_dollar_pnl,
        "unique_events": unique_events,
        "unique_series": unique_series,
        "data_span_days": span_days,
        "data_span_years": float(span_years),
        "annualized_dollar_pnl": total_dollar_pnl / span_years,
        "extrapolation_298_series": {
            "multiplier": float(series_multiplier),
            "projected_annual_pnl": total_dollar_pnl / span_years * series_multiplier,
            "projected_annual_volume": total_volume / span_years * series_multiplier,
            "caveat": "Linear extrapolation assumes similar edge across all 298 series",
        },
    }


# ---------------------------------------------------------------------------
# 6. Plotting
# ---------------------------------------------------------------------------

def make_plots(markets, expanding, pnl_tiers, calibration, strategies, sweep):
    """Generate all plots to output/backtest/."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as mticker
    except ImportError:
        print("  matplotlib not available, skipping plots")
        return

    plt.rcParams.update({"font.size": 10, "figure.dpi": 150})

    # --- Plot 1: Expanding window edge shrinkage ---
    fig, ax = plt.subplots(figsize=(10, 5))
    series_data = expanding["by_series"]
    series_names = []
    full_edges = []
    expanding_edges = []
    for s, d in sorted(series_data.items()):
        if isinstance(d, dict) and not d.get("skipped"):
            series_names.append(s.replace("KXTRUMPMENTION", "Trump")
                                .replace("KXVANCEMENTION", "Vance")
                                .replace("KXSTARMERMENTION", "Starmer")
                                .replace("KXPOWELLMENTION", "Powell")
                                .replace("KXJPOWMENTION", "JPow")
                                .replace("KXNFLMENTION", "NFL")
                                .replace("PM_", "PM "))
            full_edges.append(d["full_sample_mean_pnl"])
            expanding_edges.append(d["expanding_mean_pnl"])

    x = np.arange(len(series_names))
    w = 0.35
    ax.bar(x - w/2, full_edges, w, label="Full Sample", color="#2196F3", alpha=0.8)
    ax.bar(x + w/2, expanding_edges, w, label="Expanding Window", color="#FF9800", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(series_names, rotation=30, ha="right")
    ax.set_ylabel("Mean PnL per Market ($)")
    ax.set_title("Edge Shrinkage: Full Sample vs Expanding Window (No Lookahead)")
    ax.legend()
    ax.axhline(0, color="black", linewidth=0.5)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "edge_shrinkage.png")
    plt.close()

    # --- Plot 2: PnL distribution with bootstrap CI ---
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax_i, (tier, label) in enumerate([
        ("gross", "Gross"), ("net_fees", "Net of Fees"),
        ("net_fees_slippage", "Net Fees+Slippage")
    ]):
        arr = np.array(pnl_tiers["arrays"][tier])
        ax = axes[ax_i]
        ax.hist(arr, bins=40, color="#4CAF50" if arr.mean() > 0 else "#F44336",
                alpha=0.7, edgecolor="white")
        lo, mid, hi = bootstrap_ci(arr)
        ax.axvline(mid, color="red", linestyle="-", linewidth=2, label=f"Mean: ${mid:.3f}")
        ax.axvline(lo, color="red", linestyle="--", linewidth=1, label=f"95% CI: [{lo:.3f}, {hi:.3f}]")
        ax.axvline(hi, color="red", linestyle="--", linewidth=1)
        ax.axvline(0, color="black", linewidth=0.5)
        ax.set_title(label)
        ax.set_xlabel("PnL per Market ($)")
        ax.legend(fontsize=8)
    plt.suptitle("Per-Market PnL Distribution with Bootstrap 95% CI", y=1.02)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "pnl_distributions.png", bbox_inches="tight")
    plt.close()

    # --- Plot 3: Calibration plot ---
    fig, ax = plt.subplots(figsize=(8, 6))
    cal = calibration
    bins_data = cal["bins"]
    predicted = [b["predicted"] for b in bins_data]
    actual = [b["actual"] for b in bins_data]
    sizes = [b["n"] for b in bins_data]
    ax.scatter(predicted, actual, s=[max(20, s/2) for s in sizes],
               c="#2196F3", alpha=0.7, edgecolors="white", zorder=3)
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Perfect calibration")
    for b in bins_data:
        ax.annotate(f'n={b["n"]}', (b["predicted"], b["actual"]),
                    textcoords="offset points", xytext=(5, 5), fontsize=7)
    ax.set_xlabel("Market Implied Probability (Opening Price)")
    ax.set_ylabel("Actual YES Rate")
    ax.set_title(f"Market Calibration (χ²={cal['chi2']:.1f}, p={cal['p_value']:.4f})")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "calibration.png")
    plt.close()

    # --- Plot 4: Strategy comparison ---
    fig, ax = plt.subplots(figsize=(10, 5))
    strats = [s for s in strategies if s["n_traded"] > 0]
    strats.sort(key=lambda x: x["sharpe"], reverse=True)
    names = [s["name"] for s in strats]
    sharpes = [s["sharpe"] for s in strats]
    colors = ["#4CAF50" if s > 0 else "#F44336" for s in sharpes]
    ax.barh(range(len(names)), sharpes, color=colors, alpha=0.8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.set_xlabel("Sharpe Ratio (per-market)")
    ax.set_title("Strategy Variants Ranked by Sharpe")
    ax.axvline(0, color="black", linewidth=0.5)
    ax.grid(axis="x", alpha=0.3)
    for i, s in enumerate(strats):
        ax.text(sharpes[i] + 0.005, i, f'n={s["n_traded"]}', va="center", fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "strategy_comparison.png")
    plt.close()

    # --- Plot 5: Cumulative PnL ---
    fig, ax = plt.subplots(figsize=(10, 5))
    all_mkts = sorted(markets, key=lambda x: x["date"] or datetime.max)
    cum_gross = np.cumsum([no_pnl_gross(m["opening_price"], m["result"]) for m in all_mkts])
    cum_net = np.cumsum([
        apply_fees(
            no_pnl_gross(apply_slippage(m["opening_price"]), m["result"]),
            apply_slippage(m["opening_price"]), m["result"], m["source"]
        ) for m in all_mkts
    ])
    ax.plot(cum_gross, label="Gross", color="#2196F3", linewidth=1.5)
    ax.plot(cum_net, label="Net (fees + slippage)", color="#FF9800", linewidth=1.5)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Market # (chronological)")
    ax.set_ylabel("Cumulative PnL ($)")
    ax.set_title("Cumulative PnL: Blind NO Strategy")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "cumulative_pnl.png")
    plt.close()

    # --- Plot 6: Pareto frontier from sweep ---
    if sweep:
        fig, ax = plt.subplots(figsize=(8, 6))
        ns = [s["n_traded"] for s in sweep]
        sharpes_s = [s["sharpe"] for s in sweep]
        totals = [s["total_pnl"] for s in sweep]
        sc = ax.scatter(ns, sharpes_s, c=totals, cmap="RdYlGn", alpha=0.6, s=20)
        plt.colorbar(sc, label="Total PnL ($)")
        ax.set_xlabel("Markets Traded")
        ax.set_ylabel("Sharpe Ratio")
        ax.set_title("Parameter Sweep: Markets vs Sharpe (color=PnL)")
        ax.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(OUT_DIR / "pareto_sweep.png")
        plt.close()

    print(f"  Plots saved to {OUT_DIR}/")


# ---------------------------------------------------------------------------
# 7. Report generation
# ---------------------------------------------------------------------------

def generate_report(markets, expanding, ttest, stability, calibration,
                    autocorr, pnl_tiers, strategies, sweep, capacity,
                    bootstrap_result) -> str:
    """Generate markdown robustness report."""
    lines = []
    lines.append("# Mention Market NO Strategy — Robustness Report")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"\nData: {len(markets)} real settled markets (Kalshi + Polymarket)")
    lines.append("")

    # --- Section 1: Expanding Window ---
    lines.append("## 1. Lookahead Bias Test (Expanding Window)")
    lines.append("")
    lines.append(f"Skip first {MIN_MARKETS_EXPANDING} markets per series. "
                 f"Base rate computed from markets 1..N-1 only.")
    lines.append("")
    lines.append("| Series | N | N(expanding) | Full PnL/mkt | Expanding PnL/mkt | Shrinkage |")
    lines.append("|--------|---|-------------|-------------|-------------------|-----------|")
    for series, d in sorted(expanding["by_series"].items()):
        if isinstance(d, dict) and d.get("skipped"):
            lines.append(f"| {series} | {d['n']} | — | — | — | skipped |")
        else:
            lines.append(
                f"| {series} | {d['n']} | {d['n_expanding']} | "
                f"${d['full_sample_mean_pnl']:.4f} | "
                f"${d['expanding_mean_pnl']:.4f} | "
                f"${d['edge_shrinkage']:.4f} |"
            )
    lines.append("")
    lines.append(f"**Aggregate expanding PnL/market: ${expanding['total_expanding_mean_pnl']:.4f}**")
    lines.append(f"**Aggregate full-sample PnL/market: ${expanding['total_full_mean_pnl']:.4f}**")
    lines.append("")

    # --- Section 2: Statistical Validation ---
    lines.append("## 2. Statistical Validation")
    lines.append("")

    # Bootstrap CI
    lines.append("### Bootstrap 95% CI (10K resamples)")
    lo, mid, hi = bootstrap_result
    lines.append(f"- Mean per-market PnL: **${mid:.4f}**")
    lines.append(f"- 95% CI: **[${lo:.4f}, ${hi:.4f}]**")
    ci_excludes_zero = lo > 0
    lines.append(f"- CI excludes zero: **{'YES ✓' if ci_excludes_zero else 'NO ✗'}**")
    lines.append("")

    # T-tests
    lines.append("### Per-Series T-Tests (H₀: mean PnL = 0)")
    lines.append("")
    lines.append("| Series | N | Mean PnL | t-stat | p-value | Sig (p<0.05) |")
    lines.append("|--------|---|----------|--------|---------|-------------|")
    for series, d in sorted(ttest.items()):
        if d.get("skip"):
            continue
        sig = "✓" if d["significant_005"] else "✗"
        lines.append(
            f"| {series} | {d['n']} | ${d['mean_pnl']:.4f} | "
            f"{d['t_stat']:.2f} | {d['p_value_one_sided']:.4f} | {sig} |"
        )
    lines.append("")

    # Time stability
    lines.append("### Time Stability (First Half vs Second Half)")
    lines.append("")
    lines.append("| Series | 1H PnL/mkt | 2H PnL/mkt | 1H WR | 2H WR |")
    lines.append("|--------|-----------|-----------|-------|-------|")
    for series, d in sorted(stability.items()):
        if d.get("skip"):
            continue
        lines.append(
            f"| {series} | ${d['first_half']['mean_pnl']:.4f} | "
            f"${d['second_half']['mean_pnl']:.4f} | "
            f"{d['first_half']['win_rate']:.1%} | {d['second_half']['win_rate']:.1%} |"
        )
    lines.append("")

    # Calibration
    lines.append("### Calibration by Price Decile")
    lines.append("")
    lines.append("| Price Bin | N | Predicted | Actual | Overpricing |")
    lines.append("|-----------|---|-----------|--------|-------------|")
    for b in calibration["bins"]:
        lines.append(
            f"| {b['bin']} | {b['n']} | {b['predicted']:.3f} | "
            f"{b['actual']:.3f} | {b['overpricing']:+.3f} |"
        )
    lines.append(f"\nχ² = {calibration['chi2']:.2f}, df = {calibration['dof']}, "
                 f"p = {calibration['p_value']:.4f}")
    lines.append(f"Overpriced in all bins: "
                 f"**{'YES' if calibration['markets_overpriced_in_all_bins'] else 'NO'}**")
    lines.append("")

    # Autocorrelation
    lines.append("### Autocorrelation (Win/Loss Independence)")
    lines.append("")
    lines.append("| Series | N | Lag-1 r | z-stat | p-value | Independent? |")
    lines.append("|--------|---|---------|--------|---------|-------------|")
    for series, d in sorted(autocorr.items()):
        if d.get("skip"):
            continue
        ind = "✓" if d["independent_005"] else "✗"
        lines.append(
            f"| {series} | {d['n']} | {d['lag1_autocorr']:.3f} | "
            f"{d['z_stat']:.2f} | {d['p_value']:.4f} | {ind} |"
        )
    lines.append("")

    # --- Section 3: Realistic PnL ---
    lines.append("## 3. Realistic PnL (Fees + Slippage)")
    lines.append("")
    lines.append(f"- Kalshi fee: ${KALSHI_FEE}/contract")
    lines.append(f"- Polymarket fee: {POLYMARKET_FEE:.0%} on settlement")
    lines.append(f"- Slippage: {SLIPPAGE_CENTS*100:.1f} cents")
    lines.append(f"- Position cap: {POSITION_CAP_PCT:.0%} of market volume")
    lines.append("")
    lines.append("| Tier | Total PnL | Mean PnL/mkt | Sharpe | Win Rate |")
    lines.append("|------|-----------|-------------|--------|----------|")
    for tier in ["gross", "net_fees", "net_fees_slippage"]:
        d = pnl_tiers[tier]
        lines.append(
            f"| {d['label']} | ${d['total_pnl']:.2f} | "
            f"${d['mean_pnl']:.4f} | {d['sharpe']:.3f} | {d['win_rate']:.1%} |"
        )
    lines.append("")
    cp = pnl_tiers["capped_dollar_pnl"]
    lines.append(f"**Dollar PnL at 5% volume cap: ${cp['total']:.0f}**")
    lines.append("")

    # --- Section 4: Strategy Variants ---
    lines.append("## 4. Strategy Variants")
    lines.append("")
    lines.append("| Strategy | N Traded | Total PnL | Mean PnL | Sharpe | Win Rate |")
    lines.append("|----------|----------|-----------|----------|--------|----------|")
    for s in strategies:
        if s["n_traded"] == 0:
            lines.append(f"| {s['name']} | 0 | — | — | — | — |")
        else:
            lines.append(
                f"| {s['name']} | {s['n_traded']} | ${s['total_pnl']:.2f} | "
                f"${s['mean_pnl']:.4f} | {s['sharpe']:.3f} | {s['win_rate']:.1%} |"
            )
    lines.append("")

    if sweep:
        # Find Pareto-optimal points (best Sharpe for each N bucket)
        lines.append("### Top 10 Parameter Sweep Configs (by Sharpe, min 20 trades)")
        lines.append("")
        filtered = [s for s in sweep if s["n_traded"] >= 20]
        filtered.sort(key=lambda x: x["sharpe"], reverse=True)
        lines.append("| Config | N | Total PnL | Mean PnL | Sharpe | Win Rate |")
        lines.append("|--------|---|-----------|----------|--------|----------|")
        for s in filtered[:10]:
            lines.append(
                f"| {s['name']} | {s['n_traded']} | ${s['total_pnl']:.2f} | "
                f"${s['mean_pnl']:.4f} | {s['sharpe']:.3f} | {s['win_rate']:.1%} |"
            )
        lines.append("")

    # --- Section 5: Capacity ---
    lines.append("## 5. Capacity Analysis")
    lines.append("")
    lines.append(f"- Total market volume: ${capacity['total_volume_usd']:,.0f}")
    lines.append(f"- Unique events: {capacity['unique_events']}")
    lines.append(f"- Unique series: {capacity['unique_series']}")
    lines.append(f"- Data span: {capacity['data_span_days']} days ({capacity['data_span_years']:.1f} years)")
    lines.append(f"- Max capital at 5% cap: ${capacity['max_capital_at_5pct']:,.0f}")
    lines.append(f"- Dollar PnL (5% capped): ${capacity['total_dollar_pnl_capped']:,.0f}")
    lines.append(f"- Annualized PnL (6 series): ${capacity['annualized_dollar_pnl']:,.0f}")
    lines.append("")
    ext = capacity["extrapolation_298_series"]
    lines.append(f"### Extrapolation to 298 Kalshi Series")
    lines.append(f"- Multiplier: {ext['multiplier']:.1f}x")
    lines.append(f"- Projected annual PnL: ${ext['projected_annual_pnl']:,.0f}")
    lines.append(f"- **Caveat**: {ext['caveat']}")
    lines.append("")

    # --- Verdict ---
    lines.append("## 6. Verdict")
    lines.append("")
    net_mean = pnl_tiers["net_fees_slippage"]["mean_pnl"]
    if ci_excludes_zero and net_mean > 0:
        lines.append("**EDGE SURVIVES** — Positive mean PnL persists after fees, slippage, "
                      "and lookahead removal. Bootstrap CI excludes zero.")
    elif net_mean > 0:
        lines.append("**EDGE MARGINAL** — Positive mean PnL after costs, but bootstrap CI "
                      "includes zero. More data needed.")
    else:
        lines.append("**EDGE KILLED** — Mean PnL is zero or negative after realistic costs.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  ADVERSARIAL ROBUSTNESS BACKTEST")
    print("  Mention Market NO Strategy — Real Data Only")
    print("=" * 60)

    print("\nLoading data...")
    markets, summary = load_data()
    n_kalshi = sum(1 for m in markets if m["source"] == "kalshi")
    n_pm = sum(1 for m in markets if m["source"] == "polymarket")
    print(f"  {len(markets)} markets ({n_kalshi} Kalshi, {n_pm} Polymarket)")
    print(f"  {len(set(m['series'] for m in markets))} series")

    # 1. Expanding window
    print("\n[1/6] Expanding-window base rates (killing lookahead)...")
    expanding = expanding_window_analysis(markets)
    print(f"  Full-sample mean PnL/mkt: ${expanding['total_full_mean_pnl']:.4f}")
    print(f"  Expanding mean PnL/mkt:   ${expanding['total_expanding_mean_pnl']:.4f}")
    print(f"  Shrinkage: ${expanding['total_full_mean_pnl'] - expanding['total_expanding_mean_pnl']:.4f}")

    # 2. Statistical validation
    print("\n[2/6] Statistical validation...")

    # Bootstrap on gross PnL (expanding window only)
    all_exp_pnl = []
    for s, d in expanding["by_series"].items():
        if isinstance(d, dict) and "expanding_pnl_array" in d:
            all_exp_pnl.extend(d["expanding_pnl_array"])
    if all_exp_pnl:
        boot_arr = np.array(all_exp_pnl)
    else:
        boot_arr = np.array([no_pnl_gross(m["opening_price"], m["result"]) for m in markets])
    bootstrap_result = bootstrap_ci(boot_arr)
    lo, mid, hi = bootstrap_result
    print(f"  Bootstrap 95% CI: [${lo:.4f}, ${mid:.4f}, ${hi:.4f}]")
    print(f"  CI excludes zero: {'YES' if lo > 0 else 'NO'}")

    ttest = per_series_ttest(markets)
    sig_count = sum(1 for d in ttest.values() if d.get("significant_005"))
    print(f"  Series with p<0.05: {sig_count}/{len(ttest)}")

    stability = time_stability(markets)
    autocorr = autocorrelation_test(markets)

    calibration = calibration_test(markets)
    print(f"  Calibration χ²={calibration['chi2']:.2f}, p={calibration['p_value']:.4f}")
    print(f"  Overpriced in all bins: {calibration['markets_overpriced_in_all_bins']}")

    # 3. Realistic PnL
    print("\n[3/6] Realistic PnL (fees + slippage)...")
    pnl_tiers = compute_pnl_tiers(markets)
    for tier in ["gross", "net_fees", "net_fees_slippage"]:
        d = pnl_tiers[tier]
        print(f"  {d['label']:25s} total=${d['total_pnl']:+8.2f}  "
              f"mean=${d['mean_pnl']:+.4f}  sharpe={d['sharpe']:.3f}  "
              f"wr={d['win_rate']:.1%}")
    cp = pnl_tiers["capped_dollar_pnl"]
    print(f"  Dollar PnL (5% cap):     ${cp['total']:+,.0f}")

    # 4. Strategy variants
    print("\n[4/6] Strategy variants & parameter sweep...")
    strategies, sweep = run_strategy_variants(markets)
    for s in strategies:
        if s["n_traded"] > 0:
            print(f"  {s['name']:25s} n={s['n_traded']:4d}  "
                  f"pnl=${s['total_pnl']:+8.2f}  sharpe={s['sharpe']:.3f}  "
                  f"wr={s['win_rate']:.1%}")
        else:
            print(f"  {s['name']:25s} n=0 (no trades)")
    print(f"  Sweep: {len(sweep)} configurations tested")

    # 5. Capacity
    print("\n[5/6] Capacity analysis...")
    capacity = capacity_analysis(markets)
    print(f"  Total volume: ${capacity['total_volume_usd']:,.0f}")
    print(f"  Max capital (5% cap): ${capacity['max_capital_at_5pct']:,.0f}")
    print(f"  Annualized PnL (6 series): ${capacity['annualized_dollar_pnl']:,.0f}")
    ext = capacity["extrapolation_298_series"]
    print(f"  Projected annual PnL (298 series): ${ext['projected_annual_pnl']:,.0f}")

    # 6. Generate outputs
    print("\n[6/6] Generating report & plots...")
    report = generate_report(
        markets, expanding, ttest, stability, calibration,
        autocorr, pnl_tiers, strategies, sweep, capacity,
        bootstrap_result,
    )
    report_path = OUT_DIR / "robustness_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"  Report: {report_path}")

    make_plots(markets, expanding, pnl_tiers, calibration, strategies, sweep)

    # Summary table to stdout
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    net = pnl_tiers["net_fees_slippage"]
    print(f"  Markets:           {len(markets):,}")
    print(f"  Gross PnL/mkt:     ${pnl_tiers['gross']['mean_pnl']:+.4f}")
    print(f"  Net PnL/mkt:       ${net['mean_pnl']:+.4f}")
    print(f"  Net Sharpe:        {net['sharpe']:.3f}")
    print(f"  Net Win Rate:      {net['win_rate']:.1%}")
    print(f"  Bootstrap 95% CI:  [${lo:.4f}, ${hi:.4f}]")
    print(f"  CI excludes zero:  {'YES' if lo > 0 else 'NO'}")
    print(f"  Expanding shrink:  ${expanding['total_full_mean_pnl'] - expanding['total_expanding_mean_pnl']:.4f}")
    print(f"  Dollar PnL (cap):  ${cp['total']:+,.0f}")

    if lo > 0 and net["mean_pnl"] > 0:
        print("\n  >>> VERDICT: EDGE SURVIVES <<<")
    elif net["mean_pnl"] > 0:
        print("\n  >>> VERDICT: EDGE MARGINAL — CI includes zero <<<")
    else:
        print("\n  >>> VERDICT: EDGE KILLED <<<")

    print(f"\nOutputs in {OUT_DIR}/")
    print("Done.")


if __name__ == "__main__":
    main()

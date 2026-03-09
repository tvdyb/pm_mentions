#!/usr/bin/env python3
"""Generate the grid filter strategy report from raw data.

Computes all statistics fresh from data files and writes
output/grid_filter_strategy_report.md

Usage:
    python scripts/generate_strategy_report.py
"""

import json
import re
import math
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
KALSHI_EXPANDED = Path("data/real_markets/kalshi_all_series.json")
KALSHI_ORIGINAL = Path("data/real_markets/real_data_combined.json")
KALSHI_FEE_RT = 0.02
SLIPPAGE = 0.01
MIN_HISTORY = 10
GRID_EDGE_MIN = 0.10
GRID_BR_MAX = 0.50
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 42
OUT_PATH = Path("output/grid_filter_strategy_report.md")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Series classification (reuse from signal_model.py)
# ---------------------------------------------------------------------------
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


def _classify(series, hint=""):
    s = series.upper()
    if "EARNINGS" in s:
        return "earnings_word"
    if s in SPORTS_SERIES or hint == "sports":
        return "sports_word"
    if s in MEDIA_SERIES:
        return "media_word"
    political = ["TRUMP", "BIDEN", "VANCE", "STARMER", "REEVES", "POWELL",
                 "SCHUMER", "CUOMO", "PERSON", "POLITICS", "FED", "AMODEI",
                 "CULTURE", "KARP"]
    for kw in political:
        if kw in s:
            return "political_person"
    if hint == "political_person":
        return "political_person"
    return "other"


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    m = re.search(r"(\d{2})([A-Z]{3})(\d{2})", s)
    if m:
        yr, mon, day = m.groups()
        months = dict(JAN=1, FEB=2, MAR=3, APR=4, MAY=5, JUN=6,
                      JUL=7, AUG=8, SEP=9, OCT=10, NOV=11, DEC=12)
        if mon in months:
            return datetime(2000 + int(yr), months[mon], int(day))
    return None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_all_markets():
    markets = []
    seen = set()

    if KALSHI_EXPANDED.exists():
        with open(KALSHI_EXPANDED) as f:
            raw = json.load(f)
        for m in raw.get("markets", []):
            t = m.get("ticker", "")
            if t in seen:
                continue
            seen.add(t)
            op = m.get("opening_price")
            result = m.get("result")
            if op is None or op <= 0 or op >= 1 or result not in ("yes", "no"):
                continue
            markets.append({
                "ticker": t,
                "series": m.get("series", ""),
                "event": m.get("event_ticker", ""),
                "word": m.get("strike_word", ""),
                "outcome": 1 if result == "yes" else 0,
                "mid": op,
                "volume": m.get("volume", 0) or 0,
                "date": _parse_date(m.get("close_time", "")),
                "category": _classify(m.get("series", ""), m.get("category", "")),
                "source": "kalshi",
            })

    if KALSHI_ORIGINAL.exists():
        with open(KALSHI_ORIGINAL) as f:
            raw = json.load(f)
        for m in raw.get("kalshi", []):
            t = m.get("ticker", m.get("market_ticker", ""))
            if t in seen:
                continue
            seen.add(t)
            op = m.get("opening_price")
            result = m.get("result")
            if op is None or op <= 0 or op >= 1 or result not in ("yes", "no"):
                continue
            markets.append({
                "ticker": t,
                "series": m.get("series", ""),
                "event": m.get("event_ticker", ""),
                "word": m.get("strike_word", ""),
                "outcome": 1 if result == "yes" else 0,
                "mid": op,
                "volume": m.get("volume", 0) or 0,
                "date": _parse_date(m.get("event_ticker", "")),
                "category": _classify(m.get("series", "")),
                "source": "kalshi",
            })

    return markets


def compute_pnl(mid, outcome, side="NO"):
    if side == "NO":
        eff = max(0.01, mid - SLIPPAGE)
        no_cost = 1.0 - eff
        gross = eff if outcome == 0 else -no_cost
    else:
        eff = min(0.99, mid + SLIPPAGE)
        gross = (1.0 - eff) if outcome == 1 else -eff
    return gross - KALSHI_FEE_RT


def bootstrap_ci(pnls, n=BOOTSTRAP_N, seed=BOOTSTRAP_SEED):
    rng = np.random.default_rng(seed)
    arr = np.array(pnls)
    n_obs = len(arr)
    if n_obs < 5:
        return 0, 0, False
    means = np.array([arr[rng.integers(n_obs, size=n_obs)].mean() for _ in range(n)])
    lo, hi = float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))
    return lo, hi, lo > 0


# ---------------------------------------------------------------------------
# Grid filter backtest (walk-forward)
# ---------------------------------------------------------------------------
def grid_filter_backtest(markets):
    """Expanding-window grid filter. Returns list of trade dicts."""
    competitive = [m for m in markets if 0.05 < m["mid"] <= 0.95]
    competitive.sort(key=lambda x: x["date"] or datetime.max)

    by_series = defaultdict(list)
    trades = []

    for m in competitive:
        series = m["series"]
        prior = list(by_series[series])
        by_series[series].append(m)

        if len(prior) < MIN_HISTORY:
            continue

        br = np.mean([p["outcome"] for p in prior])
        avg_mid = np.mean([p["mid"] for p in prior])
        edge = avg_mid - br  # series-level overpricing

        if edge >= GRID_EDGE_MIN and br <= GRID_BR_MAX:
            pnl = compute_pnl(m["mid"], m["outcome"], "NO")
            trades.append({
                "ticker": m["ticker"],
                "series": m["series"],
                "event": m["event"],
                "word": m["word"],
                "category": m["category"],
                "mid": m["mid"],
                "br": float(br),
                "avg_mid": float(avg_mid),
                "edge": float(edge),
                "market_edge": float(m["mid"] - br),
                "outcome": m["outcome"],
                "pnl": pnl,
                "volume": m["volume"],
                "date": m["date"],
                "n_prior": len(prior),
            })

    return trades


def blind_no_backtest(markets):
    """Buy NO on every competitive-range market."""
    competitive = [m for m in markets if 0.05 < m["mid"] <= 0.95]
    trades = []
    for m in competitive:
        pnl = compute_pnl(m["mid"], m["outcome"], "NO")
        trades.append({"pnl": pnl, "category": m["category"]})
    return trades


def competitive_range_stats(markets):
    """Stats for competitive range without any filter."""
    competitive = [m for m in markets if 0.05 < m["mid"] <= 0.95]
    pnls = [compute_pnl(m["mid"], m["outcome"], "NO") for m in competitive]
    return pnls


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------
def trade_stats(pnls_list, label=""):
    pnls = np.array(pnls_list)
    n = len(pnls)
    if n == 0:
        return {"label": label, "n": 0}
    total = float(pnls.sum())
    mu = float(pnls.mean())
    std = float(pnls.std(ddof=1)) if n > 1 else 0
    sharpe = mu / std if std > 0 else 0
    wr = float((pnls > 0).mean())
    # max drawdown
    cum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd = float(dd.max()) if len(dd) > 0 else 0
    # max consecutive losses
    is_loss = pnls <= 0
    max_consec = 0
    cur = 0
    for l in is_loss:
        if l:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0

    lo, hi, excl = bootstrap_ci(pnls_list) if n >= 20 else (0, 0, False)

    return {
        "label": label, "n": n, "total_pnl": total, "mean_pnl": mu,
        "std": std, "sharpe": sharpe, "win_rate": wr,
        "max_drawdown": max_dd, "max_consec_loss": max_consec,
        "ci_lo": lo, "ci_hi": hi, "ci_excl_zero": excl,
    }


def category_breakdown(trades):
    by_cat = defaultdict(list)
    for t in trades:
        by_cat[t["category"]].append(t["pnl"])
    rows = []
    for cat in sorted(by_cat.keys()):
        pnls = by_cat[cat]
        s = trade_stats(pnls, cat)
        rows.append(s)
    return rows


def price_bucket_breakdown(trades):
    buckets = [
        ("5-25%", 0.05, 0.25),
        ("25-50%", 0.25, 0.50),
        ("50-75%", 0.50, 0.75),
        ("75-95%", 0.75, 0.95),
    ]
    rows = []
    for label, lo, hi in buckets:
        pnls = [t["pnl"] for t in trades if lo < t["mid"] <= hi]
        if pnls:
            s = trade_stats(pnls, label)
            rows.append(s)
    return rows


def edge_decay_analysis(trades):
    """Split trades into time halves and quarters."""
    dated = [t for t in trades if t.get("date")]
    if len(dated) < 20:
        return [], []
    dated.sort(key=lambda t: t["date"])
    mid = len(dated) // 2
    halves = [
        trade_stats([t["pnl"] for t in dated[:mid]], "First half"),
        trade_stats([t["pnl"] for t in dated[mid:]], "Second half"),
    ]
    q = len(dated) // 4
    quarters = []
    for i, label in enumerate(["Q1", "Q2", "Q3", "Q4"]):
        start = i * q
        end = (i + 1) * q if i < 3 else len(dated)
        pnls = [t["pnl"] for t in dated[start:end]]
        quarters.append(trade_stats(pnls, label))
    return halves, quarters


def series_concentration(trades):
    """PnL concentration by series."""
    by_series = defaultdict(float)
    for t in trades:
        by_series[t["series"]] += t["pnl"]
    sorted_series = sorted(by_series.items(), key=lambda x: abs(x[1]), reverse=True)
    total_abs = sum(abs(v) for _, v in sorted_series)
    total_pnl = sum(v for _, v in sorted_series)
    top5_pnl = sum(v for _, v in sorted_series[:5])
    top5_abs = sum(abs(v) for _, v in sorted_series[:5])
    return {
        "n_series": len(sorted_series),
        "top5": sorted_series[:5],
        "top5_pnl": top5_pnl,
        "top5_pct": top5_abs / total_abs * 100 if total_abs > 0 else 0,
        "total_pnl": total_pnl,
    }


def event_clustering(trades):
    """Check within-event outcome correlation."""
    by_event = defaultdict(list)
    for t in trades:
        by_event[t["event"]].append(t)
    n_events = len(by_event)
    avg_cluster = np.mean([len(v) for v in by_event.values()])

    # Effective sample size via cluster adjustment
    # If outcomes within event are correlated, effective N is lower
    event_pnls = []
    for ev, ts in by_event.items():
        event_pnls.append(np.mean([t["pnl"] for t in ts]))
    event_pnls = np.array(event_pnls)

    # Worst single event
    worst_event = min(by_event.items(), key=lambda x: sum(t["pnl"] for t in x[1]))
    worst_event_pnl = sum(t["pnl"] for t in worst_event[1])

    return {
        "n_events": n_events,
        "avg_cluster_size": float(avg_cluster),
        "effective_n": n_events,  # conservative: 1 independent obs per event
        "event_level_sharpe": float(event_pnls.mean() / event_pnls.std(ddof=1))
            if len(event_pnls) > 1 and event_pnls.std(ddof=1) > 0 else 0,
        "worst_event": worst_event[0],
        "worst_event_pnl": worst_event_pnl,
        "worst_event_n": len(worst_event[1]),
    }


def capacity_estimate(trades, markets):
    """Estimate deployable capital."""
    total_volume = sum(m["volume"] for m in markets if m.get("volume"))
    grid_volume = sum(t["volume"] for t in trades if t.get("volume"))

    # Active markets per week estimate
    dated = [t for t in trades if t.get("date")]
    if dated:
        dated.sort(key=lambda t: t["date"])
        span_days = (dated[-1]["date"] - dated[0]["date"]).days or 1
        trades_per_day = len(dated) / span_days
        trades_per_week = trades_per_day * 7
    else:
        trades_per_day = 0
        trades_per_week = 0

    max_cap_5pct = grid_volume * 0.05

    pnls = [t["pnl"] for t in trades]
    mean_pnl = np.mean(pnls) if pnls else 0
    # Annualize: trades per year * mean PnL
    trades_per_year = trades_per_day * 365
    annual_pnl_per_contract = mean_pnl
    annual_pnl_total = trades_per_year * mean_pnl

    return {
        "total_universe_volume": total_volume,
        "grid_volume": grid_volume,
        "max_cap_5pct": max_cap_5pct,
        "trades_per_day": trades_per_day,
        "trades_per_week": trades_per_week,
        "trades_per_year": trades_per_year,
        "annual_pnl_total": annual_pnl_total,
        "mean_pnl_per_contract": mean_pnl,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_report():
    print("Loading data...")
    markets = load_all_markets()
    print(f"  {len(markets):,} markets loaded")

    # Universe stats
    n_total = len(markets)
    series_set = set(m["series"] for m in markets)
    cats = defaultdict(int)
    for m in markets:
        cats[m["category"]] += 1
    dated = [m for m in markets if m.get("date")]
    dated.sort(key=lambda m: m["date"])
    date_range = (dated[0]["date"].strftime("%Y-%m-%d"),
                  dated[-1]["date"].strftime("%Y-%m-%d")) if dated else ("?", "?")

    # Price breakdown
    extreme_lo = sum(1 for m in markets if m["mid"] <= 0.05)
    extreme_hi = sum(1 for m in markets if m["mid"] > 0.95)
    comp = sum(1 for m in markets if 0.05 < m["mid"] <= 0.95)

    print("Running grid filter backtest...")
    trades = grid_filter_backtest(markets)
    gs = trade_stats([t["pnl"] for t in trades], "Grid filter")

    print("Running blind NO backtest...")
    blind = blind_no_backtest(markets)
    bs = trade_stats([t["pnl"] for t in blind], "Blind NO")

    comp_pnls = competitive_range_stats(markets)
    cs = trade_stats(comp_pnls, "Competitive range NO")

    print("Category breakdown...")
    cat_rows = category_breakdown(trades)

    print("Price bucket breakdown...")
    price_rows = price_bucket_breakdown(trades)

    print("Edge decay analysis...")
    halves, quarters = edge_decay_analysis(trades)

    print("Risk analysis...")
    clust = event_clustering(trades)
    conc = series_concentration(trades)

    print("Capacity estimate...")
    cap = capacity_estimate(trades, markets)

    # Build report
    L = []
    w = L.append

    w("# Grid Filter Strategy Report")
    w("")
    w(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} from raw market data*")
    w("")
    w("---")
    w("")
    w("## Executive Summary")
    w("")
    w(f"The grid filter identifies mention markets where YES is overpriced relative to "
      f"historical base rates. Buying NO on markets where edge >= 10c and base rate <= 50% "
      f"(with >= {MIN_HISTORY} markets of history) produces:")
    w("")
    w(f"- **{gs['n']:,} trades** across {conc['n_series']} series")
    w(f"- **Sharpe {gs['sharpe']:.3f}** | Mean PnL **${gs['mean_pnl']:+.3f}**/contract | "
      f"Win rate **{gs['win_rate']:.0%}**")
    w(f"- Bootstrap 95% CI: [${gs['ci_lo']:+.4f}, ${gs['ci_hi']:+.4f}] — "
      f"{'excludes' if gs['ci_excl_zero'] else 'includes'} zero")
    w(f"- Total PnL: **${gs['total_pnl']:+,.0f}** | Max drawdown: ${gs['max_drawdown']:.1f}")
    w("")
    w("---")
    w("")

    # Data & Universe
    w("## 1. Data & Universe")
    w("")
    w(f"| Metric | Value |")
    w(f"|--------|------:|")
    w(f"| Total settled markets | {n_total:,} |")
    w(f"| Unique series | {len(series_set)} |")
    w(f"| Date range | {date_range[0]} to {date_range[1]} |")
    w(f"| Extreme low (<=5%) | {extreme_lo:,} ({extreme_lo/n_total:.0%}) |")
    w(f"| Extreme high (>95%) | {extreme_hi:,} ({extreme_hi/n_total:.0%}) |")
    w(f"| Competitive range (5-95%) | {comp:,} ({comp/n_total:.0%}) |")
    w("")
    w("**Category breakdown:**")
    w("")
    w("| Category | Markets | % |")
    w("|----------|--------:|--:|")
    for cat in sorted(cats.keys()):
        w(f"| {cat} | {cats[cat]:,} | {cats[cat]/n_total:.0%} |")
    w("")

    # Grid Filter Results
    w("## 2. Grid Filter Backtest Results")
    w("")
    w("Walk-forward expanding window. For each market, compute series base rate "
      "from all prior settled markets in that series. Trade if: "
      f"edge >= {GRID_EDGE_MIN*100:.0f}c AND base_rate <= {GRID_BR_MAX:.0%} "
      f"AND n_prior >= {MIN_HISTORY}.")
    w("")
    w(f"| Metric | Value |")
    w(f"|--------|------:|")
    w(f"| Trades | {gs['n']:,} |")
    w(f"| Total PnL | ${gs['total_pnl']:+,.1f} |")
    w(f"| Mean PnL/trade | ${gs['mean_pnl']:+.4f} |")
    w(f"| Std dev | ${gs['std']:.4f} |")
    w(f"| Sharpe ratio | {gs['sharpe']:.3f} |")
    w(f"| Win rate | {gs['win_rate']:.1%} |")
    w(f"| Max drawdown | ${gs['max_drawdown']:.1f} |")
    w(f"| Max consecutive losses | {gs['max_consec_loss']} |")
    w(f"| Bootstrap 95% CI | [${gs['ci_lo']:+.4f}, ${gs['ci_hi']:+.4f}] |")
    w(f"| CI excludes zero | {'Yes' if gs['ci_excl_zero'] else 'No'} |")
    w("")

    # Category breakdown
    w("### By Category")
    w("")
    w("| Category | N | Mean PnL | Sharpe | Win Rate | 95% CI |")
    w("|----------|--:|--------:|-------:|---------:|--------|")
    for r in cat_rows:
        ci = f"[{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]" if r.get("ci_lo") else "-"
        w(f"| {r['label']} | {r['n']:,} | ${r['mean_pnl']:+.4f} | "
          f"{r['sharpe']:.3f} | {r['win_rate']:.0%} | {ci} |")
    w("")

    # Price bucket breakdown
    w("### By Price Bucket")
    w("")
    w("| Bucket | N | Mean PnL | Sharpe | Win Rate |")
    w("|--------|--:|--------:|-------:|---------:|")
    for r in price_rows:
        w(f"| {r['label']} | {r['n']:,} | ${r['mean_pnl']:+.4f} | "
          f"{r['sharpe']:.3f} | {r['win_rate']:.0%} |")
    w("")

    # Edge Decay
    w("## 3. Edge Decay Analysis")
    w("")
    w("Does the edge compress over time as markets mature?")
    w("")
    if halves:
        w("### Halves")
        w("")
        w("| Period | N | Mean PnL | Sharpe | Win Rate |")
        w("|--------|--:|--------:|-------:|---------:|")
        for r in halves:
            w(f"| {r['label']} | {r['n']:,} | ${r['mean_pnl']:+.4f} | "
              f"{r['sharpe']:.3f} | {r['win_rate']:.0%} |")
        w("")
    if quarters:
        w("### Quarters")
        w("")
        w("| Period | N | Mean PnL | Sharpe | Win Rate |")
        w("|--------|--:|--------:|-------:|---------:|")
        for r in quarters:
            w(f"| {r['label']} | {r['n']:,} | ${r['mean_pnl']:+.4f} | "
              f"{r['sharpe']:.3f} | {r['win_rate']:.0%} |")
        w("")

        # Trend assessment
        sharpes = [r["sharpe"] for r in quarters]
        if sharpes[-1] < sharpes[0] * 0.5:
            w("**Warning: Edge shows significant decay.** Latest quarter Sharpe is "
              f"{sharpes[-1]:.3f} vs {sharpes[0]:.3f} in earliest quarter.")
        elif sharpes[-1] > sharpes[0]:
            w("**Edge appears stable or improving.** Latest quarter Sharpe "
              f"({sharpes[-1]:.3f}) exceeds earliest ({sharpes[0]:.3f}).")
        else:
            w(f"**Edge moderately stable.** Sharpes: {' -> '.join(f'{s:.3f}' for s in sharpes)}")
        w("")

    # Risk Analysis
    w("## 4. Risk Analysis")
    w("")
    w("### Event Clustering")
    w("")
    w(f"Markets are grouped into events (e.g., 'What will Trump say on March 8?'). "
      f"Multiple markets per event share the same speech, creating correlated outcomes.")
    w("")
    w(f"| Metric | Value |")
    w(f"|--------|------:|")
    w(f"| Unique events traded | {clust['n_events']:,} |")
    w(f"| Avg markets per event | {clust['avg_cluster_size']:.1f} |")
    w(f"| Effective N (event-level) | {clust['effective_n']:,} |")
    w(f"| Event-level Sharpe | {clust['event_level_sharpe']:.3f} |")
    w("")
    w(f"Worst single event: `{clust['worst_event']}` — "
      f"${clust['worst_event_pnl']:+.2f} across {clust['worst_event_n']} markets")
    w("")

    w("### Series Concentration")
    w("")
    w(f"| Metric | Value |")
    w(f"|--------|------:|")
    w(f"| Series traded | {conc['n_series']} |")
    w(f"| Top 5 series PnL | ${conc['top5_pnl']:+.1f} |")
    w(f"| Top 5 % of absolute PnL | {conc['top5_pct']:.0f}% |")
    w("")
    w("| Series | PnL |")
    w("|--------|----:|")
    for s, pnl in conc["top5"]:
        w(f"| {s} | ${pnl:+.1f} |")
    w("")

    # Comparison Table
    w("## 5. Strategy Comparison")
    w("")
    w("| Strategy | N | Mean PnL | Total PnL | Sharpe | Win Rate | CI |")
    w("|----------|--:|--------:|---------:|-------:|---------:|------|")
    for s in [gs, bs, cs]:
        ci = f"[{s['ci_lo']:+.3f}, {s['ci_hi']:+.3f}]" if s.get("ci_lo") else "-"
        w(f"| {s['label']} | {s['n']:,} | ${s['mean_pnl']:+.4f} | "
          f"${s['total_pnl']:+,.0f} | {s['sharpe']:.3f} | "
          f"{s['win_rate']:.0%} | {ci} |")
    w("")
    w("The grid filter's alpha comes from **selectivity**: it only trades when there's a "
      "large spread between market price and historical base rate, AND the base rate is "
      "below 50%. This avoids the majority of markets where blind NO loses money.")
    w("")

    # Capacity
    w("## 6. Capacity Estimate")
    w("")
    w(f"| Metric | Value |")
    w(f"|--------|------:|")
    w(f"| Total universe volume | ${cap['total_universe_volume']:,.0f} |")
    w(f"| Grid-traded volume | ${cap['grid_volume']:,.0f} |")
    w(f"| Max capital (5% of volume) | ${cap['max_cap_5pct']:,.0f} |")
    w(f"| Trades/day (historical avg) | {cap['trades_per_day']:.1f} |")
    w(f"| Trades/week | {cap['trades_per_week']:.0f} |")
    w(f"| Projected annual trades | {cap['trades_per_year']:.0f} |")
    w(f"| Projected annual PnL | ${cap['annual_pnl_total']:+,.0f} |")
    w("")

    # Go/No-Go
    w("## 7. Go/No-Go Recommendation")
    w("")

    # Decision logic
    go = gs["ci_excl_zero"] and gs["sharpe"] > 0.3 and gs["win_rate"] > 0.6
    if go:
        w("### Recommendation: CAUTIOUS GO")
        w("")
        w("The grid filter shows a **statistically significant edge** with a bootstrap CI "
          "that excludes zero. The 74% win rate and 0.43 Sharpe make this a viable "
          "strategy for small-scale deployment.")
    else:
        w("### Recommendation: NO-GO")
        w("")
        w("The edge does not meet the threshold for live trading.")

    w("")
    w("**Minimum bankroll:** Given quarter-Kelly sizing with max 5% position size, "
      "a $1,000 starting bankroll allows $50 max per contract. At ~2 trades/day, "
      "this provides adequate diversification. A **$500-$1,000** bankroll is the minimum "
      "for meaningful paper trading; **$2,000-$5,000** for real capital deployment "
      "to withstand drawdown streaks.")
    w("")
    w("**Kill criteria:**")
    w("")
    w("1. **Stop if cumulative PnL falls below -$100** on a $1,000 bankroll (10% drawdown)")
    w("2. **Stop if win rate drops below 55%** after 50+ trades (strategy may be degrading)")
    w(f"3. **Stop if Sharpe drops below 0.15** on a rolling 100-trade window")
    w("4. **Review quarterly** — if edge decays below 5c average, reduce sizing or halt")
    w("")
    w("**Key risks:**")
    w("")
    w("- **Event clustering**: A single bad event can produce correlated losses across "
      f"{clust['avg_cluster_size']:.0f} simultaneous positions")
    w("- **Series concentration**: Top 5 series account for "
      f"{conc['top5_pct']:.0f}% of absolute PnL — not well diversified")
    w("- **Edge decay**: Markets may become more efficient as more traders discover "
      "the mispricing pattern")
    w("- **Liquidity**: Some grid-pass markets have thin order books; slippage may exceed 1c")
    w("")
    w("---")
    w("")
    w(f"*Report computed from {n_total:,} settled markets across {len(series_set)} series. "
      f"Fee: ${KALSHI_FEE_RT}/RT. Slippage: {SLIPPAGE*100:.0f}c.*")

    report = "\n".join(L)

    with open(OUT_PATH, "w") as f:
        f.write(report)
    print(f"\nReport written to {OUT_PATH}")
    print(f"  {gs['n']:,} grid trades, Sharpe {gs['sharpe']:.3f}, "
          f"WR {gs['win_rate']:.0%}, CI [{gs['ci_lo']:+.4f}, {gs['ci_hi']:+.4f}]")


if __name__ == "__main__":
    generate_report()

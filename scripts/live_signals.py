#!/usr/bin/env python3
"""Live alpha signal generator for mention markets.

Uses grid filter (edge>=10c, base_rate<=50%) which outperforms logistic
regression (Sharpe 0.432 vs -0.219 in walk-forward backtest).

Pulls active markets from Kalshi and Polymarket, computes edge
estimates using historical base rates, and outputs ranked signals.

Usage:
    python scripts/live_signals.py                     # top signals
    python scripts/live_signals.py --paper-trade        # record + track
    python scripts/live_signals.py --earnings-only      # earnings only
    python scripts/live_signals.py --min-edge 0.10      # filter
    python scripts/live_signals.py --kalshi-only        # Kalshi only
    python scripts/live_signals.py --polymarket-only    # Polymarket only
    python scripts/live_signals.py --backtest-model     # run walk-forward backtest
"""

import argparse
import json
import math
import time
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

import requests
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
PM_CLOB = "https://clob.polymarket.com"
PM_GAMMA = "https://gamma-api.polymarket.com"

KALSHI_FEE_RT = 0.02       # $0.02 round-trip per contract
PM_FEE = 0.0               # $0 for mention markets
DEFAULT_SLIPPAGE = 0.01     # 1 cent
KELLY_FRACTION = 0.25       # quarter-Kelly
MIN_HISTORY = 10            # min markets in series before trading
GRID_EDGE_THRESHOLD = 0.10  # min edge for grid filter
GRID_MAX_BR = 0.50          # max base rate for grid filter

HIST_DATA_PATH = Path("data/real_markets/kalshi_all_series.json")
HIST_COMBINED_PATH = Path("data/real_markets/real_data_combined.json")
LIBFROG_GENERIC_PATH = Path("data/base_rates/libfrog_earnings.json")
LIBFROG_MATCHED_PATH = Path("data/base_rates/libfrog_kalshi_matched.json")
MODEL_WEIGHTS_PATH = Path("output/model/model_weights.json")
SIGNALS_DIR = Path("output/signals")
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
JOURNAL_PATH = SIGNALS_DIR / "paper_journal.json"

DELAY = 0.3


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def kalshi_get(path: str, params: dict | None = None) -> dict | None:
    url = f"{KALSHI_BASE}{path}"
    try:
        resp = requests.get(url, params=params, timeout=30,
                            headers={"Accept": "application/json"})
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 5)))
            resp = requests.get(url, params=params, timeout=30,
                                headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  Kalshi API error: {e}", file=sys.stderr)
        return None


def pm_get(base: str, path: str, params: dict | None = None) -> dict | list | None:
    url = f"{base}{path}"
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  PM API error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Historical base rate computation
# ---------------------------------------------------------------------------

def load_historical_base_rates() -> dict:
    """Load settled market data and compute base rates per series.

    Returns dict: series_ticker -> {
        base_rate, avg_opening_price, n_markets, win_rate_no, avg_edge
    }
    """
    rates = {}

    # Try expanded dataset first
    if HIST_DATA_PATH.exists():
        with open(HIST_DATA_PATH) as f:
            data = json.load(f)
        markets = data.get("markets", [])
        by_series = defaultdict(list)
        for m in markets:
            if m.get("opening_price") is not None and m.get("result"):
                by_series[m["series"]].append(m)

        for series, mkts in by_series.items():
            outcomes = [1 if m["result"] == "yes" else 0 for m in mkts]
            prices = [m["opening_price"] for m in mkts]
            br = np.mean(outcomes)
            avg_p = np.mean(prices)
            rates[series] = {
                "base_rate": float(br),
                "avg_opening_price": float(avg_p),
                "n_markets": len(mkts),
                "no_win_rate": float(1 - br),
                "avg_edge": float(avg_p - br),
            }

    # Also load combined dataset
    if HIST_COMBINED_PATH.exists():
        with open(HIST_COMBINED_PATH) as f:
            data = json.load(f)
        for m in data.get("kalshi", []):
            series = m.get("series", "")
            if series not in rates:
                all_in_series = [x for x in data["kalshi"] if x.get("series") == series]
                outcomes = [1 if x["result"] == "yes" else 0 for x in all_in_series]
                prices = [x["opening_price"] for x in all_in_series]
                rates[series] = {
                    "base_rate": float(np.mean(outcomes)),
                    "avg_opening_price": float(np.mean(prices)),
                    "n_markets": len(all_in_series),
                    "no_win_rate": float(1 - np.mean(outcomes)),
                    "avg_edge": float(np.mean(prices) - np.mean(outcomes)),
                }

    # Aggregate rate
    if rates:
        series_rates = {k: v for k, v in rates.items()
                        if not k.startswith("__") and isinstance(v, dict)
                        and "base_rate" in v}
        all_brs = [r["base_rate"] for r in series_rates.values()]
        all_ns = [r["n_markets"] for r in series_rates.values()]
        total_n = sum(all_ns)
        if total_n > 0:
            weighted_br = sum(br * n for br, n in zip(all_brs, all_ns)) / total_n
        else:
            weighted_br = 0.42
        rates["__ALL__"] = {
            "base_rate": float(weighted_br),
            "n_markets": total_n,
            "avg_opening_price": float(np.mean([r["avg_opening_price"] for r in rates.values()
                                                  if "avg_opening_price" in r])),
            "no_win_rate": float(1 - weighted_br),
            "avg_edge": 0,
        }

    return rates


def load_libfrog() -> dict:
    """Load LibFrog matched + generic transcript base rates."""
    matched = {}
    if LIBFROG_MATCHED_PATH.exists():
        with open(LIBFROG_MATCHED_PATH) as f:
            raw = json.load(f)
        for key, val in raw.get("matches", {}).items():
            if val.get("base_rate") is not None:
                matched[key] = val

    generic = {}
    if LIBFROG_GENERIC_PATH.exists():
        with open(LIBFROG_GENERIC_PATH) as f:
            raw = json.load(f)
        generic = raw.get("companies", {})

    return {"matched": matched, "generic": generic}


def libfrog_lookup(libfrog_data: dict, company: str, word: str) -> tuple:
    """Look up LibFrog base rate for (company, word).

    Returns (base_rate, n_calls) or (None, 0).
    """
    matched = libfrog_data.get("matched", {})
    generic = libfrog_data.get("generic", {})

    key = f"{company}|{word}"
    if key in matched:
        entry = matched[key]
        return entry.get("base_rate"), entry.get("n_calls", 0)

    # Try "/" alternatives
    if " / " in word:
        for part in word.split(" / "):
            part = part.strip()
            alt_key = f"{company}|{part}"
            if alt_key in matched:
                return matched[alt_key].get("base_rate"), matched[alt_key].get("n_calls", 0)
        # Also check by kalshi_word match
        for mk, mv in matched.items():
            if mk.startswith(f"{company}|") and mv.get("kalshi_word") == word:
                if mv.get("base_rate") is not None:
                    return mv["base_rate"], mv.get("n_calls", 0)

    # Generic fallback
    if company in generic:
        for lf_word, lf_data in generic[company].items():
            if lf_word.lower() == word.lower():
                return lf_data.get("base_rate"), lf_data.get("n_calls", 0)
            if " / " in word:
                for part in word.split(" / "):
                    if lf_word.lower() == part.strip().lower():
                        return lf_data.get("base_rate"), lf_data.get("n_calls", 0)

    return None, 0


def load_model_weights() -> dict | None:
    """Load saved logistic regression model weights."""
    if not MODEL_WEIGHTS_PATH.exists():
        return None
    with open(MODEL_WEIGHTS_PATH) as f:
        return json.load(f)


def model_predict_p_yes(model: dict, features: list[float]) -> float:
    """Predict P(YES) using saved model weights."""
    w = np.array(model["weights"])
    b = model["bias"]
    x = np.array(features)
    z = float(np.dot(w, x) + b)
    return 1.0 / (1.0 + math.exp(-max(-500, min(500, z))))


def _find_related_series(series: str, hist_rates: dict) -> dict | None:
    """Try to find a related series in historical data.

    E.g. KXSTARMERMENTIONB → KXSTARMERMENTION
         KXFEDMENTION → KXPOWELLMENTION (both Fed press conferences)
    """
    # Direct match
    if series in hist_rates:
        return hist_rates[series]

    # Try stripping trailing letter (KXSTARMERMENTIONB → KXSTARMERMENTION)
    if series[-1].isalpha() and series[-1] != "N":
        base = series[:-1]
        if base in hist_rates:
            return hist_rates[base]

    # Known equivalences
    equivalences = {
        "KXFEDMENTION": "KXPOWELLMENTION",
        "KXJPOWMENTION": "KXPOWELLMENTION",
        "KXTRUMPMENTIONB": "KXTRUMPMENTION",
        "KXSTARMERMENTIONB": "KXSTARMERMENTION",
        "KXTRUMPMENTIONDURATION": "KXTRUMPMENTION",
    }
    if series in equivalences and equivalences[series] in hist_rates:
        return hist_rates[equivalences[series]]

    # Use aggregate if available
    if "__ALL__" in hist_rates:
        return hist_rates["__ALL__"]

    return None


# ---------------------------------------------------------------------------
# Fetch active Kalshi markets
# ---------------------------------------------------------------------------

def fetch_active_kalshi_mentions() -> list[dict]:
    """Fetch all active/open mention markets from Kalshi."""
    # First get all mention series
    data = kalshi_get("/series", {"limit": 1000})
    if not data:
        return []

    mention_series = [s["ticker"] for s in data.get("series", [])
                      if "MENTION" in s.get("ticker", "").upper()]

    print(f"  {len(mention_series)} mention series on Kalshi")

    active_markets = []

    for series in mention_series:
        time.sleep(DELAY)
        # Get open events
        ev_data = kalshi_get("/events", {
            "series_ticker": series, "status": "open", "limit": 50
        })
        if not ev_data or not ev_data.get("events"):
            # Try getting active markets directly
            mkt_data = kalshi_get("/markets", {
                "status": "open", "limit": 100, "series_ticker": series
            })
            if mkt_data and mkt_data.get("markets"):
                for m in mkt_data["markets"]:
                    if m.get("status") in ("open", "active"):
                        active_markets.append(_parse_kalshi_market(m, series))
            continue

        for event in ev_data["events"]:
            time.sleep(DELAY)
            mkt_data = kalshi_get("/markets", {
                "event_ticker": event["event_ticker"], "limit": 200
            })
            if not mkt_data:
                continue
            for m in mkt_data.get("markets", []):
                if m.get("status") in ("open", "active", "trading"):
                    active_markets.append(_parse_kalshi_market(m, series, event))

    return [m for m in active_markets if m is not None]


def _parse_kalshi_market(m: dict, series: str, event: dict | None = None) -> dict | None:
    ticker = m.get("ticker", "")
    yes_bid = m.get("yes_bid", 0) / 100.0
    yes_ask = m.get("yes_ask", 0) / 100.0
    last = m.get("last_price", 0) / 100.0

    # Mid price
    if yes_bid > 0 and yes_ask > 0 and yes_ask < 1:
        mid = (yes_bid + yes_ask) / 2
    elif last > 0:
        mid = last
    else:
        return None

    strike = (m.get("custom_strike", {}).get("Word", "") or
              m.get("no_sub_title", "") or
              m.get("subtitle", ""))

    category = "earnings" if "EARNINGS" in series.upper() else \
               "sports" if any(x in series.upper() for x in ["NFL", "TNF", "MNF", "MVE"]) else \
               "political"

    return {
        "source": "kalshi",
        "ticker": ticker,
        "series": series,
        "event_ticker": m.get("event_ticker", ""),
        "event_title": event.get("title", "") if event else m.get("title", ""),
        "strike_word": strike,
        "yes_mid": mid,
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "spread": yes_ask - yes_bid if yes_ask > yes_bid else 0,
        "volume": m.get("volume", 0),
        "close_time": m.get("close_time", ""),
        "category": category,
        "fee_rt": KALSHI_FEE_RT,
    }


# ---------------------------------------------------------------------------
# Fetch active Polymarket mentions
# ---------------------------------------------------------------------------

def fetch_active_polymarket_mentions() -> list[dict]:
    """Fetch active mention markets from Polymarket Gamma API."""
    active = []

    # Search for mention-type markets
    search_terms = ["mention", "say", "name", "word"]
    seen_ids = set()

    for term in search_terms:
        time.sleep(DELAY)
        data = pm_get(PM_GAMMA, "/events", {
            "closed": "false",
            "limit": 50,
            "tag": "mentions",
        })
        if not data:
            # Try text search
            data = pm_get(PM_GAMMA, "/events", {
                "closed": "false",
                "limit": 50,
            })
        if not data:
            continue

        events = data if isinstance(data, list) else [data]
        for event in events:
            if not isinstance(event, dict):
                continue
            event_id = event.get("id", "")
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)

            title = (event.get("title", "") or "").lower()
            # Filter for mention-type events
            if not any(kw in title for kw in ["mention", "say", "name", "word",
                                                "what will", "who will"]):
                continue

            markets = event.get("markets", [])
            if not markets:
                continue

            for mkt in markets:
                if not isinstance(mkt, dict):
                    continue

                outcome = mkt.get("outcomePrices")
                if not outcome:
                    continue

                try:
                    prices = json.loads(outcome) if isinstance(outcome, str) else outcome
                    yes_price = float(prices[0]) if isinstance(prices, list) else 0
                except (json.JSONDecodeError, IndexError, TypeError):
                    continue

                if yes_price <= 0 or yes_price >= 1:
                    continue

                question = mkt.get("question", mkt.get("groupItemTitle", ""))
                volume = float(mkt.get("volume", 0) or 0)

                active.append({
                    "source": "polymarket",
                    "ticker": mkt.get("conditionId", mkt.get("id", "")),
                    "series": "PM_MENTIONS",
                    "event_ticker": event_id,
                    "event_title": event.get("title", ""),
                    "strike_word": question,
                    "yes_mid": yes_price,
                    "yes_bid": yes_price,
                    "yes_ask": yes_price,
                    "spread": 0,
                    "volume": volume,
                    "close_time": event.get("endDate", ""),
                    "category": "polymarket",
                    "fee_rt": PM_FEE,
                })

    return active


# ---------------------------------------------------------------------------
# Alpha computation
# ---------------------------------------------------------------------------

def _extract_company(series: str) -> str:
    """Extract company ticker from earnings series name."""
    return (series.replace("KXEARNINGSMENTION", "")
                  .replace("KXEARNIGSMENTION", "")
                  .replace("KXEARNIGNSMENTIO", "")
                  .upper())


def compute_signals(active: list[dict], hist_rates: dict,
                    libfrog_data: dict, model: dict | None = None) -> list[dict]:
    """Compute edge estimate for each active market.

    Uses grid filter (edge>=10c, br<=50%, n>=10) as primary signal.
    Model confidence is informational only.
    """
    signals = []

    for mkt in active:
        series = mkt["series"]
        yes_mid = mkt["yes_mid"]

        # Skip extreme prices (near-settled, no real tradable edge)
        if yes_mid > 0.95 or yes_mid < 0.05:
            continue

        # --- LibFrog lookup for earnings ---
        libfrog_br = None
        libfrog_n = 0
        libfrog_flag = None  # None = not earnings, "ok", "low_data", "no_data"

        is_earnings = "EARNINGS" in series.upper()
        if is_earnings and mkt["strike_word"]:
            company = _extract_company(series)
            lf_br, lf_n = libfrog_lookup(libfrog_data, company, mkt["strike_word"])
            if lf_br is not None:
                libfrog_br = lf_br
                libfrog_n = lf_n
                libfrog_flag = "ok" if lf_n >= 10 else "low_data"
            else:
                libfrog_flag = "no_data"

        # --- Series base rate ---
        hist = hist_rates.get(series) or _find_related_series(series, hist_rates)
        if hist:
            series_br = hist["base_rate"]
            series_n = hist["n_markets"]
        else:
            cat = mkt["category"]
            series_br = 0.53 if cat == "sports" else 0.42
            series_n = 0

        # Use LibFrog rate for earnings if available, else series rate
        if libfrog_br is not None and libfrog_flag == "ok":
            hist_br = libfrog_br
            hist_n = libfrog_n
        else:
            hist_br = series_br
            hist_n = series_n

        # Edge = YES mid-price - base rate
        edge = yes_mid - hist_br

        # --- Grid filter: does this market pass? ---
        grid_pass = (edge >= GRID_EDGE_THRESHOLD
                     and hist_br <= GRID_MAX_BR
                     and hist_n >= MIN_HISTORY)

        # Determine side
        if grid_pass:
            side = "NO"
        elif edge > 0:
            side = "NO"
        else:
            side = "YES"

        # Confidence based on sample size
        if hist_n >= 100:
            confidence = 0.95
        elif hist_n >= 50:
            confidence = 0.85
        elif hist_n >= 20:
            confidence = 0.70
        elif hist_n >= 10:
            confidence = 0.50
        else:
            confidence = 0.25

        # Net expected PnL (NO buyer perspective)
        fee = mkt["fee_rt"]
        effective_yes = max(0.01, yes_mid - DEFAULT_SLIPPAGE)
        no_cost = 1 - effective_yes

        p_no_wins = 1 - hist_br
        expected_pnl_gross = p_no_wins * effective_yes - hist_br * no_cost
        expected_pnl_net = expected_pnl_gross - fee

        # Quarter-Kelly sizing
        if expected_pnl_net > 0 and edge > 0:
            b = effective_yes / no_cost if no_cost > 0 else 0
            if b > 0:
                kelly_full = (p_no_wins * b - hist_br) / b
                kelly_quarter = max(0, kelly_full * KELLY_FRACTION)
            else:
                kelly_quarter = 0
        else:
            kelly_quarter = 0

        # --- Model confidence (informational) ---
        model_confidence = None
        if model and model.get("weights"):
            log_vol = math.log1p(mkt["volume"])
            lf_rate = libfrog_br if libfrog_br is not None else 0.5
            features = [
                series_br,       # series_base_rate
                series_br,       # word_base_rate (use series as proxy for live)
                yes_mid,         # opening_price
                log_vol / 15.0,  # log_volume_norm
                min(series_n / 100.0, 1.0),  # n_history_norm
                1.0,             # series_age_norm (assume mature)
                lf_rate,         # libfrog_rate
            ]
            model_confidence = model_predict_p_yes(model, features)

        # Score: grid-pass markets ranked by expected PnL, others by edge
        score = expected_pnl_net * confidence if grid_pass else edge * confidence * 0.1

        signals.append({
            "source": mkt["source"],
            "ticker": mkt["ticker"],
            "series": series,
            "event_title": mkt["event_title"],
            "strike_word": mkt["strike_word"],
            "side": side,
            "grid_pass": grid_pass,
            "yes_mid": yes_mid,
            "spread": mkt["spread"],
            "hist_base_rate": hist_br,
            "hist_n": hist_n,
            "edge": edge,
            "confidence": confidence,
            "expected_pnl_net": expected_pnl_net,
            "kelly_quarter": kelly_quarter,
            "model_confidence": model_confidence,
            "libfrog_flag": libfrog_flag,
            "libfrog_br": libfrog_br,
            "volume": mkt["volume"],
            "close_time": mkt["close_time"],
            "category": mkt["category"],
            "score": score,
        })

    # Grid-pass first, then by score descending
    signals.sort(key=lambda s: (s["grid_pass"], s["score"]), reverse=True)
    return signals


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_signal_table(signals: list[dict], max_rows: int = 30):
    """Print ranked signal table to stdout."""
    grid_pass = [s for s in signals if s.get("grid_pass")]
    non_grid = [s for s in signals if not s.get("grid_pass")]

    if grid_pass:
        print(f"\n  GRID FILTER SIGNALS ({len(grid_pass)} markets pass)")
        print(f"  edge>=10c, base_rate<=50%, n>={MIN_HISTORY}")
        hdr = (f"{'Rk':>3}  {'Src':>3}  {'Market':<35s}  {'Side':>4}  "
               f"{'YES$':>5}  {'BR':>5}  {'Edge':>6}  "
               f"{'E[PnL]':>7}  {'Kelly':>6}  {'MCf':>5}  {'LF':>4}  {'Vol':>9}")
        print()
        print(hdr)
        print("─" * len(hdr))

        for i, s in enumerate(grid_pass[:max_rows]):
            _print_signal_row(i, s)

    if non_grid:
        shown = max_rows - len(grid_pass[:max_rows])
        if shown > 0:
            print(f"\n  OTHER MARKETS ({len(non_grid)} below grid threshold)")
            hdr = (f"{'Rk':>3}  {'Src':>3}  {'Market':<35s}  {'Side':>4}  "
                   f"{'YES$':>5}  {'BR':>5}  {'Edge':>6}  "
                   f"{'E[PnL]':>7}  {'Kelly':>6}  {'MCf':>5}  {'LF':>4}  {'Vol':>9}")
            print()
            print(hdr)
            print("─" * len(hdr))
            for i, s in enumerate(non_grid[:shown]):
                _print_signal_row(i + len(grid_pass), s)

    # Summary
    print(f"\n  Total active: {len(signals)}  |  "
          f"Grid pass: {len(grid_pass)}  |  "
          f"Earnings: {sum(1 for s in signals if 'EARNINGS' in s['series'].upper())}")
    if grid_pass:
        avg_edge = np.mean([s["edge"] for s in grid_pass])
        avg_epnl = np.mean([s["expected_pnl_net"] for s in grid_pass])
        print(f"  Grid avg edge: {avg_edge:+.3f}  |  "
              f"Grid avg E[PnL]: {avg_epnl:+.3f}")


def _print_signal_row(i: int, s: dict):
    word = s["strike_word"][:32]
    src = "K" if s["source"] == "kalshi" else "PM"
    vol_str = f"${s['volume']:,.0f}" if s["volume"] >= 1000 else f"${s['volume']:.0f}"

    # Model confidence
    mc = f"{s['model_confidence']:.2f}" if s.get("model_confidence") is not None else "  - "

    # LibFrog flag
    lf = s.get("libfrog_flag", "")
    if lf == "ok":
        lf_str = " ok "
    elif lf == "low_data":
        lf_str = "low!"
    elif lf == "no_data":
        lf_str = " -- "
    else:
        lf_str = "    "

    print(
        f"{i+1:>3}  {src:>3}  {word:<35s}  {s['side']:>4}  "
        f"{s['yes_mid']:>4.0%}  {s['hist_base_rate']:>4.0%}  "
        f"{s['edge']:>+5.0%}  "
        f"{s['expected_pnl_net']:>+6.3f}  {s['kelly_quarter']:>5.1%}  "
        f"{mc:>5}  {lf_str:>4}  "
        f"{vol_str:>9}"
    )


def save_signals(signals: list[dict]):
    """Save signal files."""
    today = datetime.now().strftime("%Y-%m-%d")
    grid_pass = [s for s in signals if s.get("grid_pass")]

    # JSON
    json_path = SIGNALS_DIR / f"signals_{today}.json"
    with open(json_path, "w") as f:
        json.dump({
            "generated": datetime.now().isoformat(),
            "n_signals": len(signals),
            "n_grid_pass": len(grid_pass),
            "signal_method": "grid_filter",
            "grid_params": {
                "edge_threshold": GRID_EDGE_THRESHOLD,
                "max_br": GRID_MAX_BR,
                "min_history": MIN_HISTORY,
            },
            "signals": signals,
        }, f, indent=2, default=str)

    # Markdown
    md_path = SIGNALS_DIR / f"signals_{today}.md"
    lines = [
        f"# Live Mention Market Signals — {today}",
        f"\nGenerated {datetime.now().strftime('%H:%M')} · "
        f"{len(signals)} active · {len(grid_pass)} grid pass",
        "",
        "## Grid filter signals (edge>=10c, br<=50%)",
        "",
        "| # | Src | Market | Side | Price | BR | Edge | E[PnL] | MCf | LF | Vol |",
        "|---|-----|--------|------|-------|----|------|--------|-----|-----|-----|",
    ]
    for i, s in enumerate(grid_pass[:50]):
        src = "K" if s["source"] == "kalshi" else "PM"
        word = s["strike_word"][:30]
        mc = f"{s['model_confidence']:.2f}" if s.get("model_confidence") is not None else "-"
        lf = s.get("libfrog_flag") or "-"
        lines.append(
            f"| {i+1} | {src} | {word} | {s['side']} | "
            f"{s['yes_mid']:.2f} | {s['hist_base_rate']:.0%} | "
            f"{s['edge']:+.2f} | "
            f"{s['expected_pnl_net']:+.3f} | {mc} | {lf} | "
            f"${s['volume']:,.0f} |"
        )
    lines.append(f"\n*Grid filter: edge>={GRID_EDGE_THRESHOLD*100:.0f}c, "
                 f"BR<={GRID_MAX_BR:.0%}, n>={MIN_HISTORY} · "
                 f"Kalshi fee: ${KALSHI_FEE_RT}/RT · "
                 f"Slippage: {DEFAULT_SLIPPAGE*100:.0f}c*")

    with open(md_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\n  Saved: {json_path}")
    print(f"  Saved: {md_path}")


# ---------------------------------------------------------------------------
# Paper trading
# ---------------------------------------------------------------------------

def load_journal() -> dict:
    if JOURNAL_PATH.exists():
        with open(JOURNAL_PATH) as f:
            return json.load(f)
    return {"entries": [], "settled": [], "summary": {}}


def save_journal(journal: dict):
    with open(JOURNAL_PATH, "w") as f:
        json.dump(journal, f, indent=2, default=str)


def paper_trade(signals: list[dict]):
    """Record grid-pass signals and check for settled markets."""
    journal = load_journal()
    now = datetime.now().isoformat()

    # Only record grid-pass signals
    new_entries = []
    for s in signals:
        if not s.get("grid_pass"):
            continue
        entry = {
            "recorded_at": now,
            "source": s["source"],
            "ticker": s["ticker"],
            "series": s["series"],
            "strike_word": s["strike_word"],
            "side": s["side"],
            "yes_mid_at_signal": s["yes_mid"],
            "hist_base_rate": s["hist_base_rate"],
            "edge_at_signal": s["edge"],
            "expected_pnl": s["expected_pnl_net"],
            "kelly_quarter": s["kelly_quarter"],
            "model_confidence": s.get("model_confidence"),
            "libfrog_flag": s.get("libfrog_flag"),
            "libfrog_br": s.get("libfrog_br"),
            "volume": s["volume"],
            "close_time": s["close_time"],
            "settled": False,
            "result": None,
            "realized_pnl": None,
        }
        # Don't duplicate
        existing_tickers = {e["ticker"] for e in journal["entries"]
                           if not e.get("settled")}
        if s["ticker"] not in existing_tickers:
            new_entries.append(entry)

    journal["entries"].extend(new_entries)
    print(f"\n  Paper trade: {len(new_entries)} new signals recorded")

    # Check for settled markets
    settled_count = 0
    total_pnl = 0
    for entry in journal["entries"]:
        if entry.get("settled"):
            total_pnl += entry.get("realized_pnl", 0) or 0
            continue

        # Check if market has settled
        if entry["source"] == "kalshi":
            time.sleep(DELAY)
            data = kalshi_get(f"/markets/{entry['ticker']}")
            if data and data.get("market", {}).get("result"):
                mkt = data["market"]
                result = mkt["result"]
                entry["settled"] = True
                entry["result"] = result
                entry["settled_at"] = now

                # Compute realized PnL
                yes_mid = entry["yes_mid_at_signal"]
                effective_yes = max(0.01, yes_mid - DEFAULT_SLIPPAGE)
                no_cost = 1 - effective_yes

                if entry["side"] == "NO":
                    if result == "no":
                        entry["realized_pnl"] = effective_yes - KALSHI_FEE_RT
                    else:
                        entry["realized_pnl"] = -no_cost - KALSHI_FEE_RT
                else:
                    if result == "yes":
                        no_price = 1 - effective_yes
                        entry["realized_pnl"] = no_price - KALSHI_FEE_RT
                    else:
                        entry["realized_pnl"] = -effective_yes - KALSHI_FEE_RT

                total_pnl += entry["realized_pnl"]
                settled_count += 1

    # Update summary
    all_settled = [e for e in journal["entries"] if e.get("settled")]
    journal["summary"] = {
        "total_signals": len(journal["entries"]),
        "settled": len(all_settled),
        "pending": len(journal["entries"]) - len(all_settled),
        "total_realized_pnl": total_pnl,
        "wins": sum(1 for e in all_settled if (e.get("realized_pnl") or 0) > 0),
        "losses": sum(1 for e in all_settled if (e.get("realized_pnl") or 0) <= 0),
        "last_updated": now,
    }

    save_journal(journal)

    # Print summary
    s = journal["summary"]
    print(f"  Total signals: {s['total_signals']} "
          f"(settled: {s['settled']}, pending: {s['pending']})")
    if s["settled"] > 0:
        wr = s["wins"] / s["settled"] if s["settled"] > 0 else 0
        print(f"  Realized PnL: ${s['total_realized_pnl']:+.2f}")
        print(f"  Win rate: {wr:.0%} ({s['wins']}W / {s['losses']}L)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_backtest_model():
    """Run walk-forward backtest inline (--backtest-model flag)."""
    print("\n" + "=" * 65)
    print("  RUNNING WALK-FORWARD MODEL BACKTEST")
    print("=" * 65)

    # Import and run signal_model
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "signal_model", Path(__file__).parent / "signal_model.py")
    sm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sm)

    markets = sm.load_markets()
    libfrog = sm.load_libfrog()
    competitive = [m for m in markets if 0.05 < m["mid"] <= 0.95]
    print(f"\n  {len(markets):,} total markets, "
          f"{len(competitive):,} competitive range")

    model_results, w, b = sm.walk_forward_backtest(markets, libfrog)
    model_stats = sm.analyze_results(model_results, "model")

    grid_results = sm.grid_filter_backtest(markets)
    grid_stats = sm.analyze_results(grid_results, "grid")

    print(f"\n  Model: Sharpe={model_stats.get('sharpe', 0):.3f}  "
          f"mu=${model_stats.get('mean_pnl', 0):+.4f}  "
          f"n={model_stats.get('n', 0)}  "
          f"WR={model_stats.get('win_rate', 0):.0%}")
    print(f"  Grid:  Sharpe={grid_stats.get('sharpe', 0):.3f}  "
          f"mu=${grid_stats.get('mean_pnl', 0):+.4f}  "
          f"n={grid_stats.get('n', 0)}  "
          f"WR={grid_stats.get('win_rate', 0):.0%}")

    winner = "MODEL" if model_stats.get("sharpe", 0) > grid_stats.get("sharpe", 0) else "GRID"
    print(f"\n  Winner: {winner}")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Live mention market signals")
    parser.add_argument("--paper-trade", action="store_true",
                        help="Record signals and track PnL")
    parser.add_argument("--earnings-only", action="store_true",
                        help="Only show earnings-call markets")
    parser.add_argument("--kalshi-only", action="store_true",
                        help="Only Kalshi markets")
    parser.add_argument("--polymarket-only", action="store_true",
                        help="Only Polymarket markets")
    parser.add_argument("--min-edge", type=float, default=0.0,
                        help="Minimum edge to display")
    parser.add_argument("--top", type=int, default=30,
                        help="Number of signals to show")
    parser.add_argument("--backtest-model", action="store_true",
                        help="Run walk-forward model backtest and compare")
    args = parser.parse_args()

    if args.backtest_model:
        run_backtest_model()
        return

    print("=" * 75)
    print("  LIVE MENTION MARKET SIGNALS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  "
          f"Signal: grid filter (edge>={GRID_EDGE_THRESHOLD*100:.0f}c, "
          f"BR<={GRID_MAX_BR:.0%})")
    print("=" * 75)

    # Load data
    print("\nLoading historical base rates...")
    hist_rates = load_historical_base_rates()
    series_count = len([k for k in hist_rates if not k.startswith("__")])
    print(f"  {series_count} series with historical data")

    print("Loading LibFrog transcript data...")
    libfrog_data = load_libfrog()
    n_matched = len(libfrog_data.get("matched", {}))
    n_generic = sum(len(v) for v in libfrog_data.get("generic", {}).values())
    print(f"  {n_matched} matched + {n_generic} generic word rates")

    model = load_model_weights()
    if model:
        print(f"  Model weights loaded ({len(model.get('weights', []))} features)")

    # Fetch active markets
    active = []

    if not args.polymarket_only:
        print("\nFetching active Kalshi markets...")
        kalshi_active = fetch_active_kalshi_mentions()
        active.extend(kalshi_active)
        print(f"  {len(kalshi_active)} active Kalshi markets")

    if not args.kalshi_only:
        print("\nFetching active Polymarket markets...")
        pm_active = fetch_active_polymarket_mentions()
        active.extend(pm_active)
        print(f"  {len(pm_active)} active Polymarket markets")

    if not active:
        print("\n  No active markets found.")
        return

    # Filter
    if args.earnings_only:
        active = [m for m in active if m["category"] == "earnings"]
        print(f"\n  Filtered to {len(active)} earnings markets")

    # Compute signals
    print("\nComputing signals (grid filter + model confidence)...")
    signals = compute_signals(active, hist_rates, libfrog_data, model)

    # Apply edge filter
    if args.min_edge > 0:
        signals = [s for s in signals if s["edge"] >= args.min_edge]

    # Output
    print_signal_table(signals, max_rows=args.top)
    save_signals(signals)

    if args.paper_trade:
        paper_trade(signals)


if __name__ == "__main__":
    main()

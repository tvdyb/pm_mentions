#!/usr/bin/env python3
"""Paper trading system for the grid filter mention market strategy.

Pulls active markets, filters through grid filter (edge>=10c, br<=50%,
n>=10 history), manages positions, checks settlements, and tracks PnL.

Usage:
    python scripts/paper_trader.py                    # full run
    python scripts/paper_trader.py --signals-only     # show signals, don't record
    python scripts/paper_trader.py --status           # portfolio status
    python scripts/paper_trader.py --export-csv       # export closed trades
    python scripts/paper_trader.py --reset            # reset journal
    python scripts/paper_trader.py --dry-run          # show what would happen
"""

import argparse
import csv
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

import requests
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
PM_GAMMA = "https://gamma-api.polymarket.com"

DELAY = 0.3  # seconds between API calls

PAPER_DIR = Path("output/paper_trading")
PAPER_DIR.mkdir(parents=True, exist_ok=True)
JOURNAL_PATH = PAPER_DIR / "journal.json"
DAILY_LOG_PATH = PAPER_DIR / "daily_log.md"

HIST_DATA_PATH = Path("data/real_markets/kalshi_all_series.json")
HIST_COMBINED_PATH = Path("data/real_markets/real_data_combined.json")
LIBFROG_MATCHED_PATH = Path("data/base_rates/libfrog_kalshi_matched.json")

# Series classification
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

DEFAULT_CONFIG = {
    "initial_capital": 1000.0,
    "max_position_pct": 0.05,
    "kelly_fraction": 0.25,
    "kalshi_fee_rt": 0.02,
    "pm_fee_rt": 0.0,
    "slippage": 0.01,
    "grid_edge_min": 0.10,
    "grid_br_max": 0.50,
    "min_history": 10,
}


def log(msg):
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Journal management (atomic writes)
# ---------------------------------------------------------------------------
def load_journal() -> dict:
    if JOURNAL_PATH.exists():
        with open(JOURNAL_PATH) as f:
            return json.load(f)
    return {
        "config": DEFAULT_CONFIG,
        "capital": DEFAULT_CONFIG["initial_capital"],
        "positions": [],
        "closed_trades": [],
        "daily_pnl": [],
        "stats": {},
    }


def save_journal(journal: dict):
    """Atomic write: write to temp file then rename."""
    fd, tmp = tempfile.mkstemp(dir=PAPER_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(journal, f, indent=2, default=str)
        os.replace(tmp, JOURNAL_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# API helpers with retry
# ---------------------------------------------------------------------------
def _get(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30,
                                headers={"Accept": "application/json"})
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 5))
                log(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                log(f"  API error after {retries} attempts: {e}")
                return None
    return None


def kalshi_get(path, params=None):
    time.sleep(DELAY)
    return _get(f"{KALSHI_BASE}{path}", params)


def pm_get(path, params=None):
    time.sleep(DELAY)
    return _get(f"{PM_GAMMA}{path}", params)


# ---------------------------------------------------------------------------
# Historical base rates (expanding window, no lookahead)
# ---------------------------------------------------------------------------
def load_base_rates() -> dict:
    """Load historical settled markets and compute per-series stats.

    Returns: {series: {base_rate, avg_mid, n_markets, outcomes, mids}}
    """
    markets_by_series = defaultdict(lambda: {"outcomes": [], "mids": []})

    if HIST_DATA_PATH.exists():
        with open(HIST_DATA_PATH) as f:
            data = json.load(f)
        for m in data.get("markets", []):
            op = m.get("opening_price")
            result = m.get("result")
            if op is None or op <= 0 or op >= 1 or result not in ("yes", "no"):
                continue
            s = m.get("series", "")
            markets_by_series[s]["outcomes"].append(1 if result == "yes" else 0)
            markets_by_series[s]["mids"].append(op)

    if HIST_COMBINED_PATH.exists():
        with open(HIST_COMBINED_PATH) as f:
            data = json.load(f)
        seen_tickers = set()
        if HIST_DATA_PATH.exists():
            with open(HIST_DATA_PATH) as f:
                for m in json.load(f).get("markets", []):
                    seen_tickers.add(m.get("ticker", ""))
        for m in data.get("kalshi", []):
            t = m.get("ticker", m.get("market_ticker", ""))
            if t in seen_tickers:
                continue
            seen_tickers.add(t)
            op = m.get("opening_price")
            result = m.get("result")
            if op is None or op <= 0 or op >= 1 or result not in ("yes", "no"):
                continue
            s = m.get("series", "")
            markets_by_series[s]["outcomes"].append(1 if result == "yes" else 0)
            markets_by_series[s]["mids"].append(op)

    rates = {}
    for series, data in markets_by_series.items():
        n = len(data["outcomes"])
        if n == 0:
            continue
        br = np.mean(data["outcomes"])
        avg_mid = np.mean(data["mids"])
        rates[series] = {
            "base_rate": float(br),
            "avg_mid": float(avg_mid),
            "n_markets": n,
            "edge": float(avg_mid - br),
        }

    return rates


def load_libfrog() -> dict:
    """Load LibFrog matched data for earnings markets."""
    if not LIBFROG_MATCHED_PATH.exists():
        return {}
    with open(LIBFROG_MATCHED_PATH) as f:
        raw = json.load(f)
    matched = {}
    for key, val in raw.get("matches", {}).items():
        if val.get("base_rate") is not None:
            matched[key] = val
    return matched


# ---------------------------------------------------------------------------
# Classify series
# ---------------------------------------------------------------------------
def classify_series(series):
    s = series.upper()
    if "EARNINGS" in s:
        return "earnings"
    if s in SPORTS_SERIES:
        return "sports"
    if s in MEDIA_SERIES:
        return "media"
    political = ["TRUMP", "BIDEN", "VANCE", "STARMER", "REEVES", "POWELL",
                 "SCHUMER", "CUOMO", "PERSON", "POLITICS", "FED", "AMODEI",
                 "CULTURE", "KARP"]
    for kw in political:
        if kw in s:
            return "political"
    return "other"


# ---------------------------------------------------------------------------
# Fetch active markets
# ---------------------------------------------------------------------------
def fetch_active_kalshi(rates) -> list[dict]:
    """Fetch active mention markets from Kalshi."""
    # Get all mention series
    data = kalshi_get("/series", {"limit": 1000})
    if not data:
        return []

    mention_series = [s["ticker"] for s in data.get("series", [])
                      if "MENTION" in s.get("ticker", "").upper()]
    log(f"  {len(mention_series)} mention series on Kalshi")

    active = []
    for series in mention_series:
        time.sleep(DELAY)
        ev_data = kalshi_get("/events", {
            "series_ticker": series, "status": "open", "limit": 50
        })
        if not ev_data or not ev_data.get("events"):
            mkt_data = kalshi_get("/markets", {
                "status": "open", "limit": 100, "series_ticker": series
            })
            if mkt_data and mkt_data.get("markets"):
                for m in mkt_data["markets"]:
                    if m.get("status") in ("open", "active"):
                        parsed = _parse_kalshi(m, series, rates)
                        if parsed:
                            active.append(parsed)
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
                    parsed = _parse_kalshi(m, series, rates, event)
                    if parsed:
                        active.append(parsed)

    return active


def _parse_kalshi(m, series, rates, event=None) -> dict | None:
    yes_bid = m.get("yes_bid", 0) / 100.0
    yes_ask = m.get("yes_ask", 0) / 100.0
    last = m.get("last_price", 0) / 100.0

    if yes_bid > 0 and yes_ask > 0 and yes_ask < 1:
        mid = (yes_bid + yes_ask) / 2
    elif last > 0:
        mid = last
    else:
        return None

    # Skip extreme prices
    if mid <= 0.05 or mid > 0.95:
        return None

    strike = (m.get("custom_strike", {}).get("Word", "") or
              m.get("no_sub_title", "") or
              m.get("subtitle", ""))

    return {
        "source": "kalshi",
        "ticker": m.get("ticker", ""),
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
        "category": classify_series(series),
    }


def fetch_active_polymarket(rates) -> list[dict]:
    """Fetch active mention markets from Polymarket."""
    active = []
    seen = set()

    data = pm_get("/events", {"closed": "false", "limit": 100})
    if not data or not isinstance(data, list):
        return []

    for event in data:
        if not isinstance(event, dict):
            continue
        event_id = event.get("id", "")
        if event_id in seen:
            continue
        seen.add(event_id)

        title = (event.get("title", "") or "").lower()
        if not any(kw in title for kw in [
            "mention", "say", "name", "word", "what will", "who will"
        ]):
            continue

        for mkt in event.get("markets", []):
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
            if yes_price <= 0.05 or yes_price > 0.95:
                continue

            active.append({
                "source": "polymarket",
                "ticker": mkt.get("conditionId", mkt.get("id", "")),
                "series": "PM_MENTIONS",
                "event_ticker": event_id,
                "event_title": event.get("title", ""),
                "strike_word": mkt.get("question", mkt.get("groupItemTitle", "")),
                "yes_mid": yes_price,
                "yes_bid": yes_price,
                "yes_ask": yes_price,
                "spread": 0,
                "volume": float(mkt.get("volume", 0) or 0),
                "close_time": event.get("endDate", ""),
                "category": "polymarket",
            })

    return active


# ---------------------------------------------------------------------------
# Grid filter signal generation
# ---------------------------------------------------------------------------
def _find_related_series(series, rates):
    """Try to find a related series in historical data."""
    if series in rates:
        return rates[series]
    # Strip trailing letter (KXSTARMERMENTIONB → KXSTARMERMENTION)
    if series[-1:].isalpha() and series[-1] != "N":
        base = series[:-1]
        if base in rates:
            return rates[base]
    equivalences = {
        "KXFEDMENTION": "KXPOWELLMENTION",
        "KXJPOWMENTION": "KXPOWELLMENTION",
        "KXTRUMPMENTIONB": "KXTRUMPMENTION",
        "KXSTARMERMENTIONB": "KXSTARMERMENTION",
        "KXTRUMPMENTIONDURATION": "KXTRUMPMENTION",
    }
    if series in equivalences and equivalences[series] in rates:
        return rates[equivalences[series]]
    return None


def compute_signals(active_markets, rates, config) -> list[dict]:
    """Apply grid filter to active markets. Returns qualifying signals.

    Uses per-market edge: (yes_price - series_base_rate) >= 10c.
    This matches live_signals.py behavior.
    """
    signals = []

    for mkt in active_markets:
        series = mkt["series"]
        info = rates.get(series) or _find_related_series(series, rates)
        if not info:
            continue

        if info["n_markets"] < config["min_history"]:
            continue

        br = info["base_rate"]
        yes_mid = mkt["yes_mid"]
        market_edge = yes_mid - br  # per-market overpricing

        if market_edge < config["grid_edge_min"] or br > config["grid_br_max"]:
            continue

        fee = config["kalshi_fee_rt"] if mkt["source"] == "kalshi" else config["pm_fee_rt"]
        slippage = config["slippage"]
        eff_yes = max(0.01, yes_mid - slippage)
        no_cost = 1.0 - eff_yes

        # Expected PnL
        p_no = 1 - br
        epnl = p_no * eff_yes - br * no_cost - fee

        # Quarter-Kelly sizing
        if epnl > 0:
            b = eff_yes / no_cost if no_cost > 0 else 0
            kelly_full = (p_no * b - br) / b if b > 0 else 0
            kelly_q = max(0, kelly_full * config["kelly_fraction"])
        else:
            kelly_q = 0

        signals.append({
            "source": mkt["source"],
            "ticker": mkt["ticker"],
            "series": series,
            "event_ticker": mkt["event_ticker"],
            "event_title": mkt["event_title"],
            "strike_word": mkt["strike_word"],
            "category": mkt["category"],
            "side": "NO",
            "yes_mid": yes_mid,
            "yes_bid": mkt["yes_bid"],
            "yes_ask": mkt["yes_ask"],
            "spread": mkt["spread"],
            "base_rate": br,
            "series_edge": info["edge"],
            "market_edge": market_edge,
            "expected_pnl": epnl,
            "kelly_quarter": kelly_q,
            "volume": mkt["volume"],
            "close_time": mkt["close_time"],
            "n_history": info["n_markets"],
        })

    signals.sort(key=lambda s: s["expected_pnl"], reverse=True)
    return signals


# ---------------------------------------------------------------------------
# Position management
# ---------------------------------------------------------------------------
def open_positions(journal, signals, dry_run=False):
    """Open new positions from signals. Returns count of new positions."""
    config = journal["config"]
    existing_tickers = {p["ticker"] for p in journal["positions"]}
    new_count = 0
    now = datetime.now(timezone.utc).isoformat()

    for sig in signals:
        if sig["ticker"] in existing_tickers:
            continue

        # Sizing: min of quarter-Kelly and max_position_pct
        max_size = journal["capital"] * config["max_position_pct"]
        kelly_size = journal["capital"] * sig["kelly_quarter"]
        position_size = min(kelly_size, max_size)

        if position_size < 1.0:
            continue

        # Number of contracts
        eff_yes = max(0.01, sig["yes_mid"] - config["slippage"])
        no_cost = 1.0 - eff_yes
        n_contracts = int(position_size / no_cost)
        if n_contracts < 1:
            continue

        position = {
            "ticker": sig["ticker"],
            "series": sig["series"],
            "event_ticker": sig["event_ticker"],
            "event_title": sig["event_title"],
            "strike_word": sig["strike_word"],
            "source": sig["source"],
            "side": "NO",
            "entry_price": sig["yes_mid"],
            "entry_time": now,
            "base_rate": sig["base_rate"],
            "series_edge": sig["series_edge"],
            "market_edge": sig["market_edge"],
            "expected_pnl": sig["expected_pnl"],
            "kelly_size": position_size,
            "n_contracts": n_contracts,
            "close_time": sig["close_time"],
            "category": sig["category"],
        }

        if not dry_run:
            journal["positions"].append(position)
            existing_tickers.add(sig["ticker"])
        new_count += 1

    return new_count


def check_settlements(journal, dry_run=False):
    """Check open positions for settlement. Returns list of settled trades."""
    settled = []
    config = journal["config"]
    now = datetime.now(timezone.utc).isoformat()
    remaining = []

    for pos in journal["positions"]:
        result = None

        if pos["source"] == "kalshi":
            data = kalshi_get(f"/markets/{pos['ticker']}")
            if data and isinstance(data, dict):
                mkt = data.get("market", data)
                result = mkt.get("result")
        elif pos["source"] == "polymarket":
            # Check if market is resolved
            data = pm_get(f"/markets/{pos['ticker']}")
            if data and isinstance(data, dict):
                if data.get("resolved"):
                    outcome = data.get("outcomePrices")
                    if outcome:
                        try:
                            prices = json.loads(outcome) if isinstance(outcome, str) else outcome
                            if isinstance(prices, list) and len(prices) >= 2:
                                if float(prices[0]) > 0.99:
                                    result = "yes"
                                elif float(prices[1]) > 0.99:
                                    result = "no"
                        except (json.JSONDecodeError, TypeError, ValueError):
                            pass

        if result in ("yes", "no"):
            slippage = config["slippage"]
            eff_yes = max(0.01, pos["entry_price"] - slippage)
            no_cost = 1.0 - eff_yes
            fee = config["kalshi_fee_rt"] if pos["source"] == "kalshi" else config["pm_fee_rt"]

            if pos["side"] == "NO":
                if result == "no":
                    pnl_per = eff_yes - fee
                else:
                    pnl_per = -no_cost - fee
            else:
                if result == "yes":
                    pnl_per = (1.0 - eff_yes) - fee
                else:
                    pnl_per = -eff_yes - fee

            total_pnl = pnl_per * pos["n_contracts"]

            trade = {
                **pos,
                "result": result,
                "pnl_per_contract": pnl_per,
                "total_pnl": total_pnl,
                "settled_at": now,
                "win": pnl_per > 0,
            }
            settled.append(trade)

            if not dry_run:
                journal["closed_trades"].append(trade)
                journal["capital"] += total_pnl
        else:
            remaining.append(pos)

    if not dry_run:
        journal["positions"] = remaining

    return settled


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_signals_table(signals, max_rows=30):
    """Print current signals to stdout."""
    if not signals:
        print("\n  No grid filter signals found.")
        return

    print(f"\n  GRID FILTER SIGNALS ({len(signals)} found)")
    print(f"  edge>=10c, BR<=50%, n>=10 history")
    hdr = (f"{'#':>3}  {'Src':>3}  {'Market':<32s}  {'YES$':>5}  "
           f"{'BR':>5}  {'Edge':>6}  {'E[PnL]':>7}  {'Kelly':>6}  {'Vol':>9}")
    print()
    print(hdr)
    print("─" * len(hdr))

    for i, s in enumerate(signals[:max_rows]):
        word = s["strike_word"][:29]
        src = "K" if s["source"] == "kalshi" else "PM"
        vol = f"${s['volume']:,.0f}" if s["volume"] >= 1000 else f"${s['volume']:.0f}"
        print(
            f"{i+1:>3}  {src:>3}  {word:<32s}  {s['yes_mid']:>4.0%}  "
            f"{s['base_rate']:>4.0%}  {s['series_edge']:>+5.0%}  "
            f"{s['expected_pnl']:>+6.3f}  {s['kelly_quarter']:>5.1%}  "
            f"{vol:>9}"
        )


def print_status(journal):
    """Print portfolio status."""
    config = journal["config"]
    positions = journal["positions"]
    closed = journal["closed_trades"]

    print(f"\n{'='*60}")
    print(f"  PAPER TRADING STATUS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    print(f"\n  Capital: ${journal['capital']:,.2f} "
          f"(initial: ${config['initial_capital']:,.2f})")

    # Open positions
    total_exposure = sum(
        p["n_contracts"] * (1.0 - max(0.01, p["entry_price"] - config["slippage"]))
        for p in positions
    )
    print(f"  Open positions: {len(positions)} (exposure: ${total_exposure:,.2f})")
    if positions:
        print()
        print(f"  {'Ticker':<30s}  {'Side':>4}  {'Entry':>5}  {'BR':>5}  "
              f"{'Edge':>6}  {'Ctrs':>5}  {'Close':>12}")
        print(f"  {'─'*85}")
        for p in positions:
            close = p.get("close_time", "")[:10]
            print(f"  {p['ticker'][:28]:<30s}  {p['side']:>4}  "
                  f"{p['entry_price']:>4.0%}  {p['base_rate']:>4.0%}  "
                  f"{p['series_edge']:>+5.0%}  {p['n_contracts']:>5}  {close:>12}")

    # Closed trades summary
    if closed:
        pnls = [t["pnl_per_contract"] for t in closed]
        wins = sum(1 for t in closed if t.get("win"))
        total_pnl = sum(t["total_pnl"] for t in closed)
        wr = wins / len(closed) if closed else 0
        mu = np.mean(pnls)
        std = np.std(pnls, ddof=1) if len(pnls) > 1 else 0
        sharpe = mu / std if std > 0 else 0

        print(f"\n  Closed trades: {len(closed)}")
        print(f"  Win rate: {wr:.0%} ({wins}W / {len(closed) - wins}L)")
        print(f"  Total PnL: ${total_pnl:+,.2f}")
        print(f"  Mean PnL/contract: ${mu:+.4f}")
        print(f"  Sharpe estimate: {sharpe:.3f}")
    else:
        print(f"\n  No closed trades yet.")

    print(f"\n{'='*60}")


def print_settled(settled):
    """Print settled trades from this run."""
    if not settled:
        return
    print(f"\n  SETTLED THIS RUN ({len(settled)} trades)")
    for t in settled:
        win = "WIN" if t.get("win") else "LOSS"
        print(f"  {win}  {t['ticker'][:30]:<32s}  "
              f"result={t['result']}  PnL=${t['total_pnl']:+.2f}  "
              f"({t['n_contracts']} contracts)")


def append_daily_log(journal, new_signals, settled):
    """Append today's summary to daily_log.md."""
    now = datetime.now()
    closed = journal["closed_trades"]

    lines = [
        f"\n## {now.strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"- Capital: ${journal['capital']:,.2f}",
        f"- Open positions: {len(journal['positions'])}",
        f"- New signals: {new_signals}",
        f"- Settled this run: {len(settled)}",
    ]
    if settled:
        run_pnl = sum(t["total_pnl"] for t in settled)
        lines.append(f"- Settlement PnL: ${run_pnl:+.2f}")
    if closed:
        total_pnl = sum(t["total_pnl"] for t in closed)
        wins = sum(1 for t in closed if t.get("win"))
        lines.append(f"- Cumulative: {len(closed)} trades, "
                      f"${total_pnl:+.2f} PnL, "
                      f"{wins}/{len(closed)} wins")
    lines.append("")

    with open(DAILY_LOG_PATH, "a") as f:
        f.write("\n".join(lines))


def export_csv(journal):
    """Export closed trades to CSV."""
    closed = journal["closed_trades"]
    if not closed:
        print("No closed trades to export.")
        return

    csv_path = PAPER_DIR / "closed_trades.csv"
    fields = [
        "ticker", "series", "source", "side", "entry_price", "entry_time",
        "base_rate", "series_edge", "market_edge", "n_contracts",
        "result", "pnl_per_contract", "total_pnl", "win", "settled_at",
        "strike_word", "category",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for t in closed:
            writer.writerow(t)
    print(f"Exported {len(closed)} trades to {csv_path}")


def reset_journal():
    """Reset journal with confirmation."""
    if JOURNAL_PATH.exists():
        confirm = input("Reset paper trading journal? This deletes all history. (y/N): ")
        if confirm.lower() != "y":
            print("Aborted.")
            return
    journal = {
        "config": DEFAULT_CONFIG,
        "capital": DEFAULT_CONFIG["initial_capital"],
        "positions": [],
        "closed_trades": [],
        "daily_pnl": [],
        "stats": {},
    }
    save_journal(journal)
    print("Journal reset.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Paper trading system for grid filter mention market strategy")
    parser.add_argument("--signals-only", action="store_true",
                        help="Show current signals without recording")
    parser.add_argument("--status", action="store_true",
                        help="Show portfolio status")
    parser.add_argument("--export-csv", action="store_true",
                        help="Export closed trades to CSV")
    parser.add_argument("--reset", action="store_true",
                        help="Reset journal")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without writing")
    parser.add_argument("--kalshi-only", action="store_true",
                        help="Only Kalshi markets")
    parser.add_argument("--polymarket-only", action="store_true",
                        help="Only Polymarket markets")
    args = parser.parse_args()

    if args.reset:
        reset_journal()
        return

    journal = load_journal()

    if args.status:
        print_status(journal)
        return

    if args.export_csv:
        export_csv(journal)
        return

    # --- Full run ---
    log(f"{'='*60}")
    log(f"  PAPER TRADER — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log(f"{'='*60}")

    # Load base rates
    log("\nLoading base rates...")
    rates = load_base_rates()
    qualifying = {s: r for s, r in rates.items()
                  if r["n_markets"] >= journal["config"]["min_history"]
                  and r["base_rate"] <= journal["config"]["grid_br_max"]
                  and r["edge"] >= journal["config"]["grid_edge_min"]}
    log(f"  {len(rates)} series loaded, {len(qualifying)} qualifying")

    # Check settlements first (unless signals-only)
    settled = []
    if not args.signals_only and journal["positions"]:
        log(f"\nChecking {len(journal['positions'])} open positions...")
        settled = check_settlements(journal, dry_run=args.dry_run)
        if settled:
            log(f"  {len(settled)} settled!")
            print_settled(settled)
        else:
            log("  None settled yet.")

    # Fetch active markets
    active = []
    if not args.polymarket_only:
        log("\nFetching active Kalshi markets...")
        kalshi = fetch_active_kalshi(rates)
        active.extend(kalshi)
        log(f"  {len(kalshi)} active Kalshi markets")

    if not args.kalshi_only:
        log("\nFetching active Polymarket markets...")
        pm = fetch_active_polymarket(rates)
        active.extend(pm)
        log(f"  {len(pm)} active Polymarket markets")

    if not active:
        log("\n  No active markets found.")
        if not args.signals_only and not args.dry_run:
            save_journal(journal)
        return

    # Compute signals
    log("\nApplying grid filter...")
    signals = compute_signals(active, rates, journal["config"])
    log(f"  {len(signals)} signals pass filter")

    # Print signals
    print_signals_table(signals)

    if args.signals_only:
        return

    # Open new positions
    new_count = open_positions(journal, signals, dry_run=args.dry_run)
    if new_count:
        log(f"\n  {'Would open' if args.dry_run else 'Opened'} "
            f"{new_count} new positions")

    # Print status
    print_status(journal)

    # Save
    if not args.dry_run:
        save_journal(journal)
        append_daily_log(journal, new_count, settled)
        log(f"\n  Journal saved to {JOURNAL_PATH}")
    else:
        log("\n  [DRY RUN] No changes written.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fetch ALL settled Kalshi mention markets with opening prices.

Iterates all 270 mention series, fetches settled events and markets,
then retrieves first-trade prices as opening price estimates.

Output: data/real_markets/kalshi_all_series.json
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
HEADERS = {"Accept": "application/json"}
OUT_PATH = Path("data/real_markets/kalshi_all_series.json")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

DELAY = 0.25  # seconds between requests (be polite)


def api_get(path: str, params: dict | None = None, retries: int = 3) -> dict | None:
    url = f"{BASE}{path}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 5))
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"    FAIL {path}: {e}")
                return None
    return None


def fetch_all_mention_series() -> list[str]:
    """Get all series tickers containing MENTION."""
    tickers = []
    cursor = ""
    while True:
        params = {"limit": 1000}
        if cursor:
            params["cursor"] = cursor
        data = api_get("/series", params)
        if not data:
            break
        for s in data.get("series", []):
            if "MENTION" in s.get("ticker", "").upper():
                tickers.append(s["ticker"])
        cursor = data.get("cursor", "")
        if not cursor or not data.get("series"):
            break
    return tickers


def fetch_settled_events(series_ticker: str) -> list[dict]:
    """Get all settled events for a series."""
    events = []
    cursor = ""
    while True:
        params = {"series_ticker": series_ticker, "status": "settled", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        data = api_get("/events", params)
        if not data:
            break
        batch = data.get("events", [])
        events.extend(batch)
        cursor = data.get("cursor", "")
        if not cursor or not batch:
            break
        time.sleep(DELAY)
    return events


def fetch_markets_for_event(event_ticker: str) -> list[dict]:
    """Get all markets for an event."""
    markets = []
    cursor = ""
    while True:
        params = {"event_ticker": event_ticker, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        data = api_get("/markets", params)
        if not data:
            break
        batch = data.get("markets", [])
        markets.extend(batch)
        cursor = data.get("cursor", "")
        if not cursor or not batch:
            break
        time.sleep(DELAY)
    return markets


def fetch_opening_price(ticker: str, open_time: str) -> float | None:
    """Get opening price from first trades."""
    try:
        # Parse open_time to unix timestamp
        dt = datetime.fromisoformat(open_time.replace("Z", "+00:00"))
        min_ts = int(dt.timestamp())
    except (ValueError, TypeError):
        min_ts = 0

    params = {"ticker": ticker, "limit": 10, "min_ts": min_ts}
    data = api_get("/markets/trades", params)
    if not data:
        return None

    trades = data.get("trades", [])
    if not trades:
        return None

    # Sort by time, take earliest trade price
    trades.sort(key=lambda t: t.get("created_time", ""))
    first_price = trades[0].get("yes_price", 0)
    # Kalshi prices in cents → dollars
    return first_price / 100.0


def categorize_series(ticker: str) -> str:
    t = ticker.upper()
    if "EARNINGS" in t:
        return "earnings"
    if any(x in t for x in ["NFL", "TNF", "MNF", "SNF", "MVE", "UFC"]):
        return "sports"
    if any(x in t for x in ["TRUMP", "VANCE", "STARMER", "POWELL", "JPOW",
                              "RUBIO", "HOMAN", "WALZ", "AOC", "MADDOW",
                              "ACKMAN", "ZUCK", "ELON", "LEBRON", "ROGAN",
                              "SECPRESS", "FED"]):
        return "political_person"
    return "other"


def main():
    print("=" * 60)
    print("  Fetching ALL Kalshi mention markets")
    print("=" * 60)

    # Load existing data to avoid re-fetching
    existing = {}
    if OUT_PATH.exists():
        with open(OUT_PATH) as f:
            old = json.load(f)
        for m in old.get("markets", []):
            existing[m.get("ticker", "")] = m
        print(f"  Loaded {len(existing)} existing markets")

    # Step 1: Get all mention series
    print("\n[1/3] Fetching mention series...")
    series_tickers = fetch_all_mention_series()
    print(f"  Found {len(series_tickers)} mention series")

    # Step 2: For each series, get settled events and markets
    print("\n[2/3] Fetching settled events and markets...")
    all_markets = []
    series_stats = Counter()

    for i, series in enumerate(series_tickers):
        category = categorize_series(series)
        sys.stdout.write(f"\r  [{i+1}/{len(series_tickers)}] {series:45s}")
        sys.stdout.flush()

        events = fetch_settled_events(series)
        if not events:
            continue

        for event in events:
            evt_ticker = event["event_ticker"]
            time.sleep(DELAY)
            markets = fetch_markets_for_event(evt_ticker)

            for mkt in markets:
                ticker = mkt.get("ticker", "")
                result = mkt.get("result", "")
                volume = mkt.get("volume", 0)
                status = mkt.get("status", "")

                if status not in ("finalized", "settled"):
                    continue
                if not result or result not in ("yes", "no"):
                    continue

                # Check if we already have this with opening price
                if ticker in existing and existing[ticker].get("opening_price"):
                    all_markets.append(existing[ticker])
                    series_stats[series] += 1
                    continue

                # Get opening price from first trade
                open_time = mkt.get("open_time", "")
                time.sleep(DELAY)
                opening = fetch_opening_price(ticker, open_time)

                strike = (mkt.get("custom_strike", {}).get("Word", "") or
                          mkt.get("no_sub_title", "") or
                          mkt.get("subtitle", ""))

                record = {
                    "ticker": ticker,
                    "event_ticker": evt_ticker,
                    "series": series,
                    "category": category,
                    "event_title": event.get("title", ""),
                    "strike_word": strike,
                    "result": result,
                    "opening_price": opening,
                    "last_price": mkt.get("last_price", 0) / 100.0,
                    "volume": volume,
                    "open_time": open_time,
                    "close_time": mkt.get("close_time", ""),
                }
                all_markets.append(record)
                series_stats[series] += 1

        # Save periodically
        if (i + 1) % 10 == 0:
            _save(all_markets, series_stats)

    print(f"\n  Total: {len(all_markets)} settled markets")

    # Step 3: Save
    _save(all_markets, series_stats)


def _save(markets: list[dict], series_stats: Counter):
    # Compute summary
    with_opening = [m for m in markets if m.get("opening_price") is not None]
    categories = Counter(m.get("category", "unknown") for m in markets)

    output = {
        "markets": markets,
        "summary": {
            "total_markets": len(markets),
            "with_opening_price": len(with_opening),
            "unique_series": len(series_stats),
            "by_category": dict(categories),
            "by_series_top20": dict(series_stats.most_common(20)),
            "fetched_at": datetime.now().isoformat(),
        },
    }

    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved {len(markets)} markets to {OUT_PATH}")


if __name__ == "__main__":
    main()

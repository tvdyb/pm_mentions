#!/usr/bin/env python3
"""Fetch all settled Polymarket mention/speech markets.

Searches Gamma API for resolved mention-type events and pulls
pre-event prices from CLOB API.

Output: data/real_markets/polymarket_all_mentions.json
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime

import requests

PM_GAMMA = "https://gamma-api.polymarket.com"
PM_CLOB = "https://clob.polymarket.com"
OUT_PATH = Path("data/real_markets/polymarket_all_mentions.json")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

DELAY = 0.5


def gamma_get(path: str, params: dict | None = None) -> list | dict | None:
    url = f"{PM_GAMMA}{path}"
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  Gamma error: {e}", file=sys.stderr)
        return None


def clob_get(path: str, params: dict | None = None) -> dict | list | None:
    url = f"{PM_CLOB}{path}"
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  CLOB error: {e}", file=sys.stderr)
        return None


def fetch_mention_events() -> list[dict]:
    """Fetch closed mention-type events from Gamma API."""
    all_events = []
    offset = 0

    while True:
        time.sleep(DELAY)
        data = gamma_get("/events", {
            "closed": "true",
            "limit": 100,
            "offset": offset,
        })
        if not data or not isinstance(data, list) or len(data) == 0:
            break

        for event in data:
            if not isinstance(event, dict):
                continue
            title = (event.get("title", "") or "").lower()
            # Filter for mention-type events
            if any(kw in title for kw in [
                "mention", "what will", "who will", "what places",
                "what will trump say", "what will trump name",
                "what will be said", "what words",
            ]):
                all_events.append(event)

        offset += len(data)
        if len(data) < 100:
            break

        sys.stdout.write(f"\r  Scanned {offset} events, found {len(all_events)} mention events")
        sys.stdout.flush()

    print(f"\n  Found {len(all_events)} mention events")
    return all_events


def extract_markets(events: list[dict]) -> list[dict]:
    """Extract individual markets from events with prices."""
    markets = []

    for event in events:
        event_title = event.get("title", "")
        event_id = event.get("id", "")
        end_date = event.get("endDate", "")

        event_markets = event.get("markets", [])
        if not event_markets:
            continue

        for mkt in event_markets:
            if not isinstance(mkt, dict):
                continue

            # Get resolution
            outcome = mkt.get("outcomePrices")
            resolution = mkt.get("resolution", "")
            resolved = mkt.get("resolved")

            question = mkt.get("question", mkt.get("groupItemTitle", ""))
            volume = float(mkt.get("volume", 0) or 0)
            condition_id = mkt.get("conditionId", "")

            # Determine result from resolution field or outcome prices
            result = None
            if resolution:
                result = resolution.lower()
            elif outcome:
                # Infer resolution from outcome prices near 0 or 1
                try:
                    prices = json.loads(outcome) if isinstance(outcome, str) else outcome
                    if isinstance(prices, list) and len(prices) >= 2:
                        p0, p1 = float(prices[0]), float(prices[1])
                        if p0 > 0.99:
                            result = "yes"
                        elif p1 > 0.99:
                            result = "no"
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass

            if result is None:
                continue

            if result in ("p1",):
                result = "yes"
            elif result in ("p2",):
                result = "no"
            if result not in ("yes", "no"):
                continue

            # Try to get pre-event price from outcome prices
            try:
                if outcome:
                    prices = json.loads(outcome) if isinstance(outcome, str) else outcome
                    if isinstance(prices, list) and len(prices) >= 1:
                        yes_price = float(prices[0])
                    else:
                        yes_price = None
                else:
                    yes_price = None
            except (json.JSONDecodeError, TypeError):
                yes_price = None

            # For settled markets, outcomePrices will be 1/0.
            # We need historical price. Try CLOB price history.
            opening_price = None
            tokens = mkt.get("clobTokenIds")
            if tokens:
                try:
                    token_list = json.loads(tokens) if isinstance(tokens, str) else tokens
                    if isinstance(token_list, list) and len(token_list) >= 1:
                        time.sleep(DELAY)
                        hist = clob_get("/prices-history", {
                            "market": token_list[0],
                            "interval": "max",
                            "fidelity": 60,
                        })
                        if hist and isinstance(hist, dict):
                            history = hist.get("history", [])
                            if history:
                                # Get price from early in the market's life
                                # Sort by timestamp, take first quartile average
                                prices_sorted = sorted(history, key=lambda h: h.get("t", 0))
                                n = len(prices_sorted)
                                early = prices_sorted[:max(1, n // 4)]
                                opening_price = sum(float(p.get("p", 0)) for p in early) / len(early)
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass

            # Fall back to outcomePrices if no history
            if opening_price is None and yes_price is not None and yes_price not in (0, 1):
                opening_price = yes_price

            markets.append({
                "source": "polymarket",
                "event": event_title,
                "event_id": event_id,
                "question": question,
                "condition_id": condition_id,
                "result": result,
                "opening_price": opening_price,
                "volume": volume,
                "end_date": end_date,
            })

    return markets


EVENTS_CACHE = Path("data/real_markets/_pm_events_cache.json")


def main():
    print("=" * 60)
    print("  Fetching Polymarket mention markets")
    print("=" * 60)

    # Use cached events if available (scanning is slow)
    if EVENTS_CACHE.exists():
        print("\n[1/2] Loading cached events...")
        with open(EVENTS_CACHE) as f:
            events = json.load(f)
        print(f"  {len(events)} events from cache")
    else:
        print("\n[1/2] Scanning events...")
        events = fetch_mention_events()
        with open(EVENTS_CACHE, "w") as f:
            json.dump(events, f)
        print(f"  Cached {len(events)} events")

    print("\n[2/2] Extracting markets with prices...")
    markets = extract_markets(events)

    # Filter to those with usable prices
    with_price = [m for m in markets if m.get("opening_price") is not None
                  and 0 < m["opening_price"] < 1]
    print(f"\n  Total markets: {len(markets)}")
    print(f"  With opening price: {len(with_price)}")

    # Save
    output = {
        "markets": markets,
        "summary": {
            "total": len(markets),
            "with_price": len(with_price),
            "unique_events": len(set(m["event"] for m in markets)),
            "fetched_at": datetime.now().isoformat(),
        },
    }

    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {OUT_PATH}")


if __name__ == "__main__":
    main()

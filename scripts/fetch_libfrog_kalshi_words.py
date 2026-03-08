#!/usr/bin/env python3
"""Query LibFrog for every Kalshi earnings strike word.

Reads kalshi_all_series.json to get all (company, word) pairs from
earnings markets, then queries LibFrog for each one.

Output: data/base_rates/libfrog_kalshi_matched.json
"""

import json
import os
import time
import sys
from pathlib import Path
from datetime import datetime

import requests

LIBFROG_BASE = "https://us-central1-mentionmarket-dddf0.cloudfunctions.net"
API_KEY = os.environ.get("LIBFROG_API_KEY", "")

if not API_KEY:
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("LIBFROG_API_KEY="):
                API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")

KALSHI_PATH = Path("data/real_markets/kalshi_all_series.json")
OUT_PATH = Path("data/base_rates/libfrog_kalshi_matched.json")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

DELAY = 0.4  # seconds between API calls


def libfrog_get(word: str, ticker: str) -> dict | None:
    if not API_KEY:
        return None
    url = f"{LIBFROG_BASE}/searchEarningsStrikeWord"
    params = {"target_phrase": word, "ticker": ticker, "apiKey": API_KEY}
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"    Error: {e}", file=sys.stderr)
        return None


def extract_pairs() -> list[tuple[str, str, str]]:
    """Extract unique (company_ticker, strike_word, normalized_word) from Kalshi."""
    with open(KALSHI_PATH) as f:
        data = json.load(f)

    pairs = set()
    for m in data["markets"]:
        series = m.get("series", "")
        if "EARNINGS" not in series:
            continue
        # Extract company ticker
        company = (series.replace("KXEARNINGSMENTION", "")
                        .replace("KXEARNIGSMENTION", "")
                        .replace("KXEARNIGNSMENTIO", "")
                        .upper())
        word = m.get("strike_word", "")
        if not company or not word:
            continue

        # For "AI / Artificial Intelligence", query both "AI" and "Artificial Intelligence"
        # For "Shutdown / Shut Down", query "Shutdown" and "Shut Down"
        if " / " in word:
            parts = [p.strip() for p in word.split(" / ")]
            for part in parts:
                pairs.add((company, word, part))
        else:
            pairs.add((company, word, word))

    return sorted(pairs)


def main():
    print("=" * 60)
    print("  Fetching LibFrog base rates for Kalshi earnings words")
    print("=" * 60)

    if not API_KEY:
        print("\n  ERROR: No LIBFROG_API_KEY found. Set in .env")
        return

    pairs = extract_pairs()
    print(f"\n  {len(pairs)} (company, word) queries to make")
    companies = set(p[0] for p in pairs)
    print(f"  {len(companies)} unique companies")

    # Load existing results to resume
    results = {}
    if OUT_PATH.exists():
        with open(OUT_PATH) as f:
            existing = json.load(f)
        results = existing.get("matches", {})
        print(f"  {len(results)} existing results loaded")

    queried = 0
    skipped = 0
    for i, (company, original_word, query_word) in enumerate(pairs):
        key = f"{company}|{original_word}"

        # Skip if we already have a result for this (company, original_word)
        if key in results and results[key].get("base_rate") is not None:
            skipped += 1
            continue

        sys.stdout.write(f"\r  [{i+1}/{len(pairs)}] {company}/{query_word:30s}")
        sys.stdout.flush()

        time.sleep(DELAY)
        data = libfrog_get(query_word, company)

        if data and isinstance(data, dict):
            n_total = data.get("total_transcripts_checked", 0)
            n_mentions = data.get("transcripts_with_phrase", 0)
            br = data.get("probability", None)
            if br is None and n_total > 0:
                br = n_mentions / n_total

            # Only store if we got real data
            if n_total > 0:
                results[key] = {
                    "company": company,
                    "kalshi_word": original_word,
                    "query_word": query_word,
                    "base_rate": br,
                    "n_calls": n_total,
                    "n_mentions": n_mentions,
                    "source": "libfrog",
                }
                queried += 1
        else:
            # Store miss so we don't re-query
            if key not in results:
                results[key] = {
                    "company": company,
                    "kalshi_word": original_word,
                    "query_word": query_word,
                    "base_rate": None,
                    "n_calls": 0,
                    "source": "libfrog_no_data",
                }

        # Save periodically
        if (i + 1) % 50 == 0:
            _save(results)

    _save(results)

    # Summary
    with_data = {k: v for k, v in results.items() if v.get("base_rate") is not None}
    print(f"\n\n  Total queries: {len(pairs)}")
    print(f"  Skipped (cached): {skipped}")
    print(f"  New results: {queried}")
    print(f"  With base rate: {len(with_data)}")
    print(f"  Saved to {OUT_PATH}")


def _save(results):
    with_data = {k: v for k, v in results.items() if v.get("base_rate") is not None}
    output = {
        "matches": results,
        "summary": {
            "total": len(results),
            "with_base_rate": len(with_data),
            "unique_companies": len(set(v["company"] for v in results.values())),
            "fetched_at": datetime.now().isoformat(),
        },
    }
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()

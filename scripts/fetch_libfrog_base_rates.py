#!/usr/bin/env python3
"""Fetch earnings call mention base rates from LibFrog API.

Queries transcript data for companies with active Kalshi earnings
mention markets. Computes historical base rates for each word/phrase.

Output: data/base_rates/libfrog_earnings.json

Requires: LIBFROG_API_KEY in .env or environment
API docs: https://docs.libfrog.com
"""

import json
import os
import time
import sys
from pathlib import Path
from datetime import datetime

import requests

# LibFrog API
LIBFROG_BASE = "https://us-central1-mentionmarket-dddf0.cloudfunctions.net"
API_KEY = os.environ.get("LIBFROG_API_KEY", "")

# Try loading from .env
if not API_KEY:
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("LIBFROG_API_KEY="):
                API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")

OUT_PATH = Path("data/base_rates/libfrog_earnings.json")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

DELAY = 0.5

# Map Kalshi earnings series tickers to company tickers/names
# Format: KXEARNINGSMENTIONXXXX -> XXXX is the stock ticker
KNOWN_COMPANIES = {
    "AAPL": ["AI", "Artificial Intelligence", "iPhone", "China", "Services",
             "Mac", "iPad", "Vision Pro", "Apple Intelligence"],
    "NVDA": ["AI", "Artificial Intelligence", "GPU", "Data Center", "China",
             "Blackwell", "Gaming", "Automotive"],
    "TSLA": ["Robotaxi", "Cybertruck", "FSD", "Full Self-Driving", "China",
             "AI", "Optimus", "Solar", "Megapack"],
    "MSFT": ["AI", "Azure", "Copilot", "OpenAI", "Cloud", "Gaming", "LinkedIn"],
    "GOOGL": ["AI", "Gemini", "Search", "YouTube", "Cloud", "Waymo", "Antitrust"],
    "AMZN": ["AWS", "AI", "Alexa", "Prime", "Advertising", "Grocery"],
    "META": ["AI", "Metaverse", "Reality Labs", "Instagram", "WhatsApp",
             "Threads", "Llama", "Advertising"],
}


def libfrog_get(path: str, params: dict | None = None) -> dict | None:
    if not API_KEY:
        return None
    url = f"{LIBFROG_BASE}{path}"
    if params is None:
        params = {}
    params["apiKey"] = API_KEY
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  LibFrog error: {e}", file=sys.stderr)
        return None


def fetch_libfrog_docs() -> dict | None:
    """Try to fetch API documentation to discover endpoints."""
    try:
        resp = requests.get("https://docs.libfrog.com", timeout=15)
        return {"status": resp.status_code, "text": resp.text[:2000]}
    except requests.RequestException:
        return None


def query_mention_rate(company: str, word: str) -> dict | None:
    """Query LibFrog for how often a word appears in earnings transcripts."""
    result = libfrog_get("/searchEarningsStrikeWord", {
        "target_phrase": word,
        "ticker": company,
    })
    return result


def extract_kalshi_earnings_companies() -> list[str]:
    """Get company tickers from Kalshi earnings mention series."""
    try:
        resp = requests.get(
            "https://api.elections.kalshi.com/trade-api/v2/series",
            params={"limit": 1000},
            headers={"Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return list(KNOWN_COMPANIES.keys())

    tickers = []
    for s in data.get("series", []):
        t = s.get("ticker", "")
        if t.startswith("KXEARNINGSMENTION"):
            company = t.replace("KXEARNINGSMENTION", "")
            if company:
                tickers.append(company)
    return tickers


def main():
    print("=" * 60)
    print("  Fetching LibFrog earnings base rates")
    print("=" * 60)

    if not API_KEY:
        print("\n  WARNING: No LIBFROG_API_KEY found in environment or .env")
        print("  Set LIBFROG_API_KEY=<key> in .env to enable LibFrog queries.")
        print("  Generating stub output with known companies only...")

        # Generate stub with placeholder data
        stub = {}
        for company, words in KNOWN_COMPANIES.items():
            stub[company] = {}
            for word in words:
                stub[company][word] = {
                    "base_rate": None,
                    "n_calls": 0,
                    "source": "stub — set LIBFROG_API_KEY to fetch real data",
                }

        output = {
            "companies": stub,
            "summary": {
                "n_companies": len(stub),
                "api_key_set": False,
                "fetched_at": datetime.now().isoformat(),
            },
        }
        with open(OUT_PATH, "w") as f:
            json.dump(output, f, indent=2)
        print(f"  Stub saved to {OUT_PATH}")
        return

    # Discover API endpoints
    print("\n[1/3] Checking LibFrog API...")
    docs = fetch_libfrog_docs()

    # Get earnings companies from Kalshi
    print("\n[2/3] Getting earnings companies from Kalshi...")
    companies = extract_kalshi_earnings_companies()
    print(f"  {len(companies)} earnings mention series found")

    # Query base rates
    print("\n[3/3] Querying mention base rates...")
    results = {}

    for company in companies:
        words = KNOWN_COMPANIES.get(company, ["AI", "China", "Revenue"])
        results[company] = {}

        for word in words:
            sys.stdout.write(f"\r  {company}/{word:20s}")
            sys.stdout.flush()
            time.sleep(DELAY)

            data = query_mention_rate(company, word)
            if data and isinstance(data, dict):
                n_total = data.get("total_transcripts_checked", 0)
                n_mentions = data.get("transcripts_with_phrase", 0)
                br = data.get("probability", None)
                if br is None and n_total > 0:
                    br = n_mentions / n_total

                results[company][word] = {
                    "base_rate": br,
                    "n_calls": n_total,
                    "n_mentions": n_mentions,
                    "source": "libfrog",
                }
            else:
                results[company][word] = {
                    "base_rate": None,
                    "n_calls": 0,
                    "source": "libfrog_no_data",
                }

    print(f"\n  Queried {sum(len(v) for v in results.values())} word/company pairs")

    output = {
        "companies": results,
        "summary": {
            "n_companies": len(results),
            "n_pairs": sum(len(v) for v in results.values()),
            "api_key_set": True,
            "fetched_at": datetime.now().isoformat(),
        },
    }

    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {OUT_PATH}")


if __name__ == "__main__":
    main()

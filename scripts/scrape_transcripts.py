#!/usr/bin/env python3
"""Scrape presidential speech transcripts.

Usage:
    python scripts/scrape_transcripts.py                    # all types, 2015-2025
    python scripts/scrape_transcripts.py --type sotu        # SOTU only
    python scripts/scrape_transcripts.py --start 2020       # from 2020
"""

import argparse
import sys
sys.path.insert(0, ".")

from pm_mentions.data.scraper import scrape_all, CATEGORY_URLS


def main():
    parser = argparse.ArgumentParser(description="Scrape speech transcripts")
    parser.add_argument("--type", choices=list(CATEGORY_URLS.keys()),
                        help="Specific event type to scrape")
    parser.add_argument("--start", type=int, default=2015, help="Start year")
    parser.add_argument("--end", type=int, default=2025, help="End year")
    parser.add_argument("--output", default="data/transcripts", help="Output directory")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Delay between requests (seconds)")
    args = parser.parse_args()

    event_types = [args.type] if args.type else None

    events = scrape_all(
        event_types=event_types,
        start_year=args.start,
        end_year=args.end,
        output_dir=args.output,
        delay=args.delay,
    )

    print(f"\nDone. {len(events)} transcripts collected.")


if __name__ == "__main__":
    main()

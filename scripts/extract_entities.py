#!/usr/bin/env python3
"""Run entity extraction on scraped transcripts.

Usage:
    python scripts/extract_entities.py
    python scripts/extract_entities.py --input data/transcripts/sotu.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from pm_mentions.data.scraper import load_events, _save_events
from pm_mentions.ner.extractor import extract_all


def main():
    parser = argparse.ArgumentParser(description="Extract person mentions from transcripts")
    parser.add_argument("--input", default="data/transcripts/all_events.json",
                        help="Input JSON file with scraped events")
    parser.add_argument("--output", default="data/entities/events_with_entities.json",
                        help="Output JSON file")
    args = parser.parse_args()

    print(f"Loading events from {args.input}...")
    events = load_events(args.input)
    print(f"  {len(events)} events loaded")

    print("\nRunning entity extraction...")
    events = extract_all(events, show_progress=True)

    # Summary
    total_mentions = sum(len(e.entities_mentioned) for e in events)
    avg_mentions = total_mentions / len(events) if events else 0
    print(f"\n  Total unique person mentions across all events: {total_mentions}")
    print(f"  Average people mentioned per event: {avg_mentions:.1f}")

    # Save
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = []
    for e in events:
        data.append({
            "event_id": e.event_id,
            "event_type": e.event_type,
            "speaker": e.speaker,
            "date": e.date.isoformat(),
            "title": e.title,
            "transcript": e.transcript,
            "url": e.url,
            "word_count": e.word_count,
            "entities_mentioned": e.entities_mentioned,
            "mention_counts": e.mention_counts,
        })

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to {out_path}")

    # Print top mentioned people
    from collections import Counter
    all_mentions = Counter()
    for e in events:
        for person, count in e.mention_counts.items():
            all_mentions[person] += count

    print(f"\n--- Top 20 Most Mentioned People ---")
    for person, count in all_mentions.most_common(20):
        n_events = sum(1 for e in events if person in e.entities_mentioned)
        print(f"  {person:<30} {count:>5} mentions in {n_events:>3} events "
              f"({n_events/len(events):.0%})")


if __name__ == "__main__":
    main()

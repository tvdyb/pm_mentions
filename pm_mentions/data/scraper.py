"""Scrape presidential speech transcripts from the American Presidency Project.

Source: https://www.presidency.ucsb.edu
Uses category listing pages (more reliable than the advanced search).
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from ..models import SpeechEvent

BASE_URL = "https://www.presidency.ucsb.edu"
HEADERS = {
    "User-Agent": "MentionMarketResearch/1.0 (academic research)",
}

# Category listing pages (much more reliable than advanced search)
CATEGORY_URLS = {
    "sotu": (
        "/documents/app-categories/spoken-addresses-and-remarks"
        "/presidential/state-the-union-addresses"
    ),
    "press_conference": (
        "/documents/app-categories/presidential/news-conferences"
    ),
    "debate": (
        "/documents/app-categories/elections-and-transitions/debates"
    ),
}


def _fetch(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  Failed to fetch {url}: {e}")
                return None


def _parse_listing_page(html: str) -> list[dict]:
    """Parse a category listing page. Returns list of {title, url, date_str, speaker}."""
    soup = BeautifulSoup(html, "lxml")
    results = []

    for row in soup.select(".views-row"):
        title_el = row.select_one(".field-title a")
        date_el = row.select_one(".date-display-single")
        col4 = row.select_one(".col-sm-4")
        person_el = col4.select_one("a") if col4 else None

        if not title_el:
            continue

        url = title_el.get("href", "")
        if url and not url.startswith("http"):
            url = BASE_URL + url

        results.append({
            "title": title_el.get_text(strip=True),
            "url": url,
            "date_str": date_el.get_text(strip=True) if date_el else "",
            "speaker": person_el.get_text(strip=True) if person_el else "",
        })

    return results


def _parse_transcript_page(html: str) -> dict:
    """Parse a single transcript page. Returns {transcript, speaker, date_str}."""
    soup = BeautifulSoup(html, "lxml")

    body = soup.select_one(".field-docs-content")
    if not body:
        body = soup.select_one(".field--name-field-docs-content")
    transcript = body.get_text(separator="\n", strip=True) if body else ""

    speaker_el = soup.select_one(".field-docs-person a")
    if not speaker_el:
        speaker_el = soup.select_one(".field--name-field-docs-person a")
    speaker = speaker_el.get_text(strip=True) if speaker_el else ""

    date_el = soup.select_one(".field-docs-start-date-sort span")
    if not date_el:
        date_el = soup.select_one(".field--name-field-docs-start-date-sort span")
    date_str = date_el.get_text(strip=True) if date_el else ""

    return {"transcript": transcript, "speaker": speaker, "date_str": date_str}


def _parse_date(date_str: str) -> datetime | None:
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    m = re.search(r"(\w+ \d{1,2}, \d{4})", date_str)
    if m:
        try:
            return datetime.strptime(m.group(1), "%B %d, %Y")
        except ValueError:
            pass
    return None


def _clean_speaker(raw: str) -> str:
    """Normalize speaker names from the presidency project format."""
    # Remove term annotations like "(2nd Term)", "(1st Term)"
    cleaned = re.sub(r"\s*\(\d+\w*\s*Term\)\s*", "", raw).strip()
    # Remove "Jr." suffix variations for matching purposes, but keep full name
    return cleaned


def scrape_event_type(
    event_type: str,
    start_year: int = 2015,
    end_year: int = 2025,
    delay: float = 1.0,
) -> list[SpeechEvent]:
    """Scrape all events of a given type from category listing pages."""
    if event_type not in CATEGORY_URLS:
        raise ValueError(f"Unknown event type: {event_type}. "
                         f"Options: {list(CATEGORY_URLS.keys())}")

    category_path = CATEGORY_URLS[event_type]
    base_listing_url = f"{BASE_URL}{category_path}?items_per_page=60"

    print(f"Fetching {event_type} listing...")
    html = _fetch(base_listing_url)
    if not html:
        return []

    all_results = _parse_listing_page(html)

    # Handle pagination
    soup = BeautifulSoup(html, "lxml")
    pager_last = soup.select_one(".pager-last a")
    if pager_last:
        last_href = pager_last.get("href", "")
        m = re.search(r"page=(\d+)", last_href)
        if m:
            last_page = int(m.group(1))
            for page in range(1, last_page + 1):
                time.sleep(delay)
                page_url = f"{base_listing_url}&page={page}"
                page_html = _fetch(page_url)
                if page_html:
                    all_results.extend(_parse_listing_page(page_html))

    # Filter by date range
    filtered = []
    for item in all_results:
        date = _parse_date(item["date_str"])
        if date and start_year <= date.year <= end_year:
            item["date"] = date
            filtered.append(item)

    print(f"  Found {len(filtered)} {event_type} events in {start_year}-{end_year} "
          f"(from {len(all_results)} total)")

    # Fetch each transcript
    events = []
    for item in tqdm(filtered, desc=f"Fetching {event_type} transcripts"):
        time.sleep(delay)
        page_html = _fetch(item["url"])
        if not page_html:
            continue

        parsed = _parse_transcript_page(page_html)
        if not parsed["transcript"] or len(parsed["transcript"]) < 200:
            continue

        speaker = _clean_speaker(parsed["speaker"] or item.get("speaker", "Unknown"))
        date = item["date"]

        event_id = f"{event_type}_{date.strftime('%Y%m%d')}_{len(events)}"
        event = SpeechEvent(
            event_id=event_id,
            event_type=event_type,
            speaker=speaker,
            date=date,
            transcript=parsed["transcript"],
            title=item["title"],
            url=item["url"],
        )
        events.append(event)

    print(f"  Collected {len(events)} {event_type} transcripts")
    return events


def scrape_all(
    event_types: list[str] | None = None,
    start_year: int = 2015,
    end_year: int = 2025,
    output_dir: str = "data/transcripts",
    delay: float = 1.5,
) -> list[SpeechEvent]:
    """Scrape all event types and save to disk."""
    if event_types is None:
        event_types = list(CATEGORY_URLS.keys())

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_events: list[SpeechEvent] = []

    for etype in event_types:
        events = scrape_event_type(etype, start_year, end_year, delay)
        all_events.extend(events)

        save_path = out / f"{etype}.json"
        _save_events(events, save_path)
        print(f"  Saved to {save_path}")

    # Save combined
    combined_path = out / "all_events.json"
    _save_events(all_events, combined_path)
    print(f"\nTotal: {len(all_events)} events saved to {combined_path}")

    return all_events


def _save_events(events: list[SpeechEvent], path: Path):
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
        })
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_events(path: str | Path) -> list[SpeechEvent]:
    """Load previously scraped events from JSON."""
    with open(path) as f:
        data = json.load(f)

    events = []
    for d in data:
        events.append(SpeechEvent(
            event_id=d["event_id"],
            event_type=d["event_type"],
            speaker=d["speaker"],
            date=datetime.fromisoformat(d["date"]),
            title=d.get("title", ""),
            transcript=d["transcript"],
            url=d.get("url", ""),
            entities_mentioned=d.get("entities_mentioned", []),
            mention_counts=d.get("mention_counts", {}),
        ))
    return events

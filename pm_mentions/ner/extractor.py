"""Entity extraction pipeline for speech transcripts.

Extracts person mentions using spaCy NER + alias resolution.
Handles titles, nicknames, and coreference ("the former president" -> Trump).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from functools import lru_cache

import spacy
from spacy.tokens import Doc

from ..models import SpeechEvent

# Canonical name -> all known aliases
# This is the core knowledge base for political figure resolution.
POLITICAL_ALIASES: dict[str, list[str]] = {
    # Presidents
    "Donald Trump": [
        "Trump", "Donald Trump", "President Trump", "Donald J. Trump",
        "the former President", "45", "DJT", "the 45th President",
    ],
    "Joe Biden": [
        "Biden", "Joe Biden", "President Biden", "Joseph Biden",
        "Joseph R. Biden", "the President", "46",
    ],
    "Barack Obama": [
        "Obama", "Barack Obama", "President Obama", "Barack",
        "the 44th President",
    ],
    "George W. Bush": [
        "Bush", "George W. Bush", "President Bush", "George Bush",
        "W.", "43",
    ],

    # Vice Presidents
    "Kamala Harris": [
        "Harris", "Kamala Harris", "Vice President Harris", "Kamala",
        "the Vice President",
    ],
    "Mike Pence": [
        "Pence", "Mike Pence", "Vice President Pence", "Michael Pence",
    ],
    "JD Vance": [
        "Vance", "JD Vance", "J.D. Vance", "Senator Vance",
    ],

    # Congressional leaders
    "Nancy Pelosi": [
        "Pelosi", "Nancy Pelosi", "Speaker Pelosi", "the Speaker",
    ],
    "Mitch McConnell": [
        "McConnell", "Mitch McConnell", "Senator McConnell",
        "the Minority Leader", "the Majority Leader",
    ],
    "Chuck Schumer": [
        "Schumer", "Chuck Schumer", "Senator Schumer",
    ],
    "Kevin McCarthy": [
        "McCarthy", "Kevin McCarthy", "Speaker McCarthy",
    ],
    "Mike Johnson": [
        "Mike Johnson", "Speaker Johnson",
    ],

    # 2024 cycle figures
    "Ron DeSantis": [
        "DeSantis", "Ron DeSantis", "Governor DeSantis",
    ],
    "Nikki Haley": [
        "Haley", "Nikki Haley", "Ambassador Haley",
    ],
    "Vivek Ramaswamy": [
        "Vivek", "Ramaswamy", "Vivek Ramaswamy",
    ],
    "Tim Walz": [
        "Walz", "Tim Walz", "Governor Walz",
    ],
    "Pete Buttigieg": [
        "Buttigieg", "Pete Buttigieg", "Mayor Pete", "Secretary Buttigieg",
    ],

    # Cabinet / key officials
    "Anthony Fauci": [
        "Fauci", "Dr. Fauci", "Anthony Fauci",
    ],
    "Merrick Garland": [
        "Garland", "Merrick Garland", "Attorney General Garland",
    ],
    "Janet Yellen": [
        "Yellen", "Janet Yellen", "Secretary Yellen",
    ],
    "Lloyd Austin": [
        "Austin", "Lloyd Austin", "Secretary Austin",
    ],

    # Media / tech figures
    "Elon Musk": [
        "Musk", "Elon Musk", "Elon",
    ],
    "Mark Zuckerberg": [
        "Zuckerberg", "Mark Zuckerberg", "Zuck",
    ],
    "Jeff Bezos": [
        "Bezos", "Jeff Bezos",
    ],
    "Tucker Carlson": [
        "Tucker", "Tucker Carlson", "Carlson",
    ],

    # International
    "Vladimir Putin": [
        "Putin", "Vladimir Putin", "President Putin",
    ],
    "Xi Jinping": [
        "Xi", "Xi Jinping", "President Xi",
    ],
    "Volodymyr Zelenskyy": [
        "Zelenskyy", "Zelensky", "Volodymyr Zelenskyy", "President Zelenskyy",
    ],
    "Benjamin Netanyahu": [
        "Netanyahu", "Benjamin Netanyahu", "Bibi", "Prime Minister Netanyahu",
    ],
    "Kim Jong Un": [
        "Kim Jong Un", "Kim", "Chairman Kim",
    ],

    # Historical / other
    "Hillary Clinton": [
        "Hillary", "Hillary Clinton", "Clinton", "Secretary Clinton",
    ],
    "Bernie Sanders": [
        "Bernie", "Bernie Sanders", "Senator Sanders",
    ],
    "Alexandria Ocasio-Cortez": [
        "AOC", "Ocasio-Cortez", "Alexandria Ocasio-Cortez",
    ],
    "Ted Cruz": [
        "Cruz", "Ted Cruz", "Senator Cruz",
    ],
    "Marco Rubio": [
        "Rubio", "Marco Rubio", "Senator Rubio", "Secretary Rubio",
    ],
    "Lindsey Graham": [
        "Graham", "Lindsey Graham", "Senator Graham",
    ],
    "Adam Schiff": [
        "Schiff", "Adam Schiff", "Representative Schiff",
    ],
    "Jim Jordan": [
        "Jim Jordan", "Jordan", "Representative Jordan",
    ],
    "Matt Gaetz": [
        "Gaetz", "Matt Gaetz", "Representative Gaetz",
    ],
    "Marjorie Taylor Greene": [
        "MTG", "Marjorie Taylor Greene", "Greene",
    ],
    "Tim Scott": [
        "Tim Scott", "Senator Scott",
    ],
    "Elizabeth Warren": [
        "Warren", "Elizabeth Warren", "Senator Warren",
    ],
    "Susan Collins": [
        "Collins", "Susan Collins", "Senator Collins",
    ],
    "Mitt Romney": [
        "Romney", "Mitt Romney", "Senator Romney",
    ],
    "John Fetterman": [
        "Fetterman", "John Fetterman", "Senator Fetterman",
    ],
    "Robert F. Kennedy Jr.": [
        "RFK", "RFK Jr.", "Robert Kennedy", "Bobby Kennedy", "Kennedy",
    ],
}


def _build_alias_lookup() -> dict[str, str]:
    """Build reverse lookup: alias -> canonical name."""
    lookup = {}
    for canonical, aliases in POLITICAL_ALIASES.items():
        for alias in aliases:
            # Case-insensitive matching
            lookup[alias.lower()] = canonical
        lookup[canonical.lower()] = canonical
    return lookup


ALIAS_LOOKUP = _build_alias_lookup()

# Ambiguous single names that need context (skip standalone)
AMBIGUOUS_NAMES = {
    "clinton",  # could be Bill or Hillary
    "bush",     # could be HW or W
    "kennedy",  # could be JFK, RFK, etc.
    "austin",   # common city name
    "jordan",   # common first name
    "graham",   # common first name
    "greene",   # common surname
    "scott",    # common first name
    "collins",  # common surname
    "kim",      # common first name
}

# Titles that precede person references
TITLE_PATTERNS = re.compile(
    r"\b(President|Vice President|Senator|Secretary|Speaker|"
    r"Representative|Congressman|Congresswoman|Governor|Attorney General|"
    r"Ambassador|General|Justice|Chief Justice|Chairman|"
    r"Prime Minister|Chancellor|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _load_spacy():
    try:
        return spacy.load("en_core_web_lg")
    except OSError:
        print("Downloading spaCy model en_core_web_lg...")
        spacy.cli.download("en_core_web_lg")
        return spacy.load("en_core_web_lg")


def _resolve_speaker_canonical(speaker: str) -> str | None:
    """Resolve a speaker name to canonical form for self-mention filtering."""
    # Try direct lookup
    s = speaker.strip().lower()
    if s in ALIAS_LOOKUP:
        return ALIAS_LOOKUP[s]
    # Try progressively shorter versions
    # "Joseph R. Biden, Jr." -> try "Joseph Biden", "Biden", etc.
    parts = re.sub(r"[,.]", "", speaker).split()
    for part in parts:
        if part.lower() in ALIAS_LOOKUP:
            return ALIAS_LOOKUP[part.lower()]
    # Try first + last name
    if len(parts) >= 2:
        first_last = f"{parts[0]} {parts[-1]}".lower()
        if first_last in ALIAS_LOOKUP:
            return ALIAS_LOOKUP[first_last]
    return None


def resolve_name(name: str, speaker: str = "", speaker_canonical: str | None = None) -> str | None:
    """Resolve a name string to a canonical person name.

    Returns None if the name is ambiguous or not a known figure.
    """
    name_lower = name.strip().lower()

    # Direct alias lookup
    if name_lower in ALIAS_LOOKUP:
        canonical = ALIAS_LOOKUP[name_lower]
        if speaker_canonical and canonical == speaker_canonical:
            return None
        return canonical

    # Try with "the" stripped
    if name_lower.startswith("the "):
        stripped = name_lower[4:]
        if stripped in ALIAS_LOOKUP:
            canonical = ALIAS_LOOKUP[stripped]
            if speaker_canonical and canonical == speaker_canonical:
                return None
            return canonical

    return None


def extract_mentions(event: SpeechEvent, nlp=None) -> dict[str, int]:
    """Extract and count person mentions from a speech transcript.

    Uses three passes:
    1. spaCy NER PERSON entities
    2. Title + name pattern matching
    3. Direct alias scanning

    Returns dict of canonical_name -> mention_count.
    """
    if nlp is None:
        nlp = _load_spacy()

    text = event.transcript
    speaker_canonical = _resolve_speaker_canonical(event.speaker)
    counts: Counter = Counter()

    # Pass 1: spaCy NER
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            canonical = resolve_name(ent.text, speaker_canonical=speaker_canonical)
            if canonical:
                counts[canonical] += 1

    # Pass 2: Title + name patterns
    for match in TITLE_PATTERNS.finditer(text):
        full = match.group(0).strip()
        canonical = resolve_name(full, speaker_canonical=speaker_canonical)
        if canonical and canonical not in counts:
            counts[canonical] += 1

    # Pass 3: Direct alias scan for high-value targets
    for canonical, aliases in POLITICAL_ALIASES.items():
        if speaker_canonical and canonical == speaker_canonical:
            continue
        if canonical in counts:
            continue
        for alias in aliases:
            alias_lower = alias.lower()
            if alias_lower in AMBIGUOUS_NAMES:
                continue
            if len(alias_lower) < 4:
                continue
            pattern = r'\b' + re.escape(alias) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                counts[canonical] = len(matches)
                break

    return dict(counts)


def extract_all(events: list[SpeechEvent], show_progress: bool = True) -> list[SpeechEvent]:
    """Run entity extraction on all events. Modifies events in-place."""
    nlp = _load_spacy()
    iterator = events
    if show_progress:
        from tqdm import tqdm
        iterator = tqdm(events, desc="Extracting entities")

    for event in iterator:
        mentions = extract_mentions(event, nlp)
        event.mention_counts = mentions
        event.entities_mentioned = list(mentions.keys())

    return events


def get_all_known_people() -> list[str]:
    """Return list of all canonical person names in our knowledge base."""
    return list(POLITICAL_ALIASES.keys())

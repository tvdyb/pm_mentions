"""Feature engineering for mention prediction.

Computes person-level and event-level features from historical data.
All features use only data available BEFORE the target event (no lookahead).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from ..models import SpeechEvent


def build_features(
    person: str,
    target_event: SpeechEvent,
    prior_events: list[SpeechEvent],
) -> dict:
    """Compute features for a (person, event) pair using only prior data."""
    features: dict = {}

    # Filter to events before the target
    history = [e for e in prior_events if e.date < target_event.date]
    if not history:
        return _empty_features(person, target_event)

    # --- Person-level historical features ---
    mentioned_events = [e for e in history if person in e.entities_mentioned]
    n_events = len(history)
    n_mentioned = len(mentioned_events)

    features["base_mention_rate"] = n_mentioned / n_events if n_events > 0 else 0.0

    # Recent mention rate (last 5 events)
    recent = sorted(history, key=lambda e: e.date, reverse=True)[:5]
    recent_mentioned = sum(1 for e in recent if person in e.entities_mentioned)
    features["mention_rate_last_5"] = recent_mentioned / len(recent) if recent else 0.0

    # Mention rate by event type
    same_type = [e for e in history if e.event_type == target_event.event_type]
    same_type_mentioned = [e for e in same_type if person in e.entities_mentioned]
    features["mention_rate_by_type"] = (
        len(same_type_mentioned) / len(same_type) if same_type else 0.0
    )

    # Speaker-specific mention rate
    same_speaker = [e for e in history if e.speaker == target_event.speaker]
    same_speaker_mentioned = [e for e in same_speaker if person in e.entities_mentioned]
    features["mention_rate_by_speaker"] = (
        len(same_speaker_mentioned) / len(same_speaker) if same_speaker else 0.0
    )

    # Average mentions when mentioned
    mention_counts = [
        e.mention_counts.get(person, 0) for e in mentioned_events
    ]
    features["avg_mentions_when_mentioned"] = (
        np.mean(mention_counts) if mention_counts else 0.0
    )

    # Days since last mention
    if mentioned_events:
        last_mention = max(e.date for e in mentioned_events)
        features["days_since_last_mention"] = (
            target_event.date - last_mention
        ).days
    else:
        features["days_since_last_mention"] = 9999

    # Mentioned in prior speech by this speaker
    same_speaker_sorted = sorted(same_speaker, key=lambda e: e.date, reverse=True)
    features["mentioned_in_prior_speech"] = (
        1.0 if same_speaker_sorted and person in same_speaker_sorted[0].entities_mentioned
        else 0.0
    )

    # Mention trend: is rate increasing or decreasing?
    if n_events >= 5:
        first_half = history[:n_events // 2]
        second_half = history[n_events // 2:]
        rate_first = sum(1 for e in first_half if person in e.entities_mentioned) / len(first_half)
        rate_second = sum(1 for e in second_half if person in e.entities_mentioned) / len(second_half)
        features["mention_trend"] = rate_second - rate_first
    else:
        features["mention_trend"] = 0.0

    # --- Yapper score (composite) ---
    features["yapper_score"] = _compute_yapper_score(features)

    # --- Event-level features ---
    features["event_type"] = target_event.event_type
    features["speaker"] = target_event.speaker

    # Average unique people mentioned in this event type
    if same_type:
        avg_unique = np.mean([len(e.entities_mentioned) for e in same_type])
    else:
        avg_unique = np.mean([len(e.entities_mentioned) for e in history])
    features["avg_unique_mentions_event_type"] = avg_unique

    # Average word count for this event type
    if same_type:
        features["avg_word_count_event_type"] = np.mean([e.word_count for e in same_type])
    else:
        features["avg_word_count_event_type"] = np.mean([e.word_count for e in history])

    # N historical events available
    features["n_prior_events"] = n_events

    return features


def _compute_yapper_score(features: dict) -> float:
    """Composite yapper score: how much of a 'frequent mention' is this person?

    Weighted combination of:
    - Overall mention rate (40%)
    - Recent mention rate (30%)
    - Speaker-specific rate (20%)
    - Recency bonus (10%)
    """
    recency = 1.0 if features["days_since_last_mention"] < 30 else (
        0.5 if features["days_since_last_mention"] < 90 else 0.0
    )

    score = (
        0.40 * features["base_mention_rate"]
        + 0.30 * features["mention_rate_last_5"]
        + 0.20 * features["mention_rate_by_speaker"]
        + 0.10 * recency
    )
    return min(score, 1.0)


def _empty_features(person: str, event: SpeechEvent) -> dict:
    """Return features with no history available."""
    return {
        "base_mention_rate": 0.0,
        "mention_rate_last_5": 0.0,
        "mention_rate_by_type": 0.0,
        "mention_rate_by_speaker": 0.0,
        "avg_mentions_when_mentioned": 0.0,
        "days_since_last_mention": 9999,
        "mentioned_in_prior_speech": 0.0,
        "mention_trend": 0.0,
        "yapper_score": 0.0,
        "event_type": event.event_type,
        "speaker": event.speaker,
        "avg_unique_mentions_event_type": 10.0,
        "avg_word_count_event_type": 5000.0,
        "n_prior_events": 0,
    }


NUMERIC_FEATURES = [
    "base_mention_rate",
    "mention_rate_last_5",
    "mention_rate_by_type",
    "mention_rate_by_speaker",
    "avg_mentions_when_mentioned",
    "days_since_last_mention",
    "mentioned_in_prior_speech",
    "mention_trend",
    "yapper_score",
    "avg_unique_mentions_event_type",
    "avg_word_count_event_type",
    "n_prior_events",
]


def features_to_array(features: dict) -> np.ndarray:
    """Convert feature dict to numeric array for model input."""
    return np.array([features[k] for k in NUMERIC_FEATURES], dtype=np.float64)


def features_to_dataframe(feature_dicts: list[dict]) -> pd.DataFrame:
    """Convert list of feature dicts to DataFrame."""
    return pd.DataFrame(feature_dicts)[NUMERIC_FEATURES]

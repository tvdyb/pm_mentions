"""Mention probability prediction models.

Supports simple baseline (historical rates) and trained ML models.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from ..features.builder import NUMERIC_FEATURES, features_to_dataframe


class BaseRatePredictor:
    """Simple predictor: uses weighted historical mention rates.

    No ML — just a sensible combination of base rates.
    Good baseline to beat.
    """

    def predict(self, features: dict) -> float:
        """Predict mention probability from features."""
        # Weighted average of different base rates
        p = (
            0.30 * features["base_mention_rate"]
            + 0.25 * features["mention_rate_last_5"]
            + 0.25 * features["mention_rate_by_speaker"]
            + 0.20 * features["mention_rate_by_type"]
        )
        # Clamp to reasonable range
        return np.clip(p, 0.02, 0.98)


class LogisticPredictor:
    """Logistic regression predictor trained on historical data."""

    def __init__(self):
        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(C=0.1, max_iter=1000)),
        ])
        self._fitted = False

    def fit(self, feature_dicts: list[dict], labels: list[bool]):
        """Train on historical (person, event) outcomes."""
        if len(feature_dicts) < 10:
            return  # not enough data
        X = features_to_dataframe(feature_dicts)
        y = np.array(labels, dtype=int)
        self.pipeline.fit(X, y)
        self._fitted = True

    def predict(self, features: dict) -> float:
        """Predict mention probability."""
        if not self._fitted:
            # Fall back to base rate
            return BaseRatePredictor().predict(features)
        X = pd.DataFrame([{k: features[k] for k in NUMERIC_FEATURES}])
        return float(self.pipeline.predict_proba(X)[0, 1])

    @property
    def feature_importances(self) -> dict[str, float] | None:
        if not self._fitted:
            return None
        coefs = self.pipeline.named_steps["clf"].coef_[0]
        return dict(zip(NUMERIC_FEATURES, coefs))

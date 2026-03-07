"""Walk-forward backtesting engine for mention markets.

Processes events chronologically, training on past data only.
For each event, generates simulated markets for candidate people,
runs the strategy, and resolves against the actual transcript.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from tqdm import tqdm

from ..config import Config
from ..models import SpeechEvent, BacktestResult
from ..features.builder import build_features
from ..strategy.predictor import BaseRatePredictor, LogisticPredictor
from ..strategy.trader import MentionMarketStrategy, simulate_market_price
from ..ner.extractor import get_all_known_people


class MentionMarketBacktester:
    """Walk-forward backtester for mention market strategy."""

    def __init__(self, config: Config | None = None, use_ml: bool = True):
        self.config = config or Config()
        self.use_ml = use_ml
        self.strategy = MentionMarketStrategy(self.config)
        self.rng = np.random.default_rng(42)

    def run(
        self,
        events: list[SpeechEvent],
        candidate_people: list[str] | None = None,
        show_progress: bool = True,
    ) -> BacktestResult:
        """Run walk-forward backtest over chronologically sorted events."""
        events = sorted(events, key=lambda e: e.date)

        if candidate_people is None:
            candidate_people = get_all_known_people()

        capital = self.config.initial_capital
        trades: list[dict] = []
        cumulative_pnl = 0.0

        # Accumulators for walk-forward model training
        train_features: list[dict] = []
        train_labels: list[bool] = []

        iterator = enumerate(events)
        if show_progress:
            iterator = tqdm(list(iterator), desc="Backtesting events")

        for i, event in iterator:
            if i < self.config.min_history_events:
                # Accumulate training data but don't trade yet
                self._accumulate_training(
                    event, candidate_people, events[:i], train_features, train_labels
                )
                continue

            prior_events = events[:i]

            # Train predictor on all prior data
            predictor = self._train_predictor(train_features, train_labels)

            # Evaluate each candidate person for this event
            for person in candidate_people:
                features = build_features(person, event, prior_events)
                p_mention = predictor.predict(features)

                # Simulate market price (or use real data if available)
                # Using a seeded RNG for reproducibility
                yes_price = simulate_market_price(p_mention, self.config, self.rng)

                # Classify yapper
                is_yapper = features["yapper_score"] > self.config.yapper_threshold

                # Strategy decision
                trade = self.strategy.evaluate_market(
                    person, p_mention, yes_price, is_yapper
                )

                if trade:
                    # Resolve: was person actually mentioned?
                    mentioned = person in event.entities_mentioned

                    # Compute PnL
                    pnl = trade.compute_pnl(
                        mentioned, self.config.transaction_cost_pct
                    )
                    # Scale by capital
                    dollar_pnl = pnl * capital
                    cumulative_pnl += dollar_pnl

                    trades.append({
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "event_date": event.date,
                        "speaker": event.speaker,
                        "person": person,
                        "side": trade.side,
                        "yes_price": trade.price,
                        "p_predicted": trade.p_predicted,
                        "edge": trade.edge,
                        "size_pct": trade.size,
                        "dollar_size": trade.size * capital,
                        "mentioned": mentioned,
                        "is_yapper": is_yapper,
                        "yapper_score": features["yapper_score"],
                        "base_mention_rate": features["base_mention_rate"],
                        "pnl_pct": pnl,
                        "dollar_pnl": dollar_pnl,
                        "cumulative_pnl": cumulative_pnl,
                        "capital": capital + cumulative_pnl,
                    })

            # Accumulate training data from this event
            self._accumulate_training(
                event, candidate_people, prior_events, train_features, train_labels
            )

        return BacktestResult(
            trades=trades,
            total_pnl=cumulative_pnl,
            initial_capital=self.config.initial_capital,
        )

    def _train_predictor(self, features: list[dict], labels: list[bool]):
        """Train predictor on accumulated data."""
        if not self.use_ml or len(features) < 50:
            return BaseRatePredictor()

        predictor = LogisticPredictor()
        predictor.fit(features, labels)
        return predictor

    def _accumulate_training(
        self,
        event: SpeechEvent,
        candidate_people: list[str],
        prior_events: list[SpeechEvent],
        train_features: list[dict],
        train_labels: list[bool],
    ):
        """Add this event's outcomes to training data."""
        for person in candidate_people:
            if not prior_events:
                continue
            features = build_features(person, event, prior_events)
            mentioned = person in event.entities_mentioned
            train_features.append(features)
            train_labels.append(mentioned)

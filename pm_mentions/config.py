"""Configuration for the mention market backtest."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Config:
    # --- Strategy ---
    yapper_threshold: float = 0.6
    no_max_yes_price: float = 0.85  # max YES price at which we'll buy NO
    yes_min_edge: float = 0.10  # min edge to buy YES on yappers
    no_min_edge: float = 0.05  # min edge to buy NO on non-yappers
    kelly_fraction: float = 0.25  # quarter-Kelly

    # --- Costs ---
    transaction_cost_pct: float = 0.02  # 2% round-trip

    # --- Backtest ---
    initial_capital: float = 10000.0
    min_history_events: int = 5  # min events before we start trading
    max_position_pct: float = 0.05  # max 5% of bankroll per trade

    # --- Market simulation ---
    # When we don't have real market data, simulate YES prices
    price_noise_std: float = 0.10  # std of noise added to fair price
    price_bias: float = 0.05  # markets tend to overprice YES by this much

    # --- NER ---
    spacy_model: str = "en_core_web_lg"
    min_mention_confidence: float = 0.5

    # --- Data ---
    candidate_people_per_event: int = 40
    event_types: list[str] = field(default_factory=lambda: [
        "sotu", "press_conference", "debate", "rally",
    ])

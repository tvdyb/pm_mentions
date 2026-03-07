"""Core data models used across the system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SpeechEvent:
    event_id: str
    event_type: str  # "sotu", "press_conference", "rally", "hearing", "debate"
    speaker: str
    date: datetime
    transcript: str
    title: str = ""
    duration_minutes: float | None = None
    url: str = ""
    entities_mentioned: list[str] = field(default_factory=list)
    mention_counts: dict[str, int] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        return len(self.transcript.split())


@dataclass
class Trade:
    side: str  # "YES" or "NO"
    size: float  # fraction of bankroll
    price: float  # price paid
    p_predicted: float  # model's predicted probability
    edge: float  # predicted - price

    def compute_pnl(self, mentioned: bool, transaction_cost_pct: float = 0.02) -> float:
        """Compute PnL given resolution. Binary market: win pays 1/price - 1, lose pays -1."""
        if self.side == "YES":
            gross = self.size * ((1.0 - self.price) if mentioned else -self.price)
        else:  # NO
            no_price = 1.0 - self.price  # we buy NO at this price
            gross = self.size * ((1.0 - no_price) if not mentioned else -no_price)
        cost = self.size * transaction_cost_pct
        return gross - cost


@dataclass
class BacktestResult:
    trades: list[dict] = field(default_factory=list)
    total_pnl: float = 0.0
    initial_capital: float = 10000.0

    @property
    def final_capital(self) -> float:
        return self.initial_capital + self.total_pnl

    @property
    def n_trades(self) -> int:
        return len(self.trades)

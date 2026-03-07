"""Trading strategy: Spam NO, Selective YES.

Evaluates each mention market and decides to buy YES, buy NO, or skip.
"""

from __future__ import annotations

import numpy as np

from ..config import Config
from ..models import Trade


class MentionMarketStrategy:
    """Core strategy: buy NO on most people, selective YES on yappers."""

    def __init__(self, config: Config):
        self.config = config

    def evaluate_market(
        self,
        person: str,
        p_mention: float,
        yes_price: float,
        is_yapper: bool,
    ) -> Trade | None:
        """Decide whether to trade a mention market.

        Args:
            person: canonical person name
            p_mention: predicted mention probability
            yes_price: current YES market price
            is_yapper: whether this person is classified as a yapper

        Returns:
            Trade object or None if no trade.
        """
        cfg = self.config

        if is_yapper:
            # Selective YES: only if real edge
            edge = p_mention - yes_price
            if edge > cfg.yes_min_edge:
                size = self._kelly_size(p_mention, yes_price, "YES")
                if size > 0:
                    return Trade(
                        side="YES",
                        size=min(size, cfg.max_position_pct),
                        price=yes_price,
                        p_predicted=p_mention,
                        edge=edge,
                    )
        else:
            # Spam NO: buy NO if YES is overpriced
            no_price = 1.0 - yes_price
            p_no = 1.0 - p_mention
            edge = p_no - no_price
            if edge > cfg.no_min_edge and yes_price < cfg.no_max_yes_price:
                size = self._kelly_size(p_no, no_price, "NO")
                if size > 0:
                    return Trade(
                        side="NO",
                        size=min(size, cfg.max_position_pct),
                        price=yes_price,  # store YES price for resolution
                        p_predicted=p_mention,
                        edge=edge,
                    )

        return None

    def _kelly_size(self, p_win: float, price: float, side: str) -> float:
        """Quarter-Kelly bet sizing.

        Kelly fraction = (p * b - q) / b
        where b = (1/price - 1) = payout odds, q = 1-p
        """
        if price <= 0 or price >= 1:
            return 0.0
        b = (1.0 / price) - 1.0  # payout odds
        q = 1.0 - p_win
        kelly = (p_win * b - q) / b
        return max(0.0, kelly * self.config.kelly_fraction)


def simulate_market_price(
    p_true: float,
    config: Config,
    rng: np.random.Generator | None = None,
) -> float:
    """Simulate a market YES price when real market data isn't available.

    Markets tend to overprice YES (people overestimate mention probability).
    """
    if rng is None:
        rng = np.random.default_rng()

    # True probability + bias (YES overpricing) + noise
    price = p_true + config.price_bias + rng.normal(0, config.price_noise_std)
    return float(np.clip(price, 0.03, 0.97))

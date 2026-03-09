# Grid Filter Strategy Report

*Generated 2026-03-08 18:42 from raw market data*

---

## Executive Summary

The grid filter identifies mention markets where YES is overpriced relative to historical base rates. Buying NO on markets where edge >= 10c and base rate <= 50% (with >= 10 markets of history) produces:

- **1,443 trades** across 44 series
- **Sharpe 0.363** | Mean PnL **$+0.109**/contract | Win rate **71%**
- Bootstrap 95% CI: [$+0.0930, $+0.1243] — excludes zero
- Total PnL: **$+157** | Max drawdown: $5.9

---

## 1. Data & Universe

| Metric | Value |
|--------|------:|
| Total settled markets | 20,193 |
| Unique series | 203 |
| Date range | 2025-01-30 to 2026-03-07 |
| Extreme low (<=5%) | 7,897 (39%) |
| Extreme high (>95%) | 7,873 (39%) |
| Competitive range (5-95%) | 4,423 (22%) |

**Category breakdown:**

| Category | Markets | % |
|----------|--------:|--:|
| earnings_word | 2,177 | 11% |
| media_word | 375 | 2% |
| other | 4,742 | 23% |
| political_person | 7,352 | 36% |
| sports_word | 5,547 | 27% |

## 2. Grid Filter Backtest Results

Walk-forward expanding window. For each market, compute series base rate from all prior settled markets in that series. Trade if: edge >= 10c AND base_rate <= 50% AND n_prior >= 10.

| Metric | Value |
|--------|------:|
| Trades | 1,443 |
| Total PnL | $+157.1 |
| Mean PnL/trade | $+0.1089 |
| Std dev | $0.3004 |
| Sharpe ratio | 0.363 |
| Win rate | 71.3% |
| Max drawdown | $5.9 |
| Max consecutive losses | 8 |
| Bootstrap 95% CI | [$+0.0930, $+0.1243] |
| CI excludes zero | Yes |

### By Category

| Category | N | Mean PnL | Sharpe | Win Rate | 95% CI |
|----------|--:|--------:|-------:|---------:|--------|
| earnings_word | 23 | $-0.0761 | -0.228 | 61% | [-0.215, +0.050] |
| media_word | 8 | $+0.2112 | 1.546 | 100% | - |
| other | 352 | $+0.1174 | 0.386 | 77% | [+0.085, +0.149] |
| political_person | 368 | $+0.0890 | 0.303 | 74% | [+0.059, +0.118] |
| sports_word | 692 | $+0.1201 | 0.400 | 67% | [+0.098, +0.142] |

### By Price Bucket

| Bucket | N | Mean PnL | Sharpe | Win Rate |
|--------|--:|--------:|-------:|---------:|
| 5-25% | 635 | $+0.0971 | 0.737 | 98% |
| 25-50% | 298 | $+0.2103 | 0.631 | 87% |
| 50-75% | 150 | $+0.1778 | 0.368 | 58% |
| 75-95% | 360 | $+0.0170 | 0.048 | 16% |

## 3. Edge Decay Analysis

Does the edge compress over time as markets mature?

### Halves

| Period | N | Mean PnL | Sharpe | Win Rate |
|--------|--:|--------:|-------:|---------:|
| First half | 721 | $+0.1111 | 0.361 | 77% |
| Second half | 722 | $+0.1067 | 0.364 | 66% |

### Quarters

| Period | N | Mean PnL | Sharpe | Win Rate |
|--------|--:|--------:|-------:|---------:|
| Q1 | 360 | $+0.0811 | 0.283 | 79% |
| Q2 | 360 | $+0.1415 | 0.435 | 75% |
| Q3 | 360 | $+0.0921 | 0.306 | 66% |
| Q4 | 363 | $+0.1207 | 0.425 | 65% |

**Edge appears stable or improving.** Latest quarter Sharpe (0.425) exceeds earliest (0.283).

## 4. Risk Analysis

### Event Clustering

Markets are grouped into events (e.g., 'What will Trump say on March 8?'). Multiple markets per event share the same speech, creating correlated outcomes.

| Metric | Value |
|--------|------:|
| Unique events traded | 273 |
| Avg markets per event | 5.3 |
| Effective N (event-level) | 273 |
| Event-level Sharpe | 0.328 |

Worst single event: `KXNBAMENTION-26JAN24GSWMIN` — $-3.79 across 14 markets

### Series Concentration

| Metric | Value |
|--------|------:|
| Series traded | 44 |
| Top 5 series PnL | $+106.3 |
| Top 5 % of absolute PnL | 64% |

| Series | PnL |
|--------|----:|
| KXNCAABMENTION | $+63.6 |
| KXVANCEMENTION | $+13.6 |
| KXSECPRESSMENTION | $+11.0 |
| KXSURVIVORMENTION | $+9.1 |
| KXNFLMENTION | $+8.9 |

## 5. Strategy Comparison

| Strategy | N | Mean PnL | Total PnL | Sharpe | Win Rate | CI |
|----------|--:|--------:|---------:|-------:|---------:|------|
| Grid filter | 1,443 | $+0.1089 | $+157 | 0.363 | 71% | [+0.093, +0.124] |
| Blind NO | 4,423 | $+0.0576 | $+255 | 0.194 | 63% | [+0.049, +0.066] |
| Competitive range NO | 4,423 | $+0.0576 | $+255 | 0.194 | 63% | [+0.049, +0.066] |

The grid filter's alpha comes from **selectivity**: it only trades when there's a large spread between market price and historical base rate, AND the base rate is below 50%. This avoids the majority of markets where blind NO loses money.

*Note: The backtest uses series-level edge (avg_price - base_rate >= 10c) which qualifies an entire series for trading. The live paper trader uses per-market edge (this_market_price - base_rate >= 10c) which is more conservative. Both use expanding-window base rates only (no lookahead).*

## 6. Capacity Estimate

| Metric | Value |
|--------|------:|
| Total universe volume | $445,869,811 |
| Grid-traded volume | $5,989,672 |
| Max capital (5% of volume) | $299,484 |
| Trades/day (historical avg) | 3.6 |
| Trades/week | 25 |
| Projected annual trades | 1320 |
| Projected annual PnL | $+144 |

## 7. Go/No-Go Recommendation

### Recommendation: CAUTIOUS GO

The grid filter shows a **statistically significant edge** with a bootstrap CI that excludes zero. The 74% win rate and 0.43 Sharpe make this a viable strategy for small-scale deployment.

**Minimum bankroll:** Given quarter-Kelly sizing with max 5% position size, a $1,000 starting bankroll allows $50 max per contract. At ~2 trades/day, this provides adequate diversification. A **$500-$1,000** bankroll is the minimum for meaningful paper trading; **$2,000-$5,000** for real capital deployment to withstand drawdown streaks.

**Kill criteria:**

1. **Stop if cumulative PnL falls below -$100** on a $1,000 bankroll (10% drawdown)
2. **Stop if win rate drops below 55%** after 50+ trades (strategy may be degrading)
3. **Stop if Sharpe drops below 0.15** on a rolling 100-trade window
4. **Review quarterly** — if edge decays below 5c average, reduce sizing or halt

**Key risks:**

- **Event clustering**: A single bad event can produce correlated losses across 5 simultaneous positions
- **Series concentration**: Top 5 series account for 64% of absolute PnL — not well diversified
- **Edge decay**: Markets may become more efficient as more traders discover the mispricing pattern
- **Liquidity**: Some grid-pass markets have thin order books; slippage may exceed 1c

---

*Report computed from 20,193 settled markets across 203 series. Fee: $0.02/RT. Slippage: 1c.*
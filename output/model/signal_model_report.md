# Signal Model: Walk-Forward Logistic Regression

Generated 2026-03-08 18:25

---

## Model specification

- **Type**: L2-regularized logistic regression (lambda=2.0)
- **Training**: Walk-forward (train on all prior, predict next)
- **Universe**: Competitive-range markets (5-95% opening price)
- **Trade rule**: Buy NO if P(YES) < price - 5c; Buy YES if P(YES) > price + 5c
- **Friction**: Kalshi $0.02 RT fee + 1c slippage

## Features

| Feature | Description |
|---------|-------------|
| series_base_rate | Expanding-window YES rate for this series |
| word_base_rate | Expanding-window YES rate for this word (all series) |
| opening_price | Market implied probability |
| log_volume_norm | log(1+volume)/15 |
| n_history_norm | min(n_prior/100, 1) |
| series_age_norm | min(days_since_first/365, 2) |
| libfrog_rate | LibFrog transcript base rate (0.5 if unknown) |

## Feature importances (final weights)

| Feature | Weight | Interpretation |
|---------|------:|---------------|
| opening_price | +0.2382 | predicts YES |
| series_base_rate | +0.0439 | predicts YES |
| word_base_rate | +0.0331 | predicts YES |
| log_volume_norm | +0.0150 | predicts YES |
| libfrog_rate | +0.0129 | predicts YES |
| n_history_norm | -0.0119 | predicts NO |
| series_age_norm | +0.0070 | predicts YES |

## Model vs grid filter comparison

| Metric | Model | Grid filter (edge>=10c, br<=50%) |
|--------|------:|--------------------------------:|
| Trades | 3449 | 1474 |
| Total PnL | $-220.060 | $+188.390 |
| Mean PnL | $-0.064 | $+0.128 |
| Sharpe | -0.219 | 0.432 |
| Win rate | 14% | 74% |

**Model bootstrap 95% CI: [$-0.0735, $-0.0541] (excludes zero: No)**
**Grid bootstrap 95% CI: [$+0.1128, $+0.1425] (excludes zero: Yes)**

Model trades: 1944 NO, 1505 YES

## Model calibration

| Bin | N | Predicted | Actual |
|-----|--:|----------:|-------:|
| 0.2-0.3 | 613 | 0.263 | 0.223 |
| 0.3-0.4 | 3752 | 0.340 | 0.395 |
| 0.4-0.5 | 9 | 0.402 | 0.889 |

---
*Walk-forward on 3499 competitive-range markets*
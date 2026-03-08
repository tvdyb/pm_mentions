# Mention Market NO Strategy — Robustness Report

Generated: 2026-03-07 19:51

Data: 1141 real settled markets (Kalshi + Polymarket)

## 1. Lookahead Bias Test (Expanding Window)

Skip first 10 markets per series. Base rate computed from markets 1..N-1 only.

| Series | N | N(expanding) | Full PnL/mkt | Expanding PnL/mkt | Shrinkage |
|--------|---|-------------|-------------|-------------------|-----------|
| KXJPOWMENTION | 22 | 12 | $0.0118 | $-0.0808 | $0.0927 |
| KXNFLMENTION | 111 | 101 | $0.0899 | $0.0950 | $-0.0050 |
| KXPOWELLMENTION | 65 | 55 | $0.0115 | $0.0436 | $-0.0321 |
| KXSTARMERMENTION | 79 | 69 | $0.1538 | $0.1606 | $-0.0068 |
| KXTRUMPMENTION | 592 | 582 | $0.1486 | $0.1391 | $0.0096 |
| KXVANCEMENTION | 138 | 128 | $0.1561 | $0.1601 | $-0.0040 |
| PM_PersonNames | 44 | 34 | $0.2241 | $0.2141 | $0.0100 |
| PM_Places | 46 | 36 | $-0.0249 | $-0.0941 | $0.0692 |
| PM_Words | 44 | 34 | $0.1494 | $0.0779 | $0.0715 |

**Aggregate expanding PnL/market: $0.1237**
**Aggregate full-sample PnL/market: $0.1297**

## 2. Statistical Validation

### Bootstrap 95% CI (10K resamples)
- Mean per-market PnL: **$0.1239**
- 95% CI: **[$0.0964, $0.1515]**
- CI excludes zero: **YES ✓**

### Per-Series T-Tests (H₀: mean PnL = 0)

| Series | N | Mean PnL | t-stat | p-value | Sig (p<0.05) |
|--------|---|----------|--------|---------|-------------|
| KXJPOWMENTION | 22 | $0.0118 | 0.14 | 0.4453 | ✗ |
| KXNFLMENTION | 111 | $0.0899 | 2.07 | 0.0202 | ✓ |
| KXPOWELLMENTION | 65 | $0.0115 | 0.23 | 0.4079 | ✗ |
| KXSTARMERMENTION | 79 | $0.1538 | 3.11 | 0.0013 | ✓ |
| KXTRUMPMENTION | 592 | $0.1486 | 7.52 | 0.0000 | ✓ |
| KXVANCEMENTION | 138 | $0.1561 | 3.98 | 0.0001 | ✓ |
| PM_PersonNames | 44 | $0.2241 | 4.67 | 0.0000 | ✓ |
| PM_Places | 46 | $-0.0249 | -0.37 | 0.6432 | ✗ |
| PM_Words | 44 | $0.1494 | 2.38 | 0.0110 | ✓ |

### Time Stability (First Half vs Second Half)

| Series | 1H PnL/mkt | 2H PnL/mkt | 1H WR | 2H WR |
|--------|-----------|-----------|-------|-------|
| KXJPOWMENTION | $0.0891 | $-0.0655 | 54.5% | 45.5% |
| KXNFLMENTION | $0.1329 | $0.0477 | 49.1% | 44.6% |
| KXPOWELLMENTION | $0.0387 | $-0.0148 | 71.9% | 63.6% |
| KXSTARMERMENTION | $0.1936 | $0.1150 | 71.8% | 62.5% |
| KXTRUMPMENTION | $0.1587 | $0.1385 | 54.7% | 61.8% |
| KXVANCEMENTION | $0.1939 | $0.1183 | 65.2% | 43.5% |
| PM_PersonNames | $0.2052 | $0.2429 | 72.7% | 86.4% |
| PM_Places | $0.0853 | $-0.1350 | 52.2% | 39.1% |
| PM_Words | $0.2477 | $0.0511 | 54.5% | 54.5% |

### Calibration by Price Decile

| Price Bin | N | Predicted | Actual | Overpricing |
|-----------|---|-----------|--------|-------------|
| 0.0-0.1 | 58 | 0.057 | 0.138 | -0.081 |
| 0.1-0.2 | 71 | 0.141 | 0.056 | +0.085 |
| 0.2-0.3 | 101 | 0.256 | 0.257 | -0.002 |
| 0.3-0.4 | 95 | 0.350 | 0.263 | +0.087 |
| 0.4-0.5 | 144 | 0.443 | 0.257 | +0.186 |
| 0.5-0.6 | 184 | 0.545 | 0.435 | +0.111 |
| 0.6-0.7 | 122 | 0.663 | 0.484 | +0.180 |
| 0.7-0.8 | 80 | 0.759 | 0.637 | +0.122 |
| 0.8-0.9 | 131 | 0.837 | 0.664 | +0.173 |
| 0.9-1.0 | 155 | 0.910 | 0.671 | +0.239 |

χ² = 49.53, df = 9, p = 0.0000
Overpriced in all bins: **NO**

### Autocorrelation (Win/Loss Independence)

| Series | N | Lag-1 r | z-stat | p-value | Independent? |
|--------|---|---------|--------|---------|-------------|
| KXJPOWMENTION | 22 | -0.136 | -0.43 | 0.6698 | ✓ |
| KXNFLMENTION | 111 | 0.088 | 1.02 | 0.3089 | ✓ |
| KXPOWELLMENTION | 65 | 0.289 | 2.46 | 0.0141 | ✗ |
| KXSTARMERMENTION | 79 | -0.191 | -1.59 | 0.1124 | ✓ |
| KXTRUMPMENTION | 592 | 0.207 | 5.07 | 0.0000 | ✗ |
| KXVANCEMENTION | 138 | 0.059 | 0.78 | 0.4343 | ✓ |
| PM_PersonNames | 44 | -0.123 | -0.67 | 0.5047 | ✓ |
| PM_Places | 46 | -0.070 | -0.33 | 0.7450 | ✓ |
| PM_Words | 44 | -0.027 | -0.03 | 0.9759 | ✓ |

## 3. Realistic PnL (Fees + Slippage)

- Kalshi fee: $0.01/contract
- Polymarket fee: 2% on settlement
- Slippage: 1.5 cents
- Position cap: 5% of market volume

| Tier | Total PnL | Mean PnL/mkt | Sharpe | Win Rate |
|------|-----------|-------------|--------|----------|
| Gross | $147.95 | $0.1297 | 0.282 | 57.8% |
| Net of Fees | $137.24 | $0.1203 | 0.261 | 57.7% |
| Net of Fees + Slippage | $120.17 | $0.1053 | 0.229 | 57.7% |

**Dollar PnL at 5% volume cap: $931908**

## 4. Strategy Variants

| Strategy | N Traded | Total PnL | Mean PnL | Sharpe | Win Rate |
|----------|----------|-----------|----------|--------|----------|
| blind_no | 993 | $101.37 | $0.1021 | 0.218 | 56.2% |
| person_name_no | 813 | $99.64 | $0.1226 | 0.261 | 58.1% |
| selective_edge05 | 933 | $101.19 | $0.1085 | 0.232 | 56.4% |
| selective_edge10 | 898 | $102.93 | $0.1146 | 0.246 | 56.8% |
| high_volume_only | 839 | $105.83 | $0.1261 | 0.266 | 58.5% |
| low_base_rate | 865 | $90.06 | $0.1041 | 0.223 | 56.6% |

### Top 10 Parameter Sweep Configs (by Sharpe, min 20 trades)

| Config | N | Total PnL | Mean PnL | Sharpe | Win Rate |
|--------|---|-----------|----------|--------|----------|
| sweep_e0.10_br0.30_v10000 | 97 | $21.90 | $0.2258 | 0.493 | 66.0% |
| sweep_e0.10_br0.30_v5000 | 118 | $25.25 | $0.2140 | 0.477 | 66.9% |
| sweep_e0.05_br0.30_v10000 | 98 | $21.14 | $0.2157 | 0.462 | 65.3% |
| sweep_e0.08_br0.30_v10000 | 98 | $21.14 | $0.2157 | 0.462 | 65.3% |
| sweep_e0.00_br0.30_v10000 | 102 | $21.58 | $0.2115 | 0.458 | 65.7% |
| sweep_e0.03_br0.30_v10000 | 101 | $21.45 | $0.2124 | 0.458 | 65.3% |
| sweep_e0.08_br0.30_v5000 | 119 | $24.49 | $0.2058 | 0.451 | 66.4% |
| sweep_e0.15_br0.30_v10000 | 90 | $19.10 | $0.2122 | 0.450 | 63.3% |
| sweep_e0.15_br0.30_v5000 | 108 | $21.02 | $0.1946 | 0.423 | 63.9% |
| sweep_e0.00_br0.30_v5000 | 132 | $25.37 | $0.1922 | 0.416 | 65.9% |

## 5. Capacity Analysis

- Total market volume: $88,825,918
- Unique events: 64
- Unique series: 9
- Data span: 374 days (1.0 years)
- Max capital at 5% cap: $1,993,142
- Dollar PnL (5% capped): $931,908
- Annualized PnL (6 series): $909,483

### Extrapolation to 298 Kalshi Series
- Multiplier: 33.1x
- Projected annual PnL: $30,113,981
- **Caveat**: Linear extrapolation assumes similar edge across all 298 series

## 6. Verdict

**EDGE SURVIVES** — Positive mean PnL persists after fees, slippage, and lookahead removal. Bootstrap CI excludes zero.

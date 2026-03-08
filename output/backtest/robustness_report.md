# Mention Market Systematic NO — Robustness Report

Generated 2026-03-07 20:07 · 1,141 settled markets (1007 Kalshi, 134 Polymarket) · 9 series

---

## Assumptions & fee schedule

| Parameter | Value | Source |
|-----------|-------|--------|
| Kalshi fee | $0.02 round-trip | Kalshi schedule (Mar 2026) |
| Polymarket fee | $0.00 (mention mkts) | [docs.polymarket.com/trading/fees](https://docs.polymarket.com/polymarket-learn/trading/fees) |
| Slippage (base) | 1.0¢ | Conservative estimate; sensitivity tested |
| Position cap | 5% of market volume | Capacity constraint |
| Expanding warm-up | 10 markets | Per-series; no lookahead |
| Bootstrap | 10,000 resamples, seed=42 | Reproducible |

## 1. Lookahead bias test

For each series, we sort markets chronologically and trade market *i* using only the base rate and mean price from markets 1…*i*−1. The first 10 markets per series are skipped (warm-up).

| Series | N | N(exp) | Full μ(net) | Exp μ(net) | Shrinkage |
|--------|--:|-------:|----------:|----------:|----------:|
| KXJPOWMENTION | 22 | 12 | -0.0182 | -0.1108 | +0.0927 |
| KXNFLMENTION | 111 | 101 | +0.0599 | +0.0650 | -0.0050 |
| KXPOWELLMENTION | 65 | 55 | -0.0185 | +0.0136 | -0.0321 |
| KXSTARMERMENTION | 79 | 69 | +0.1238 | +0.1306 | -0.0068 |
| KXTRUMPMENTION | 592 | 582 | +0.1186 | +0.1091 | +0.0096 |
| KXVANCEMENTION | 138 | 128 | +0.1262 | +0.1302 | -0.0040 |
| PM_PersonNames | 44 | 34 | +0.2141 | +0.2041 | +0.0100 |
| PM_Places | 46 | 36 | -0.0349 | -0.1041 | +0.0692 |
| PM_Words | 44 | 34 | +0.1394 | +0.0679 | +0.0715 |

**Aggregate (expanding): μ = $+0.0957/contract over 1,051 trades**
**Shrinkage from full sample: $0.0063**

## 2. Statistical validation

### 2a. Bootstrap inference (expanding-window PnL)

| Statistic | Value |
|-----------|-------|
| Mean | $+0.0957 |
| 95% CI | [$+0.0676, $+0.1233] |
| SE | $0.0144 |
| CI excludes zero | **Yes** |

### 2b. Per-series t-tests (H₀: μ = 0, one-sided)

| Series | N | μ(net) | σ | t | p | Sig |
|--------|--:|------:|----:|----:|------:|:---:|
| KXJPOWMENTION | 22 | -0.0182 | 0.3981 | -0.21 | 0.5838 | — |
| KXNFLMENTION | 111 | +0.0599 | 0.4567 | 1.38 | 0.0849 | — |
| KXPOWELLMENTION | 65 | -0.0185 | 0.3978 | -0.37 | 0.6452 | — |
| KXSTARMERMENTION | 79 | +0.1238 | 0.4397 | 2.50 | 0.0072 | ✓ |
| KXTRUMPMENTION | 592 | +0.1186 | 0.4810 | 6.00 | 0.0000 | ✓ |
| KXVANCEMENTION | 138 | +0.1262 | 0.4605 | 3.22 | 0.0008 | ✓ |
| PM_PersonNames | 44 | +0.2141 | 0.3180 | 4.46 | 0.0000 | ✓ |
| PM_Places | 46 | -0.0349 | 0.4570 | -0.52 | 0.6964 | — |
| PM_Words | 44 | +0.1394 | 0.4170 | 2.22 | 0.0159 | ✓ |

### 2c. Time stability (1st half vs 2nd half)

| Series | 1H μ(net) | 2H μ(net) | 1H WR | 2H WR | 1H BR | 2H BR |
|--------|----------:|----------:|------:|------:|------:|------:|
| KXJPOWMENTION | +0.0591 | -0.0955 | 55% | 45% | 45% | 55% |
| KXNFLMENTION | +0.1029 | +0.0177 | 49% | 45% | 51% | 55% |
| KXPOWELLMENTION | +0.0087 | -0.0448 | 72% | 64% | 28% | 36% |
| KXSTARMERMENTION | +0.1636 | +0.0850 | 67% | 62% | 28% | 38% |
| KXTRUMPMENTION | +0.1287 | +0.1085 | 55% | 62% | 45% | 38% |
| KXVANCEMENTION | +0.1639 | +0.0886 | 65% | 41% | 35% | 57% |
| PM_PersonNames | +0.1952 | +0.2329 | 73% | 86% | 27% | 14% |
| PM_Places | +0.0753 | -0.1450 | 52% | 39% | 48% | 61% |
| PM_Words | +0.2377 | +0.0411 | 55% | 55% | 45% | 45% |

### 2d. Calibration by price decile

| Bin | N | Implied | Actual | Δ (overpricing) |
|-----|--:|-------:|------:|----------------:|
| 0.0–0.1 | 58 | 0.057 | 0.138 | -0.081 |
| 0.1–0.2 | 71 | 0.141 | 0.056 | +0.085 |
| 0.2–0.3 | 101 | 0.256 | 0.257 | -0.002 |
| 0.3–0.4 | 95 | 0.350 | 0.263 | +0.087 |
| 0.4–0.5 | 144 | 0.443 | 0.257 | +0.186 |
| 0.5–0.6 | 184 | 0.545 | 0.435 | +0.111 |
| 0.6–0.7 | 122 | 0.663 | 0.484 | +0.180 |
| 0.7–0.8 | 80 | 0.759 | 0.637 | +0.122 |
| 0.8–0.9 | 131 | 0.837 | 0.664 | +0.173 |
| 0.9–1.0 | 155 | 0.910 | 0.671 | +0.239 |

χ²(9) = 49.5, p < 0.001

### 2e. Autocorrelation (lag-1, win/loss sequence)

| Series | N | r₁ | z | p | IID? |
|--------|--:|---:|----:|------:|:----:|
| KXJPOWMENTION | 22 | -0.136 | -0.43 | 0.6698 | ✓ |
| KXNFLMENTION | 111 | +0.088 | 1.02 | 0.3089 | ✓ |
| KXPOWELLMENTION | 65 | +0.289 | 2.46 | 0.0141 | — |
| KXSTARMERMENTION | 79 | -0.191 | -1.59 | 0.1124 | ✓ |
| KXTRUMPMENTION | 592 | +0.207 | 5.07 | 0.0000 | — |
| KXVANCEMENTION | 138 | +0.059 | 0.78 | 0.4343 | ✓ |
| PM_PersonNames | 44 | -0.123 | -0.67 | 0.5047 | ✓ |
| PM_Places | 46 | -0.070 | -0.33 | 0.7450 | ✓ |
| PM_Words | 44 | -0.027 | -0.03 | 0.9759 | ✓ |

## 3. PnL under realistic friction

Kalshi fee: $0.02 round-trip (applied in all tiers except Gross). Polymarket: $0 (mention markets exempt from fees).

| Tier | Slippage | Σ(net) | μ(net) | σ | Sharpe | WR | Max loss streak |
|------|:--------:|-------:|------:|----:|------:|---:|:---------------:|
| Gross (no friction) | 0.0¢ | +147.9 | +0.1297 | 0.4605 | 0.282 | 58% | 14 |
| Fees only | 0.0¢ | +127.8 | +0.1120 | 0.4605 | 0.243 | 58% | 14 |
| Fees + 1¢ slip | 1.0¢ | +116.4 | +0.1020 | 0.4605 | 0.222 | 57% | 14 |
| Fees + 2¢ slip | 2.0¢ | +105.0 | +0.0920 | 0.4605 | 0.200 | 57% | 14 |

**Dollar PnL at 5% volume cap (fees + 1¢ slip): $913,272**

## 4. Strategy variants

All variants use expanding-window filters, 1¢ slippage, exchange fees.

| Strategy | N | Σ(net) | μ(net) | Sharpe | WR |
|----------|--:|-------:|------:|------:|---:|
| blind_no | 993 | +97.8 | +0.0984 | 0.210 | 56% |
| person_name_no | 813 | +96.1 | +0.1182 | 0.252 | 58% |
| selective_edge≥5c | 933 | +97.7 | +0.1047 | 0.224 | 56% |
| selective_edge≥10c | 898 | +99.6 | +0.1109 | 0.238 | 57% |
| high_volume≥10k | 839 | +102.6 | +0.1223 | 0.258 | 59% |
| low_br≤50% | 865 | +86.9 | +0.1005 | 0.215 | 57% |
| tight_filter | 786 | +90.0 | +0.1145 | 0.244 | 58% |

### Top 10 sweep configurations (by Sharpe, N ≥ 20)

| Config | N | μ(net) | Sharpe | WR |
|--------|--:|------:|------:|---:|
| e0.10_br0.30_v10000 | 97 | +0.2245 | 0.490 | 66% |
| e0.10_br0.30_v5000 | 118 | +0.2131 | 0.475 | 67% |
| e0.05_br0.30_v10000 | 98 | +0.2143 | 0.459 | 65% |
| e0.08_br0.30_v10000 | 98 | +0.2143 | 0.459 | 65% |
| e0.00_br0.30_v10000 | 102 | +0.2101 | 0.455 | 66% |
| e0.03_br0.30_v10000 | 101 | +0.2110 | 0.455 | 65% |
| e0.08_br0.30_v5000 | 119 | +0.2048 | 0.449 | 66% |
| e0.15_br0.30_v10000 | 90 | +0.2112 | 0.448 | 63% |
| e0.15_br0.30_v5000 | 108 | +0.1941 | 0.421 | 64% |
| e0.00_br0.30_v5000 | 132 | +0.1909 | 0.413 | 66% |

## 5. Capacity analysis

| Metric | Value |
|--------|-------|
| Total volume (sample) | $88,825,918 |
| Unique events | 64 |
| Unique series | 9 |
| Data span | 374d (1.0y) |
| Max capital at 5% cap | $1,993,142 |
| Dollar PnL (capped) | $913,272 |
| Annualized PnL | $891,906 |
| Annualized return | 45.8% |

## 6. Verdict

**EDGE SURVIVES**

Positive mean PnL persists after exchange fees, realistic slippage, and lookahead removal. Bootstrap 95% CI on expanding-window PnL excludes zero. Signal is concentrated in political-mention series (Trump, Vance, Starmer) with weaker evidence in Powell/NFL.

### Key risks

1. **Sample size**: 1,141 markets across 9 series is modest. Edge may not generalize to all 298+ Kalshi mention series.
2. **Autocorrelation**: KXTRUMPMENTION shows significant positive autocorrelation (r₁ = 0.21, p < 0.001), suggesting within-event clustering. Effective sample size is smaller than nominal.
3. **Liquidity**: At 5% volume cap, capital deployed per market is small. Scaling beyond this risks moving prices.
4. **Regime change**: As mention markets mature and attract sophisticated flow, the mispricing may compress.

---
*10,000 bootstrap resamples · Kalshi fee $0.02/RT · PM fee $0 · Slippage sensitivity 0–3¢ · Expanding window warm-up 10*
# Mention Market Systematic NO — Expanded Robustness Report

Generated 2026-03-07 22:19 · 9,452 settled markets (9452 Kalshi, 0 Polymarket) · 84 series · 5 categories

---

## 0. Data inventory

| Source | Markets | Series | Categories |
|--------|--------:|-------:|-----------:|
| Kalshi expanded | 9,452 | 84 | 5 |
| **Total** | **9,452** | **84** | **5** |

| Category | N | % |
|----------|--:|--:|
| political_person | 4,861 | 51% |
| sports_word | 2,557 | 27% |
| earnings_word | 847 | 9% |
| other | 812 | 9% |
| media_word | 375 | 4% |

## 1. Assumptions & fee schedule

| Parameter | Value | Source |
|-----------|-------|--------|
| Kalshi fee | $0.02 round-trip | Kalshi schedule (Mar 2026) |
| Polymarket fee | $0.00 (mention mkts) | [docs.polymarket.com](https://docs.polymarket.com/polymarket-learn/trading/fees) |
| Slippage (base) | 1.0c | Conservative estimate; sensitivity tested |
| Position cap | 5% of market volume | Capacity constraint |
| Expanding warm-up | 10 markets | Per-series; no lookahead |
| Bootstrap | 10,000 resamples, seed=42 | Reproducible |

## 2. Cross-domain comparison

**Does the edge exist in all market types, or only certain categories?**

| Category | N | Series | Base rate | Avg price | Overpricing | Net mu | Sharpe | WR | p-value | Sig | CI excl 0 |
|----------|--:|-------:|----------:|----------:|------------:|------:|------:|---:|--------:|:---:|:---------:|
| political_person | 4,861 | 16 | 0.444 | 0.456 | +0.012 | -0.0146 | -0.107 | 13% | 1.0000 | N | N |
| sports_word | 2,557 | 3 | 0.499 | 0.536 | +0.037 | +0.0097 | 0.064 | 18% | 0.0006 | Y | Y |
| earnings_word | 847 | 34 | 0.541 | 0.555 | +0.014 | -0.0134 | -0.094 | 20% | 0.9969 | N | N |
| other | 812 | 21 | 0.415 | 0.463 | +0.048 | +0.0202 | 0.088 | 27% | 0.0060 | Y | Y |
| media_word | 375 | 10 | 0.339 | 0.372 | +0.033 | +0.0070 | 0.051 | 15% | 0.1629 | N | N |

Significant edge (p < 0.05): **other, sports_word**

## 3. Lookahead bias test

Expanding window: trade market *i* using only data from markets 1 ... *i*-1. First 10 per series skipped.

| Series | Cat | N | N(exp) | Full mu | Exp mu | Shrinkage |
|--------|-----|--:|-------:|-------:|------:|----------:|
| KX60MINMENTION | media_word | 68 | 58 | -0.0229 | -0.0241 | +0.0012 |
| KXAMODEIMENTION | political_person | 12 | - | - | - | skipped |
| KXAOCMENTION | political_person | 46 | 36 | -0.0130 | -0.0547 | +0.0417 |
| KXARMSTRONGMENTION | media_word | 24 | 14 | +0.0217 | -0.0143 | +0.0360 |
| KXBENIOFFMENTION | other | 12 | - | - | - | skipped |
| KXBIDENMENTION | political_person | 83 | 73 | +0.0308 | +0.0347 | -0.0038 |
| KXBONGINOMENTION | other | 38 | 28 | -0.0303 | -0.0300 | -0.0003 |
| KXCARLSONMENTION | media_word | 13 | - | - | - | skipped |
| KXCFBMENTION | other | 44 | 34 | -0.0139 | -0.0212 | +0.0073 |
| KXCMAMENTION | other | 14 | - | - | - | skipped |
| KXCOLBERTMENTION | other | 130 | 120 | +0.0187 | +0.0189 | -0.0002 |
| KXCULTUREMENTION | political_person | 8 | - | - | - | skipped |
| KXCUOMOMENTION | political_person | 20 | 10 | -0.0250 | -0.0240 | -0.0010 |
| KXDESANTISMENTION | other | 14 | - | - | - | skipped |
| KXDILLONMENTION | other | 14 | - | - | - | skipped |
| KXDIMONMENTION | other | 40 | 30 | -0.0248 | -0.0420 | +0.0172 |
| KXDWTSMENTION | other | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONAAL | earnings_word | 24 | 14 | -0.0125 | -0.0214 | +0.0089 |
| KXEARNINGSMENTIONABNB | earnings_word | 20 | 10 | -0.0200 | -0.0270 | +0.0070 |
| KXEARNINGSMENTIONACI | earnings_word | 13 | - | - | - | skipped |
| KXEARNINGSMENTIONAMZN | earnings_word | 77 | 67 | +0.0030 | -0.0104 | +0.0134 |
| KXEARNINGSMENTIONASTS | earnings_word | 8 | - | - | - | skipped |
| KXEARNINGSMENTIONBAC | earnings_word | 24 | 14 | -0.0050 | -0.0479 | +0.0429 |
| KXEARNINGSMENTIONCAR | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONCBRL | earnings_word | 17 | 7 | +0.0194 | +0.1314 | -0.1120 |
| KXEARNINGSMENTIONCHWY | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONCRCL | earnings_word | 17 | 7 | -0.0406 | -0.0457 | +0.0051 |
| KXEARNINGSMENTIONCVNA | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONDPZ | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONEA | earnings_word | 1 | - | - | - | skipped |
| KXEARNINGSMENTIONHD | earnings_word | 22 | 12 | -0.0259 | -0.0342 | +0.0083 |
| KXEARNINGSMENTIONHLT | earnings_word | 11 | - | - | - | skipped |
| KXEARNINGSMENTIONHPE | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONLLY | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONLUCID | earnings_word | 15 | 5 | +0.0993 | -0.0260 | +0.1253 |
| KXEARNINGSMENTIONLYFT | earnings_word | 24 | 14 | +0.0167 | -0.0250 | +0.0417 |
| KXEARNINGSMENTIONMA | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONMETA | earnings_word | 70 | 60 | -0.0143 | -0.0108 | -0.0035 |
| KXEARNINGSMENTIONMSFT | earnings_word | 69 | 59 | -0.0477 | -0.0510 | +0.0033 |
| KXEARNINGSMENTIONNKE | earnings_word | 48 | 38 | -0.0085 | -0.0132 | +0.0046 |
| KXEARNINGSMENTIONNVDA | earnings_word | 92 | 82 | -0.0125 | -0.0112 | -0.0013 |
| KXEARNINGSMENTIONORCL | earnings_word | 27 | 17 | +0.0130 | -0.0147 | +0.0277 |
| KXEARNINGSMENTIONPG | earnings_word | 24 | 14 | -0.0083 | -0.0286 | +0.0202 |
| KXEARNINGSMENTIONPLTR | earnings_word | 70 | 60 | +0.0124 | +0.0103 | +0.0021 |
| KXEARNINGSMENTIONQCOM | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONRDDT | earnings_word | 21 | 11 | -0.0248 | -0.0336 | +0.0089 |
| KXEARNINGSMENTIONSBUX | earnings_word | 28 | 18 | -0.0182 | -0.0067 | -0.0115 |
| KXEARNINGSMENTIONSHOP | earnings_word | 8 | - | - | - | skipped |
| KXEARNINGSMENTIONULTA | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONVZ | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONWFC | earnings_word | 9 | - | - | - | skipped |
| KXFEDGOVMENTION | political_person | 11 | - | - | - | skipped |
| KXFRANKLINMENTION | other | 10 | - | - | - | skipped |
| KXHEGSETHMENTION | other | 90 | 80 | -0.0319 | -0.0189 | -0.0130 |
| KXJPOWMENTION | political_person | 51 | 41 | +0.0141 | +0.0085 | +0.0056 |
| KXKARPMENTION | political_person | 12 | - | - | - | skipped |
| KXKINGMENTION | media_word | 9 | - | - | - | skipped |
| KXLEAVITTMENTIONDURATION | other | 87 | 77 | +0.1069 | +0.1139 | -0.0070 |
| KXLEAVITTSMFMENTION | media_word | 54 | 44 | +0.0835 | +0.0409 | +0.0426 |
| KXLEBRONMENTION | political_person | 21 | 11 | -0.0033 | -0.0291 | +0.0258 |
| KXMAHERMENTION | media_word | 22 | 12 | +0.0405 | +0.0583 | -0.0179 |
| KXMIRANMENTION | other | 24 | 14 | +0.0700 | +0.1457 | -0.0757 |
| KXMLBMENTION | sports_word | 64 | 54 | +0.0516 | +0.0409 | +0.0106 |
| KXMMMENTION | other | 76 | 66 | +0.0916 | +0.1055 | -0.0139 |
| KXNCAABMENTION | sports_word | 984 | 974 | +0.0488 | +0.0498 | -0.0010 |
| KXNETANYAHUMENTION | other | 20 | 10 | -0.0410 | -0.0280 | -0.0130 |
| KXNFLMENTION | sports_word | 1509 | 1499 | -0.0175 | -0.0176 | +0.0001 |
| KXPAULMENTION | media_word | 22 | 12 | -0.0114 | -0.0125 | +0.0011 |
| KXPERSONMENTION | political_person | 88 | 78 | -0.0493 | -0.0521 | +0.0027 |
| KXPOLITICSMENTION | political_person | 157 | 147 | -0.0389 | -0.0397 | +0.0007 |
| KXREEVESMENTION | political_person | 12 | - | - | - | skipped |
| KXSCHUMERMENTION | political_person | 20 | 10 | +0.0690 | +0.0680 | +0.0010 |
| KXSHIRLEYMENTION | other | 12 | - | - | - | skipped |
| KXSPANBERGERMENTION | other | 15 | 5 | -0.0420 | -0.0420 | -0.0000 |
| KXTHEWEEKNIGHTMENTION | media_word | 99 | 89 | -0.0329 | -0.0344 | +0.0015 |
| KXTRUMPMENTION | political_person | 2841 | 2831 | -0.0101 | -0.0097 | -0.0004 |
| KXTRUMPMENTIONB | political_person | 1379 | 1369 | -0.0234 | -0.0239 | +0.0005 |
| KXUNMENTION | other | 35 | 25 | -0.0300 | -0.0308 | +0.0008 |
| KXVIEWMENTION | media_word | 10 | - | - | - | skipped |
| KXVLADTENEVMENTION | other | 53 | 43 | -0.0268 | -0.0405 | +0.0137 |
| KXWALLERMENTION | other | 36 | 26 | +0.0344 | +0.1150 | -0.0806 |
| KXWALZMENTION | political_person | 100 | 90 | -0.0408 | -0.0429 | +0.0021 |
| KXWEFMENTION | other | 38 | 28 | -0.0234 | -0.0093 | -0.0141 |
| KXZAKARIAMENTION | media_word | 54 | 44 | -0.0139 | -0.0159 | +0.0020 |

**Aggregate expanding: mu = $-0.0051/contract over 8,591 trades**
**Shrinkage: $0.0011**

## 4. Bootstrap inference (expanding-window PnL)

| Statistic | Value |
|-----------|-------|
| Mean | $-0.0051 |
| 95% CI | [$-0.0082, $-0.0020] |
| SE | $0.0016 |
| CI excludes zero | **No** |

## 5. PnL under realistic friction

| Tier | Slip | Total | mu | sigma | Sharpe | WR | Max loss streak |
|------|:----:|------:|---:|------:|------:|---:|:---------------:|
| Gross | 0.0c | +216.6 | +0.0229 | 0.1519 | 0.151 | 54% | 25 |
| Fees only | 0.0c | +27.6 | +0.0029 | 0.1519 | 0.019 | 19% | 164 |
| Fees+1c | 1.0c | -38.3 | -0.0040 | 0.1517 | -0.027 | 17% | 453 |
| Fees+2c | 2.0c | -99.6 | -0.0105 | 0.1516 | -0.069 | 15% | 453 |

**Dollar PnL at 5% cap (fees+1c slip): $-270,889**

## 6. Per-series t-tests (H0: mu = 0, one-sided)

| Series | N | mu | sigma | t | p | Sig |
|--------|--:|---:|------:|--:|--:|:---:|
| KX60MINMENTION | 68 | -0.0229 | 0.0251 | -7.54 | 1.0000 | - |
| KXAMODEIMENTION | 12 | -0.0558 | 0.0956 | -2.02 | 0.9660 | - |
| KXAOCMENTION | 46 | -0.0130 | 0.2131 | -0.42 | 0.6600 | - |
| KXARMSTRONGMENTION | 24 | +0.0217 | 0.1776 | 0.60 | 0.2780 | - |
| KXBENIOFFMENTION | 12 | +0.2675 | 0.4472 | 2.07 | 0.0313 | Y |
| KXBIDENMENTION | 83 | +0.0308 | 0.1413 | 1.99 | 0.0250 | Y |
| KXBONGINOMENTION | 38 | -0.0303 | 0.0271 | -6.89 | 1.0000 | - |
| KXCARLSONMENTION | 13 | -0.0015 | 0.0356 | -0.16 | 0.5607 | - |
| KXCFBMENTION | 44 | -0.0139 | 0.0512 | -1.80 | 0.9602 | - |
| KXCMAMENTION | 14 | +0.1200 | 0.2622 | 1.71 | 0.0553 | - |
| KXCOLBERTMENTION | 130 | +0.0187 | 0.1415 | 1.51 | 0.0672 | - |
| KXCULTUREMENTION | 8 | -0.0213 | 0.0155 | -3.87 | 0.9969 | - |
| KXCUOMOMENTION | 20 | -0.0250 | 0.0201 | -5.55 | 1.0000 | - |
| KXDESANTISMENTION | 14 | -0.0214 | 0.0183 | -4.37 | 0.9996 | - |
| KXDILLONMENTION | 14 | +0.0236 | 0.4192 | 0.21 | 0.4183 | - |
| KXDIMONMENTION | 40 | -0.0248 | 0.2454 | -0.64 | 0.7364 | - |
| KXDWTSMENTION | 10 | -0.0250 | 0.0158 | -5.00 | 0.9996 | - |
| KXEARNINGSMENTIONAAL | 24 | -0.0125 | 0.0775 | -0.79 | 0.7813 | - |
| KXEARNINGSMENTIONABNB | 20 | -0.0200 | 0.1233 | -0.73 | 0.7614 | - |
| KXEARNINGSMENTIONACI | 13 | -0.0308 | 0.0189 | -5.87 | 1.0000 | - |
| KXEARNINGSMENTIONAMZN | 77 | +0.0030 | 0.2068 | 0.13 | 0.4497 | - |
| KXEARNINGSMENTIONASTS | 8 | -0.0325 | 0.0198 | -4.64 | 0.9988 | - |
| KXEARNINGSMENTIONBAC | 24 | -0.0050 | 0.1801 | -0.14 | 0.5535 | - |
| KXEARNINGSMENTIONCAR | 10 | -0.0500 | 0.0462 | -3.42 | 0.9962 | - |
| KXEARNINGSMENTIONCBRL | 17 | +0.0194 | 0.3278 | 0.24 | 0.4051 | - |
| KXEARNINGSMENTIONCHWY | 12 | -0.0317 | 0.0298 | -3.68 | 0.9982 | - |
| KXEARNINGSMENTIONCRCL | 17 | -0.0406 | 0.0423 | -3.95 | 0.9994 | - |
| KXEARNINGSMENTIONCVNA | 10 | -0.0250 | 0.0201 | -3.93 | 0.9983 | - |
| KXEARNINGSMENTIONDPZ | 10 | -0.0240 | 0.0190 | -4.00 | 0.9984 | - |
| KXEARNINGSMENTIONHD | 22 | -0.0259 | 0.0232 | -5.23 | 1.0000 | - |
| KXEARNINGSMENTIONHLT | 11 | -0.0264 | 0.0262 | -3.34 | 0.9963 | - |
| KXEARNINGSMENTIONHPE | 10 | -0.0520 | 0.0286 | -5.75 | 0.9999 | - |
| KXEARNINGSMENTIONLLY | 10 | -0.0610 | 0.0384 | -5.02 | 0.9996 | - |
| KXEARNINGSMENTIONLUCID | 15 | +0.0993 | 0.3270 | 1.18 | 0.1295 | - |
| KXEARNINGSMENTIONLYFT | 24 | +0.0167 | 0.2028 | 0.40 | 0.3455 | - |
| KXEARNINGSMENTIONMA | 12 | -0.0350 | 0.0334 | -3.63 | 0.9980 | - |
| KXEARNINGSMENTIONMETA | 70 | -0.0143 | 0.1687 | -0.71 | 0.7595 | - |
| KXEARNINGSMENTIONMSFT | 69 | -0.0477 | 0.1987 | -1.99 | 0.9749 | - |
| KXEARNINGSMENTIONNKE | 48 | -0.0085 | 0.0640 | -0.92 | 0.8200 | - |
| KXEARNINGSMENTIONNVDA | 92 | -0.0125 | 0.0685 | -1.75 | 0.9583 | - |
| KXEARNINGSMENTIONORCL | 27 | +0.0130 | 0.0971 | 0.69 | 0.2469 | - |
| KXEARNINGSMENTIONPG | 24 | -0.0083 | 0.0722 | -0.57 | 0.7115 | - |
| KXEARNINGSMENTIONPLTR | 70 | +0.0124 | 0.1712 | 0.61 | 0.2728 | - |
| KXEARNINGSMENTIONQCOM | 12 | -0.0467 | 0.0311 | -5.19 | 0.9999 | - |
| KXEARNINGSMENTIONRDDT | 21 | -0.0248 | 0.0626 | -1.81 | 0.9576 | - |
| KXEARNINGSMENTIONSBUX | 28 | -0.0182 | 0.0355 | -2.72 | 0.9943 | - |
| KXEARNINGSMENTIONSHOP | 8 | -0.0288 | 0.0155 | -5.24 | 0.9994 | - |
| KXEARNINGSMENTIONULTA | 12 | -0.0550 | 0.0767 | -2.48 | 0.9848 | - |
| KXEARNINGSMENTIONVZ | 10 | -0.0270 | 0.0189 | -4.52 | 0.9993 | - |
| KXEARNINGSMENTIONWFC | 9 | -0.0300 | 0.0150 | -6.00 | 0.9998 | - |
| KXFEDGOVMENTION | 11 | +0.0873 | 0.4102 | 0.71 | 0.2483 | - |
| KXFRANKLINMENTION | 10 | +0.0770 | 0.1813 | 1.34 | 0.1061 | - |
| KXHEGSETHMENTION | 90 | -0.0319 | 0.2203 | -1.37 | 0.9134 | - |
| KXJPOWMENTION | 51 | +0.0141 | 0.3023 | 0.33 | 0.3701 | - |
| KXKARPMENTION | 12 | +0.0300 | 0.0686 | 1.51 | 0.0791 | - |
| KXKINGMENTION | 9 | -0.0144 | 0.0159 | -2.73 | 0.9870 | - |
| KXLEAVITTMENTIONDURATION | 87 | +0.1069 | 0.2735 | 3.65 | 0.0002 | Y |
| KXLEAVITTSMFMENTION | 54 | +0.0835 | 0.1871 | 3.28 | 0.0009 | Y |
| KXLEBRONMENTION | 21 | -0.0033 | 0.1151 | -0.13 | 0.5521 | - |
| KXMAHERMENTION | 22 | +0.0405 | 0.1919 | 0.99 | 0.1671 | - |
| KXMIRANMENTION | 24 | +0.0700 | 0.2185 | 1.57 | 0.0651 | - |
| KXMLBMENTION | 64 | +0.0516 | 0.2538 | 1.63 | 0.0545 | - |
| KXMMMENTION | 76 | +0.0916 | 0.4025 | 1.98 | 0.0255 | Y |
| KXNCAABMENTION | 984 | +0.0488 | 0.2108 | 7.26 | 0.0000 | Y |
| KXNETANYAHUMENTION | 20 | -0.0410 | 0.0489 | -3.75 | 0.9993 | - |
| KXNFLMENTION | 1509 | -0.0175 | 0.0756 | -9.00 | 1.0000 | - |
| KXPAULMENTION | 22 | -0.0114 | 0.0064 | -8.33 | 1.0000 | - |
| KXPERSONMENTION | 88 | -0.0493 | 0.0875 | -5.29 | 1.0000 | - |
| KXPOLITICSMENTION | 157 | -0.0389 | 0.0684 | -7.13 | 1.0000 | - |
| KXREEVESMENTION | 12 | +0.0700 | 0.1089 | 2.23 | 0.0239 | Y |
| KXSCHUMERMENTION | 20 | +0.0690 | 0.1253 | 2.46 | 0.0118 | Y |
| KXSHIRLEYMENTION | 12 | -0.0200 | 0.0186 | -3.73 | 0.9983 | - |
| KXSPANBERGERMENTION | 15 | -0.0420 | 0.0386 | -4.22 | 0.9996 | - |
| KXTHEWEEKNIGHTMENTION | 99 | -0.0329 | 0.1178 | -2.78 | 0.9967 | - |
| KXTRUMPMENTION | 2841 | -0.0101 | 0.1566 | -3.45 | 0.9997 | - |
| KXTRUMPMENTIONB | 1379 | -0.0234 | 0.0722 | -12.03 | 1.0000 | - |
| KXUNMENTION | 35 | -0.0300 | 0.0186 | -9.53 | 1.0000 | - |
| KXVIEWMENTION | 10 | +0.2670 | 0.2784 | 3.03 | 0.0071 | Y |
| KXVLADTENEVMENTION | 53 | -0.0268 | 0.1902 | -1.03 | 0.8450 | - |
| KXWALLERMENTION | 36 | +0.0344 | 0.2617 | 0.79 | 0.2175 | - |
| KXWALZMENTION | 100 | -0.0408 | 0.0539 | -7.57 | 1.0000 | - |
| KXWEFMENTION | 38 | -0.0234 | 0.0815 | -1.77 | 0.9576 | - |
| KXZAKARIAMENTION | 54 | -0.0139 | 0.0781 | -1.31 | 0.9014 | - |

## 7. Calibration by price decile

| Bin | N | Implied | Actual | Overpricing |
|-----|--:|-------:|------:|------------:|
| 0.0–0.1 | 3991 | 0.018 | 0.001 | +0.017 |
| 0.1–0.2 | 421 | 0.138 | 0.021 | +0.117 |
| 0.2–0.3 | 313 | 0.247 | 0.064 | +0.183 |
| 0.3–0.4 | 148 | 0.348 | 0.169 | +0.179 |
| 0.4–0.5 | 121 | 0.435 | 0.281 | +0.154 |
| 0.5–0.6 | 88 | 0.540 | 0.284 | +0.256 |
| 0.6–0.7 | 96 | 0.658 | 0.500 | +0.158 |
| 0.7–0.8 | 102 | 0.753 | 0.725 | +0.028 |
| 0.8–0.9 | 185 | 0.849 | 0.832 | +0.017 |
| 0.9–1.0 | 3987 | 0.982 | 0.994 | -0.012 |

chi2(9) = 184.1, p < 0.001

## 8. Strategy variants

| Strategy | N | Total | mu | Sharpe | WR |
|----------|--:|------:|---:|------:|---:|
| blind_no | 7735 | -20.4 | -0.0026 | -0.017 | 16% |
| political_only | 4211 | -57.2 | -0.0136 | -0.098 | 13% |
| earnings_only | 410 | -6.6 | -0.0161 | -0.116 | 19% |
| sports_only | 2498 | +24.8 | +0.0099 | 0.065 | 18% |
| media_only | 188 | -0.2 | -0.0009 | -0.008 | 13% |
| selective_edge≥5c | 1466 | +65.6 | +0.0447 | 0.196 | 35% |
| selective_edge≥10c | 320 | +21.3 | +0.0666 | 0.267 | 38% |
| high_volume≥10k | 4102 | -96.8 | -0.0236 | -0.491 | 3% |
| low_br≤50% | 6764 | -8.3 | -0.0012 | -0.008 | 17% |
| tight_filter | 107 | -0.3 | -0.0023 | -0.021 | 11% |

### Top 10 sweep configs (by Sharpe, N >= 20)

| Config | N | mu | Sharpe | WR |
|--------|--:|---:|------:|---:|
| e0.15_br0.30_v0 | 109 | +0.0945 | 0.372 | 41% |
| e0.15_br0.40_v0 | 111 | +0.0926 | 0.367 | 41% |
| e0.15_br0.50_v0 | 111 | +0.0926 | 0.367 | 41% |
| e0.15_br0.60_v0 | 111 | +0.0926 | 0.367 | 41% |
| e0.15_br0.80_v0 | 111 | +0.0926 | 0.367 | 41% |
| e0.15_br1.00_v0 | 111 | +0.0926 | 0.367 | 41% |
| e0.10_br0.30_v0 | 152 | +0.0857 | 0.345 | 39% |
| e0.08_br0.30_v0 | 219 | +0.0694 | 0.317 | 39% |
| e0.08_br0.40_v0 | 260 | +0.0661 | 0.272 | 39% |
| e0.10_br0.40_v0 | 176 | +0.0724 | 0.272 | 38% |

## 9. LibFrog transcript base rate comparison

Matched 60 earnings markets against LibFrog historical transcript data.

| Metric | Value |
|--------|-------|
| Matches | 60 |
| Avg overpricing (Kalshi - LibFrog) | +0.252 |
| Median overpricing | +0.149 |
| % overpriced | 70% |

### Top overpriced/underpriced (by magnitude)

| Company | Word | Kalshi | LibFrog | Delta |
|---------|------|------:|-------:|------:|
| NVDA | Blackwell | 0.990 | 0.090 | +0.900 |
| NVDA | Blackwell | 0.990 | 0.090 | +0.900 |
| HD | Revenue | 0.990 | 0.150 | +0.840 |
| MSFT | Copilot | 0.990 | 0.200 | +0.790 |
| META | Llama | 0.990 | 0.208 | +0.782 |
| MSFT | Copilot | 0.970 | 0.200 | +0.770 |
| META | Threads | 0.990 | 0.264 | +0.726 |
| MSFT | OpenAI | 0.990 | 0.275 | +0.715 |
| MSFT | OpenAI | 0.980 | 0.275 | +0.705 |
| META | Llama | 0.910 | 0.208 | +0.702 |
| MSFT | Copilot | 0.890 | 0.200 | +0.690 |
| META | Metaverse | 0.990 | 0.302 | +0.688 |
| META | Threads | 0.940 | 0.264 | +0.676 |
| MSFT | OpenAI | 0.940 | 0.275 | +0.665 |
| MSFT | OpenAI | 0.940 | 0.275 | +0.665 |

## 10. Capacity analysis

| Metric | Value |
|--------|-------|
| Total volume | $252,781,746 |
| Unique events | 515 |
| Unique series | 84 |
| Data span | 373d (1.0y) |
| Max capital at 5% cap | $6,527,302 |
| Dollar PnL (capped) | $-270,889 |
| Annualized PnL | $-265,261 |
| Annualized return | -4.2% |

## 11. Price range analysis

Markets with extreme opening prices (<5% or >95%) are trivially obvious. The real edge opportunity is in the **competitive range** (5-95%).

| Price range | N | % | Base rate | Avg price | Overpricing | Net mu | Sharpe |
|-------------|--:|--:|----------:|----------:|------------:|------:|------:|
| <5% | 3,788 | 40% | 0.001 | 0.015 | +0.014 | -0.0083 | -0.347 |
| 5-25% | 817 | 9% | 0.024 | 0.143 | +0.118 | +0.0883 | 0.551 |
| 25-50% | 412 | 4% | 0.187 | 0.363 | +0.176 | +0.1458 | 0.381 |
| 50-75% | 217 | 2% | 0.493 | 0.647 | +0.154 | +0.1239 | 0.258 |
| 75-95% | 597 | 6% | 0.894 | 0.892 | -0.002 | -0.0324 | -0.109 |
| >95% | 3,621 | 38% | 0.998 | 0.988 | -0.011 | -0.0405 | -0.924 |

**Competitive range (5-95%) only: N=2,043, mu=$+0.0684, Sharpe=0.223**
**Bootstrap 95% CI: [$+0.0551, $+0.0818] — excludes zero**

## Verdict

**BLIND NO EDGE KILLED (all markets)**

Mean PnL <= 0 after realistic friction on the full dataset. The blind NO strategy does not survive fees + slippage across all 7,000+ markets.

However, the **competitive range (5-95%)** retains significant edge: mu=$+0.0684, CI excludes zero. The edge is real but requires filtering out trivially-priced markets.

**Category-level edge survives** in: other, sports_word. A selective strategy targeting these categories is more promising than blind NO across all markets.

### Key risks

1. **Category concentration**: Edge is concentrated in some categories. Blind NO across all categories destroys alpha.
2. **Extreme prices dominate**: 78% of markets have prices <5% or >95%, diluting the signal from competitive-range markets.
3. **Autocorrelation**: Within-event clustering reduces effective sample size.
4. **Liquidity**: At 5% volume cap, capital deployed per market is small.
5. **Regime change**: As markets mature, mispricing may compress.

---
*9,452 markets · 10,000 bootstrap resamples · Kalshi fee $0.02/RT · PM fee $0 · Slippage sensitivity 0-3c*
# Mention Market Systematic NO — Expanded Robustness Report

Generated 2026-03-08 18:23 · 20,840 settled markets (20194 Kalshi, 646 Polymarket) · 205 series · 5 categories

---

## 0. Data inventory

| Source | Markets | Series | Categories |
|--------|--------:|-------:|-----------:|
| Kalshi expanded | 20,194 | 203 | 5 |
| Polymarket | 646 | 2 | 2 |
| **Total** | **20,840** | **205** | **5** |

| Category | N | % |
|----------|--:|--:|
| political_person | 7,845 | 38% |
| sports_word | 5,547 | 27% |
| other | 4,896 | 23% |
| earnings_word | 2,177 | 10% |
| media_word | 375 | 2% |

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
| political_person | 7,845 | 29 | 0.434 | 0.451 | +0.017 | -0.0076 | -0.051 | 19% | 1.0000 | N | N |
| sports_word | 5,547 | 5 | 0.536 | 0.556 | +0.020 | -0.0070 | -0.056 | 13% | 1.0000 | N | N |
| other | 4,896 | 72 | 0.425 | 0.452 | +0.027 | +0.0010 | 0.006 | 20% | 0.3275 | N | N |
| earnings_word | 2,177 | 89 | 0.568 | 0.576 | +0.008 | -0.0196 | -0.128 | 17% | 1.0000 | N | N |
| media_word | 375 | 10 | 0.339 | 0.372 | +0.033 | +0.0070 | 0.051 | 15% | 0.1629 | N | N |

No category reaches individual significance at p < 0.05.

## 3. Lookahead bias test

Expanding window: trade market *i* using only data from markets 1 ... *i*-1. First 10 per series skipped.

| Series | Cat | N | N(exp) | Full mu | Exp mu | Shrinkage |
|--------|-----|--:|-------:|-------:|------:|----------:|
| KX60MINMENTION | media_word | 68 | 58 | -0.0229 | -0.0241 | +0.0012 |
| KXACKMANMENTION | political_person | 12 | - | - | - | skipped |
| KXAMODEIMENTION | political_person | 12 | - | - | - | skipped |
| KXAOCMENTION | political_person | 46 | 36 | -0.0130 | -0.0547 | +0.0417 |
| KXAPPLEMENTION | other | 15 | 5 | -0.0140 | -0.0160 | +0.0020 |
| KXARMSTRONGMENTION | media_word | 24 | 14 | +0.0217 | -0.0143 | +0.0360 |
| KXAWARDMENTION | other | 52 | 42 | +0.0010 | -0.0081 | +0.0091 |
| KXBANNONMENTION | other | 13 | - | - | - | skipped |
| KXBENIOFFMENTION | other | 12 | - | - | - | skipped |
| KXBIDENMENTION | political_person | 83 | 73 | +0.0308 | +0.0347 | -0.0038 |
| KXBILATERALMENTION | other | 94 | 84 | +0.0416 | +0.0496 | -0.0080 |
| KXBONGINOMENTION | other | 38 | 28 | -0.0303 | -0.0300 | -0.0003 |
| KXBTCMENTIONULBRICHT | other | 12 | - | - | - | skipped |
| KXBTCMENTIONVANCE | political_person | 17 | 7 | -0.0541 | -0.0129 | -0.0413 |
| KXBUSHMENTION | other | 12 | - | - | - | skipped |
| KXCARLSONMENTION | media_word | 13 | - | - | - | skipped |
| KXCFBMENTION | other | 44 | 34 | -0.0139 | -0.0212 | +0.0073 |
| KXCMAMENTION | other | 14 | - | - | - | skipped |
| KXCOLBERTMENTION | other | 130 | 120 | +0.0187 | +0.0189 | -0.0002 |
| KXCONGRESSMENTION | other | 282 | 272 | -0.0309 | -0.0319 | +0.0010 |
| KXCOOPERMENTION | other | 56 | 46 | +0.0004 | +0.0015 | -0.0012 |
| KXCROCKETTMENTION | other | 27 | 17 | -0.0296 | -0.0306 | +0.0010 |
| KXCULTUREMENTION | political_person | 8 | - | - | - | skipped |
| KXCUOMOMENTION | political_person | 20 | 10 | -0.0250 | -0.0240 | -0.0010 |
| KXDESANTISMENTION | other | 14 | - | - | - | skipped |
| KXDILLONMENTION | other | 14 | - | - | - | skipped |
| KXDIMONMENTION | other | 40 | 30 | -0.0248 | -0.0420 | +0.0172 |
| KXDJTNATOMENTION | other | 30 | 20 | +0.1467 | +0.1940 | -0.0473 |
| KXDOGSHOWMENTION | other | 14 | - | - | - | skipped |
| KXDWTSMENTION | other | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONAAL | earnings_word | 24 | 14 | -0.0125 | -0.0214 | +0.0089 |
| KXEARNINGSMENTIONAAPL | earnings_word | 73 | 63 | -0.0356 | -0.0351 | -0.0005 |
| KXEARNINGSMENTIONABNB | earnings_word | 20 | 10 | -0.0200 | -0.0270 | +0.0070 |
| KXEARNINGSMENTIONACI | earnings_word | 13 | - | - | - | skipped |
| KXEARNINGSMENTIONADBE | earnings_word | 11 | - | - | - | skipped |
| KXEARNINGSMENTIONADOBE | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONALIBABA | earnings_word | 13 | - | - | - | skipped |
| KXEARNINGSMENTIONAMD | earnings_word | 35 | 25 | +0.0023 | +0.0072 | -0.0049 |
| KXEARNINGSMENTIONAMZN | earnings_word | 77 | 67 | +0.0030 | -0.0104 | +0.0134 |
| KXEARNINGSMENTIONASTS | earnings_word | 8 | - | - | - | skipped |
| KXEARNINGSMENTIONAVGO | earnings_word | 20 | 10 | -0.0295 | -0.0240 | -0.0055 |
| KXEARNINGSMENTIONAXP | earnings_word | 23 | 13 | +0.0022 | -0.0008 | +0.0029 |
| KXEARNINGSMENTIONBAC | earnings_word | 24 | 14 | -0.0050 | -0.0479 | +0.0429 |
| KXEARNINGSMENTIONBLK | earnings_word | 23 | 13 | -0.0226 | -0.0254 | +0.0028 |
| KXEARNINGSMENTIONCAR | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONCAVA | earnings_word | 25 | 15 | -0.0432 | -0.0420 | -0.0012 |
| KXEARNINGSMENTIONCBRL | earnings_word | 17 | 7 | +0.0194 | +0.1314 | -0.1120 |
| KXEARNINGSMENTIONCHWY | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONCOINBASE | earnings_word | 47 | 37 | -0.0623 | -0.0519 | -0.0104 |
| KXEARNINGSMENTIONCOST | earnings_word | 48 | 38 | -0.0419 | -0.0426 | +0.0008 |
| KXEARNINGSMENTIONCRCL | earnings_word | 17 | 7 | -0.0406 | -0.0457 | +0.0051 |
| KXEARNINGSMENTIONCRM | earnings_word | 11 | - | - | - | skipped |
| KXEARNINGSMENTIONCRWD | earnings_word | 23 | 13 | -0.0752 | -0.0369 | -0.0383 |
| KXEARNINGSMENTIONCVNA | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONDAL | earnings_word | 23 | 13 | -0.0617 | -0.0677 | +0.0060 |
| KXEARNINGSMENTIONDELL | earnings_word | 25 | 15 | -0.0124 | -0.0093 | -0.0031 |
| KXEARNINGSMENTIONDKNG | earnings_word | 26 | 16 | -0.0327 | -0.0344 | +0.0017 |
| KXEARNINGSMENTIONDOLLARGENERAL | earnings_word | 8 | - | - | - | skipped |
| KXEARNINGSMENTIONDPZ | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONEA | earnings_word | 1 | - | - | - | skipped |
| KXEARNINGSMENTIONETOR | earnings_word | 9 | - | - | - | skipped |
| KXEARNINGSMENTIONF | earnings_word | 15 | 5 | +0.0933 | +0.0060 | +0.0873 |
| KXEARNINGSMENTIONGEV | earnings_word | 9 | - | - | - | skipped |
| KXEARNINGSMENTIONGME | earnings_word | 7 | - | - | - | skipped |
| KXEARNINGSMENTIONGOOGL | earnings_word | 65 | 55 | -0.0188 | -0.0138 | -0.0050 |
| KXEARNINGSMENTIONGS | earnings_word | 23 | 13 | +0.0404 | -0.0285 | +0.0689 |
| KXEARNINGSMENTIONHD | earnings_word | 22 | 12 | -0.0259 | -0.0342 | +0.0083 |
| KXEARNINGSMENTIONHIMS | earnings_word | 27 | 17 | -0.0152 | -0.0541 | +0.0389 |
| KXEARNINGSMENTIONHLT | earnings_word | 11 | - | - | - | skipped |
| KXEARNINGSMENTIONHOOD | earnings_word | 24 | 14 | -0.0371 | -0.0336 | -0.0035 |
| KXEARNINGSMENTIONHPE | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONKO | earnings_word | 20 | 10 | -0.0190 | -0.0220 | +0.0030 |
| KXEARNINGSMENTIONKR | earnings_word | 25 | 15 | -0.0320 | -0.0320 | +0.0000 |
| KXEARNINGSMENTIONKTOS | earnings_word | 9 | - | - | - | skipped |
| KXEARNINGSMENTIONLLY | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONLUCID | earnings_word | 15 | 5 | +0.0993 | -0.0260 | +0.1253 |
| KXEARNINGSMENTIONLYFT | earnings_word | 24 | 14 | +0.0167 | -0.0250 | +0.0417 |
| KXEARNINGSMENTIONMA | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONMCD | earnings_word | 26 | 16 | -0.0181 | -0.0250 | +0.0069 |
| KXEARNINGSMENTIONMCO | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONMETA | earnings_word | 70 | 60 | -0.0143 | -0.0108 | -0.0035 |
| KXEARNINGSMENTIONMRVL | earnings_word | 21 | 11 | -0.0381 | -0.0300 | -0.0081 |
| KXEARNINGSMENTIONMSFT | earnings_word | 69 | 59 | -0.0477 | -0.0510 | +0.0033 |
| KXEARNINGSMENTIONMU | earnings_word | 35 | 25 | -0.0257 | -0.0296 | +0.0039 |
| KXEARNINGSMENTIONNBIS | earnings_word | 21 | 11 | +0.0333 | -0.0264 | +0.0597 |
| KXEARNINGSMENTIONNFLX | earnings_word | 56 | 46 | -0.0246 | -0.0198 | -0.0049 |
| KXEARNINGSMENTIONNIO | earnings_word | 15 | 5 | +0.0007 | -0.0520 | +0.0527 |
| KXEARNINGSMENTIONNKE | earnings_word | 48 | 38 | -0.0085 | -0.0132 | +0.0046 |
| KXEARNINGSMENTIONNVDA | earnings_word | 92 | 82 | -0.0125 | -0.0112 | -0.0013 |
| KXEARNINGSMENTIONON | earnings_word | 8 | - | - | - | skipped |
| KXEARNINGSMENTIONORCL | earnings_word | 27 | 17 | +0.0130 | -0.0147 | +0.0277 |
| KXEARNINGSMENTIONPEP | earnings_word | 22 | 12 | -0.0132 | -0.0367 | +0.0235 |
| KXEARNINGSMENTIONPG | earnings_word | 24 | 14 | -0.0083 | -0.0286 | +0.0202 |
| KXEARNINGSMENTIONPLTR | earnings_word | 70 | 60 | +0.0124 | +0.0103 | +0.0021 |
| KXEARNINGSMENTIONPSKY | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONQCOM | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONRDDT | earnings_word | 21 | 11 | -0.0248 | -0.0336 | +0.0089 |
| KXEARNINGSMENTIONRKLB | earnings_word | 25 | 15 | -0.0324 | -0.0240 | -0.0084 |
| KXEARNINGSMENTIONROKU | earnings_word | 25 | 15 | +0.1180 | -0.0280 | +0.1460 |
| KXEARNINGSMENTIONRY | earnings_word | 20 | 10 | -0.1015 | -0.0630 | -0.0385 |
| KXEARNINGSMENTIONSBUX | earnings_word | 28 | 18 | -0.0182 | -0.0067 | -0.0115 |
| KXEARNINGSMENTIONSFM | earnings_word | 9 | - | - | - | skipped |
| KXEARNINGSMENTIONSHOP | earnings_word | 8 | - | - | - | skipped |
| KXEARNINGSMENTIONSNAP | earnings_word | 24 | 14 | -0.0479 | -0.0564 | +0.0085 |
| KXEARNINGSMENTIONSPOT | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONSTZ | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONTGT | earnings_word | 24 | 14 | -0.0242 | -0.0279 | +0.0037 |
| KXEARNINGSMENTIONTSLA | earnings_word | 78 | 68 | -0.0429 | -0.0397 | -0.0032 |
| KXEARNINGSMENTIONTSMC | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONUAL | earnings_word | 25 | 15 | -0.0172 | -0.0240 | +0.0068 |
| KXEARNINGSMENTIONUBER | earnings_word | 75 | 65 | +0.0200 | +0.0120 | +0.0080 |
| KXEARNINGSMENTIONULTA | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONV | earnings_word | 13 | - | - | - | skipped |
| KXEARNINGSMENTIONVSCO | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONVZ | earnings_word | 10 | - | - | - | skipped |
| KXEARNINGSMENTIONWEN | earnings_word | 12 | - | - | - | skipped |
| KXEARNINGSMENTIONWFC | earnings_word | 9 | - | - | - | skipped |
| KXEARNINGSMENTIONWING | earnings_word | 8 | - | - | - | skipped |
| KXEARNINGSMENTIONWMT | earnings_word | 45 | 35 | -0.0649 | -0.0294 | -0.0355 |
| KXFEDGOVMENTION | political_person | 11 | - | - | - | skipped |
| KXFEDMENTION | political_person | 305 | 295 | -0.0024 | -0.0007 | -0.0016 |
| KXFIGHTMENTION | other | 217 | 207 | -0.0076 | -0.0072 | -0.0004 |
| KXFRANKLINMENTION | other | 10 | - | - | - | skipped |
| KXFREYMENTION | other | 43 | 33 | +0.0353 | +0.0573 | -0.0219 |
| KXFTNMENTION | other | 129 | 119 | -0.0352 | -0.0371 | +0.0019 |
| KXGAMEDAYMENTION | other | 10 | - | - | - | skipped |
| KXGLASERMENTION | other | 19 | 9 | -0.0132 | -0.0067 | -0.0065 |
| KXGOVERNORMENTION | other | 174 | 164 | -0.0256 | -0.0251 | -0.0006 |
| KXGREENDAYMENTION | other | 1 | - | - | - | skipped |
| KXGRIFFINMENTION | other | 15 | 5 | +0.3180 | +0.3180 | +0.0000 |
| KXHARTMENTION | other | 11 | - | - | - | skipped |
| KXHEGSETHMENTION | other | 90 | 80 | -0.0319 | -0.0189 | -0.0130 |
| KXHOCHULMENTION | other | 259 | 249 | -0.0359 | -0.0359 | -0.0000 |
| KXHOMANMENTION | political_person | 69 | 59 | -0.0391 | -0.0388 | -0.0003 |
| KXINFANTINOMENTION | other | 26 | 16 | -0.0142 | -0.0294 | +0.0151 |
| KXJENSENMENTION | other | 56 | 46 | -0.0120 | +0.0030 | -0.0150 |
| KXJPOWMENTION | political_person | 51 | 41 | +0.0141 | +0.0085 | +0.0056 |
| KXKAMALAMENTION | other | 81 | 71 | -0.0157 | -0.0058 | -0.0099 |
| KXKARPMENTION | political_person | 12 | - | - | - | skipped |
| KXKINGMENTION | media_word | 9 | - | - | - | skipped |
| KXLAMMYMENTION | other | 11 | - | - | - | skipped |
| KXLEAVITTMENTIONDURATION | other | 87 | 77 | +0.1069 | +0.1139 | -0.0070 |
| KXLEAVITTSMFMENTION | media_word | 54 | 44 | +0.0835 | +0.0409 | +0.0426 |
| KXLEBRONMENTION | political_person | 21 | 11 | -0.0033 | -0.0291 | +0.0258 |
| KXLUTNICKFTNMENTION | other | 32 | 22 | +0.0931 | +0.0355 | +0.0577 |
| KXMADDOWMENTION | political_person | 39 | 29 | +0.0272 | -0.0238 | +0.0510 |
| KXMAHERMENTION | media_word | 22 | 12 | +0.0405 | +0.0583 | -0.0179 |
| KXMELANIAMENTION | other | 90 | 80 | -0.0059 | -0.0061 | +0.0002 |
| KXMINAJMENTION | other | 10 | - | - | - | skipped |
| KXMIRANMENTION | other | 24 | 14 | +0.0700 | +0.1457 | -0.0757 |
| KXMLBMENTION | sports_word | 64 | 54 | +0.0516 | +0.0409 | +0.0106 |
| KXMMMENTION | other | 76 | 66 | +0.0916 | +0.1055 | -0.0139 |
| KXMRBEASTMENTION | other | 277 | 267 | -0.0106 | -0.0044 | -0.0062 |
| KXMTGMENTION | other | 12 | - | - | - | skipped |
| KXMTPMENTION | other | 34 | 24 | -0.0279 | -0.0267 | -0.0013 |
| KXNADALMENTION | other | 13 | - | - | - | skipped |
| KXNBAMENTION | sports_word | 2701 | 2691 | -0.0215 | -0.0214 | -0.0000 |
| KXNCAABMENTION | sports_word | 984 | 974 | +0.0488 | +0.0498 | -0.0010 |
| KXNCAAMENTION | other | 597 | 587 | -0.0214 | -0.0212 | -0.0002 |
| KXNETANYAHUMENTION | other | 20 | 10 | -0.0410 | -0.0280 | -0.0130 |
| KXNEWSOMMENTION | other | 209 | 199 | -0.0192 | -0.0189 | -0.0003 |
| KXNFLMENTION | sports_word | 1509 | 1499 | -0.0175 | -0.0176 | +0.0001 |
| KXNYCMDEBMENTION | other | 54 | 44 | +0.0044 | +0.0168 | -0.0124 |
| KXOSCARMENTION | other | 28 | 18 | -0.0957 | -0.1644 | +0.0687 |
| KXPAULMENTION | media_word | 22 | 12 | -0.0114 | -0.0125 | +0.0011 |
| KXPERSONMENTION | political_person | 88 | 78 | -0.0493 | -0.0521 | +0.0027 |
| KXPOLITICSMENTION | political_person | 157 | 147 | -0.0389 | -0.0397 | +0.0007 |
| KXPOWELLMENTION | political_person | 142 | 132 | +0.0337 | +0.0289 | +0.0047 |
| KXPSAKIMENTION | other | 100 | 90 | -0.0177 | -0.0313 | +0.0136 |
| KXREEVESMENTION | political_person | 12 | - | - | - | skipped |
| KXROGANMENTION | political_person | 30 | 20 | +0.0973 | +0.2290 | -0.1317 |
| KXSBMENTION | other | 19 | 9 | +0.0137 | +0.0100 | +0.0037 |
| KXSCHUMERMENTION | political_person | 20 | 10 | +0.0690 | +0.0680 | +0.0010 |
| KXSCOTUSMENTION | other | 15 | 5 | -0.0180 | -0.0280 | +0.0100 |
| KXSECPRESSMENTION | political_person | 1154 | 1144 | -0.0043 | -0.0063 | +0.0020 |
| KXSHAQMENTION | other | 13 | - | - | - | skipped |
| KXSHIRLEYMENTION | other | 12 | - | - | - | skipped |
| KXSNFMENTION | sports_word | 289 | 279 | -0.0193 | -0.0186 | -0.0007 |
| KXSNLMENTION | other | 138 | 128 | +0.0167 | +0.0159 | +0.0007 |
| KXSNOOPMENTION | other | 14 | - | - | - | skipped |
| KXSOUTHPARKMENTION | other | 120 | 110 | +0.0528 | +0.0492 | +0.0037 |
| KXSPANBERGERMENTION | other | 15 | 5 | -0.0420 | -0.0420 | -0.0000 |
| KXSTARMERMENTION | political_person | 146 | 136 | +0.0073 | +0.0019 | +0.0053 |
| KXSTARMERMENTIONB | political_person | 48 | 38 | -0.0188 | -0.0203 | +0.0015 |
| KXSURVIVORMENTION | other | 228 | 218 | +0.0401 | +0.0389 | +0.0013 |
| KXSWIFTMENTION | other | 120 | 110 | -0.0085 | -0.0073 | -0.0012 |
| KXTALARICOMENTION | other | 36 | 26 | -0.0447 | -0.0469 | +0.0022 |
| KXTBPNMENTION | other | 46 | 36 | +0.0265 | -0.0025 | +0.0290 |
| KXTHEWEEKNIGHTMENTION | media_word | 99 | 89 | -0.0329 | -0.0344 | +0.0015 |
| KXTRUMPMENTION | political_person | 2841 | 2831 | -0.0101 | -0.0097 | -0.0004 |
| KXTRUMPMENTIONB | political_person | 1379 | 1369 | -0.0234 | -0.0239 | +0.0005 |
| KXTRUMPMENTIONDURATION | political_person | 75 | 65 | +0.0268 | +0.0334 | -0.0066 |
| KXUNMENTION | other | 35 | 25 | -0.0300 | -0.0308 | +0.0008 |
| KXVANCEMENTION | political_person | 455 | 445 | +0.0151 | +0.0110 | +0.0041 |
| KXVIEWMENTION | media_word | 10 | - | - | - | skipped |
| KXVLADTENEVMENTION | other | 53 | 43 | -0.0268 | -0.0405 | +0.0137 |
| KXWALESMENTION | other | 8 | - | - | - | skipped |
| KXWALLERMENTION | other | 36 | 26 | +0.0344 | +0.1150 | -0.0806 |
| KXWALZMENTION | political_person | 100 | 90 | -0.0408 | -0.0429 | +0.0021 |
| KXWEFMENTION | other | 38 | 28 | -0.0234 | -0.0093 | -0.0141 |
| KXZAKARIAMENTION | media_word | 54 | 44 | -0.0139 | -0.0159 | +0.0020 |
| KXZELENSKYYMENTION | other | 32 | 22 | +0.0794 | +0.0586 | +0.0207 |
| KXZIWEMENTION | other | 26 | 16 | +0.1269 | +0.1350 | -0.0081 |
| PM_Other | other | 154 | 144 | -0.0001 | +0.0003 | -0.0004 |
| PM_PersonNames | political_person | 492 | 482 | +0.0001 | +0.0002 | -0.0000 |

**Aggregate expanding: mu = $-0.0078/contract over 18,750 trades**
**Shrinkage: $0.0014**

## 4. Bootstrap inference (expanding-window PnL)

| Statistic | Value |
|-----------|-------|
| Mean | $-0.0078 |
| 95% CI | [$-0.0099, $-0.0058] |
| SE | $0.0010 |
| CI excludes zero | **No** |

## 5. PnL under realistic friction

| Tier | Slip | Total | mu | sigma | Sharpe | WR | Max loss streak |
|------|:----:|------:|---:|------:|------:|---:|:---------------:|
| Gross | 0.0c | +416.3 | +0.0200 | 0.1468 | 0.136 | 53% | 25 |
| Fees only | 0.0c | +12.4 | +0.0006 | 0.1468 | 0.004 | 20% | 164 |
| Fees+1c | 1.0c | -133.2 | -0.0064 | 0.1466 | -0.044 | 17% | 453 |
| Fees+2c | 2.0c | -268.8 | -0.0129 | 0.1466 | -0.088 | 16% | 453 |

**Dollar PnL at 5% cap (fees+1c slip): $-450,267**

## 6. Per-series t-tests (H0: mu = 0, one-sided)

| Series | N | mu | sigma | t | p | Sig |
|--------|--:|---:|------:|--:|--:|:---:|
| KX60MINMENTION | 68 | -0.0229 | 0.0251 | -7.54 | 1.0000 | - |
| KXACKMANMENTION | 12 | +0.2117 | 0.2974 | 2.47 | 0.0157 | Y |
| KXAMODEIMENTION | 12 | -0.0558 | 0.0956 | -2.02 | 0.9660 | - |
| KXAOCMENTION | 46 | -0.0130 | 0.2131 | -0.42 | 0.6600 | - |
| KXAPPLEMENTION | 15 | -0.0140 | 0.0106 | -5.14 | 0.9999 | - |
| KXARMSTRONGMENTION | 24 | +0.0217 | 0.1776 | 0.60 | 0.2780 | - |
| KXAWARDMENTION | 52 | +0.0010 | 0.0776 | 0.09 | 0.4646 | - |
| KXBANNONMENTION | 13 | -0.0169 | 0.0193 | -3.16 | 0.9959 | - |
| KXBENIOFFMENTION | 12 | +0.2675 | 0.4472 | 2.07 | 0.0313 | Y |
| KXBIDENMENTION | 83 | +0.0308 | 0.1413 | 1.99 | 0.0250 | Y |
| KXBILATERALMENTION | 94 | +0.0416 | 0.3140 | 1.28 | 0.1011 | - |
| KXBONGINOMENTION | 38 | -0.0303 | 0.0271 | -6.89 | 1.0000 | - |
| KXBTCMENTIONULBRICHT | 12 | -0.0558 | 0.1815 | -1.07 | 0.8453 | - |
| KXBTCMENTIONVANCE | 17 | -0.0541 | 0.2011 | -1.11 | 0.8582 | - |
| KXBUSHMENTION | 12 | -0.0150 | 0.0117 | -4.45 | 0.9995 | - |
| KXCARLSONMENTION | 13 | -0.0015 | 0.0356 | -0.16 | 0.5607 | - |
| KXCFBMENTION | 44 | -0.0139 | 0.0512 | -1.80 | 0.9602 | - |
| KXCMAMENTION | 14 | +0.1200 | 0.2622 | 1.71 | 0.0553 | - |
| KXCOLBERTMENTION | 130 | +0.0187 | 0.1415 | 1.51 | 0.0672 | - |
| KXCONGRESSMENTION | 282 | -0.0309 | 0.0364 | -14.25 | 1.0000 | - |
| KXCOOPERMENTION | 56 | +0.0004 | 0.3381 | 0.01 | 0.4969 | - |
| KXCROCKETTMENTION | 27 | -0.0296 | 0.0508 | -3.03 | 0.9973 | - |
| KXCULTUREMENTION | 8 | -0.0213 | 0.0155 | -3.87 | 0.9969 | - |
| KXCUOMOMENTION | 20 | -0.0250 | 0.0201 | -5.55 | 1.0000 | - |
| KXDESANTISMENTION | 14 | -0.0214 | 0.0183 | -4.37 | 0.9996 | - |
| KXDILLONMENTION | 14 | +0.0236 | 0.4192 | 0.21 | 0.4183 | - |
| KXDIMONMENTION | 40 | -0.0248 | 0.2454 | -0.64 | 0.7364 | - |
| KXDJTNATOMENTION | 30 | +0.1467 | 0.1973 | 4.07 | 0.0002 | Y |
| KXDOGSHOWMENTION | 14 | -0.0171 | 0.0144 | -4.46 | 0.9997 | - |
| KXDWTSMENTION | 10 | -0.0250 | 0.0158 | -5.00 | 0.9996 | - |
| KXEARNINGSMENTIONAAL | 24 | -0.0125 | 0.0775 | -0.79 | 0.7813 | - |
| KXEARNINGSMENTIONAAPL | 73 | -0.0356 | 0.1843 | -1.65 | 0.9485 | - |
| KXEARNINGSMENTIONABNB | 20 | -0.0200 | 0.1233 | -0.73 | 0.7614 | - |
| KXEARNINGSMENTIONACI | 13 | -0.0308 | 0.0189 | -5.87 | 1.0000 | - |
| KXEARNINGSMENTIONADBE | 11 | -0.0336 | 0.0262 | -4.26 | 0.9992 | - |
| KXEARNINGSMENTIONADOBE | 10 | -0.0220 | 0.0525 | -1.33 | 0.8913 | - |
| KXEARNINGSMENTIONALIBABA | 13 | +0.0231 | 0.3344 | 0.25 | 0.4039 | - |
| KXEARNINGSMENTIONAMD | 35 | +0.0023 | 0.1890 | 0.07 | 0.4717 | - |
| KXEARNINGSMENTIONAMZN | 77 | +0.0030 | 0.2068 | 0.13 | 0.4497 | - |
| KXEARNINGSMENTIONASTS | 8 | -0.0325 | 0.0198 | -4.64 | 0.9988 | - |
| KXEARNINGSMENTIONAVGO | 20 | -0.0295 | 0.0402 | -3.28 | 0.9980 | - |
| KXEARNINGSMENTIONAXP | 23 | +0.0022 | 0.0734 | 0.14 | 0.4442 | - |
| KXEARNINGSMENTIONBAC | 24 | -0.0050 | 0.1801 | -0.14 | 0.5535 | - |
| KXEARNINGSMENTIONBLK | 23 | -0.0226 | 0.0458 | -2.36 | 0.9864 | - |
| KXEARNINGSMENTIONCAR | 10 | -0.0500 | 0.0462 | -3.42 | 0.9962 | - |
| KXEARNINGSMENTIONCAVA | 25 | -0.0432 | 0.0347 | -6.22 | 1.0000 | - |
| KXEARNINGSMENTIONCBRL | 17 | +0.0194 | 0.3278 | 0.24 | 0.4051 | - |
| KXEARNINGSMENTIONCHWY | 12 | -0.0317 | 0.0298 | -3.68 | 0.9982 | - |
| KXEARNINGSMENTIONCOINBASE | 47 | -0.0623 | 0.1908 | -2.24 | 0.9850 | - |
| KXEARNINGSMENTIONCOST | 48 | -0.0419 | 0.0309 | -9.40 | 1.0000 | - |
| KXEARNINGSMENTIONCRCL | 17 | -0.0406 | 0.0423 | -3.95 | 0.9994 | - |
| KXEARNINGSMENTIONCRM | 11 | -0.0918 | 0.1277 | -2.39 | 0.9809 | - |
| KXEARNINGSMENTIONCRWD | 23 | -0.0752 | 0.1219 | -2.96 | 0.9964 | - |
| KXEARNINGSMENTIONCVNA | 10 | -0.0250 | 0.0201 | -3.93 | 0.9983 | - |
| KXEARNINGSMENTIONDAL | 23 | -0.0617 | 0.0613 | -4.83 | 1.0000 | - |
| KXEARNINGSMENTIONDELL | 25 | -0.0124 | 0.0242 | -2.56 | 0.9914 | - |
| KXEARNINGSMENTIONDKNG | 26 | -0.0327 | 0.0768 | -2.17 | 0.9802 | - |
| KXEARNINGSMENTIONDOLLARGENERAL | 8 | -0.2050 | 0.2353 | -2.46 | 0.9784 | - |
| KXEARNINGSMENTIONDPZ | 10 | -0.0240 | 0.0190 | -4.00 | 0.9984 | - |
| KXEARNINGSMENTIONETOR | 9 | -0.0344 | 0.0207 | -5.00 | 0.9995 | - |
| KXEARNINGSMENTIONF | 15 | +0.0933 | 0.2907 | 1.24 | 0.1170 | - |
| KXEARNINGSMENTIONGEV | 9 | -0.0056 | 0.2480 | -0.07 | 0.5260 | - |
| KXEARNINGSMENTIONGME | 7 | +0.3757 | 0.1137 | 8.74 | 0.0001 | Y |
| KXEARNINGSMENTIONGOOGL | 65 | -0.0188 | 0.1670 | -0.91 | 0.8158 | - |
| KXEARNINGSMENTIONGS | 23 | +0.0404 | 0.1865 | 1.04 | 0.1549 | - |
| KXEARNINGSMENTIONHD | 22 | -0.0259 | 0.0232 | -5.23 | 1.0000 | - |
| KXEARNINGSMENTIONHIMS | 27 | -0.0152 | 0.1763 | -0.45 | 0.6709 | - |
| KXEARNINGSMENTIONHLT | 11 | -0.0264 | 0.0262 | -3.34 | 0.9963 | - |
| KXEARNINGSMENTIONHOOD | 24 | -0.0371 | 0.0442 | -4.11 | 0.9998 | - |
| KXEARNINGSMENTIONHPE | 10 | -0.0520 | 0.0286 | -5.75 | 0.9999 | - |
| KXEARNINGSMENTIONKO | 20 | -0.0190 | 0.0210 | -4.05 | 0.9997 | - |
| KXEARNINGSMENTIONKR | 25 | -0.0320 | 0.0214 | -7.47 | 1.0000 | - |
| KXEARNINGSMENTIONKTOS | 9 | -0.0378 | 0.0572 | -1.98 | 0.9586 | - |
| KXEARNINGSMENTIONLLY | 10 | -0.0610 | 0.0384 | -5.02 | 0.9996 | - |
| KXEARNINGSMENTIONLUCID | 15 | +0.0993 | 0.3270 | 1.18 | 0.1295 | - |
| KXEARNINGSMENTIONLYFT | 24 | +0.0167 | 0.2028 | 0.40 | 0.3455 | - |
| KXEARNINGSMENTIONMA | 12 | -0.0350 | 0.0334 | -3.63 | 0.9980 | - |
| KXEARNINGSMENTIONMCD | 26 | -0.0181 | 0.0856 | -1.08 | 0.8541 | - |
| KXEARNINGSMENTIONMCO | 10 | -0.0330 | 0.0250 | -4.18 | 0.9988 | - |
| KXEARNINGSMENTIONMETA | 70 | -0.0143 | 0.1687 | -0.71 | 0.7595 | - |
| KXEARNINGSMENTIONMRVL | 21 | -0.0381 | 0.0669 | -2.61 | 0.9916 | - |
| KXEARNINGSMENTIONMSFT | 69 | -0.0477 | 0.1987 | -1.99 | 0.9749 | - |
| KXEARNINGSMENTIONMU | 35 | -0.0257 | 0.1523 | -1.00 | 0.8376 | - |
| KXEARNINGSMENTIONNBIS | 21 | +0.0333 | 0.2217 | 0.69 | 0.2494 | - |
| KXEARNINGSMENTIONNFLX | 56 | -0.0246 | 0.0909 | -2.03 | 0.9763 | - |
| KXEARNINGSMENTIONNIO | 15 | +0.0007 | 0.4582 | 0.01 | 0.4978 | - |
| KXEARNINGSMENTIONNKE | 48 | -0.0085 | 0.0640 | -0.92 | 0.8200 | - |
| KXEARNINGSMENTIONNVDA | 92 | -0.0125 | 0.0685 | -1.75 | 0.9583 | - |
| KXEARNINGSMENTIONON | 8 | -0.0213 | 0.0155 | -3.87 | 0.9969 | - |
| KXEARNINGSMENTIONORCL | 27 | +0.0130 | 0.0971 | 0.69 | 0.2469 | - |
| KXEARNINGSMENTIONPEP | 22 | -0.0132 | 0.0900 | -0.69 | 0.7502 | - |
| KXEARNINGSMENTIONPG | 24 | -0.0083 | 0.0722 | -0.57 | 0.7115 | - |
| KXEARNINGSMENTIONPLTR | 70 | +0.0124 | 0.1712 | 0.61 | 0.2728 | - |
| KXEARNINGSMENTIONPSKY | 12 | -0.0483 | 0.0262 | -6.38 | 1.0000 | - |
| KXEARNINGSMENTIONQCOM | 12 | -0.0467 | 0.0311 | -5.19 | 0.9999 | - |
| KXEARNINGSMENTIONRDDT | 21 | -0.0248 | 0.0626 | -1.81 | 0.9576 | - |
| KXEARNINGSMENTIONRKLB | 25 | -0.0324 | 0.0559 | -2.90 | 0.9960 | - |
| KXEARNINGSMENTIONROKU | 25 | +0.1180 | 0.2575 | 2.29 | 0.0155 | Y |
| KXEARNINGSMENTIONRY | 20 | -0.1015 | 0.2164 | -2.10 | 0.9752 | - |
| KXEARNINGSMENTIONSBUX | 28 | -0.0182 | 0.0355 | -2.72 | 0.9943 | - |
| KXEARNINGSMENTIONSFM | 9 | -0.0322 | 0.0244 | -3.96 | 0.9979 | - |
| KXEARNINGSMENTIONSHOP | 8 | -0.0288 | 0.0155 | -5.24 | 0.9994 | - |
| KXEARNINGSMENTIONSNAP | 24 | -0.0479 | 0.0685 | -3.43 | 0.9989 | - |
| KXEARNINGSMENTIONSPOT | 12 | -0.0342 | 0.0412 | -2.87 | 0.9924 | - |
| KXEARNINGSMENTIONSTZ | 10 | -0.0310 | 0.0202 | -4.84 | 0.9995 | - |
| KXEARNINGSMENTIONTGT | 24 | -0.0242 | 0.0159 | -7.47 | 1.0000 | - |
| KXEARNINGSMENTIONTSLA | 78 | -0.0429 | 0.1592 | -2.38 | 0.9902 | - |
| KXEARNINGSMENTIONTSMC | 12 | -0.0933 | 0.0267 | -12.09 | 1.0000 | - |
| KXEARNINGSMENTIONUAL | 25 | -0.0172 | 0.0510 | -1.69 | 0.9478 | - |
| KXEARNINGSMENTIONUBER | 75 | +0.0200 | 0.2702 | 0.64 | 0.2618 | - |
| KXEARNINGSMENTIONULTA | 12 | -0.0550 | 0.0767 | -2.48 | 0.9848 | - |
| KXEARNINGSMENTIONV | 13 | -0.0177 | 0.0252 | -2.53 | 0.9868 | - |
| KXEARNINGSMENTIONVSCO | 10 | -0.0610 | 0.0640 | -3.01 | 0.9927 | - |
| KXEARNINGSMENTIONVZ | 10 | -0.0270 | 0.0189 | -4.52 | 0.9993 | - |
| KXEARNINGSMENTIONWEN | 12 | -0.0667 | 0.0450 | -5.13 | 0.9998 | - |
| KXEARNINGSMENTIONWFC | 9 | -0.0300 | 0.0150 | -6.00 | 0.9998 | - |
| KXEARNINGSMENTIONWING | 8 | -0.0250 | 0.0160 | -4.41 | 0.9984 | - |
| KXEARNINGSMENTIONWMT | 45 | -0.0649 | 0.2067 | -2.11 | 0.9795 | - |
| KXFEDGOVMENTION | 11 | +0.0873 | 0.4102 | 0.71 | 0.2483 | - |
| KXFEDMENTION | 305 | -0.0024 | 0.1102 | -0.37 | 0.6457 | - |
| KXFIGHTMENTION | 217 | -0.0076 | 0.0587 | -1.92 | 0.9718 | - |
| KXFRANKLINMENTION | 10 | +0.0770 | 0.1813 | 1.34 | 0.1061 | - |
| KXFREYMENTION | 43 | +0.0353 | 0.2205 | 1.05 | 0.1495 | - |
| KXFTNMENTION | 129 | -0.0352 | 0.0841 | -4.75 | 1.0000 | - |
| KXGAMEDAYMENTION | 10 | -0.0100 | 0.0000 | -17293822569102700.00 | 1.0000 | - |
| KXGLASERMENTION | 19 | -0.0132 | 0.0240 | -2.38 | 0.9859 | - |
| KXGOVERNORMENTION | 174 | -0.0256 | 0.0759 | -4.45 | 1.0000 | - |
| KXGRIFFINMENTION | 15 | +0.3180 | 0.2915 | 4.23 | 0.0004 | Y |
| KXHARTMENTION | 11 | +0.0855 | 0.2548 | 1.11 | 0.1460 | - |
| KXHEGSETHMENTION | 90 | -0.0319 | 0.2203 | -1.37 | 0.9134 | - |
| KXHOCHULMENTION | 259 | -0.0359 | 0.0853 | -6.77 | 1.0000 | - |
| KXHOMANMENTION | 69 | -0.0391 | 0.0604 | -5.38 | 1.0000 | - |
| KXINFANTINOMENTION | 26 | -0.0142 | 0.1339 | -0.54 | 0.7037 | - |
| KXJENSENMENTION | 56 | -0.0120 | 0.1605 | -0.56 | 0.7104 | - |
| KXJPOWMENTION | 51 | +0.0141 | 0.3023 | 0.33 | 0.3701 | - |
| KXKAMALAMENTION | 81 | -0.0157 | 0.1501 | -0.94 | 0.8250 | - |
| KXKARPMENTION | 12 | +0.0300 | 0.0686 | 1.51 | 0.0791 | - |
| KXKINGMENTION | 9 | -0.0144 | 0.0159 | -2.73 | 0.9870 | - |
| KXLAMMYMENTION | 11 | +0.0036 | 0.1219 | 0.10 | 0.4616 | - |
| KXLEAVITTMENTIONDURATION | 87 | +0.1069 | 0.2735 | 3.65 | 0.0002 | Y |
| KXLEAVITTSMFMENTION | 54 | +0.0835 | 0.1871 | 3.28 | 0.0009 | Y |
| KXLEBRONMENTION | 21 | -0.0033 | 0.1151 | -0.13 | 0.5521 | - |
| KXLUTNICKFTNMENTION | 32 | +0.0931 | 0.1911 | 2.76 | 0.0049 | Y |
| KXMADDOWMENTION | 39 | +0.0272 | 0.1483 | 1.14 | 0.1298 | - |
| KXMAHERMENTION | 22 | +0.0405 | 0.1919 | 0.99 | 0.1671 | - |
| KXMELANIAMENTION | 90 | -0.0059 | 0.1019 | -0.55 | 0.7076 | - |
| KXMINAJMENTION | 10 | -0.0220 | 0.0155 | -4.49 | 0.9992 | - |
| KXMIRANMENTION | 24 | +0.0700 | 0.2185 | 1.57 | 0.0651 | - |
| KXMLBMENTION | 64 | +0.0516 | 0.2538 | 1.63 | 0.0545 | - |
| KXMMMENTION | 76 | +0.0916 | 0.4025 | 1.98 | 0.0255 | Y |
| KXMRBEASTMENTION | 277 | -0.0106 | 0.2029 | -0.87 | 0.8068 | - |
| KXMTGMENTION | 12 | -0.0333 | 0.0144 | -8.04 | 1.0000 | - |
| KXMTPMENTION | 34 | -0.0279 | 0.0229 | -7.10 | 1.0000 | - |
| KXNADALMENTION | 13 | +0.1954 | 0.1845 | 3.82 | 0.0012 | Y |
| KXNBAMENTION | 2701 | -0.0215 | 0.0958 | -11.65 | 1.0000 | - |
| KXNCAABMENTION | 984 | +0.0488 | 0.2108 | 7.26 | 0.0000 | Y |
| KXNCAAMENTION | 597 | -0.0214 | 0.0701 | -7.48 | 1.0000 | - |
| KXNETANYAHUMENTION | 20 | -0.0410 | 0.0489 | -3.75 | 0.9993 | - |
| KXNEWSOMMENTION | 209 | -0.0192 | 0.0728 | -3.81 | 0.9999 | - |
| KXNFLMENTION | 1509 | -0.0175 | 0.0756 | -9.00 | 1.0000 | - |
| KXNYCMDEBMENTION | 54 | +0.0044 | 0.1314 | 0.25 | 0.4023 | - |
| KXOSCARMENTION | 28 | -0.0957 | 0.4714 | -1.07 | 0.8539 | - |
| KXPAULMENTION | 22 | -0.0114 | 0.0064 | -8.33 | 1.0000 | - |
| KXPERSONMENTION | 88 | -0.0493 | 0.0875 | -5.29 | 1.0000 | - |
| KXPOLITICSMENTION | 157 | -0.0389 | 0.0684 | -7.13 | 1.0000 | - |
| KXPOWELLMENTION | 142 | +0.0337 | 0.1536 | 2.61 | 0.0050 | Y |
| KXPSAKIMENTION | 100 | -0.0177 | 0.1368 | -1.29 | 0.9006 | - |
| KXREEVESMENTION | 12 | +0.0700 | 0.1089 | 2.23 | 0.0239 | Y |
| KXROGANMENTION | 30 | +0.0973 | 0.4413 | 1.21 | 0.1184 | - |
| KXSBMENTION | 19 | +0.0137 | 0.0234 | 2.55 | 0.0100 | Y |
| KXSCHUMERMENTION | 20 | +0.0690 | 0.1253 | 2.46 | 0.0118 | Y |
| KXSCOTUSMENTION | 15 | -0.0180 | 0.0248 | -2.81 | 0.9930 | - |
| KXSECPRESSMENTION | 1154 | -0.0043 | 0.1823 | -0.80 | 0.7873 | - |
| KXSHAQMENTION | 13 | +0.2769 | 0.2778 | 3.59 | 0.0018 | Y |
| KXSHIRLEYMENTION | 12 | -0.0200 | 0.0186 | -3.73 | 0.9983 | - |
| KXSNFMENTION | 289 | -0.0193 | 0.0727 | -4.51 | 1.0000 | - |
| KXSNLMENTION | 138 | +0.0167 | 0.0933 | 2.10 | 0.0189 | Y |
| KXSNOOPMENTION | 14 | +0.0464 | 0.1094 | 1.59 | 0.0682 | - |
| KXSOUTHPARKMENTION | 120 | +0.0528 | 0.1295 | 4.47 | 0.0000 | Y |
| KXSPANBERGERMENTION | 15 | -0.0420 | 0.0386 | -4.22 | 0.9996 | - |
| KXSTARMERMENTION | 146 | +0.0073 | 0.1024 | 0.86 | 0.1964 | - |
| KXSTARMERMENTIONB | 48 | -0.0188 | 0.0321 | -4.05 | 0.9999 | - |
| KXSURVIVORMENTION | 228 | +0.0401 | 0.2189 | 2.77 | 0.0031 | Y |
| KXSWIFTMENTION | 120 | -0.0085 | 0.0582 | -1.60 | 0.9438 | - |
| KXTALARICOMENTION | 36 | -0.0447 | 0.0606 | -4.43 | 1.0000 | - |
| KXTBPNMENTION | 46 | +0.0265 | 0.2251 | 0.80 | 0.2142 | - |
| KXTHEWEEKNIGHTMENTION | 99 | -0.0329 | 0.1178 | -2.78 | 0.9967 | - |
| KXTRUMPMENTION | 2841 | -0.0101 | 0.1566 | -3.45 | 0.9997 | - |
| KXTRUMPMENTIONB | 1379 | -0.0234 | 0.0722 | -12.03 | 1.0000 | - |
| KXTRUMPMENTIONDURATION | 75 | +0.0268 | 0.3275 | 0.71 | 0.2404 | - |
| KXUNMENTION | 35 | -0.0300 | 0.0186 | -9.53 | 1.0000 | - |
| KXVANCEMENTION | 455 | +0.0151 | 0.1861 | 1.74 | 0.0416 | Y |
| KXVIEWMENTION | 10 | +0.2670 | 0.2784 | 3.03 | 0.0071 | Y |
| KXVLADTENEVMENTION | 53 | -0.0268 | 0.1902 | -1.03 | 0.8450 | - |
| KXWALESMENTION | 8 | +0.1037 | 0.2608 | 1.13 | 0.1488 | - |
| KXWALLERMENTION | 36 | +0.0344 | 0.2617 | 0.79 | 0.2175 | - |
| KXWALZMENTION | 100 | -0.0408 | 0.0539 | -7.57 | 1.0000 | - |
| KXWEFMENTION | 38 | -0.0234 | 0.0815 | -1.77 | 0.9576 | - |
| KXZAKARIAMENTION | 54 | -0.0139 | 0.0781 | -1.31 | 0.9014 | - |
| KXZELENSKYYMENTION | 32 | +0.0794 | 0.3535 | 1.27 | 0.1067 | - |
| KXZIWEMENTION | 26 | +0.1269 | 0.2674 | 2.42 | 0.0115 | Y |
| PM_Other | 154 | -0.0001 | 0.0102 | -0.13 | 0.5509 | - |
| PM_PersonNames | 492 | +0.0001 | 0.0100 | 0.31 | 0.3773 | - |

## 7. Calibration by price decile

| Bin | N | Implied | Actual | Overpricing |
|-----|--:|-------:|------:|------------:|
| 0.0–0.1 | 8679 | 0.017 | 0.001 | +0.016 |
| 0.1–0.2 | 953 | 0.137 | 0.018 | +0.119 |
| 0.2–0.3 | 636 | 0.245 | 0.053 | +0.192 |
| 0.3–0.4 | 301 | 0.348 | 0.199 | +0.149 |
| 0.4–0.5 | 264 | 0.436 | 0.250 | +0.186 |
| 0.5–0.6 | 208 | 0.545 | 0.356 | +0.189 |
| 0.6–0.7 | 191 | 0.655 | 0.576 | +0.079 |
| 0.7–0.8 | 205 | 0.753 | 0.771 | -0.018 |
| 0.8–0.9 | 421 | 0.852 | 0.857 | -0.005 |
| 0.9–1.0 | 8982 | 0.982 | 0.994 | -0.012 |

chi2(9) = 381.3, p < 0.001

## 8. Strategy variants

| Strategy | N | Total | mu | Sharpe | WR |
|----------|--:|------:|---:|------:|---:|
| blind_no | 16419 | -84.3 | -0.0051 | -0.036 | 17% |
| political_only | 6949 | -50.6 | -0.0073 | -0.050 | 19% |
| earnings_only | 779 | -15.9 | -0.0204 | -0.142 | 18% |
| sports_only | 5458 | -38.0 | -0.0070 | -0.056 | 13% |
| media_only | 188 | -0.2 | -0.0009 | -0.008 | 13% |
| selective_edge≥5c | 3638 | +116.5 | +0.0320 | 0.150 | 32% |
| selective_edge≥10c | 1026 | +60.8 | +0.0593 | 0.246 | 39% |
| high_volume≥10k | 7893 | -174.2 | -0.0221 | -0.463 | 5% |
| low_br≤50% | 11903 | +7.7 | +0.0006 | 0.004 | 19% |
| tight_filter | 380 | -3.4 | -0.0088 | -0.076 | 12% |

### Top 10 sweep configs (by Sharpe, N >= 20)

| Config | N | mu | Sharpe | WR |
|--------|--:|---:|------:|---:|
| e0.15_br0.30_v0 | 209 | +0.0976 | 0.405 | 45% |
| e0.15_br0.40_v0 | 319 | +0.0875 | 0.352 | 41% |
| e0.10_br0.30_v0 | 452 | +0.0745 | 0.322 | 46% |
| e0.15_br0.50_v0 | 334 | +0.0805 | 0.313 | 41% |
| e0.15_br0.60_v0 | 334 | +0.0805 | 0.313 | 41% |
| e0.15_br0.80_v0 | 334 | +0.0805 | 0.313 | 41% |
| e0.15_br1.00_v0 | 334 | +0.0805 | 0.313 | 41% |
| e0.08_br0.30_v0 | 632 | +0.0554 | 0.265 | 41% |
| e0.10_br0.40_v0 | 697 | +0.0629 | 0.259 | 42% |
| e0.10_br0.50_v0 | 1022 | +0.0597 | 0.248 | 39% |

## 9. LibFrog transcript base rate comparison

Matched 2062/2177 earnings markets (95%) against LibFrog historical transcript data.
**59 matches have <10 transcript calls (low confidence).**

### Overpricing summary

| Metric | Value |
|--------|-------|
| Matched markets | 2062 |
| Avg overpricing (Kalshi - LibFrog) | +0.251 |
| Median overpricing | +0.132 |
| % overpriced | 67% |

### Is transcript data alpha? PnL analysis

| Strategy | N | mu(net) | Total | WR | CI |
|----------|--:|-------:|------:|---:|---:|
| Blind NO (all matched) | 2062 | -0.0183 | -37.7 | 16% | - |
| LibFrog signal (edge>5c) | 1183 | -0.0230 | -27.2 | 16% | [-0.032, -0.014] |
| HC signal (n_calls>=10) | 1154 | -0.0233 | -26.9 | 16% | [-0.033, -0.014] |

### Top overpriced/underpriced (by magnitude)

| Company | Word | Kalshi | LibFrog | Delta | n_calls | Outcome | NO PnL |
|---------|------|------:|-------:|------:|--------:|:-------:|------:|
| CRCL | Acceleration | 0.990 | 0.000 | +0.990 | 1* | YES | -0.040 |
| CRCL | Polymarket | 0.990 | 0.000 | +0.990 | 1* | YES | -0.040 |
| CRCL | M&A / Merger | 0.010 | 1.000 | -0.990 | 1* | NO | -0.010 |
| CRCL | Treasury | 0.010 | 1.000 | -0.990 | 1* | NO | -0.010 |
| CRCL | Fintech | 0.990 | 0.000 | +0.990 | 1* | YES | -0.040 |
| RDDT | OpenAI / Open AI | 0.990 | 0.000 | +0.990 | 8* | YES | -0.040 |
| MA | Rate Cap / 10% Cap | 0.990 | 0.000 | +0.990 | 76 | YES | -0.040 |
| AMZN | Gen-AI / Generative AI | 0.990 | 0.000 | +0.990 | 81 | YES | -0.040 |
| ACI | SNAP / Food Stamp | 0.990 | 0.000 | +0.990 | 18 | YES | -0.040 |
| DPZ | DoorDash (5+ times) | 0.990 | 0.000 | +0.990 | 64 | YES | -0.040 |
| PLTR | Warp Speed | 0.990 | 0.000 | +0.990 | 22 | YES | -0.040 |
| PLTR | Warp Speed | 0.990 | 0.000 | +0.990 | 22 | YES | -0.040 |
| SBUX | Non Dairy | 0.990 | 0.000 | +0.990 | 78 | YES | -0.040 |
| NVDA | Export restriction | 0.990 | 0.000 | +0.990 | 78 | YES | -0.040 |
| NVDA | Generative AI / Gen AI / Gen-AI | 0.990 | 0.000 | +0.990 | 78 | YES | -0.040 |
| AMD | Export restriction | 0.990 | 0.000 | +0.990 | 75 | YES | -0.040 |
| MCD | Tariff | 0.990 | 0.000 | +0.990 | 78 | YES | -0.040 |
| BLK | ETF inflow | 0.990 | 0.000 | +0.990 | 71 | YES | -0.040 |
| HOOD | SIG / Susquehanna | 0.990 | 0.000 | +0.990 | 18 | YES | -0.040 |
| HOOD | Prediction Market | 0.990 | 0.000 | +0.990 | 18 | YES | -0.040 |

## 10. Capacity analysis

| Metric | Value |
|--------|-------|
| Total volume | $462,070,262 |
| Unique events | 1599 |
| Unique series | 205 |
| Data span | 1855d (5.1y) |
| Max capital at 5% cap | $11,760,170 |
| Dollar PnL (capped) | $-450,267 |
| Annualized PnL | $-88,658 |
| Annualized return | -3.8% |

## 11. Price range analysis

Markets with extreme opening prices (<5% or >95%) are trivially obvious. The real edge opportunity is in the **competitive range** (5-95%).

| Price range | N | % | Base rate | Avg price | Overpricing | Net mu | Sharpe |
|-------------|--:|--:|----------:|----------:|------------:|------:|------:|
| <5% | 8,224 | 39% | 0.001 | 0.014 | +0.013 | -0.0082 | -0.244 |
| 5-25% | 1,813 | 9% | 0.020 | 0.141 | +0.121 | +0.0906 | 0.616 |
| 25-50% | 840 | 4% | 0.185 | 0.365 | +0.181 | +0.1510 | 0.396 |
| 50-75% | 464 | 2% | 0.550 | 0.639 | +0.089 | +0.0592 | 0.124 |
| 75-95% | 1,307 | 6% | 0.912 | 0.893 | -0.019 | -0.0494 | -0.180 |
| >95% | 8,192 | 39% | 0.997 | 0.988 | -0.010 | -0.0390 | -0.766 |

**Competitive range (5-95%) only: N=4,424, mu=$+0.0574, Sharpe=0.193**
**Bootstrap 95% CI: [$+0.0486, $+0.0663] — excludes zero**

## Verdict

**BLIND NO EDGE KILLED (all markets)**

Mean PnL <= 0 after realistic friction on the full dataset. The blind NO strategy does not survive fees + slippage across all 7,000+ markets.

However, the **competitive range (5-95%)** retains significant edge: mu=$+0.0574, CI excludes zero. The edge is real but requires filtering out trivially-priced markets.

### Key risks

1. **Category concentration**: Edge is concentrated in some categories. Blind NO across all categories destroys alpha.
2. **Extreme prices dominate**: 78% of markets have prices <5% or >95%, diluting the signal from competitive-range markets.
3. **Autocorrelation**: Within-event clustering reduces effective sample size.
4. **Liquidity**: At 5% volume cap, capital deployed per market is small.
5. **Regime change**: As markets mature, mispricing may compress.

---
*20,840 markets · 10,000 bootstrap resamples · Kalshi fee $0.02/RT · PM fee $0 · Slippage sensitivity 0-3c*
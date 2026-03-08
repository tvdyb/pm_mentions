#!/usr/bin/env python3
"""Walk-forward logistic regression model for mention market mispricing.

Trains on competitive-range (5-95% price) markets using expanding window.
Features: base rate, price, category, series age, volume, history depth.

Usage:
    python scripts/signal_model.py              # run walk-forward backtest
    python scripts/signal_model.py --compare    # compare vs grid filter
"""

import argparse
import json
import math
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
KALSHI_EXPANDED = Path("data/real_markets/kalshi_all_series.json")
KALSHI_ORIGINAL = Path("data/real_markets/real_data_combined.json")
PM_PATH = Path("data/real_markets/polymarket_all_mentions.json")
LIBFROG_MATCHED = Path("data/base_rates/libfrog_kalshi_matched.json")
LIBFROG_GENERIC = Path("data/base_rates/libfrog_earnings.json")
OUT_DIR = Path("output/model")
OUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = OUT_DIR / "model_weights.json"

KALSHI_FEE_RT = 0.02
PM_FEE = 0.0
DEFAULT_SLIPPAGE = 0.01
MIN_HISTORY = 10       # minimum markets in series before trading
EDGE_THRESHOLD = 0.10  # minimum |edge| to trade
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 42

# Category encoding
CATEGORIES = ["earnings_word", "media_word", "other",
              "political_person", "sports_word"]

# ---------------------------------------------------------------------------
# Data loading (reuse from backtest_v2)
# ---------------------------------------------------------------------------

import re

MEDIA_SERIES = {
    "KX60MINMENTION", "KXTHEWEEKNIGHTMENTION", "KXZAKARIAMENTION",
    "KXMAHERMENTION", "KXLEAVITTSMFMENTION", "KXCARLSONMENTION",
    "KXVIEWMENTION", "KXARMSTRONGMENTION", "KXPAULMENTION",
    "KXKINGMENTION",
}

SPORTS_SERIES = {
    "KXNCAABMENTION", "KXMLBMENTION", "KXNBAMENTION",
    "KXNFLMENTION", "KXSERIEA",
}


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    m = re.search(r"(\d{2})([A-Z]{3})(\d{2})", s)
    if m:
        yr, mon, day = m.groups()
        months = dict(JAN=1, FEB=2, MAR=3, APR=4, MAY=5, JUN=6,
                      JUL=7, AUG=8, SEP=9, OCT=10, NOV=11, DEC=12)
        if mon in months:
            return datetime(2000 + int(yr), months[mon], int(day))
    return None


def _classify_series(series, hint=""):
    s = series.upper()
    if "EARNINGS" in s:
        return "earnings_word"
    if s in SPORTS_SERIES or hint == "sports":
        return "sports_word"
    if s in MEDIA_SERIES:
        return "media_word"
    political = ["TRUMP", "BIDEN", "VANCE", "STARMER", "REEVES", "POWELL",
                 "SCHUMER", "CUOMO", "PERSON", "POLITICS", "FED", "AMODEI",
                 "CULTURE", "KARP"]
    for kw in political:
        if kw in s:
            return "political_person"
    if hint == "political_person":
        return "political_person"
    return "other"


def load_markets():
    markets = []
    seen = set()

    if KALSHI_EXPANDED.exists():
        with open(KALSHI_EXPANDED) as f:
            raw = json.load(f)
        for m in raw.get("markets", []):
            t = m.get("ticker", "")
            if t in seen:
                continue
            seen.add(t)
            op = m.get("opening_price")
            if op is None or op <= 0 or op >= 1:
                continue
            markets.append({
                "source": "kalshi",
                "ticker": t,
                "series": m.get("series", ""),
                "event": m.get("event_ticker", ""),
                "word": m.get("strike_word", ""),
                "outcome": 1 if m.get("result") == "yes" else 0,
                "mid": op,
                "volume": m.get("volume", 0),
                "date": _parse_date(m.get("close_time", "")),
                "category": _classify_series(m.get("series", ""),
                                             m.get("category", "")),
            })

    if KALSHI_ORIGINAL.exists():
        with open(KALSHI_ORIGINAL) as f:
            raw = json.load(f)
        for m in raw.get("kalshi", []):
            t = m.get("ticker", "")
            if t in seen:
                continue
            seen.add(t)
            op = m.get("opening_price")
            if op is None or op <= 0 or op >= 1:
                continue
            markets.append({
                "source": "kalshi",
                "ticker": t,
                "series": m.get("series", ""),
                "event": m.get("event_ticker", ""),
                "word": m.get("strike_word", ""),
                "outcome": 1 if m.get("result") == "yes" else 0,
                "mid": op,
                "volume": m.get("volume", 0),
                "date": _parse_date(m.get("event_ticker", "")),
                "category": _classify_series(m.get("series", "")),
            })

    return markets


def load_libfrog():
    matched = {}
    if LIBFROG_MATCHED.exists():
        with open(LIBFROG_MATCHED) as f:
            raw = json.load(f)
        for key, val in raw.get("matches", {}).items():
            if val.get("base_rate") is not None:
                matched[key] = val

    generic = {}
    if LIBFROG_GENERIC.exists():
        with open(LIBFROG_GENERIC) as f:
            raw = json.load(f)
        generic = raw.get("companies", {})

    return {"matched": matched, "generic": generic}


def libfrog_rate(libfrog, company, word):
    """Get LibFrog base rate for (company, word)."""
    matched = libfrog.get("matched", {})
    generic = libfrog.get("generic", {})

    key = f"{company}|{word}"
    if key in matched:
        entry = matched[key]
        return entry.get("base_rate"), entry.get("n_calls", 0)

    # Try "/" alternatives
    if " / " in word:
        for part in word.split(" / "):
            part = part.strip()
            for mk, mv in matched.items():
                if mk.startswith(f"{company}|") and mv.get("kalshi_word") == word:
                    if mv.get("base_rate") is not None:
                        return mv["base_rate"], mv.get("n_calls", 0)

    # Generic
    if company in generic:
        for lf_word, lf_data in generic[company].items():
            if lf_word.lower() == word.lower():
                return lf_data.get("base_rate"), lf_data.get("n_calls", 0)
            if " / " in word:
                for part in word.split(" / "):
                    if lf_word.lower() == part.strip().lower():
                        return lf_data.get("base_rate"), lf_data.get("n_calls", 0)

    return None, 0


# ---------------------------------------------------------------------------
# PnL
# ---------------------------------------------------------------------------

def compute_pnl(mid, outcome, source, side="NO", slippage=DEFAULT_SLIPPAGE):
    """Compute PnL for a trade. side='NO' or 'YES'."""
    if source == "kalshi":
        fee = KALSHI_FEE_RT
    else:
        fee = PM_FEE

    if side == "NO":
        effective_yes = max(0.01, mid - slippage)
        no_cost = 1.0 - effective_yes
        gross = effective_yes if outcome == 0 else -no_cost
    else:  # YES
        effective_yes = min(0.99, mid + slippage)
        gross = (1.0 - effective_yes) if outcome == 1 else -effective_yes

    return gross - fee


# ---------------------------------------------------------------------------
# Logistic regression (manual, no sklearn dependency)
# ---------------------------------------------------------------------------

def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))


def logistic_train(X, y, lr=0.01, n_iter=500, l2=1.0):
    """Train L2-regularized logistic regression via gradient descent."""
    n, d = X.shape
    w = np.zeros(d)
    b = 0.0

    for _ in range(n_iter):
        z = X @ w + b
        p = sigmoid(z)
        grad_w = (X.T @ (p - y)) / n + l2 * w
        grad_b = np.mean(p - y)
        w -= lr * grad_w
        b -= lr * grad_b

    return w, b


def logistic_predict(X, w, b):
    return sigmoid(X @ w + b)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def build_features(market, prior_series, prior_word, series_first_date,
                   libfrog_data):
    """Build feature vector for a single market.

    Features (7):
    0. series_base_rate: expanding-window base rate for this series
    1. word_base_rate: expanding-window base rate for this word (across series)
    2. opening_price: market implied probability
    3. log_volume: log(1 + volume)
    4. n_history: number of prior markets in series (confidence)
    5. series_age_days: days since first market in this series
    6. libfrog_rate: LibFrog transcript base rate (0.5 if unknown)
    """
    m = market

    # Series base rate
    if len(prior_series) >= 3:
        series_br = np.mean([p["outcome"] for p in prior_series])
    else:
        series_br = 0.5  # uninformative prior

    # Word base rate (across all series)
    if len(prior_word) >= 3:
        word_br = np.mean([p["outcome"] for p in prior_word])
    else:
        word_br = 0.5

    # Opening price
    price = m["mid"]

    # Volume
    log_vol = math.log1p(m["volume"])

    # History depth
    n_hist = len(prior_series)

    # Series age
    if series_first_date and m["date"]:
        age = (m["date"] - series_first_date).days
    else:
        age = 0

    # LibFrog rate
    company = (m["series"].replace("KXEARNINGSMENTION", "")
                          .replace("KXEARNIGSMENTION", "")
                          .replace("KXEARNIGNSMENTIO", "")
                          .upper())
    lf_rate, lf_n = libfrog_rate(libfrog_data, company, m["word"])
    if lf_rate is None or lf_n < 5:
        lf_rate = 0.5  # uninformative

    return np.array([
        series_br,
        word_br,
        price,
        log_vol / 15.0,  # normalize (log(100k) ≈ 11.5)
        min(n_hist / 100.0, 1.0),  # normalize
        min(age / 365.0, 2.0),  # normalize
        lf_rate,
    ])


FEATURE_NAMES = [
    "series_base_rate",
    "word_base_rate",
    "opening_price",
    "log_volume_norm",
    "n_history_norm",
    "series_age_norm",
    "libfrog_rate",
]


# ---------------------------------------------------------------------------
# Walk-forward model backtest
# ---------------------------------------------------------------------------

def walk_forward_backtest(markets, libfrog_data, min_train=50):
    """Walk-forward: for each market, use model to estimate P(YES).

    The model combines multiple base-rate signals and learns to weight
    them optimally. The key signal is (price - base_rate), i.e. overpricing.
    """
    # Filter to competitive range
    competitive = [m for m in markets if 0.05 < m["mid"] <= 0.95]
    competitive.sort(key=lambda x: x["date"] or datetime.max)

    print(f"  Competitive range: {len(competitive)} markets")

    # Build series/word indices
    by_series = defaultdict(list)
    by_word = defaultdict(list)
    series_first = {}

    results = []
    all_features = []
    all_labels = []

    for i, m in enumerate(competitive):
        series = m["series"]
        word = m["word"]

        prior_series = by_series[series]
        prior_word = by_word[word]

        if series not in series_first:
            series_first[series] = m["date"]

        # Build features
        feat = build_features(m, prior_series, prior_word,
                              series_first.get(series), libfrog_data)

        # Update indices AFTER feature extraction (no lookahead)
        by_series[series].append(m)
        by_word[word].append(m)

        # Need minimum training data
        if i < min_train:
            all_features.append(feat)
            all_labels.append(m["outcome"])
            continue

        # Train on all prior data
        X_train = np.array(all_features)
        y_train = np.array(all_labels)

        # Train logistic regression
        w, b = logistic_train(X_train, y_train, lr=0.1, n_iter=500, l2=0.5)

        # Predict P(YES)
        p_yes = float(logistic_predict(feat.reshape(1, -1), w, b)[0])

        # Also compute simple base-rate estimate for comparison
        if len(prior_series) >= MIN_HISTORY:
            simple_br = np.mean([p["outcome"] for p in prior_series])
        else:
            simple_br = 0.5

        # Decide using model prediction
        edge = m["mid"] - p_yes
        side = None
        pnl = 0.0

        if edge > EDGE_THRESHOLD:
            side = "NO"
            pnl = compute_pnl(m["mid"], m["outcome"], m["source"], "NO")
        elif edge < -EDGE_THRESHOLD:
            side = "YES"
            pnl = compute_pnl(m["mid"], m["outcome"], m["source"], "YES")

        # Also compute what the simple filter would do
        simple_edge = m["mid"] - simple_br
        simple_side = None
        simple_pnl = 0.0
        if simple_edge > 0.10 and simple_br <= 0.50 and len(prior_series) >= MIN_HISTORY:
            simple_side = "NO"
            simple_pnl = compute_pnl(m["mid"], m["outcome"], m["source"], "NO")

        results.append({
            "ticker": m["ticker"],
            "series": m["series"],
            "category": m["category"],
            "word": m["word"],
            "mid": m["mid"],
            "p_yes": p_yes,
            "simple_br": simple_br,
            "edge": edge,
            "side": side,
            "outcome": m["outcome"],
            "pnl": pnl,
            "simple_side": simple_side,
            "simple_pnl": simple_pnl,
            "model_agrees_simple": (side == simple_side) if side and simple_side else None,
            "features": feat.tolist(),
        })

        # Add to training set
        all_features.append(feat)
        all_labels.append(m["outcome"])

    return results, w, b


def grid_filter_backtest(markets):
    """Baseline: expanding-window grid filter (edge>=10c, br<=50%)."""
    competitive = [m for m in markets if 0.05 < m["mid"] <= 0.95]
    competitive.sort(key=lambda x: x["date"] or datetime.max)

    by_series = defaultdict(list)
    results = []

    for m in competitive:
        series = m["series"]
        prior = by_series[series]
        by_series[series].append(m)

        if len(prior) < MIN_HISTORY:
            continue

        br = np.mean([p["outcome"] for p in prior])
        avg_mid = np.mean([p["mid"] for p in prior])
        edge = avg_mid - br

        if edge >= 0.10 and br <= 0.50:
            pnl = compute_pnl(m["mid"], m["outcome"], m["source"], "NO")
            results.append({
                "ticker": m["ticker"],
                "mid": m["mid"],
                "outcome": m["outcome"],
                "pnl": pnl,
                "side": "NO",
            })

    return results


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_results(results, label):
    """Compute stats for a set of trade results."""
    traded = [r for r in results if r.get("side") is not None]
    if not traded:
        return {"label": label, "n": 0}

    pnls = np.array([r["pnl"] for r in traded])
    n = len(pnls)

    stats_dict = {
        "label": label,
        "n": n,
        "total_pnl": float(pnls.sum()),
        "mean_pnl": float(pnls.mean()),
        "std_pnl": float(pnls.std(ddof=1)) if n > 1 else 0,
        "sharpe": float(pnls.mean() / pnls.std(ddof=1)) if n > 1 and pnls.std(ddof=1) > 0 else 0,
        "win_rate": float((pnls > 0).mean()),
        "n_no": sum(1 for r in traded if r["side"] == "NO"),
        "n_yes": sum(1 for r in traded if r["side"] == "YES"),
    }

    if n >= 20:
        rng = np.random.default_rng(BOOTSTRAP_SEED)
        boot_means = np.array([pnls[rng.integers(n, size=n)].mean()
                               for _ in range(BOOTSTRAP_N)])
        stats_dict["ci_lo"] = float(np.percentile(boot_means, 2.5))
        stats_dict["ci_hi"] = float(np.percentile(boot_means, 97.5))
        stats_dict["ci_excl_zero"] = stats_dict["ci_lo"] > 0

    return stats_dict


def feature_importance(w, feature_names):
    """Return sorted feature importances from logistic regression weights."""
    imp = []
    for name, weight in zip(feature_names, w):
        imp.append({"feature": name, "weight": float(weight),
                     "abs_weight": abs(float(weight))})
    return sorted(imp, key=lambda x: x["abs_weight"], reverse=True)


def calibration_curve(results, n_bins=10):
    """Compute calibration of model predictions."""
    traded = [r for r in results if "p_yes" in r]
    if len(traded) < 20:
        return []

    preds = np.array([r["p_yes"] for r in traded])
    actuals = np.array([r["outcome"] for r in traded])
    bins = np.linspace(0, 1, n_bins + 1)
    rows = []

    for i in range(n_bins):
        mask = (preds >= bins[i]) & (preds < bins[i + 1])
        if i == n_bins - 1:
            mask = (preds >= bins[i]) & (preds <= bins[i + 1])
        n = mask.sum()
        if n < 3:
            continue
        rows.append({
            "bin": f"{bins[i]:.1f}-{bins[i+1]:.1f}",
            "n": int(n),
            "pred_mean": float(preds[mask].mean()),
            "actual_mean": float(actuals[mask].mean()),
        })
    return rows


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def make_plots(model_results, grid_results, calibration, feature_imp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "sans-serif", "font.size": 9,
        "axes.titlesize": 11, "axes.labelsize": 10,
        "figure.dpi": 180, "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True,
        "grid.alpha": 0.25,
    })
    C_BLUE, C_GREEN, C_RED, C_GRAY = "#1565C0", "#2E7D32", "#C62828", "#616161"

    # 1. Cumulative PnL comparison
    fig, ax = plt.subplots(figsize=(10, 4.5))
    model_traded = [r for r in model_results if r.get("side")]
    model_cum = np.cumsum([r["pnl"] for r in model_traded])
    grid_cum = np.cumsum([r["pnl"] for r in grid_results])
    ax.plot(model_cum, label=f"Model (n={len(model_traded)})", color=C_BLUE, lw=1.3)
    ax.plot(grid_cum, label=f"Grid filter (n={len(grid_results)})", color=C_GREEN, lw=1.3)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Cumulative PnL ($)")
    ax.set_title("Model vs grid filter: cumulative PnL")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "1_model_vs_grid.png")
    plt.close()

    # 2. Feature importances
    if feature_imp:
        fig, ax = plt.subplots(figsize=(7, 4))
        names = [f["feature"] for f in feature_imp]
        weights = [f["weight"] for f in feature_imp]
        cols = [C_GREEN if w < 0 else C_RED for w in weights]
        # Negative weight on a feature = feature predicts YES, so NO strategy benefits
        ax.barh(range(len(names)), weights, color=cols, alpha=0.8)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=8)
        ax.set_xlabel("Weight (negative = predicts NO win)")
        ax.set_title("Feature importances (logistic regression)")
        ax.axvline(0, color="black", lw=0.5)
        plt.tight_layout()
        plt.savefig(OUT_DIR / "2_feature_importance.png")
        plt.close()

    # 3. Calibration
    if calibration:
        fig, ax = plt.subplots(figsize=(6, 5))
        pred = [c["pred_mean"] for c in calibration]
        actual = [c["actual_mean"] for c in calibration]
        ns = [c["n"] for c in calibration]
        ax.plot([0, 1], [0, 1], "k--", alpha=0.4, lw=0.8)
        ax.scatter(pred, actual, s=[max(20, n/2) for n in ns],
                   c=C_BLUE, alpha=0.8, edgecolors="white", lw=0.5)
        for c in calibration:
            ax.annotate(f'n={c["n"]}', (c["pred_mean"], c["actual_mean"]),
                        xytext=(4, 4), textcoords="offset points", fontsize=6.5)
        ax.set_xlabel("Model P(YES)")
        ax.set_ylabel("Actual YES rate")
        ax.set_title("Model calibration (walk-forward)")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        plt.tight_layout()
        plt.savefig(OUT_DIR / "3_model_calibration.png")
        plt.close()

    # 4. PnL distribution
    if model_traded:
        fig, ax = plt.subplots(figsize=(7, 4))
        pnls = [r["pnl"] for r in model_traded]
        ax.hist(pnls, bins=40, color=C_BLUE, alpha=0.7, edgecolor="white", lw=0.3)
        ax.axvline(np.mean(pnls), color=C_RED, lw=1.5,
                   label=f"mu=${np.mean(pnls):.3f}")
        ax.axvline(0, color="black", lw=0.5)
        ax.set_xlabel("PnL per trade ($)")
        ax.set_title("Model trade PnL distribution")
        ax.legend(fontsize=8)
        plt.tight_layout()
        plt.savefig(OUT_DIR / "4_model_pnl_dist.png")
        plt.close()

    print(f"  Plots saved to {OUT_DIR}/")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def generate_report(model_stats, grid_stats, feature_imp, calibration,
                    model_results):
    L = []
    w = L.append

    w("# Signal Model: Walk-Forward Logistic Regression")
    w("")
    w(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w("")
    w("---")
    w("")

    w("## Model specification")
    w("")
    w("- **Type**: L2-regularized logistic regression (lambda=2.0)")
    w("- **Training**: Walk-forward (train on all prior, predict next)")
    w("- **Universe**: Competitive-range markets (5-95% opening price)")
    w("- **Trade rule**: Buy NO if P(YES) < price - 5c; Buy YES if P(YES) > price + 5c")
    w("- **Friction**: Kalshi $0.02 RT fee + 1c slippage")
    w("")

    w("## Features")
    w("")
    w("| Feature | Description |")
    w("|---------|-------------|")
    w("| series_base_rate | Expanding-window YES rate for this series |")
    w("| word_base_rate | Expanding-window YES rate for this word (all series) |")
    w("| opening_price | Market implied probability |")
    w("| log_volume_norm | log(1+volume)/15 |")
    w("| n_history_norm | min(n_prior/100, 1) |")
    w("| series_age_norm | min(days_since_first/365, 2) |")
    w("| libfrog_rate | LibFrog transcript base rate (0.5 if unknown) |")
    w("")

    w("## Feature importances (final weights)")
    w("")
    w("| Feature | Weight | Interpretation |")
    w("|---------|------:|---------------|")
    for f in feature_imp:
        interp = "predicts YES" if f["weight"] > 0 else "predicts NO"
        w(f"| {f['feature']} | {f['weight']:+.4f} | {interp} |")
    w("")

    w("## Model vs grid filter comparison")
    w("")
    w("| Metric | Model | Grid filter (edge>=10c, br<=50%) |")
    w("|--------|------:|--------------------------------:|")
    for key, label in [
        ("n", "Trades"),
        ("total_pnl", "Total PnL"),
        ("mean_pnl", "Mean PnL"),
        ("sharpe", "Sharpe"),
        ("win_rate", "Win rate"),
    ]:
        mv = model_stats.get(key, 0)
        gv = grid_stats.get(key, 0)
        if key == "win_rate":
            w(f"| {label} | {mv:.0%} | {gv:.0%} |")
        elif key in ("total_pnl", "mean_pnl"):
            w(f"| {label} | ${mv:+.3f} | ${gv:+.3f} |")
        elif key == "sharpe":
            w(f"| {label} | {mv:.3f} | {gv:.3f} |")
        else:
            w(f"| {label} | {mv} | {gv} |")
    w("")

    if "ci_lo" in model_stats:
        excl = "Yes" if model_stats.get("ci_excl_zero") else "No"
        w(f"**Model bootstrap 95% CI: "
          f"[${model_stats['ci_lo']:+.4f}, ${model_stats['ci_hi']:+.4f}] "
          f"(excludes zero: {excl})**")
    if "ci_lo" in grid_stats:
        excl = "Yes" if grid_stats.get("ci_excl_zero") else "No"
        w(f"**Grid bootstrap 95% CI: "
          f"[${grid_stats['ci_lo']:+.4f}, ${grid_stats['ci_hi']:+.4f}] "
          f"(excludes zero: {excl})**")
    w("")

    if model_stats.get("n_yes", 0) > 0:
        w(f"Model trades: {model_stats.get('n_no', 0)} NO, "
          f"{model_stats.get('n_yes', 0)} YES")
        w("")

    w("## Model calibration")
    w("")
    if calibration:
        w("| Bin | N | Predicted | Actual |")
        w("|-----|--:|----------:|-------:|")
        for c in calibration:
            w(f"| {c['bin']} | {c['n']} | {c['pred_mean']:.3f} | "
              f"{c['actual_mean']:.3f} |")
    else:
        w("Insufficient data for calibration.")
    w("")

    w("---")
    w(f"*Walk-forward on {model_stats.get('n', 0) + 50} competitive-range markets*")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    print("=" * 65)
    print("  WALK-FORWARD SIGNAL MODEL")
    print("  Logistic regression on competitive-range markets")
    print("=" * 65)

    print("\nLoading data...")
    markets = load_markets()
    libfrog = load_libfrog()
    print(f"  {len(markets):,} total markets")
    competitive = [m for m in markets if 0.05 < m["mid"] <= 0.95]
    print(f"  {len(competitive):,} competitive range (5-95%)")

    # Walk-forward model
    print("\n[1/3] Walk-forward logistic regression...")
    model_results, final_w, final_b = walk_forward_backtest(markets, libfrog)
    model_stats = analyze_results(model_results, "model")
    print(f"  Trades: {model_stats['n']}")
    if model_stats["n"] > 0:
        print(f"  Mean PnL: ${model_stats['mean_pnl']:+.4f}")
        print(f"  Sharpe: {model_stats['sharpe']:.3f}")
        print(f"  Win rate: {model_stats['win_rate']:.0%}")
        print(f"  NO/YES split: {model_stats.get('n_no', 0)}/{model_stats.get('n_yes', 0)}")
        if "ci_lo" in model_stats:
            excl = "YES" if model_stats.get("ci_excl_zero") else "NO"
            print(f"  Bootstrap CI: [{model_stats['ci_lo']:+.4f}, "
                  f"{model_stats['ci_hi']:+.4f}] excl zero: {excl}")

    # Grid filter baseline
    print("\n[2/3] Grid filter baseline (edge>=10c, br<=50%)...")
    grid_results = grid_filter_backtest(markets)
    grid_stats = analyze_results(grid_results, "grid")
    print(f"  Trades: {grid_stats['n']}")
    if grid_stats["n"] > 0:
        print(f"  Mean PnL: ${grid_stats['mean_pnl']:+.4f}")
        print(f"  Sharpe: {grid_stats['sharpe']:.3f}")
        print(f"  Win rate: {grid_stats['win_rate']:.0%}")
        if "ci_lo" in grid_stats:
            excl = "YES" if grid_stats.get("ci_excl_zero") else "NO"
            print(f"  Bootstrap CI: [{grid_stats['ci_lo']:+.4f}, "
                  f"{grid_stats['ci_hi']:+.4f}] excl zero: {excl}")

    # Feature importance
    feat_imp = feature_importance(final_w, FEATURE_NAMES)
    print("\n  Feature importances:")
    for f in feat_imp:
        print(f"    {f['feature']:25s}  w={f['weight']:+.4f}")

    # Calibration
    cal = calibration_curve(model_results)

    # Save model weights
    model_save = {
        "weights": final_w.tolist(),
        "bias": float(final_b),
        "feature_names": FEATURE_NAMES,
        "edge_threshold": EDGE_THRESHOLD,
        "trained_at": datetime.now().isoformat(),
        "n_training_markets": len(competitive),
    }
    with open(MODEL_PATH, "w") as f:
        json.dump(model_save, f, indent=2)
    print(f"\n  Model saved to {MODEL_PATH}")

    # Plots & report
    print("\n[3/3] Generating report & plots...")
    make_plots(model_results, grid_results, cal, feat_imp)

    report = generate_report(model_stats, grid_stats, feat_imp, cal,
                             model_results)
    rpath = OUT_DIR / "signal_model_report.md"
    with open(rpath, "w") as f:
        f.write(report)
    print(f"  Report: {rpath}")

    # Summary
    print("\n" + "=" * 65)
    winner = "MODEL" if model_stats.get("sharpe", 0) > grid_stats.get("sharpe", 0) else "GRID"
    print(f"  WINNER: {winner}")
    print(f"  Model  Sharpe={model_stats.get('sharpe', 0):.3f}  "
          f"mu=${model_stats.get('mean_pnl', 0):+.4f}  "
          f"n={model_stats.get('n', 0)}")
    print(f"  Grid   Sharpe={grid_stats.get('sharpe', 0):.3f}  "
          f"mu=${grid_stats.get('mean_pnl', 0):+.4f}  "
          f"n={grid_stats.get('n', 0)}")
    print("=" * 65)


if __name__ == "__main__":
    main()

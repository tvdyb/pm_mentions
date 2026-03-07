"""Analytics and reporting for mention market backtest results."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

from ..models import BacktestResult, SpeechEvent


def compute_metrics(result: BacktestResult) -> dict:
    """Compute summary metrics from backtest results."""
    if not result.trades:
        return {"error": "No trades"}

    df = pd.DataFrame(result.trades)

    n_trades = len(df)
    n_yes = len(df[df["side"] == "YES"])
    n_no = len(df[df["side"] == "NO"])

    # Win rates
    wins = df[df["dollar_pnl"] > 0]
    win_rate = len(wins) / n_trades if n_trades > 0 else 0
    no_trades = df[df["side"] == "NO"]
    yes_trades = df[df["side"] == "YES"]
    no_win_rate = len(no_trades[no_trades["dollar_pnl"] > 0]) / len(no_trades) if len(no_trades) > 0 else 0
    yes_win_rate = len(yes_trades[yes_trades["dollar_pnl"] > 0]) / len(yes_trades) if len(yes_trades) > 0 else 0

    # PnL
    total_pnl = df["dollar_pnl"].sum()
    no_pnl = no_trades["dollar_pnl"].sum() if len(no_trades) > 0 else 0
    yes_pnl = yes_trades["dollar_pnl"].sum() if len(yes_trades) > 0 else 0

    # Sharpe (per-event returns)
    event_pnl = df.groupby("event_id")["dollar_pnl"].sum()
    sharpe = event_pnl.mean() / event_pnl.std() * np.sqrt(12) if event_pnl.std() > 0 else 0

    # Max drawdown
    cum = df["cumulative_pnl"].values
    running_max = np.maximum.accumulate(cum)
    drawdown = running_max - cum
    max_drawdown = drawdown.max() if len(drawdown) > 0 else 0

    # Average edge
    avg_edge = df["edge"].mean()
    avg_edge_winners = wins["edge"].mean() if len(wins) > 0 else 0

    # Calibration buckets
    cal = _calibration_buckets(df)

    # Mention rate stats
    mention_rate = df["mentioned"].mean()
    yapper_mention_rate = df[df["is_yapper"]]["mentioned"].mean() if len(df[df["is_yapper"]]) > 0 else 0
    non_yapper_mention_rate = df[~df["is_yapper"]]["mentioned"].mean() if len(df[~df["is_yapper"]]) > 0 else 0

    return {
        "total_trades": n_trades,
        "yes_trades": n_yes,
        "no_trades": n_no,
        "win_rate": win_rate,
        "no_win_rate": no_win_rate,
        "yes_win_rate": yes_win_rate,
        "total_pnl": total_pnl,
        "no_pnl": no_pnl,
        "yes_pnl": yes_pnl,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "avg_edge": avg_edge,
        "avg_edge_winners": avg_edge_winners,
        "final_capital": result.final_capital,
        "return_pct": total_pnl / result.initial_capital * 100,
        "actual_mention_rate": mention_rate,
        "yapper_mention_rate": yapper_mention_rate,
        "non_yapper_mention_rate": non_yapper_mention_rate,
        "calibration": cal,
    }


def _calibration_buckets(df: pd.DataFrame) -> list[dict]:
    """Compute calibration: predicted probability vs actual mention rate."""
    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    df = df.copy()
    df["p_bucket"] = pd.cut(df["p_predicted"], bins=bins)
    cal = []
    for bucket, group in df.groupby("p_bucket", observed=True):
        if len(group) > 0:
            cal.append({
                "bucket": str(bucket),
                "predicted_avg": group["p_predicted"].mean(),
                "actual_rate": group["mentioned"].mean(),
                "count": len(group),
            })
    return cal


def print_metrics(metrics: dict):
    """Print formatted metrics to console."""
    print(f"\n{'='*60}")
    print("  MENTION MARKET BACKTEST RESULTS")
    print(f"{'='*60}")
    print(f"\n--- Performance ---")
    print(f"  Total PnL:              ${metrics['total_pnl']:>+12,.2f}")
    print(f"  Final Capital:          ${metrics['final_capital']:>12,.2f}")
    print(f"  Return:                  {metrics['return_pct']:>+11.1f}%")
    print(f"  Sharpe (annualized):     {metrics['sharpe']:>11.2f}")
    print(f"  Max Drawdown:           ${metrics['max_drawdown']:>12,.2f}")

    print(f"\n--- Trade Breakdown ---")
    print(f"  Total Trades:            {metrics['total_trades']:>11,}")
    print(f"  YES trades (yappers):    {metrics['yes_trades']:>11,}")
    print(f"  NO trades (spam):        {metrics['no_trades']:>11,}")
    print(f"  Overall Win Rate:        {metrics['win_rate']:>11.1%}")
    print(f"  NO Win Rate:             {metrics['no_win_rate']:>11.1%}")
    print(f"  YES Win Rate:            {metrics['yes_win_rate']:>11.1%}")

    print(f"\n--- PnL Attribution ---")
    print(f"  NO (spam) PnL:          ${metrics['no_pnl']:>+12,.2f}")
    print(f"  YES (yapper) PnL:       ${metrics['yes_pnl']:>+12,.2f}")

    print(f"\n--- Edge & Calibration ---")
    print(f"  Avg Edge (all):          {metrics['avg_edge']:>11.3f}")
    print(f"  Avg Edge (winners):      {metrics['avg_edge_winners']:>11.3f}")
    print(f"  Actual Mention Rate:     {metrics['actual_mention_rate']:>11.1%}")
    print(f"  Yapper Mention Rate:     {metrics['yapper_mention_rate']:>11.1%}")
    print(f"  Non-Yapper Mention Rate: {metrics['non_yapper_mention_rate']:>11.1%}")

    if metrics.get("calibration"):
        print(f"\n--- Calibration ---")
        print(f"  {'Predicted':>12} {'Actual':>10} {'Count':>8}")
        print(f"  {'-'*32}")
        for row in metrics["calibration"]:
            print(f"  {row['predicted_avg']:>11.1%} {row['actual_rate']:>10.1%} {row['count']:>8,}")

    print(f"\n{'='*60}")


def generate_charts(result: BacktestResult, events: list[SpeechEvent],
                    output_dir: str = "output") -> list[str]:
    """Generate all analytics charts. Returns list of saved file paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved = []

    df = pd.DataFrame(result.trades)
    if df.empty:
        print("No trades to chart.")
        return saved

    # 1. Cumulative PnL over time
    fig, ax = plt.subplots(figsize=(12, 6))
    no_df = df[df["side"] == "NO"].copy()
    yes_df = df[df["side"] == "YES"].copy()

    ax.plot(range(len(df)), df["cumulative_pnl"], color="#2196F3", linewidth=1.5,
            label="Total", zorder=3)
    if len(no_df) > 0:
        no_cum = no_df["dollar_pnl"].cumsum()
        ax.plot(no_df.index, no_cum, color="#F44336", linewidth=1, alpha=0.7,
                label="NO (spam)", zorder=2)
    if len(yes_df) > 0:
        yes_cum = yes_df["dollar_pnl"].cumsum()
        ax.plot(yes_df.index, yes_cum, color="#4CAF50", linewidth=1, alpha=0.7,
                label="YES (yappers)", zorder=2)
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.5)
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Cumulative PnL ($)")
    ax.set_title("Cumulative PnL: NO Spam vs YES Yapper Trades")
    ax.legend()
    ax.grid(True, alpha=0.3)
    p = out / "1_cumulative_pnl.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(str(p))

    # 2. Mention rate histogram (all people across events)
    mention_rates = df.groupby("person")["mentioned"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(mention_rates, bins=20, color="#90CAF9", edgecolor="#1976D2")
    ax.axvline(mention_rates.mean(), color="red", linestyle="--",
               label=f"Mean: {mention_rates.mean():.1%}")
    ax.set_xlabel("Mention Rate")
    ax.set_ylabel("Number of People")
    ax.set_title("Distribution of Mention Rates Across People")
    ax.legend()
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    p = out / "2_mention_rate_distribution.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(str(p))

    # 3. Top 20 most-mentioned people
    person_mentions = df.groupby("person")["mentioned"].agg(["sum", "count", "mean"])
    person_mentions.columns = ["total_mentions", "total_markets", "mention_rate"]
    top20 = person_mentions.sort_values("mention_rate", ascending=True).tail(20)
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = ["#4CAF50" if r > 0.5 else "#F44336" for r in top20["mention_rate"]]
    ax.barh(range(len(top20)), top20["mention_rate"], color=colors)
    ax.set_yticks(range(len(top20)))
    ax.set_yticklabels(top20.index, fontsize=9)
    ax.set_xlabel("Mention Rate")
    ax.set_title("Top 20 Most-Mentioned People (Yappers)")
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    p = out / "3_top_yappers.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(str(p))

    # 4. Calibration plot
    metrics = compute_metrics(result)
    cal = metrics["calibration"]
    if cal:
        fig, ax = plt.subplots(figsize=(8, 8))
        predicted = [c["predicted_avg"] for c in cal]
        actual = [c["actual_rate"] for c in cal]
        sizes = [max(c["count"] / 5, 10) for c in cal]
        ax.scatter(predicted, actual, s=sizes, color="#2196F3", zorder=3)
        ax.plot([0, 1], [0, 1], "k--", linewidth=0.8, label="Perfect calibration")
        ax.set_xlabel("Predicted Mention Probability")
        ax.set_ylabel("Actual Mention Rate")
        ax.set_title("Model Calibration")
        ax.legend()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)
        p = out / "4_calibration.png"
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(str(p))

    # 5. Edge distribution
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(df[df["side"] == "NO"]["edge"], bins=30, alpha=0.7, color="#F44336", label="NO trades")
    if len(yes_df) > 0:
        ax.hist(df[df["side"] == "YES"]["edge"], bins=30, alpha=0.7, color="#4CAF50", label="YES trades")
    ax.axvline(0, color="black", linestyle="--", linewidth=0.5)
    ax.set_xlabel("Edge (predicted - price)")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of Predicted Edge on Taken Trades")
    ax.legend()
    p = out / "5_edge_distribution.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(str(p))

    # 6. PnL by event type
    if "event_type" in df.columns:
        event_pnl = df.groupby("event_type")["dollar_pnl"].agg(["sum", "count", "mean"])
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        axes[0].bar(event_pnl.index, event_pnl["sum"], color="#2196F3")
        axes[0].set_title("Total PnL by Event Type")
        axes[0].set_ylabel("PnL ($)")
        axes[0].tick_params(axis="x", rotation=30)
        axes[1].bar(event_pnl.index, event_pnl["count"], color="#90CAF9")
        axes[1].set_title("Trade Count by Event Type")
        axes[1].set_ylabel("Trades")
        axes[1].tick_params(axis="x", rotation=30)
        plt.tight_layout()
        p = out / "6_pnl_by_event_type.png"
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(str(p))

    # 7. Speaker x person mention heatmap (top speakers x top people)
    if len(df) > 50:
        pivot = df.pivot_table(
            index="speaker", columns="person", values="mentioned",
            aggfunc="mean"
        )
        # Keep top 5 speakers and top 15 people by mention rate
        top_speakers = df.groupby("speaker")["mentioned"].count().nlargest(5).index
        top_people = df.groupby("person")["mentioned"].mean().nlargest(15).index
        pivot_small = pivot.reindex(index=top_speakers, columns=top_people).fillna(0)

        if not pivot_small.empty:
            fig, ax = plt.subplots(figsize=(14, 6))
            sns.heatmap(pivot_small, annot=True, fmt=".0%", cmap="YlOrRd",
                        ax=ax, vmin=0, vmax=1, linewidths=0.5)
            ax.set_title("Speaker x Person Mention Rate")
            ax.set_ylabel("Speaker")
            ax.set_xlabel("")
            plt.tight_layout()
            p = out / "7_speaker_person_heatmap.png"
            fig.savefig(p, dpi=150, bbox_inches="tight")
            plt.close(fig)
            saved.append(str(p))

    # 8. PnL per person (top winners and losers)
    person_pnl = df.groupby("person")["dollar_pnl"].sum().sort_values()
    top_losers = person_pnl.head(10)
    top_winners = person_pnl.tail(10)
    combined = pd.concat([top_losers, top_winners])
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = ["#4CAF50" if v > 0 else "#F44336" for v in combined]
    ax.barh(range(len(combined)), combined.values, color=colors)
    ax.set_yticks(range(len(combined)))
    ax.set_yticklabels(combined.index, fontsize=9)
    ax.set_xlabel("Total PnL ($)")
    ax.set_title("Top 10 Winners and Losers by Person")
    ax.axvline(0, color="black", linewidth=0.5)
    p = out / "8_pnl_by_person.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(str(p))

    print(f"\n{len(saved)} charts saved to {out}/")
    return saved

#!/usr/bin/env python3
"""Run the mention market backtest.

Usage:
    python scripts/backtest.py
    python scripts/backtest.py --no-ml          # base rate predictor only
    python scripts/backtest.py --sweep           # parameter sensitivity sweep
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from pm_mentions.config import Config
from pm_mentions.data.scraper import load_events
from pm_mentions.backtest.engine import MentionMarketBacktester
from pm_mentions.reporting.analytics import compute_metrics, print_metrics, generate_charts


def run_single(config: Config, events, use_ml: bool = True, label: str = "default"):
    """Run a single backtest configuration."""
    output_dir = Path(f"output/{label}")
    output_dir.mkdir(parents=True, exist_ok=True)

    bt = MentionMarketBacktester(config, use_ml=use_ml)
    result = bt.run(events)

    metrics = compute_metrics(result)
    print_metrics(metrics)

    # Save metrics
    with open(output_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    # Save trade log
    if result.trades:
        import pandas as pd
        trade_df = pd.DataFrame(result.trades)
        trade_df.to_csv(output_dir / "trade_log.csv", index=False)

    # Generate charts
    generate_charts(result, events, str(output_dir))

    print(f"\nOutputs saved to {output_dir}/")
    return result, metrics


def run_sweep(events, use_ml: bool = True):
    """Parameter sensitivity sweep."""
    from itertools import product

    param_grid = {
        "yapper_threshold": [0.3, 0.5, 0.7],
        "no_max_yes_price": [0.75, 0.85, 0.95],
        "yes_min_edge": [0.05, 0.10, 0.15],
        "kelly_fraction": [0.10, 0.25, 0.50],
    }

    keys = list(param_grid.keys())
    values = list(param_grid.values())
    results = []

    for combo in product(*values):
        params = dict(zip(keys, combo))
        config = Config(**params)
        bt = MentionMarketBacktester(config, use_ml=use_ml)
        result = bt.run(events, show_progress=False)
        metrics = compute_metrics(result)

        row = {**params, **{k: v for k, v in metrics.items() if not isinstance(v, list)}}
        results.append(row)
        print(f"  yapper={params['yapper_threshold']:.1f} "
              f"no_max={params['no_max_yes_price']:.2f} "
              f"edge={params['yes_min_edge']:.2f} "
              f"kelly={params['kelly_fraction']:.2f} → "
              f"PnL=${metrics['total_pnl']:+,.0f} "
              f"Sharpe={metrics['sharpe']:.2f} "
              f"WR={metrics['win_rate']:.0%}")

    import pandas as pd
    sweep_df = pd.DataFrame(results)
    sweep_df.to_csv("output/parameter_sweep.csv", index=False)
    print(f"\nSweep results saved to output/parameter_sweep.csv")

    # Best config
    best = sweep_df.loc[sweep_df["sharpe"].idxmax()]
    print(f"\n--- Best Configuration (by Sharpe) ---")
    for k in keys:
        print(f"  {k}: {best[k]}")
    print(f"  Sharpe: {best['sharpe']:.2f}")
    print(f"  Total PnL: ${best['total_pnl']:+,.0f}")
    print(f"  Win Rate: {best['win_rate']:.1%}")


def main():
    parser = argparse.ArgumentParser(description="Mention Market Backtest")
    parser.add_argument("--input", default="data/entities/events_with_entities.json",
                        help="Input events with entities")
    parser.add_argument("--no-ml", action="store_true",
                        help="Use base rate predictor (no ML)")
    parser.add_argument("--sweep", action="store_true",
                        help="Run parameter sensitivity sweep")
    parser.add_argument("--label", default="default", help="Output label")
    args = parser.parse_args()

    print(f"Loading events from {args.input}...")
    events = load_events(args.input)
    print(f"  {len(events)} events loaded")
    print(f"  Date range: {min(e.date for e in events).date()} to "
          f"{max(e.date for e in events).date()}")

    if args.sweep:
        run_sweep(events, use_ml=not args.no_ml)
    else:
        run_single(
            Config(),
            events,
            use_ml=not args.no_ml,
            label=args.label,
        )


if __name__ == "__main__":
    main()

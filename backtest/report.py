import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tabulate import tabulate


def print_summary(result: dict, capital: float):
    equity = result["equity"]
    trades = result["trades"]

    final  = equity["equity"].iloc[-1]
    total_return = (final - capital) / capital * 100
    n_trades = len(trades)

    if n_trades == 0:
        print("No trades executed.")
        return

    winners   = trades[trades["pnl"] > 0]
    losers    = trades[trades["pnl"] <= 0]
    win_rate  = len(winners) / n_trades * 100
    avg_win   = winners["pnl"].mean() if len(winners) else 0
    avg_loss  = losers["pnl"].mean()  if len(losers)  else 0
    total_pnl = trades["pnl"].sum()

    daily_ret = equity["equity"].pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std()) * np.sqrt(252) if daily_ret.std() > 0 else 0

    roll_max  = equity["equity"].cummax()
    drawdown  = (equity["equity"] - roll_max) / roll_max * 100
    max_dd    = drawdown.min()

    summary = [
        ["Starting capital",   f"${capital:,.2f}"],
        ["Final equity",        f"${final:,.2f}"],
        ["Total return",        f"{total_return:.1f}%"],
        ["Total PnL",           f"${total_pnl:,.2f}"],
        ["Total trades",        n_trades],
        ["Win rate",            f"{win_rate:.1f}%"],
        ["Avg win",             f"${avg_win:,.2f}"],
        ["Avg loss",            f"${avg_loss:,.2f}"],
        ["Sharpe ratio",        f"{sharpe:.2f}"],
        ["Max drawdown",        f"{max_dd:.1f}%"],
    ]

    print("\n" + "=" * 40)
    print("  BACKTEST RESULTS")
    print("=" * 40)
    print(tabulate(summary, tablefmt="simple"))

    if n_trades > 0:
        print(f"\n  TRADE LOG ({n_trades} trades)")
        print("-" * 40)
        display = trades[["ticker", "entry", "exit", "entry_price", "exit_price", "pnl", "reason"]].copy()
        display["entry"] = display["entry"].dt.strftime("%Y-%m-%d")
        display["exit"]  = display["exit"].dt.strftime("%Y-%m-%d")
        print(tabulate(display, headers="keys", tablefmt="simple", showindex=False))


def plot_equity(result: dict, capital: float):
    equity = result["equity"]
    trades = result["trades"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle("Momentum Trader — Backtest", fontsize=14, fontweight="bold")

    ax1.plot(equity.index, equity["equity"], color="#2196F3", linewidth=1.5, label="Portfolio")
    ax1.axhline(capital, color="gray", linestyle="--", linewidth=1, label="Starting capital")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend()
    ax1.grid(alpha=0.3)

    roll_max = equity["equity"].cummax()
    drawdown = (equity["equity"] - roll_max) / roll_max * 100
    ax2.fill_between(equity.index, drawdown, 0, color="#F44336", alpha=0.5)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("reports/backtest.png", dpi=150)
    plt.show()
    print("\nChart saved to reports/backtest.png")

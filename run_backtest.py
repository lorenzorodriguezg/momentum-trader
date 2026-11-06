from backtest.engine import run
from backtest.report import print_summary, plot_equity
from config import CAPITAL

if __name__ == "__main__":
    print("Running backtest... (this may take ~30 seconds)")
    result = run(start="2022-01-01", end="2025-01-01", capital=CAPITAL)
    print_summary(result, CAPITAL)
    plot_equity(result, CAPITAL)

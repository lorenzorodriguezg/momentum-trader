import yfinance as yf
import pandas as pd
import numpy as np
from signals.indicators import add_indicators
from config import (
    WATCHLIST, SMA_PERIOD, RSI_PERIOD,
    RSI_ENTRY_LOW, RSI_ENTRY_HIGH, RSI_EXIT,
    STOP_LOSS_PCT, MAX_POSITIONS, CAPITAL,
)


def run(
    watchlist: list[str] = WATCHLIST,
    start: str = "2022-01-01",
    end: str = "2025-01-01",
    capital: float = CAPITAL,
) -> dict:
    cash = capital
    positions: dict[str, dict] = {}   # ticker -> {shares, entry_price, stop}
    trade_log: list[dict] = []
    equity_curve: list[dict] = []

    # Download all tickers at once for efficiency
    raw = yf.download(watchlist, start=start, end=end, auto_adjust=True, progress=False)
    close = raw["Close"]
    dates = close.index

    # Pre-compute indicators per ticker
    indicators: dict[str, pd.DataFrame] = {}
    for ticker in watchlist:
        s = close[ticker].dropna()
        df = s.to_frame(name="Close")
        df = add_indicators(df, SMA_PERIOD, RSI_PERIOD)
        indicators[ticker] = df

    for i, date in enumerate(dates):
        if i < SMA_PERIOD + RSI_PERIOD:
            equity_curve.append({"date": date, "equity": cash})
            continue

        portfolio_value = cash
        for ticker, pos in positions.items():
            price = close.loc[date, ticker] if date in close.index else np.nan
            if not np.isnan(price):
                portfolio_value += pos["shares"] * price

        equity_curve.append({"date": date, "equity": portfolio_value})

        # --- Check stops and sell signals on open positions ---
        for ticker in list(positions.keys()):
            pos  = positions[ticker]
            price = close.loc[date, ticker] if date in close.index else np.nan
            if np.isnan(price):
                continue

            df  = indicators.get(ticker)
            if df is None or date not in df.index:
                continue

            row = df.loc[date]
            stop_hit  = price <= pos["stop"]
            rsi_exit  = row["rsi"] >= RSI_EXIT
            sma_break = price < row["sma"]

            if stop_hit or rsi_exit or sma_break:
                pnl = (price - pos["entry_price"]) * pos["shares"]
                cash += pos["shares"] * price
                trade_log.append({
                    "ticker": ticker,
                    "entry":  pos["entry_date"],
                    "exit":   date,
                    "entry_price": round(pos["entry_price"], 2),
                    "exit_price":  round(price, 2),
                    "shares": pos["shares"],
                    "pnl":    round(pnl, 2),
                    "reason": "stop" if stop_hit else ("rsi_exit" if rsi_exit else "sma_break"),
                })
                del positions[ticker]

        # --- Scan for buy signals ---
        if len(positions) < MAX_POSITIONS:
            slots = MAX_POSITIONS - len(positions)
            position_size = cash / (slots + len(positions)) if cash > 0 else 0

            for ticker in watchlist:
                if ticker in positions or len(positions) >= MAX_POSITIONS:
                    continue

                df = indicators.get(ticker)
                if df is None or i < 2:
                    continue

                idx = df.index.get_indexer([date], method="pad")[0]
                if idx < 2:
                    continue

                today = df.iloc[idx]
                prev  = df.iloc[idx - 1]

                price = close.loc[date, ticker] if date in close.index else np.nan
                if np.isnan(price) or price <= 0:
                    continue

                price_above_sma = today["Close"] > today["sma"]
                rsi_dipped = df["rsi"].iloc[max(0, idx - 10): idx].min() <= RSI_ENTRY_LOW
                rsi_crossed = prev["rsi"] <= RSI_ENTRY_HIGH < today["rsi"]

                if price_above_sma and rsi_dipped and rsi_crossed:
                    shares = int(position_size // price)
                    if shares < 1 or shares * price > cash:
                        continue

                    cost = shares * price
                    cash -= cost
                    positions[ticker] = {
                        "shares": shares,
                        "entry_price": price,
                        "entry_date": date,
                        "stop": price * (1 - STOP_LOSS_PCT),
                    }

    # Close any remaining open positions at last price
    last_date = dates[-1]
    for ticker, pos in positions.items():
        price = close.loc[last_date, ticker] if last_date in close.index else pos["entry_price"]
        pnl = (price - pos["entry_price"]) * pos["shares"]
        cash += pos["shares"] * price
        trade_log.append({
            "ticker": ticker,
            "entry":  pos["entry_date"],
            "exit":   last_date,
            "entry_price": round(pos["entry_price"], 2),
            "exit_price":  round(price, 2),
            "shares": pos["shares"],
            "pnl":    round(pnl, 2),
            "reason": "end_of_backtest",
        })

    equity_df = pd.DataFrame(equity_curve).set_index("date")
    trades_df  = pd.DataFrame(trade_log) if trade_log else pd.DataFrame()

    return {"equity": equity_df, "trades": trades_df, "final_cash": cash}

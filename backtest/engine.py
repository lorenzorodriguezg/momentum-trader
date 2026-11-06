import yfinance as yf
import pandas as pd
import numpy as np
from signals.indicators import add_indicators
from config import (
    WATCHLIST, SECTOR_ETF,
    SMA_PERIOD, EMA_PERIOD, RSI_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL, MACD_LOOKBACK, ATR_PERIOD,
    RSI_ENTRY_LOW, RSI_EXIT,
    STOP_LOSS_PCT, TRAILING_STOP_PCT,
    MAX_POSITIONS, CAPITAL, RISK_PER_TRADE, MAX_POSITION_PCT,
)


def _macd_cross(df: pd.DataFrame, idx: int, direction: str, lookback: int = MACD_LOOKBACK) -> bool:
    start = max(1, idx - lookback + 1)
    for i in range(start, idx + 1):
        if direction == "bullish":
            if df["macd"].iloc[i-1] <= df["macd_signal"].iloc[i-1] and \
               df["macd"].iloc[i]    >  df["macd_signal"].iloc[i]:
                return True
        else:
            if df["macd"].iloc[i-1] >= df["macd_signal"].iloc[i-1] and \
               df["macd"].iloc[i]    <  df["macd_signal"].iloc[i]:
                return True
    return False


def run(
    watchlist: list[str] = WATCHLIST,
    start: str = "2022-01-01",
    end:   str = "2025-06-01",
    capital: float = CAPITAL,
) -> dict:
    cash       = capital
    positions: dict[str, dict] = {}
    trade_log: list[dict]      = []
    equity_curve: list[dict]   = []

    all_tickers = list(set(watchlist + [SECTOR_ETF]))
    raw   = yf.download(all_tickers, start=start, end=end, auto_adjust=True, progress=False)
    close = raw["Close"]
    high  = raw["High"]
    low   = raw["Low"]
    dates = close.index

    # Pre-compute indicators
    indicators: dict[str, pd.DataFrame] = {}
    for ticker in all_tickers:
        try:
            df = pd.DataFrame({
                "Close": close[ticker],
                "High":  high[ticker],
                "Low":   low[ticker],
            }).dropna()
            df = add_indicators(
                df,
                sma_period=SMA_PERIOD, ema_period=EMA_PERIOD,
                rsi_period=RSI_PERIOD,
                macd_fast=MACD_FAST, macd_slow=MACD_SLOW, macd_signal=MACD_SIGNAL,
                atr_period=ATR_PERIOD,
            )
            indicators[ticker] = df
        except Exception:
            pass

    min_bars = SMA_PERIOD + MACD_SLOW + MACD_SIGNAL + 5

    for i, date in enumerate(dates):
        # Portfolio value snapshot
        portfolio_value = cash
        for ticker, pos in positions.items():
            price = close.loc[date, ticker] if date in close.index else np.nan
            if not np.isnan(price):
                portfolio_value += pos["shares"] * price
        equity_curve.append({"date": date, "equity": portfolio_value})

        if i < min_bars:
            continue

        # --- QQQ sector filter ---
        qqq_df  = indicators.get(SECTOR_ETF)
        qqq_idx = qqq_df.index.get_indexer([date], method="pad")[0] if qqq_df is not None else -1
        sector_ok = True
        if qqq_df is not None and qqq_idx >= 0:
            qqq_row   = qqq_df.iloc[qqq_idx]
            sector_ok = float(qqq_row["Close"]) > float(qqq_row["sma"])

        # --- Check exits for open positions ---
        for ticker in list(positions.keys()):
            pos   = positions[ticker]
            price = close.loc[date, ticker] if date in close.index else np.nan
            if np.isnan(price):
                continue

            df  = indicators.get(ticker)
            if df is None:
                continue
            idx = df.index.get_indexer([date], method="pad")[0]
            if idx < 1:
                continue
            row = df.iloc[idx]

            # Update trailing stop
            if price > pos["highest_price"]:
                pos["highest_price"] = price
            trail_stop = pos["highest_price"] * (1 - TRAILING_STOP_PCT)
            hard_stop  = pos["entry_price"]   * (1 - STOP_LOSS_PCT)
            stop       = max(trail_stop, hard_stop)

            stop_hit    = price <= stop
            rsi_exit    = float(row["rsi"]) >= RSI_EXIT
            macd_bear   = _macd_cross(df, idx, "bearish")
            ema_break   = price < float(row["ema"])

            if stop_hit or rsi_exit or macd_bear or ema_break:
                pnl = (price - pos["entry_price"]) * pos["shares"]
                cash += pos["shares"] * price
                reason = ("stop" if stop_hit else
                          "rsi_exit" if rsi_exit else
                          "macd_bear" if macd_bear else "ema_break")
                trade_log.append({
                    "ticker":      ticker,
                    "entry":       pos["entry_date"],
                    "exit":        date,
                    "entry_price": round(pos["entry_price"], 2),
                    "exit_price":  round(price, 2),
                    "shares":      pos["shares"],
                    "pnl":         round(pnl, 2),
                    "reason":      reason,
                })
                del positions[ticker]

        # --- Scan for buys ---
        if not sector_ok or len(positions) >= MAX_POSITIONS:
            continue

        for ticker in watchlist:
            if ticker in positions or len(positions) >= MAX_POSITIONS:
                continue

            df = indicators.get(ticker)
            if df is None:
                continue
            idx = df.index.get_indexer([date], method="pad")[0]
            if idx < min_bars:
                continue

            row  = df.iloc[idx]
            price = close.loc[date, ticker] if date in close.index else np.nan
            if np.isnan(price) or price <= 0:
                continue

            price_above_ema = price > float(row["ema"])
            rsi_dipped      = float(df["rsi"].iloc[max(0, idx-15):idx+1].min()) <= RSI_ENTRY_LOW
            macd_bull       = _macd_cross(df, idx, "bullish")
            not_overbought  = float(row["rsi"]) < RSI_EXIT

            if price_above_ema and rsi_dipped and macd_bull and not_overbought:
                atr_val = float(row["atr"]) if "atr" in df.columns else price * 0.02
                dollar_risk = capital * RISK_PER_TRADE
                shares = int(dollar_risk / atr_val) if atr_val > 0 else 0
                shares = max(1, min(shares, int((capital * MAX_POSITION_PCT) // price)))

                cost = shares * price
                if cost > cash:
                    continue

                cash -= cost
                positions[ticker] = {
                    "shares":        shares,
                    "entry_price":   price,
                    "entry_date":    date,
                    "highest_price": price,
                }

    # Close remaining positions
    last_date = dates[-1]
    for ticker, pos in positions.items():
        price = close.loc[last_date, ticker] if last_date in close.index else pos["entry_price"]
        pnl   = (price - pos["entry_price"]) * pos["shares"]
        cash += pos["shares"] * price
        trade_log.append({
            "ticker":      ticker,
            "entry":       pos["entry_date"],
            "exit":        last_date,
            "entry_price": round(pos["entry_price"], 2),
            "exit_price":  round(price, 2),
            "shares":      pos["shares"],
            "pnl":         round(pnl, 2),
            "reason":      "end_of_backtest",
        })

    equity_df = pd.DataFrame(equity_curve).set_index("date")
    trades_df = pd.DataFrame(trade_log) if trade_log else pd.DataFrame()
    return {"equity": equity_df, "trades": trades_df, "final_cash": cash}

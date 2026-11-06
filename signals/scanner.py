import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

from signals.indicators import add_indicators
from config import (
    WATCHLIST, SECTOR_ETF,
    SMA_PERIOD, EMA_PERIOD, RSI_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL, MACD_LOOKBACK,
    ATR_PERIOD, RSI_ENTRY_LOW, RSI_EXIT,
)


def fetch(ticker: str, days: int = 200) -> pd.DataFrame:
    end   = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    df    = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        return df
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def is_sector_healthy() -> bool:
    """Returns True when QQQ is above its 50-day SMA — sector in uptrend."""
    df = fetch(SECTOR_ETF)
    if df.empty:
        return True  # default to open if data fails
    df = add_indicators(df, sma_period=SMA_PERIOD)
    last = df.iloc[-1]
    healthy = bool(last["Close"] > last["sma"])
    if not healthy:
        print(f"  [Sector filter] {SECTOR_ETF} below 50-SMA — no new buys today")
    return healthy


def _macd_bullish_crossover(df: pd.DataFrame, lookback: int = MACD_LOOKBACK) -> bool:
    """True if MACD line crossed above signal line within the last N days."""
    recent = df.iloc[-lookback:]
    for i in range(1, len(recent)):
        prev_below = recent["macd"].iloc[i - 1] <= recent["macd_signal"].iloc[i - 1]
        now_above  = recent["macd"].iloc[i]      >  recent["macd_signal"].iloc[i]
        if prev_below and now_above:
            return True
    return False


def _macd_bearish_crossover(df: pd.DataFrame, lookback: int = MACD_LOOKBACK) -> bool:
    """True if MACD line crossed below signal line within the last N days."""
    recent = df.iloc[-lookback:]
    for i in range(1, len(recent)):
        prev_above = recent["macd"].iloc[i - 1] >= recent["macd_signal"].iloc[i - 1]
        now_below  = recent["macd"].iloc[i]      <  recent["macd_signal"].iloc[i]
        if prev_above and now_below:
            return True
    return False


def scan(watchlist: list[str] = WATCHLIST) -> dict:
    """
    Returns {"buy": [...], "sell": [...]}

    Buy conditions (all must be true):
      1. QQQ above 50-SMA (sector healthy)
      2. Price above 20-EMA (stock in short-term uptrend)
      3. RSI dipped ≤ RSI_ENTRY_LOW in last 15 days (pullback occurred)
      4. MACD bullish crossover within last MACD_LOOKBACK days (momentum turning)
      5. RSI currently < RSI_EXIT (not already overbought)

    Sell conditions (any triggers):
      1. RSI ≥ RSI_EXIT (overbought)
      2. MACD bearish crossover in last MACD_LOOKBACK days (momentum reversing)
      3. Price below 20-EMA (short-term trend broken)
    """
    sector_ok = is_sector_healthy()
    buys, sells = [], []

    min_bars = SMA_PERIOD + MACD_SLOW + MACD_SIGNAL + 5

    for ticker in watchlist:
        df = fetch(ticker)
        if df.empty or len(df) < min_bars:
            continue

        df = add_indicators(
            df,
            sma_period=SMA_PERIOD,
            ema_period=EMA_PERIOD,
            rsi_period=RSI_PERIOD,
            macd_fast=MACD_FAST,
            macd_slow=MACD_SLOW,
            macd_signal=MACD_SIGNAL,
            atr_period=ATR_PERIOD,
        )

        today = df.iloc[-1]
        price = float(today["Close"])

        # --- Sell signals ---
        rsi_overbought    = float(today["rsi"]) >= RSI_EXIT
        macd_bearish      = _macd_bearish_crossover(df)
        ema_break         = price < float(today["ema"])

        if rsi_overbought or macd_bearish or ema_break:
            sells.append(ticker)
            continue

        # --- Buy signals ---
        if not sector_ok:
            continue

        price_above_ema  = price > float(today["ema"])
        rsi_dipped       = float(df["rsi"].iloc[-15:].min()) <= RSI_ENTRY_LOW
        macd_bullish     = _macd_bullish_crossover(df)
        not_overbought   = float(today["rsi"]) < RSI_EXIT

        if price_above_ema and rsi_dipped and macd_bullish and not_overbought:
            buys.append(ticker)

    return {"buy": buys, "sell": sells}


if __name__ == "__main__":
    results = scan()
    print("BUY signals: ", results["buy"])
    print("SELL signals:", results["sell"])

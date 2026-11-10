import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

from signals.indicators import add_indicators
from config import (
    WATCHLIST, SECTOR_ETF,
    SMA_PERIOD, EMA_PERIOD, RSI_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL, MACD_LOOKBACK,
    ATR_PERIOD, RSI_ENTRY_LOW, RSI_EXIT,
    SECTOR_EMA_PERIOD,
    BOUNCE_RSI_FLOOR, BOUNCE_RSI_RECOV, BOUNCE_MIN_GAIN,
)


def fetch(ticker: str, days: int = 200) -> pd.DataFrame:
    end   = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    df    = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        return df
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def _sector_status() -> str:
    """
    Returns:
      'healthy'    — QQQ above EMA20, all clear
      'recovering' — QQQ below EMA20 but bouncing (3.5%+ in 2 days)
      'weak'       — QQQ below EMA20 and not recovering
    """
    df = fetch(SECTOR_ETF)
    if df.empty:
        return 'healthy'
    df = add_indicators(df, sma_period=SMA_PERIOD, ema_period=SECTOR_EMA_PERIOD)
    last = df.iloc[-1]
    price = float(last["Close"])
    ema   = float(last["ema"])

    if price > ema:
        return 'healthy'

    # Check if bouncing hard (>3.5% over last 2 days)
    if len(df) >= 3:
        two_days_ago = float(df["Close"].iloc[-3])
        two_day_gain = (price - two_days_ago) / two_days_ago
        if two_day_gain >= 0.035:
            print(f"  [Sector] QQQ recovering — {two_day_gain:+.1%} in 2 days")
            return 'recovering'

    print(f"  [Sector] QQQ weak — ${price:.2f} below EMA20 ${ema:.2f}")
    return 'weak'


def _macd_bullish_crossover(df: pd.DataFrame, lookback: int = MACD_LOOKBACK) -> bool:
    recent = df.iloc[-lookback:]
    for i in range(1, len(recent)):
        if (recent["macd"].iloc[i-1] <= recent["macd_signal"].iloc[i-1] and
                recent["macd"].iloc[i]    >  recent["macd_signal"].iloc[i]):
            return True
    return False


def _macd_bearish_crossover(df: pd.DataFrame, lookback: int = MACD_LOOKBACK) -> bool:
    recent = df.iloc[-lookback:]
    for i in range(1, len(recent)):
        if (recent["macd"].iloc[i-1] >= recent["macd_signal"].iloc[i-1] and
                recent["macd"].iloc[i]    <  recent["macd_signal"].iloc[i]):
            return True
    return False


def _is_bounce_recovery(df: pd.DataFrame) -> bool:
    """
    True when a stock had a deep RSI crash (< BOUNCE_RSI_FLOOR) and is now
    bouncing back above BOUNCE_RSI_RECOV with a strong 2-day price gain.
    Used during sector corrections to catch oversold reversals with smaller sizing.
    """
    if len(df) < 5:
        return False
    rsi_min5    = float(df["rsi"].iloc[-5:].min())
    rsi_now     = float(df["rsi"].iloc[-1])
    if rsi_min5 > BOUNCE_RSI_FLOOR or rsi_now < BOUNCE_RSI_RECOV:
        return False
    price_now   = float(df["Close"].iloc[-1])
    price_2d    = float(df["Close"].iloc[-3])
    two_day_gain = (price_now - price_2d) / price_2d
    return two_day_gain >= BOUNCE_MIN_GAIN


def scan(watchlist: list[str] = WATCHLIST) -> dict:
    """
    Returns {"buy": [...], "sell": [...], "bounce": [...]}

    'buy' entries are standard signals (sector healthy).
    'bounce' entries are bounce-recovery signals (sector recovering/weak)
      — these get half-sized positions in run_trader.py.

    Buy conditions (sector healthy, all must be true):
      1. QQQ above EMA20
      2. Price above 20-EMA
      3. RSI dipped ≤ RSI_ENTRY_LOW in last 15 days
      4. MACD bullish crossover within last MACD_LOOKBACK days
      5. RSI currently < RSI_EXIT

    Bounce conditions (sector recovering/weak):
      1. RSI crashed below BOUNCE_RSI_FLOOR in last 5 days
      2. RSI recovered above BOUNCE_RSI_RECOV
      3. 2-day gain >= BOUNCE_MIN_GAIN (confirms real bounce, not dead-cat)
      4. RSI < RSI_EXIT (not overbought)

    Sell conditions (any triggers):
      1. RSI >= RSI_EXIT (overbought)
      2. MACD bearish crossover in last MACD_LOOKBACK days
      3. Price below 20-EMA
    """
    sector = _sector_status()
    buys, sells, bounces = [], [], []

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
        rsi   = float(today["rsi"])

        # --- Sell signals (always check regardless of sector) ---
        rsi_overbought = rsi >= RSI_EXIT
        macd_bearish   = _macd_bearish_crossover(df)
        ema_break      = price < float(today["ema"])

        if rsi_overbought or macd_bearish or ema_break:
            sells.append(ticker)
            continue

        not_overbought = rsi < RSI_EXIT

        # --- Standard buy (sector healthy) ---
        if sector == 'healthy':
            price_above_ema = price > float(today["ema"])
            rsi_dipped      = float(df["rsi"].iloc[-15:].min()) <= RSI_ENTRY_LOW
            macd_bullish    = _macd_bullish_crossover(df)
            if price_above_ema and rsi_dipped and macd_bullish and not_overbought:
                buys.append(ticker)

        # --- Bounce recovery (sector weak/recovering) ---
        elif sector in ('recovering', 'weak'):
            if not_overbought and _is_bounce_recovery(df):
                bounces.append(ticker)

    return {"buy": buys, "sell": sells, "bounce": bounces}


if __name__ == "__main__":
    results = scan()
    print("BUY signals:    ", results["buy"])
    print("BOUNCE signals: ", results["bounce"])
    print("SELL signals:   ", results["sell"])

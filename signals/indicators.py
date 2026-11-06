import pandas as pd
import numpy as np


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def add_indicators(df: pd.DataFrame, sma_period: int = 50, rsi_period: int = 14) -> pd.DataFrame:
    """Add SMA and RSI columns to an OHLCV dataframe."""
    df = df.copy()
    df["sma"] = sma(df["Close"], sma_period)
    df["rsi"] = rsi(df["Close"], rsi_period)
    return df.dropna()

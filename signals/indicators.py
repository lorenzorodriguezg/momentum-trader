import pandas as pd
import numpy as np


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast    = series.ewm(span=fast, adjust=False).mean()
    ema_slow    = series.ewm(span=slow, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low    = df["High"] - df["Low"]
    high_close  = (df["High"] - df["Close"].shift()).abs()
    low_close   = (df["Low"]  - df["Close"].shift()).abs()
    tr          = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def add_indicators(
    df: pd.DataFrame,
    sma_period:   int = 50,
    ema_period:   int = 20,
    rsi_period:   int = 14,
    macd_fast:    int = 12,
    macd_slow:    int = 26,
    macd_signal:  int = 9,
    atr_period:   int = 14,
) -> pd.DataFrame:
    df = df.copy()
    df["sma"]  = sma(df["Close"], sma_period)
    df["ema"]  = ema(df["Close"], ema_period)
    df["rsi"]  = rsi(df["Close"], rsi_period)

    ml, sl, hist = macd(df["Close"], macd_fast, macd_slow, macd_signal)
    df["macd"]        = ml
    df["macd_signal"] = sl
    df["macd_hist"]   = hist

    if {"High", "Low"}.issubset(df.columns):
        df["atr"] = atr(df, atr_period)

    return df.dropna()

import yfinance as yf
import pandas as pd
from signals.indicators import add_indicators
from config import (
    WATCHLIST, SMA_PERIOD, RSI_PERIOD,
    RSI_ENTRY_LOW, RSI_ENTRY_HIGH, RSI_EXIT,
)


def fetch(ticker: str) -> pd.DataFrame:
    from datetime import datetime, timedelta
    end   = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=180)).strftime("%Y-%m-%d")
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        return df
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def scan(watchlist: list[str] = WATCHLIST) -> dict:
    """
    Returns a dict with two keys:
      'buy'  -> list of tickers triggering a buy signal today
      'sell' -> list of tickers triggering a sell signal today
    """
    buys, sells = [], []

    for ticker in watchlist:
        df = fetch(ticker)
        if df.empty or len(df) < SMA_PERIOD + RSI_PERIOD:
            continue

        df = add_indicators(df, SMA_PERIOD, RSI_PERIOD)
        today   = df.iloc[-1]
        prev    = df.iloc[-2]

        price_above_sma = today["Close"] > today["sma"]

        # RSI pulled back then recovered above RSI_ENTRY_HIGH and is rising
        rsi_dipped    = df["rsi"].iloc[-20:].min() <= RSI_ENTRY_LOW
        rsi_recovering = today["rsi"] > RSI_ENTRY_HIGH and today["rsi"] > prev["rsi"]
        buy_signal    = price_above_sma and rsi_dipped and rsi_recovering

        # Overbought exit
        sell_signal   = today["rsi"] >= RSI_EXIT

        if buy_signal:
            buys.append(ticker)
        if sell_signal:
            sells.append(ticker)

    return {"buy": buys, "sell": sells}


if __name__ == "__main__":
    results = scan()
    print("BUY signals: ", results["buy"])
    print("SELL signals:", results["sell"])

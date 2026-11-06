from flask import Flask, render_template
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

from broker.alpaca import get_account, get_positions
from logs.logger import get_trades
from signals.scanner import scan
from signals.indicators import add_indicators
from config import WATCHLIST, SMA_PERIOD, RSI_PERIOD, MAX_POSITIONS

app = Flask(__name__)


def get_watchlist_data(signals: dict) -> list[dict]:
    end   = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=180)).strftime("%Y-%m-%d")

    # Download all tickers in one batch call — much faster
    raw = yf.download(WATCHLIST, start=start, end=end, auto_adjust=True, progress=False)
    close = raw["Close"]

    rows = []
    for ticker in WATCHLIST:
        try:
            series = close[ticker].dropna()
            if len(series) < SMA_PERIOD + RSI_PERIOD:
                continue
            df = series.to_frame(name="Close")
            df = add_indicators(df, SMA_PERIOD, RSI_PERIOD)
            last   = df.iloc[-1]
            price  = float(last["Close"])
            rsi    = float(last["rsi"])
            vs_sma = (price - float(last["sma"])) / float(last["sma"]) * 100
            rows.append({"ticker": ticker, "price": price, "rsi": rsi, "vs_sma": vs_sma})
        except Exception:
            continue
    return rows


@app.route("/")
def index():
    account   = get_account()
    positions = get_positions()
    signals   = scan()
    watchlist = get_watchlist_data(signals)
    trades    = get_trades()
    updated   = datetime.now().strftime("%Y-%m-%d %H:%M")

    return render_template(
        "index.html",
        account=type("A", (), account)(),
        positions=positions,
        signals=signals,
        watchlist=watchlist,
        trades=trades,
        updated=updated,
        max_positions=MAX_POSITIONS,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)

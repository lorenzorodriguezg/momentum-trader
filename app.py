from flask import Flask, render_template, jsonify
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import json

from broker.alpaca import get_account, get_positions
from logs.logger import get_trades, get_equity_curve, get_performance, get_stop_price
from signals.scanner import scan
from signals.indicators import add_indicators
from config import WATCHLIST, SMA_PERIOD, EMA_PERIOD, RSI_PERIOD, MAX_POSITIONS, CAPITAL
from config import MACD_FAST, MACD_SLOW, MACD_SIGNAL, ATR_PERIOD

app = Flask(__name__)


def get_watchlist_data(signals: dict) -> list[dict]:
    end   = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=200)).strftime("%Y-%m-%d")

    all_tickers = WATCHLIST + ["QQQ"]
    raw   = yf.download(all_tickers, start=start, end=end, auto_adjust=True, progress=False)
    close = raw["Close"]
    high  = raw["High"]
    low   = raw["Low"]

    rows = []
    for ticker in WATCHLIST:
        try:
            df = pd.DataFrame({
                "Close": close[ticker],
                "High":  high[ticker],
                "Low":   low[ticker],
            }).dropna()
            if len(df) < SMA_PERIOD + 10:
                continue
            df = add_indicators(
                df,
                sma_period=SMA_PERIOD, ema_period=EMA_PERIOD,
                rsi_period=RSI_PERIOD,
                macd_fast=MACD_FAST, macd_slow=MACD_SLOW, macd_signal=MACD_SIGNAL,
                atr_period=ATR_PERIOD,
            )
            last   = df.iloc[-1]
            price  = float(last["Close"])
            rsi    = float(last["rsi"])
            macd_v = float(last["macd"])
            macd_s = float(last["macd_signal"])
            vs_ema = (price - float(last["ema"])) / float(last["ema"]) * 100
            atr_v  = float(last["atr"]) if "atr" in df.columns else 0.0
            rows.append({
                "ticker": ticker,
                "price":  price,
                "rsi":    rsi,
                "vs_ema": vs_ema,
                "macd":   macd_v,
                "macd_signal": macd_s,
                "macd_bull": macd_v > macd_s,
                "atr":    round(atr_v, 2),
            })
        except Exception:
            continue
    return rows


def enrich_positions(positions: list[dict]) -> list[dict]:
    for p in positions:
        p["stop_price"] = get_stop_price(p["ticker"])
        hard_stop = p["entry_price"] * (1 - 0.07)
        if p["stop_price"] is None:
            p["stop_price"] = round(hard_stop, 2)
    return positions


@app.route("/")
def index():
    account   = get_account()
    positions = enrich_positions(get_positions())
    signals   = scan()
    watchlist = get_watchlist_data(signals)
    trades    = get_trades()
    perf      = get_performance(CAPITAL)
    curve     = get_equity_curve()
    updated   = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Format equity curve for Chart.js
    chart_labels  = [p["date"] for p in curve[-90:]]  # last 90 data points
    chart_values  = [p["equity"] for p in curve[-90:]]

    return render_template(
        "index.html",
        account=type("A", (), account)(),
        positions=positions,
        signals=signals,
        watchlist=watchlist,
        trades=trades,
        perf=perf,
        chart_labels=json.dumps(chart_labels),
        chart_values=json.dumps(chart_values),
        capital=CAPITAL,
        updated=updated,
        max_positions=MAX_POSITIONS,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)

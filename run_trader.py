import schedule
import time
from datetime import datetime, timezone
import zoneinfo
import yfinance as yf

from signals.scanner import scan, fetch
from signals.indicators import add_indicators
from broker.alpaca import get_account, get_positions, place_buy, place_sell
from logs.logger import log_buy, log_sell, log_equity, update_trailing_stop, get_stop_price
from config import (
    CAPITAL, MAX_POSITIONS,
    STOP_LOSS_PCT, TRAILING_STOP_PCT,
    RISK_PER_TRADE, MAX_POSITION_PCT,
    ATR_PERIOD, EMA_PERIOD, SMA_PERIOD, RSI_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BOUNCE_SIZE_MULT,
)

ET = zoneinfo.ZoneInfo("America/New_York")


def is_market_open() -> bool:
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now <= market_close


def calc_shares(account_equity: float, price: float, atr_value: float) -> int:
    """ATR-based position sizing: risk RISK_PER_TRADE% of equity per ATR move."""
    dollar_risk   = account_equity * RISK_PER_TRADE
    shares_by_atr = int(dollar_risk / atr_value) if atr_value > 0 else 0
    max_shares    = int((account_equity * MAX_POSITION_PCT) // price)
    return max(1, min(shares_by_atr, max_shares))


def get_atr(ticker: str) -> float:
    df = fetch(ticker)
    if df.empty or len(df) < ATR_PERIOD + 5:
        return 0.0
    df = add_indicators(df, atr_period=ATR_PERIOD)
    return float(df["atr"].iloc[-1]) if "atr" in df.columns else 0.0


def get_price(ticker: str) -> float:
    df = yf.download(ticker, period="1d", progress=False, auto_adjust=True)
    if df.empty:
        return 0.0
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return float(df["Close"].iloc[-1])


def check_stops(positions: list[dict]) -> list[str]:
    """
    Check every open position against hard stop and trailing stop.
    Returns list of tickers that need to be sold.
    """
    to_sell = []
    for p in positions:
        ticker  = p["ticker"]
        price   = p["current_price"]
        entry   = p["entry_price"]

        # Update trailing stop upward if price moved up
        new_trail = update_trailing_stop(ticker, price, TRAILING_STOP_PCT)

        # Hard stop (original entry-based)
        hard_stop = entry * (1 - STOP_LOSS_PCT)

        # Effective stop is the higher of hard stop and trailing stop
        effective_stop = max(hard_stop, new_trail or hard_stop)

        if price <= effective_stop:
            reason = "trailing_stop" if (new_trail and new_trail > hard_stop) else "hard_stop"
            print(f"  STOP HIT: {ticker} price=${price:.2f} stop=${effective_stop:.2f} ({reason})")
            to_sell.append((ticker, reason))

    return to_sell


def run_once():
    now = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    print(f"\n{'='*50}")
    print(f"  TRADER RUNNING — {now}")
    print(f"{'='*50}")

    if not is_market_open():
        print("  Market is closed — skipping execution.")
        return

    account   = get_account()
    positions = get_positions()
    signals   = scan()

    # Log equity snapshot
    log_equity(account["equity"])

    print(f"\n  Equity:         ${account['equity']:,.2f}")
    print(f"  Cash:           ${account['cash']:,.2f}")
    print(f"  Day P&L:        ${account['pnl']:+,.2f}")
    print(f"  Open positions: {len(positions)}/{MAX_POSITIONS}")

    if positions:
        print("\n  OPEN POSITIONS:")
        for p in positions:
            stop = get_stop_price(p["ticker"])
            stop_str = f"  stop=${stop:.2f}" if stop else ""
            print(f"    {p['ticker']:<6} {p['shares']:.0f} sh  "
                  f"entry=${p['entry_price']:.2f}  "
                  f"now=${p['current_price']:.2f}  "
                  f"PnL=${p['pnl']:+.2f} ({p['pnl_pct']:.1f}%){stop_str}")

    # --- Stop loss checks ---
    stops_hit = check_stops(positions)
    for ticker, reason in stops_hit:
        p = next((x for x in positions if x["ticker"] == ticker), None)
        if p:
            place_sell(ticker)
            log_sell(ticker, p["current_price"], reason)

    # --- Sell signals ---
    positions = get_positions()
    held = {p["ticker"]: p for p in positions}
    sell_tickers = [t for t in signals["sell"] if t in held and t not in [x[0] for x in stops_hit]]

    if sell_tickers:
        print(f"\n  SELL SIGNALS: {sell_tickers}")
        for ticker in sell_tickers:
            p = held[ticker]
            place_sell(ticker)
            log_sell(ticker, p["current_price"], reason="signal")
    else:
        print("\n  No sell signals.")

    # --- Buy signals ---
    positions  = get_positions()
    open_count = len(positions)
    held       = {p["ticker"] for p in positions}
    slots      = MAX_POSITIONS - open_count

    all_buys    = signals.get("buy", [])
    all_bounces = signals.get("bounce", [])
    any_signal  = all_buys or all_bounces

    if any_signal and slots > 0:
        if all_buys:
            print(f"\n  BUY SIGNALS:    {all_buys}")
        if all_bounces:
            print(f"  BOUNCE SIGNALS: {all_bounces} (half-size, sector recovering)")
        equity = account["equity"]

        for ticker, is_bounce in [(t, False) for t in all_buys] + [(t, True) for t in all_bounces]:
            if slots <= 0:
                break
            if ticker in held:
                continue

            price = get_price(ticker)
            if price <= 0:
                continue

            atr_val = get_atr(ticker)
            if atr_val <= 0:
                shares = int((equity * MAX_POSITION_PCT) // price)
            else:
                shares = calc_shares(equity, price, atr_val)

            # Bounce entries get half the normal position size
            if is_bounce:
                shares = max(1, int(shares * BOUNCE_SIZE_MULT))

            if shares < 1 or shares * price > account["cash"]:
                print(f"  SKIP {ticker} — insufficient cash (${price:.2f}/sh)")
                continue

            hard_stop = round(price * (1 - STOP_LOSS_PCT), 2)
            place_buy(ticker, shares)
            log_buy(ticker, shares, price, hard_stop)
            slots -= 1
    else:
        print("\n  No buy signals (or no open slots).")

    print(f"\n  Done. Next scheduled run: tomorrow 09:35 ET.")


if __name__ == "__main__":
    print("Momentum Trader v2 starting...")
    print("Runs at 09:35 ET Mon–Fri. Running once now.\n")

    run_once()

    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        getattr(schedule.every(), day).at("09:35").do(run_once)

    while True:
        schedule.run_pending()
        time.sleep(60)

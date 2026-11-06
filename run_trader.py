import schedule
import time
from datetime import datetime

from signals.scanner import scan
from broker.alpaca import get_account, get_positions, place_buy, place_sell
from logs.logger import log_buy, log_sell
from config import CAPITAL, MAX_POSITIONS
import yfinance as yf


def get_price(ticker: str) -> float:
    df = yf.download(ticker, period="1d", progress=False, auto_adjust=True)
    if df.empty:
        return 0.0
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return float(df["Close"].iloc[-1])


def run_once():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*45}")
    print(f"  TRADER RUNNING — {now}")
    print(f"{'='*45}")

    account   = get_account()
    positions = get_positions()
    signals   = scan()

    print(f"\n  Account equity:  ${account['equity']:,.2f}")
    print(f"  Cash available:  ${account['cash']:,.2f}")
    print(f"  Day PnL:         ${account['pnl']:,.2f}")
    print(f"  Open positions:  {len(positions)}/{MAX_POSITIONS}")

    if positions:
        print("\n  CURRENT POSITIONS:")
        for p in positions:
            print(f"    {p['ticker']:<6} {p['shares']:.0f} shares  "
                  f"entry=${p['entry_price']:.2f}  "
                  f"now=${p['current_price']:.2f}  "
                  f"PnL=${p['pnl']:.2f} ({p['pnl_pct']:.1f}%)")

    # --- Execute sells ---
    held = {p["ticker"]: p for p in positions}
    if signals["sell"]:
        print(f"\n  SELL SIGNALS: {signals['sell']}")
        for ticker in signals["sell"]:
            if ticker in held:
                exit_price = held[ticker]["current_price"]
                place_sell(ticker)
                log_sell(ticker, exit_price, reason="rsi_exit")
    else:
        print("\n  No sell signals today.")

    # --- Execute buys ---
    positions   = get_positions()   # refresh after sells
    open_count  = len(positions)
    held        = {p["ticker"] for p in positions}
    slots       = MAX_POSITIONS - open_count

    if signals["buy"] and slots > 0:
        print(f"\n  BUY SIGNALS: {signals['buy']}")
        account       = get_account()
        position_size = account["cash"] / (slots + open_count) if account["cash"] > 0 else 0

        for ticker in signals["buy"]:
            if slots <= 0:
                break
            if ticker in held:
                continue

            price  = get_price(ticker)
            if price <= 0:
                continue

            shares = int(position_size // price)
            if shares < 1:
                print(f"  SKIP {ticker} — not enough cash for 1 share (${price:.2f})")
                continue

            place_buy(ticker, shares)
            log_buy(ticker, shares, price)
            slots -= 1
    else:
        print("\n  No buy signals today (or no open slots).")

    print(f"\n  Done. Next run at market open tomorrow.")


def job():
    run_once()


if __name__ == "__main__":
    print("Momentum Trader starting...")
    print("Running immediately, then scheduling for 09:35 ET daily.\n")

    run_once()

    # Runs every weekday at 09:35 ET (adjust if your timezone differs)
    schedule.every().monday.at("09:35").do(job)
    schedule.every().tuesday.at("09:35").do(job)
    schedule.every().wednesday.at("09:35").do(job)
    schedule.every().thursday.at("09:35").do(job)
    schedule.every().friday.at("09:35").do(job)

    while True:
        schedule.run_pending()
        time.sleep(60)

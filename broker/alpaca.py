from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass
from config import ALPACA_API_KEY, ALPACA_SECRET, ALPACA_BASE_URL

_client = None


def get_client() -> TradingClient:
    global _client
    if _client is None:
        _client = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET,
            paper=True,
        )
    return _client


def get_account() -> dict:
    account = get_client().get_account()
    return {
        "cash":          float(account.cash),
        "equity":        float(account.equity),
        "buying_power":  float(account.buying_power),
        "pnl":           float(account.equity) - float(account.last_equity),
    }


def get_positions() -> list[dict]:
    positions = get_client().get_all_positions()
    return [
        {
            "ticker":       p.symbol,
            "shares":       float(p.qty),
            "entry_price":  float(p.avg_entry_price),
            "current_price": float(p.current_price),
            "pnl":          float(p.unrealized_pl),
            "pnl_pct":      float(p.unrealized_plpc) * 100,
        }
        for p in positions
    ]


def place_buy(ticker: str, shares: int) -> dict:
    order = get_client().submit_order(
        MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
    )
    print(f"  BUY  {shares} shares of {ticker} — order id: {order.id}")
    return {"id": str(order.id), "ticker": ticker, "shares": shares, "side": "buy"}


def place_sell(ticker: str) -> dict:
    positions = {p["ticker"]: p for p in get_positions()}
    if ticker not in positions:
        print(f"  SKIP sell {ticker} — no open position")
        return {}

    shares = int(positions[ticker]["shares"])
    order = get_client().submit_order(
        MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
    )
    print(f"  SELL {shares} shares of {ticker} — order id: {order.id}")
    return {"id": str(order.id), "ticker": ticker, "shares": shares, "side": "sell"}


def close_all() -> None:
    get_client().close_all_positions(cancel_orders=True)
    print("  All positions closed.")

from dotenv import load_dotenv
import os

load_dotenv()

# --- Universe ---
WATCHLIST = [
    "NVDA", "AMD", "AVGO", "TSM", "MU", "MRVL",   # Chips & AI Memory
    "MSFT", "GOOGL", "META", "AMZN", "AAPL",        # Big Tech
    "CRM", "PLTR", "ARM", "ORCL",                    # AI Software & Cloud
    "ASML", "ANET", "APP",                            # Infrastructure & AI Apps
]

SECTOR_ETF = "QQQ"   # Only open new positions when QQQ is above its SMA

# --- Trend & momentum ---
SMA_PERIOD    = 50   # Long-term trend filter
EMA_PERIOD    = 20   # Short-term trend filter (faster)
RSI_PERIOD    = 14
MACD_FAST     = 12
MACD_SLOW     = 26
MACD_SIGNAL   = 9
ATR_PERIOD    = 14

# --- Signal thresholds ---
RSI_ENTRY_LOW  = 45   # RSI must have dipped here recently (pullback)
RSI_EXIT       = 72   # Take profit when overbought
MACD_LOOKBACK  = 3    # MACD bullish crossover must have happened within N days

# --- Risk management ---
STOP_LOSS_PCT     = 0.07   # Hard stop: 7% below entry
TRAILING_STOP_PCT = 0.05   # Trailing stop: 5% below highest price since entry
RISK_PER_TRADE    = 0.01   # ATR-based sizing: risk 1% of equity per ATR move
MAX_POSITION_PCT  = 0.15   # No single position > 15% of equity

# --- Position sizing ---
MAX_POSITIONS = 10
CAPITAL       = 100000.0

# --- Alpaca ---
ALPACA_API_KEY  = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET   = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

from dotenv import load_dotenv
import os

load_dotenv()

# --- Universe ---
WATCHLIST = [
    "NVDA", "AMD", "AVGO", "TSM",       # Chips
    "MSFT", "GOOGL", "META", "AMZN",    # Big Tech
    "AAPL", "CRM", "PLTR", "ARM",       # AI / Software
    "SMCI", "ASML", "ANET",             # Infrastructure
]

# --- Strategy parameters ---
SMA_PERIOD     = 50      # Trend filter: price must be above this SMA
RSI_PERIOD     = 14      # Standard RSI window
RSI_ENTRY_LOW  = 45      # RSI must have dipped to or below this
RSI_ENTRY_HIGH = 52      # RSI must then cross back above this to trigger buy
RSI_EXIT       = 75      # Take profit when RSI hits overbought
STOP_LOSS_PCT  = 0.07    # 7% hard stop below entry price

# --- Position sizing ---
MAX_POSITIONS  = 10      # Max concurrent open positions
CAPITAL        = 100000.0  # Paper trading capital in USD

# --- Alpaca ---
ALPACA_API_KEY  = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET   = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

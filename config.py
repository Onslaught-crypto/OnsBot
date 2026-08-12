"""
Central configuration. Edit this file to control the bot.
Nothing else needs to change for day-to-day tuning.
"""
import os

# ---------------------------------------------------------------------------
# Telegram  (see README for how to get these)
# Locally you can paste them below. On GitHub Actions they come from encrypted
# repo Secrets via environment variables and override whatever is set here.
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "PUT_YOUR_CHAT_ID_HERE")

# ---------------------------------------------------------------------------
# Data source
# ---------------------------------------------------------------------------
EXCHANGE = "bybit"          # any ccxt exchange id; bybit = deepest candle data
MARKET_TYPE = "spot"          # "spot" or "swap" (perps). Perps needed for funding/OI later.
QUOTE = "USDT"                # quote currency for the watchlist

# Watchlist: if non-empty, it overrides the auto top-N-by-volume selection.
WATCHLIST = []                # e.g. ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TOP_N_BY_VOLUME = 30          # used only when WATCHLIST is empty

TIMEFRAMES = ["4h", "1d"]     # any ccxt timeframes
CANDLE_LIMIT = 300            # candles fetched per scan (indicator warm-up buffer)

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
SCAN_INTERVAL_MINUTES = 5     # bot polls this often, but only acts on newly CLOSED candles

# ---------------------------------------------------------------------------
# Confluence — only alert when several setups agree
# ---------------------------------------------------------------------------
MIN_CONFLUENCE = 3            # how many setups must agree (same direction) to fire
CONFLUENCE_WINDOW = 3         # they may fire within this many candles of each other
                             # (set MIN_CONFLUENCE = 1 to alert on every single setup)

# ---------------------------------------------------------------------------
# Which setups are active (toggle freely)
# ---------------------------------------------------------------------------
ENABLED_SETUPS = {
    "ema_cross":         True,
    "macd_cross":        True,
    "rsi_extreme":       False,   # noisy on its own — off by default, flip on if you want it
    "rsi_divergence":    True,
    "bollinger_squeeze": True,
    "volume_spike":      True,
}

# ---------------------------------------------------------------------------
# Setup parameters
# ---------------------------------------------------------------------------
PARAMS = {
    # moving averages
    "ema_fast": 20,
    "ema_slow": 50,
    # rsi
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    # macd
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    # bollinger / squeeze
    "bb_period": 20,
    "bb_std": 2.0,
    "squeeze_lookback": 120,      # window used to judge how tight the bands are
    "squeeze_percentile": 25,     # bandwidth below this pctile of the window = "squeeze"
    # volume
    "vol_ma_period": 20,
    "vol_spike_mult": 2.0,        # volume must exceed mult x its average to fire
    # divergence
    "divergence_lookback": 40,    # bars searched for pivots
    "pivot_width": 3,             # bars on each side that define a swing pivot
}

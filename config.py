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
EXCHANGE = "kraken"           # US-based; reachable from GitHub's servers.
                             # binance/bybit/okx geoblock US cloud IPs.
MARKET_TYPE = "spot"          # "spot" or "swap" (perps). Perps needed for funding/OI later.
QUOTE = "USDT"                # quote currency for the watchlist

# Watchlist: if non-empty, it overrides the auto top-N-by-volume selection.
WATCHLIST = []                # e.g. ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TOP_N_BY_VOLUME = 30          # used only when WATCHLIST is empty

TIMEFRAMES = ["4h", "1d"]     # any ccxt timeframes
CANDLE_LIMIT = 300            # candles fetched per scan (indicator warm-up buffer)

# ---------------------------------------------------------------------------
# Chart image attached to each alert
# ---------------------------------------------------------------------------
SEND_CHARTS = True           # attach a candlestick chart image to each alert
CHART_CANDLES = 120          # how many recent candles the chart shows

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
    # atr (used by trade plan / structure)
    "atr_period": 14,
}

# ---------------------------------------------------------------------------
# Market structure, zones & trade plan  (ICT-style)
# ---------------------------------------------------------------------------
SHOW_TRADE_PLAN = True           # append entry / SL / TP1-3 to each alert
ZONES_COUNT_AS_CONFLUENCE = False  # if True, an OB tap or FVG in the trade
                                 # direction counts toward MIN_CONFLUENCE;
                                 # if False they're shown as context only

SWING_WIDTH = 2                  # bars each side that define a structural swing
EQUAL_LEVEL_TOL = 0.0015         # cluster swings within 0.15% as "equal" liquidity
SL_ATR_BUFFER = 0.25             # stop sits this many ATR beyond the strong swing
SL_ATR_FALLBACK = 1.5            # stop distance when no strong swing exists (x ATR)

OB_MOVE_ATR = 1.5                # impulse size (x ATR) that qualifies an order block
OB_MOVE_BARS = 3                 # bars the impulse may take to form
ZONE_MAX_AGE = 60                # ignore order blocks / FVGs older than this many bars

FIB_RETRACEMENTS = [0.382, 0.5, 0.618, 0.705, 0.786]
FIB_EXTENSIONS = [1.272, 1.618, 2.0]

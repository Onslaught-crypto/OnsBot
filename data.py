"""
Market-data layer (ccxt). Public endpoints only — no API key needed for
reading candles, since the bot never places orders.
"""
import ccxt
import pandas as pd
import config


def build_exchange():
    klass = getattr(ccxt, config.EXCHANGE)
    ex = klass({
        "enableRateLimit": True,
        "options": {"defaultType": config.MARKET_TYPE},
    })
    ex.load_markets()
    return ex


def resolve_symbols(ex) -> list[str]:
    """Explicit WATCHLIST if set, otherwise the top-N /QUOTE pairs by volume."""
    if config.WATCHLIST:
        return config.WATCHLIST

    tickers = ex.fetch_tickers()
    rows = []
    for sym, t in tickers.items():
        if not sym.endswith("/" + config.QUOTE):
            continue
        m = ex.markets.get(sym, {})
        if config.MARKET_TYPE == "spot" and not m.get("spot"):
            continue
        if config.MARKET_TYPE == "swap" and not m.get("swap"):
            continue
        qv = t.get("quoteVolume")
        if qv:
            rows.append((sym, qv))
    rows.sort(key=lambda r: r[1], reverse=True)
    return [s for s, _ in rows[:config.TOP_N_BY_VOLUME]]


def fetch_ohlcv(ex, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    raw = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df

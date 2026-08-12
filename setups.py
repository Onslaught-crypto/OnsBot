"""
Setup detectors.

Each detector takes an *enriched* DataFrame (indicators already attached by
indicators.enrich) whose LAST row is the most recent CLOSED candle, plus the
PARAMS dict. It returns either None (no signal) or a dict:

    {"direction": "long" | "short" | "neutral", "note": "<human readable>"}

The scanner adds symbol / timeframe / price / candle time and handles
de-duplication, so detectors only worry about the pattern itself.

To add a setup: write a detect_* function and register it in SETUP_REGISTRY at
the bottom, then flip it on in config.ENABLED_SETUPS.
"""
from typing import Optional
import pandas as pd
from indicators import pivot_lows, pivot_highs


def _crossed_up(a: pd.Series, b: pd.Series) -> bool:
    """True if series a crossed above series b on the last closed candle."""
    return a.iloc[-2] <= b.iloc[-2] and a.iloc[-1] > b.iloc[-1]


def _crossed_down(a: pd.Series, b: pd.Series) -> bool:
    return a.iloc[-2] >= b.iloc[-2] and a.iloc[-1] < b.iloc[-1]


# ---------------------------------------------------------------------------

def detect_ema_cross(df: pd.DataFrame, p: dict) -> Optional[dict]:
    fast, slow = df["ema_fast"], df["ema_slow"]
    if _crossed_up(fast, slow):
        return {"direction": "long",
                "note": f"EMA{p['ema_fast']} crossed above EMA{p['ema_slow']} (bullish)"}
    if _crossed_down(fast, slow):
        return {"direction": "short",
                "note": f"EMA{p['ema_fast']} crossed below EMA{p['ema_slow']} (bearish)"}
    return None


def detect_macd_cross(df: pd.DataFrame, p: dict) -> Optional[dict]:
    macd, sig = df["macd"], df["macd_signal"]
    if _crossed_up(macd, sig):
        return {"direction": "long", "note": "MACD crossed above signal line"}
    if _crossed_down(macd, sig):
        return {"direction": "short", "note": "MACD crossed below signal line"}
    return None


def detect_rsi_extreme(df: pd.DataFrame, p: dict) -> Optional[dict]:
    """Fires only on ENTRY into the zone, so it doesn't re-alert every candle."""
    rsi = df["rsi"]
    prev, now = rsi.iloc[-2], rsi.iloc[-1]
    if prev >= p["rsi_oversold"] and now < p["rsi_oversold"]:
        return {"direction": "long",
                "note": f"RSI dropped into oversold ({now:.1f} < {p['rsi_oversold']})"}
    if prev <= p["rsi_overbought"] and now > p["rsi_overbought"]:
        return {"direction": "short",
                "note": f"RSI pushed into overbought ({now:.1f} > {p['rsi_overbought']})"}
    return None


def detect_volume_spike(df: pd.DataFrame, p: dict) -> Optional[dict]:
    vol, vma = df["volume"].iloc[-1], df["vol_ma"].iloc[-1]
    if pd.isna(vma) or vma == 0:
        return None
    if vol > p["vol_spike_mult"] * vma:
        candle_up = df["close"].iloc[-1] >= df["open"].iloc[-1]
        bias = "long" if candle_up else "short"
        mult = vol / vma
        return {"direction": bias,
                "note": f"Volume spike {mult:.1f}x average on a "
                        f"{'green' if candle_up else 'red'} candle (confluence)"}
    return None


def detect_bollinger_squeeze(df: pd.DataFrame, p: dict) -> Optional[dict]:
    """
    Squeeze -> breakout: bands were unusually tight on the prior candle, and the
    latest close breaks out of the band.
    """
    bw = df["bb_bw"]
    look = p["squeeze_lookback"]
    if len(bw.dropna()) < look + 2:
        return None
    window = bw.iloc[-look - 1:-1]                       # exclude current bar
    threshold = window.quantile(p["squeeze_percentile"] / 100.0)
    # a squeeze anywhere in the recent run-up (last ~6 bars) counts, so a
    # breakout that takes a bar or two to develop still qualifies
    recently_squeezed = (bw.iloc[-7:-1] <= threshold).any()
    if not recently_squeezed:
        return None
    close, up, low = df["close"], df["bb_up"], df["bb_low"]
    # fire only on the candle that FIRST closes outside the band (a transition),
    # so it can't re-alert while price keeps riding the band
    if close.iloc[-1] > up.iloc[-1] and close.iloc[-2] <= up.iloc[-2]:
        return {"direction": "long", "note": "Bollinger squeeze -> upside breakout"}
    if close.iloc[-1] < low.iloc[-1] and close.iloc[-2] >= low.iloc[-2]:
        return {"direction": "short", "note": "Bollinger squeeze -> downside breakout"}
    return None


def detect_rsi_divergence(df: pd.DataFrame, p: dict) -> Optional[dict]:
    """
    Regular divergence between price and RSI, using confirmed swing pivots.

    Bullish: price makes a lower swing low but RSI makes a higher low.
    Bearish: price makes a higher swing high but RSI makes a lower high.

    Only fires when the most recent pivot is 'fresh' (just confirmed), so it
    doesn't keep re-alerting an old divergence.
    """
    look = p["divergence_lookback"]
    w = p["pivot_width"]
    if len(df) < look + w + 2:
        return None

    seg = df.iloc[-(look + w):]
    close = seg["close"]
    rsi = seg["rsi"]

    # ----- bullish: swing lows -----
    plows = pivot_lows(close, w)
    low_idx = [i for i, v in enumerate(plows.values) if v]
    if len(low_idx) >= 2:
        i1, i2 = low_idx[-2], low_idx[-1]
        # "fresh": newest pivot confirmed within the last couple of bars
        if (len(seg) - 1 - i2) <= (w + 1):
            price_lower_low = close.iloc[i2] < close.iloc[i1]
            rsi_higher_low = rsi.iloc[i2] > rsi.iloc[i1]
            if price_lower_low and rsi_higher_low:
                return {"direction": "long",
                        "note": "Bullish RSI divergence (price LL, RSI HL)"}

    # ----- bearish: swing highs -----
    phighs = pivot_highs(close, w)
    high_idx = [i for i, v in enumerate(phighs.values) if v]
    if len(high_idx) >= 2:
        i1, i2 = high_idx[-2], high_idx[-1]
        if (len(seg) - 1 - i2) <= (w + 1):
            price_higher_high = close.iloc[i2] > close.iloc[i1]
            rsi_lower_high = rsi.iloc[i2] < rsi.iloc[i1]
            if price_higher_high and rsi_lower_high:
                return {"direction": "short",
                        "note": "Bearish RSI divergence (price HH, RSI LH)"}
    return None


# ---------------------------------------------------------------------------
# Registry — the scanner iterates this, filtered by config.ENABLED_SETUPS
# ---------------------------------------------------------------------------
SETUP_REGISTRY = {
    "ema_cross":         detect_ema_cross,
    "macd_cross":        detect_macd_cross,
    "rsi_extreme":       detect_rsi_extreme,
    "rsi_divergence":    detect_rsi_divergence,
    "bollinger_squeeze": detect_bollinger_squeeze,
    "volume_spike":      detect_volume_spike,
}

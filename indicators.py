"""
Indicator implementations in plain pandas/numpy.

No pandas-ta / TA-Lib dependency: the formulas are standard and fully visible
here, which matters for a tool you're trusting with trade signals. If you'd
rather use pandas-ta later, you can swap these out — the column names below are
what the rest of the bot expects.
"""
import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100 - (100 / (1 + rs))
    # when avg_loss == 0 -> rs = inf -> rsi = 100; when both 0 -> nan, leave as is
    return out


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(close: pd.Series, period: int = 20, n_std: float = 2.0):
    mid = sma(close, period)
    std = close.rolling(period).std(ddof=0)
    upper = mid + n_std * std
    lower = mid - n_std * std
    bandwidth = (upper - lower) / mid          # relative band width
    return mid, upper, lower, bandwidth


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0.0)
    return (direction * volume).cumsum()


def volume_ma(volume: pd.Series, period: int = 20) -> pd.Series:
    return volume.rolling(period).mean()


def pivot_lows(series: pd.Series, width: int) -> pd.Series:
    """
    Boolean series: True where `series` is the minimum within +/- `width` bars.
    A pivot at index i is only *confirmed* once i+width bars exist, so callers
    should treat the last `width` bars as not-yet-confirmable.
    """
    n = len(series)
    out = pd.Series(False, index=series.index)
    vals = series.values
    for i in range(width, n - width):
        window = vals[i - width:i + width + 1]
        if vals[i] == window.min() and np.sum(window == vals[i]) == 1:
            out.iloc[i] = True
    return out


def pivot_highs(series: pd.Series, width: int) -> pd.Series:
    n = len(series)
    out = pd.Series(False, index=series.index)
    vals = series.values
    for i in range(width, n - width):
        window = vals[i - width:i + width + 1]
        if vals[i] == window.max() and np.sum(window == vals[i]) == 1:
            out.iloc[i] = True
    return out


def enrich(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    """
    Attach every indicator the setups need as columns, computed once per scan.
    Expects columns: open, high, low, close, volume.
    """
    df = df.copy()
    df["ema_fast"] = ema(df["close"], p["ema_fast"])
    df["ema_slow"] = ema(df["close"], p["ema_slow"])
    df["rsi"] = rsi(df["close"], p["rsi_period"])
    m, s, h = macd(df["close"], p["macd_fast"], p["macd_slow"], p["macd_signal"])
    df["macd"], df["macd_signal"], df["macd_hist"] = m, s, h
    mid, up, lo, bw = bollinger(df["close"], p["bb_period"], p["bb_std"])
    df["bb_mid"], df["bb_up"], df["bb_low"], df["bb_bw"] = mid, up, lo, bw
    df["obv"] = obv(df["close"], df["volume"])
    df["vol_ma"] = volume_ma(df["volume"], p["vol_ma_period"])
    return df

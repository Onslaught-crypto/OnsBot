"""
Supply/demand zones where price may react.

Fair Value Gap (FVG): a 3-candle imbalance.
  bullish  -> low[i] > high[i-2]   (gap left below current price = demand)
  bearish  -> high[i] < low[i-2]   (gap left above current price = supply)
An FVG is "filled" once price trades back through it.

Order Block (OB): the last opposite-colour candle before an impulsive move.
  bullish OB -> a down candle immediately before a strong up-move (demand)
  bearish OB -> an up candle immediately before a strong down-move (supply)
"Strong move" = travels >= OB_MOVE_ATR * ATR within OB_MOVE_BARS candles.
An OB is "mitigated" once price returns into it.

Both are approximations of discretionary concepts — tune the thresholds in
config if the zones don't match how you draw them.
"""
import config


def fair_value_gaps(df):
    n = len(df)
    hi = df["high"].values
    lo = df["low"].values
    max_age = config.ZONE_MAX_AGE
    out = []
    start = max(2, n - max_age)
    for i in range(start, n):
        # bullish FVG
        if lo[i] > hi[i - 2]:
            bottom, top = float(hi[i - 2]), float(lo[i])
            filled = bool((lo[i + 1:] <= bottom).any()) if i + 1 < n else False
            out.append({"kind": "bullish", "bottom": bottom, "top": top,
                        "idx": i, "filled": filled})
        # bearish FVG
        elif hi[i] < lo[i - 2]:
            bottom, top = float(hi[i]), float(lo[i - 2])
            filled = bool((hi[i + 1:] >= top).any()) if i + 1 < n else False
            out.append({"kind": "bearish", "bottom": bottom, "top": top,
                        "idx": i, "filled": filled})
    return out


def order_blocks(df):
    n = len(df)
    o = df["open"].values
    c = df["close"].values
    hi = df["high"].values
    lo = df["low"].values
    atr = df["atr"].values
    bars = config.OB_MOVE_BARS
    mult = config.OB_MOVE_ATR
    max_age = config.ZONE_MAX_AGE
    out = []
    start = max(1, n - max_age)
    for i in range(start, n - 1):
        a = atr[i]
        if a != a or a == 0:            # NaN / zero ATR
            continue
        j = min(n, i + 1 + bars)
        move_up = hi[i + 1:j].max() - lo[i] if i + 1 < n else 0
        move_dn = hi[i] - lo[i + 1:j].min() if i + 1 < n else 0
        bottom, top = float(lo[i]), float(hi[i])
        if c[i] < o[i] and move_up >= mult * a:          # bullish OB (demand)
            mitig = bool((lo[i + 1:] <= top).any() and (hi[i + 1:] >= bottom).any())
            out.append({"kind": "bullish", "bottom": bottom, "top": top,
                        "idx": i, "mitigated": mitig})
        elif c[i] > o[i] and move_dn >= mult * a:        # bearish OB (supply)
            mitig = bool((hi[i + 1:] >= bottom).any() and (lo[i + 1:] <= top).any())
            out.append({"kind": "bearish", "bottom": bottom, "top": top,
                        "idx": i, "mitigated": mitig})
    return out


def analyze(df):
    price = float(df["close"].iloc[-1])
    fvgs = fair_value_gaps(df)
    obs = order_blocks(df)

    # unfilled FVGs, split by side relative to price
    fvg_below = [z for z in fvgs if not z["filled"] and z["top"] <= price]
    fvg_above = [z for z in fvgs if not z["filled"] and z["bottom"] >= price]
    fvg_below.sort(key=lambda z: -z["top"])
    fvg_above.sort(key=lambda z: z["bottom"])

    # the zone price is currently sitting in (tapping), if any
    tapping = None
    for z in obs + fvgs:
        if z["bottom"] <= price <= z["top"]:
            tapping = z
            break

    # nearest unmitigated order blocks either side of price
    ob_below = [z for z in obs if not z["mitigated"] and z["top"] <= price]
    ob_above = [z for z in obs if not z["mitigated"] and z["bottom"] >= price]
    ob_below.sort(key=lambda z: -z["top"])
    ob_above.sort(key=lambda z: z["bottom"])

    return {
        "fvgs": fvgs, "order_blocks": obs,
        "fvg_below": fvg_below, "fvg_above": fvg_above,
        "ob_below": ob_below, "ob_above": ob_above,
        "tapping": tapping, "price": price,
    }

"""
Market structure (ICT-style).

Swing point  : the high/low of the middle candle in a (2*width+1)-candle window.
Strong swing : one that SWEPT the prior swing of the same type — i.e. a swing high
               above the previous swing high (took its liquidity, then reversed),
               or a swing low below the previous swing low. Strong swings are
               "protected" and are where stops belong.
Weak swing   : one that did NOT sweep the prior swing (a lower high / higher low).
               Liquidity still rests beyond it, so weak swings are targets.

Roles downstream:
  stop loss  -> beyond the nearest STRONG swing
  targets    -> unswept liquidity (WEAK swings, equal highs/lows)
"""
import config


def _pivot_idx(vals, width, kind):
    n = len(vals)
    out = []
    for i in range(width, n - width):
        w = vals[i - width:i + width + 1]
        if kind == "high" and vals[i] == w.max() and (w == vals[i]).sum() == 1:
            out.append(i)
        elif kind == "low" and vals[i] == w.min() and (w == vals[i]).sum() == 1:
            out.append(i)
    return out


def _classify(df, idxs, col, kind):
    """Tag each swing strong/weak by whether it swept the previous same-type swing."""
    out = []
    prev = None
    for i in idxs:
        price = float(df[col].iloc[i])
        if prev is None:
            strong = False
        elif kind == "high":
            strong = price > prev          # took out the previous high
        else:
            strong = price < prev          # took out the previous low
        out.append({"idx": int(i), "price": price,
                    "ts": int(df["ts"].iloc[i]), "strong": strong})
        prev = price
    return out


def _tag_equal(levels, tol):
    """Mark levels that cluster within tol of another as 'equal' liquidity."""
    for a in levels:
        for b in levels:
            if a is b:
                continue
            if abs(a["price"] - b["price"]) / max(b["price"], 1e-9) <= tol:
                a["equal"] = True
                break
        else:
            a.setdefault("equal", False)
    return levels


def analyze(df):
    w = config.SWING_WIDTH
    tol = config.EQUAL_LEVEL_TOL
    highs = _classify(df, _pivot_idx(df["high"].values, w, "high"), "high", "high")
    lows = _classify(df, _pivot_idx(df["low"].values, w, "low"), "low", "low")

    price = float(df["close"].iloc[-1])

    liq_above = [{"price": h["price"], "idx": h["idx"], "strong": h["strong"],
                  "kind": "swing high"} for h in highs if h["price"] > price]
    liq_below = [{"price": l["price"], "idx": l["idx"], "strong": l["strong"],
                  "kind": "swing low"} for l in lows if l["price"] < price]
    _tag_equal(liq_above, tol)
    _tag_equal(liq_below, tol)
    liq_above.sort(key=lambda r: r["price"])          # nearest above first
    liq_below.sort(key=lambda r: -r["price"])         # nearest below first

    strong_highs_above = sorted(h["price"] for h in highs if h["strong"] and h["price"] > price)
    strong_lows_below = sorted((l["price"] for l in lows if l["strong"] and l["price"] < price),
                               reverse=True)

    return {
        "swing_highs": highs,
        "swing_lows": lows,
        "liquidity_above": liq_above,
        "liquidity_below": liq_below,
        "nearest_strong_high": strong_highs_above[0] if strong_highs_above else None,
        "nearest_strong_low": strong_lows_below[0] if strong_lows_below else None,
        "last_high": highs[-1] if highs else None,
        "last_low": lows[-1] if lows else None,
        "price": price,
    }

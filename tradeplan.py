"""
Trade plan builder.

Given a direction plus the market structure and zones, it produces a concrete,
reactable plan — never a command:

  entry : CMP (act now) + an optional limit at a pullback (fib / OB / FVG)
  SL    : just beyond the nearest STRONG swing (+ ATR buffer); ATR-distance
          fallback when no strong swing exists
  TP1-3 : successive unswept liquidity in the profit direction (weak swings,
          equal highs/lows, unfilled FVGs); Fibonacci extensions fill any gap
  fibs  : classic retracements + extensions off the most recent impulse leg
  R:R   : shown per target so a poor setup is obvious at a glance

Everything is a suggestion to confirm on the chart.
"""
import config


def _dedupe(levels, tol):
    out = []
    for p, lbl in levels:
        if all(abs(p - q) / max(q, 1e-9) > tol for q, _ in out):
            out.append((p, lbl))
    return out


def build(direction, df, struct, zn):
    price = float(df["close"].iloc[-1])
    atr = float(df["atr"].iloc[-1])
    if atr != atr or atr <= 0:
        atr = price * 0.005
    short = direction == "short"
    tol = config.EQUAL_LEVEL_TOL

    # ---- impulse leg & fibs (anchor to the most recent swing low/high) ----
    lo = struct["last_low"]["price"] if struct["last_low"] else price - 2 * atr
    hi = struct["last_high"]["price"] if struct["last_high"] else price + 2 * atr
    if hi <= lo:
        hi, lo = price + 2 * atr, price - 2 * atr
    rng = hi - lo
    retr = {r: (hi - r * rng) for r in config.FIB_RETRACEMENTS}     # between lo..hi
    if short:
        ext = {e: (lo - (e - 1) * rng) for e in config.FIB_EXTENSIONS}  # below lo
    else:
        ext = {e: (hi + (e - 1) * rng) for e in config.FIB_EXTENSIONS}  # above hi

    # ---- stop loss ----
    if short:
        swing = struct["nearest_strong_high"]
        if swing and swing > price:
            sl = swing + config.SL_ATR_BUFFER * atr
            sl_label = "above nearest strong swing high"
        else:
            sl = price + config.SL_ATR_FALLBACK * atr
            sl_label = "ATR fallback (no strong swing)"
    else:
        swing = struct["nearest_strong_low"]
        if swing and swing < price:
            sl = swing - config.SL_ATR_BUFFER * atr
            sl_label = "below nearest strong swing low"
        else:
            sl = price - config.SL_ATR_FALLBACK * atr
            sl_label = "ATR fallback (no strong swing)"
    risk = abs(price - sl)
    if risk <= 0:
        risk = config.SL_ATR_FALLBACK * atr

    # ---- take-profit candidates from liquidity + FVG ----
    cands = []
    if short:
        for r in struct["liquidity_below"]:
            tag = "equal lows" if r.get("equal") else ("swing low" + (" (weak)" if not r["strong"] else ""))
            cands.append((r["price"], tag))
        for z in zn.get("fvg_below", []):
            cands.append((z["top"], "unfilled FVG"))
        cands = [(p, l) for p, l in cands if p < price]
        cands.sort(key=lambda t: -t[0])                 # nearest below first
        ext_targets = [(ext[e], f"fib {e}") for e in config.FIB_EXTENSIONS]
    else:
        for r in struct["liquidity_above"]:
            tag = "equal highs" if r.get("equal") else ("swing high" + (" (weak)" if not r["strong"] else ""))
            cands.append((r["price"], tag))
        for z in zn.get("fvg_above", []):
            cands.append((z["bottom"], "unfilled FVG"))
        cands = [(p, l) for p, l in cands if p > price]
        cands.sort(key=lambda t: t[0])                  # nearest above first
        ext_targets = [(ext[e], f"fib {e}") for e in config.FIB_EXTENSIONS]

    ordered = _dedupe(cands + ext_targets, tol)
    if short:
        ordered = [t for t in ordered if t[0] < price]
        ordered.sort(key=lambda t: -t[0])
    else:
        ordered = [t for t in ordered if t[0] > price]
        ordered.sort(key=lambda t: t[0])

    tps = []
    for p, lbl in ordered[:3]:
        rr = abs(p - price) / risk
        tps.append({"price": p, "rr": rr, "label": lbl})

    # ---- optional limit entry (pullback toward a fib / OB / FVG) ----
    limit = None
    if short:
        pulls = [(retr[r], f"fib {r}") for r in config.FIB_RETRACEMENTS if retr[r] > price]
        for z in zn.get("ob_above", [])[:1]:
            pulls.append((z["bottom"], "bearish OB"))
        pulls = [p for p in pulls if p[0] > price]
        if pulls:
            limit = min(pulls, key=lambda t: t[0])
    else:
        pulls = [(retr[r], f"fib {r}") for r in config.FIB_RETRACEMENTS if retr[r] < price]
        for z in zn.get("ob_below", [])[:1]:
            pulls.append((z["top"], "bullish OB"))
        pulls = [p for p in pulls if p[0] < price]
        if pulls:
            limit = max(pulls, key=lambda t: t[0])

    return {
        "direction": direction,
        "cmp": price,
        "limit": {"price": limit[0], "label": limit[1]} if limit else None,
        "sl": {"price": sl, "pct": 100 * risk / price, "label": sl_label},
        "risk": risk,
        "tps": tps,
        "fibs": {"retracements": retr, "extensions": ext},
        "leg": {"low": lo, "high": hi},
    }


def summary_lines(plan):
    """Compact text block for the alert."""
    d = plan["direction"].upper()
    out = ["", f"TRADE PLAN ({d})"]
    out.append(f"entry: CMP {plan['cmp']:g}"
               + (f"  |  limit {plan['limit']['price']:g} ({plan['limit']['label']})"
                  if plan["limit"] else ""))
    out.append(f"SL: {plan['sl']['price']:g}  ({plan['sl']['pct']:.1f}% · {plan['sl']['label']})")
    if plan["tps"]:
        for i, t in enumerate(plan["tps"], 1):
            out.append(f"TP{i}: {t['price']:g}  ({t['rr']:.1f}R · {t['label']})")
    else:
        out.append("TP: no clear target ahead — manage manually")
    return out

"""
Scan orchestration with a confluence gate.

Flow per symbol/timeframe:
  fetch -> drop still-forming candle -> enrich -> evaluate every enabled setup
  across the last CONFLUENCE_WINDOW closed candles -> if >= MIN_CONFLUENCE of
  them agree on a direction AND at least one of them fired on the CURRENT candle
  (i.e. this candle completed the confluence) -> one combined alert.

Why a rolling window: an EMA cross and an RSI divergence that confirm the same
move often land a candle or two apart. Requiring all signals on one exact candle
would miss most real confluence. The "fresh on the current candle" rule plus
per-candle de-dup means each confluence event alerts once, not every bar it
stays valid.

Because every indicator here is causal (ewm / rolling / backward pivots), a
setup's value on candle i is identical whether computed on the full series or on
the series truncated at i — so we can re-check each setup at earlier offsets just
by slicing the already-enriched frame.
"""
import pandas as pd

import config
import data
import state
import notifier
import structure
import zones
import tradeplan
from indicators import enrich
from setups import SETUP_REGISTRY

_MIN_BARS = 60


def _readings_at(row) -> dict:
    """Core indicator values at the triggering candle, for display in the alert."""
    def val(col):
        v = row[col]
        return None if pd.isna(v) else float(v)

    up, low, close = row["bb_up"], row["bb_low"], row["close"]
    pctb = None
    if not pd.isna(up) and not pd.isna(low) and up != low:
        pctb = float((close - low) / (up - low))
    vol_x = None
    if not pd.isna(row["vol_ma"]) and row["vol_ma"]:
        vol_x = float(row["volume"] / row["vol_ma"])

    return {
        "rsi": val("rsi"),
        "ema_fast": val("ema_fast"), "ema_slow": val("ema_slow"),
        "macd": val("macd"), "macd_signal": val("macd_signal"),
        "bb_pctb": pctb, "vol_x": vol_x,
    }


def _fired_within_window(df, name, params, window):
    """
    Most recent fire of `name` within the last `window` closed candles.
    Returns {name, direction, note, offset} (offset 0 = current candle) or None.
    """
    for k in range(window):
        sub = df if k == 0 else df.iloc[:len(df) - k]
        if len(sub) < _MIN_BARS:
            break
        res = SETUP_REGISTRY[name](sub, params)
        if res:
            return {"name": name, "direction": res["direction"],
                    "note": res["note"], "offset": k}
    return None


def evaluate_confluence(df, enabled, params, extra_votes=None):
    """Return (direction, members) if confluence is met on the current candle, else (None, None)."""
    window = config.CONFLUENCE_WINDOW
    fires = []
    for name in enabled:
        f = _fired_within_window(df, name, params, window)
        if f:
            fires.append(f)
    if extra_votes:
        fires.extend(extra_votes)

    longs = [f for f in fires if f["direction"] == "long"]
    shorts = [f for f in fires if f["direction"] == "short"]

    for direction, group, other in (("long", longs, shorts), ("short", shorts, longs)):
        if len(group) < config.MIN_CONFLUENCE:
            continue
        if len(group) <= len(other):          # need a strict majority — skip mixed/tied bars
            continue
        if not any(f["offset"] == 0 for f in group):  # something must be fresh this candle
            continue
        return direction, group
    return None, None


def run_scan(ex, symbols):
    enabled = [k for k, v in config.ENABLED_SETUPS.items() if v]
    for symbol in symbols:
        for tf in config.TIMEFRAMES:
            try:
                df = data.fetch_ohlcv(ex, symbol, tf, config.CANDLE_LIMIT)
            except Exception as e:
                print(f"[fetch] {symbol} {tf}: {e}")
                continue

            if len(df) < _MIN_BARS:
                continue
            df = df.iloc[:-1]                  # drop the still-forming candle
            df = enrich(df, config.PARAMS)

            # optional zone votes toward the confluence gate
            zn = None
            extra_votes = []
            if config.ZONES_COUNT_AS_CONFLUENCE:
                zn = zones.analyze(df)
                z = zn.get("tapping")
                if z:
                    vdir = "long" if z["kind"] == "bullish" else "short"
                    extra_votes.append({"name": f"{z['kind']}_zone", "direction": vdir,
                                        "note": f"price tapping {z['kind']} zone", "offset": 0})

            direction, members = evaluate_confluence(df, enabled, config.PARAMS, extra_votes)
            if not direction:
                continue

            candle_ts = int(df["ts"].iloc[-1])
            key = f"{symbol}|{tf}|confluence"
            if not state.is_new(key, candle_ts):
                continue

            # structure, zones and trade plan for the alert
            st = structure.analyze(df)
            if zn is None:
                zn = zones.analyze(df)
            plan = tradeplan.build(direction, df, st, zn) if config.SHOW_TRADE_PLAN else None

            context = []
            if zn.get("tapping"):
                z = zn["tapping"]
                context.append(f"in {z['kind']} zone {z['bottom']:g}–{z['top']:g}")

            sig = {
                "symbol": symbol, "timeframe": tf, "setup": "confluence",
                "direction": direction, "members": members,
                "price": float(df["close"].iloc[-1]),
                "candle_ts": candle_ts, "candle_dt": str(df["dt"].iloc[-1]),
                "readings": _readings_at(df.iloc[-1]),
                "plan_lines": tradeplan.summary_lines(plan) if plan else [],
                "context": context,
                "note": "; ".join(f"{m['name']}: {m['note']}" for m in members),
            }
            image = None
            if config.SEND_CHARTS:
                try:
                    import chart
                    image = chart.render(df, symbol, tf, st, zn, plan)
                except Exception as e:
                    print(f"[chart] {symbol} {tf}: {e}")
            notifier.send_alert(notifier.format_confluence(sig), image)
            state.record(key, candle_ts, sig)

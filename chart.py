"""
Renders a candlestick chart (price + EMAs + Bollinger bands, a volume panel and
an RSI panel) as PNG bytes, so alerts can carry the chart image.

Pure matplotlib on the Agg backend — works headless on GitHub Actions and adds
no dependency beyond matplotlib. render() returns None if matplotlib isn't
available or anything goes wrong, so a chart failure never blocks the text alert.
"""
import io
import os

import numpy as np
import pandas as pd

import config

os.environ.setdefault("MPLBACKEND", "Agg")

_GREEN = "#26a69a"
_RED = "#ef5350"
_BG = "#0e0e12"


def _prep(df):
    return df.tail(config.CHART_CANDLES).reset_index(drop=True)


def render(df, symbol: str, timeframe: str, struct=None, zn=None, plan=None):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except Exception:
        return None

    try:
        d = _prep(df)
        if len(d) < 5:
            return None
        p = config.PARAMS
        x = np.arange(len(d))
        colors = np.where(d["close"].values >= d["open"].values, _GREEN, _RED)

        fig = plt.figure(figsize=(9, 7), facecolor=_BG)
        gs = fig.add_gridspec(3, 1, height_ratios=[6, 2, 2], hspace=0.07)
        axp = fig.add_subplot(gs[0])
        axv = fig.add_subplot(gs[1], sharex=axp)
        axr = fig.add_subplot(gs[2], sharex=axp)
        for ax in (axp, axv, axr):
            ax.set_facecolor(_BG)
            ax.tick_params(colors="#aaaaaa", labelsize=8)
            for s in ax.spines.values():
                s.set_color("#333333")
            ax.grid(True, color="#1e1e26", linewidth=0.6)

        # candlesticks
        w = 0.6
        o = d["open"].values; c = d["close"].values
        h = d["high"].values; low = d["low"].values
        for i in range(len(d)):
            col = _GREEN if c[i] >= o[i] else _RED
            axp.plot([x[i], x[i]], [low[i], h[i]], color=col, linewidth=0.8, zorder=2)
            body_low = min(o[i], c[i])
            body_h = abs(c[i] - o[i]) or (h[i] - low[i]) * 0.001 or 1e-9
            axp.add_patch(Rectangle((x[i] - w / 2, body_low), w, body_h,
                                    color=col, zorder=3))

        # overlays
        axp.plot(x, d["ema_fast"], color="#2196f3", linewidth=1.0,
                 label=f"EMA{p['ema_fast']}")
        axp.plot(x, d["ema_slow"], color="#ff9800", linewidth=1.0,
                 label=f"EMA{p['ema_slow']}")
        axp.plot(x, d["bb_up"], color="#777777", linewidth=0.7, linestyle="--")
        axp.plot(x, d["bb_low"], color="#777777", linewidth=0.7, linestyle="--")
        axp.plot(x, d["bb_mid"], color="#555555", linewidth=0.6, linestyle=":")
        axp.legend(loc="upper left", fontsize=7, facecolor=_BG,
                   edgecolor="#333333", labelcolor="#dddddd")
        axp.set_title(f"{symbol}   ·   {timeframe}", color="#eeeeee",
                      fontsize=11, loc="left")
        axp.set_ylabel("price", color="#aaaaaa", fontsize=8)

        # ---- structure / zones / plan overlays ----
        offset = len(df) - len(d)          # map absolute idx -> chart x

        def _draw_zone(z, color):
            xs = max(0, z["idx"] - offset)
            from matplotlib.patches import Rectangle as _R
            axp.add_patch(_R((xs - 0.5, z["bottom"]), (len(d) - xs), z["top"] - z["bottom"],
                             color=color, alpha=0.13, zorder=1, linewidth=0))

        if zn is not None:
            drawn = 0
            picks = []
            if zn.get("tapping"):
                picks.append(zn["tapping"])
            picks += (zn.get("ob_below", [])[:1] + zn.get("ob_above", [])[:1]
                      + zn.get("fvg_below", [])[:1] + zn.get("fvg_above", [])[:1])
            seen = set()
            for z in picks:
                kid = (z["idx"], z["kind"])
                if kid in seen or drawn >= 5:
                    continue
                seen.add(kid)
                _draw_zone(z, _GREEN if z["kind"] == "bullish" else _RED)
                drawn += 1

        if struct is not None:
            for h in struct.get("swing_highs", []):
                if h["strong"] and h["idx"] - offset >= 0:
                    axp.scatter(h["idx"] - offset, h["price"], marker="v", s=22,
                                color="#ef5350", zorder=5)
            for l in struct.get("swing_lows", []):
                if l["strong"] and l["idx"] - offset >= 0:
                    axp.scatter(l["idx"] - offset, l["price"], marker="^", s=22,
                                color="#26a69a", zorder=5)

        if plan is not None:
            xr = len(d) - 1

            def _line(y, color, label, ls="-"):
                axp.axhline(y, color=color, linewidth=0.9, linestyle=ls, zorder=4, alpha=0.9)
                axp.text(xr, y, f" {label}", color=color, fontsize=7,
                         va="center", ha="left")

            _line(plan["cmp"], "#dddddd", f"entry {plan['cmp']:g}")
            if plan.get("limit"):
                _line(plan["limit"]["price"], "#26c6da",
                      f"limit {plan['limit']['price']:g}", ls="--")
            _line(plan["sl"]["price"], "#ef5350", f"SL {plan['sl']['price']:g}")
            for i, t in enumerate(plan["tps"], 1):
                _line(t["price"], "#66bb6a", f"TP{i} {t['price']:g} ({t['rr']:.1f}R)")

        # keep candles readable: include plan levels in view, but cap the stretch
        c_low = float(d["low"].min()); c_high = float(d["high"].max())
        c_rng = max(c_high - c_low, 1e-9)
        lo_v, hi_v = c_low, c_high
        if plan is not None:
            pv = [plan["cmp"], plan["sl"]["price"]] + [t["price"] for t in plan["tps"]]
            lo_v = min(lo_v, min(pv)); hi_v = max(hi_v, max(pv))
        axp.set_ylim(max(lo_v, c_low - 1.2 * c_rng), min(hi_v, c_high + 1.2 * c_rng))

        # volume
        axv.bar(x, d["volume"].values, color=colors, width=0.7, alpha=0.85)
        if "vol_ma" in d:
            axv.plot(x, d["vol_ma"], color="#cccccc", linewidth=0.8)
        axv.set_ylabel("vol", color="#aaaaaa", fontsize=8)

        # rsi
        axr.plot(x, d["rsi"], color="#ab47bc", linewidth=1.0)
        axr.axhline(p["rsi_overbought"], color="#555555", linewidth=0.6, linestyle="--")
        axr.axhline(p["rsi_oversold"], color="#555555", linewidth=0.6, linestyle="--")
        axr.set_ylim(0, 100)
        axr.set_ylabel("RSI", color="#aaaaaa", fontsize=8)

        # x axis: dates on the bottom panel only
        step = max(1, len(d) // 6)
        ticks = x[::step]
        labels = [pd.to_datetime(d["dt"].iloc[i]).strftime("%m-%d") for i in ticks]
        axr.set_xticks(ticks)
        axr.set_xticklabels(labels, color="#aaaaaa")
        plt.setp(axp.get_xticklabels(), visible=False)
        plt.setp(axv.get_xticklabels(), visible=False)
        axp.set_xlim(-1, len(d))

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"[chart] render failed for {symbol} {timeframe}: {e}")
        try:
            plt.close("all")
        except Exception:
            pass
        return None

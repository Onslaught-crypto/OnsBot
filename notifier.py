"""
Telegram sender.

Uses the raw Bot API (a single HTTPS POST) because the bot only *sends* alerts.
If you later want interactive commands (/status, /mute), that's the point to
add python-telegram-bot. Until a token is configured, messages print to the
console so you can dry-run the whole pipeline.
"""
import re

import requests
import config

_API = "https://api.telegram.org/bot{token}/sendMessage"
_PHOTO_API = "https://api.telegram.org/bot{token}/sendPhoto"


def _configured() -> bool:
    return not ("PUT_YOUR" in config.TELEGRAM_BOT_TOKEN
                or "PUT_YOUR" in str(config.TELEGRAM_CHAT_ID))


def send(text: str):
    if not _configured():
        print("[telegram not configured — printing instead]\n" + text + "\n")
        return
    try:
        r = requests.post(
            _API.format(token=config.TELEGRAM_BOT_TOKEN),
            data={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if not r.ok:
            print("Telegram error:", r.status_code, r.text)
    except Exception as e:
        print("Telegram send failed:", e)


def send_photo(image: bytes, caption: str) -> bool:
    """Send a photo with a caption. Returns True on success."""
    if not _configured():
        print("[telegram not configured — chart not sent]")
        return False
    try:
        r = requests.post(
            _PHOTO_API.format(token=config.TELEGRAM_BOT_TOKEN),
            data={"chat_id": config.TELEGRAM_CHAT_ID, "caption": caption,
                  "parse_mode": "HTML"},
            files={"photo": ("chart.png", image, "image/png")},
            timeout=30,
        )
        if not r.ok:
            print("Telegram photo error:", r.status_code, r.text)
            return False
        return True
    except Exception as e:
        print("Telegram photo send failed:", e)
        return False


def _visible_len(html_text: str) -> int:
    return len(re.sub(r"<[^>]+>", "", html_text))


def send_alert(text: str, image: bytes | None = None):
    """
    One combined message when possible: chart photo + full text as caption.
    Telegram caps captions at 1024 visible chars; if the text is longer (or the
    photo send fails), fall back to sending the text on its own.
    """
    if not image:
        send(text)
        return
    if _visible_len(text) <= 1000:
        if not send_photo(image, text):
            send(text)
    else:
        # too long for a caption: send chart with a short caption, text separately
        if not send_photo(image, text.split("\n", 1)[0]):
            print("[chart] photo failed; sending text only")
        send(text)


def format_signal(sig: dict) -> str:
    bias = {"long": "LONG bias", "short": "SHORT bias", "neutral": "WATCH"}[sig["direction"]]
    return (
        f"<b>{sig['symbol']}</b>  ·  {sig['timeframe']}  ·  <b>{bias}</b>\n"
        f"{sig['setup']} — {sig['note']}\n"
        f"price: {sig['price']:g}\n"
        f"candle close: {sig['candle_dt']}\n"
        f"<i>Alert only — confirm on the chart before deciding.</i>"
    )


def _fmt_readings(r: dict) -> str:
    p = config.PARAMS
    parts = []
    if r.get("rsi") is not None:
        parts.append(f"RSI {r['rsi']:.1f}")
    if r.get("ema_fast") is not None and r.get("ema_slow") is not None:
        rel = "&gt;" if r["ema_fast"] > r["ema_slow"] else "&lt;"
        parts.append(f"EMA{p['ema_fast']} {r['ema_fast']:.4g} {rel} EMA{p['ema_slow']} {r['ema_slow']:.4g}")
    if r.get("macd") is not None and r.get("macd_signal") is not None:
        rel = "&gt;" if r["macd"] > r["macd_signal"] else "&lt;"
        parts.append(f"MACD {r['macd']:.4g} {rel} sig {r['macd_signal']:.4g}")
    if r.get("bb_pctb") is not None:
        parts.append(f"%B {r['bb_pctb']:.2f}")
    if r.get("vol_x") is not None:
        parts.append(f"vol {r['vol_x']:.1f}x")
    return " · ".join(parts)


def format_confluence(sig: dict) -> str:
    bias = {"long": "LONG", "short": "SHORT"}[sig["direction"]]
    lines = [
        f"<b>{sig['symbol']}</b>  ·  {sig['timeframe']}  ·  "
        f"<b>{bias} confluence ({len(sig['members'])})</b>"
    ]
    lines.append("triggered:")
    for m in sig["members"]:
        when = "now" if m["offset"] == 0 else f"{m['offset']} candle(s) ago"
        lines.append(f"• {m['name']} — {m['note']} ({when})")
    if sig.get("readings"):
        snap = _fmt_readings(sig["readings"])
        if snap:
            lines.append(f"indicators @ close: {snap}")
    if sig.get("context"):
        lines.append("context: " + "; ".join(sig["context"]))
    for pl in sig.get("plan_lines", []):
        lines.append(pl)
    lines.append(f"price: {sig['price']:g}")
    lines.append(f"candle close: {sig['candle_dt']}")
    lines.append("<i>Alert only — confirm on the chart before deciding.</i>")
    return "\n".join(lines)

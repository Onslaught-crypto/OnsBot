"""
Persistence via a single JSON file (state.json).

Why JSON instead of SQLite: on GitHub Actions each run starts with a clean
filesystem, so the de-dup memory has to be a file the workflow can commit back
to the repo between runs. A small JSON file diffs cleanly in git; a binary DB
does not. Works identically when you run locally.

`seen`  : { "SYMBOL|TF|confluence": last_alerted_candle_ts }  -> stops repeats
`log`   : last LOG_CAP alerts, so you can browse recent history in the repo
"""
import json
import os
import time

STATE_PATH = os.environ.get("STATE_PATH", "state.json")
LOG_CAP = 200

_state = {"seen": {}, "log": []}


def init():
    global _state
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                _state = json.load(f)
        except (json.JSONDecodeError, OSError):
            _state = {"seen": {}, "log": []}
    _state.setdefault("seen", {})
    _state.setdefault("log", [])


def is_new(key: str, candle_ts: int) -> bool:
    last = _state["seen"].get(key)
    return last is None or candle_ts > last


def record(key: str, candle_ts: int, sig: dict):
    _state["seen"][key] = candle_ts
    _state["log"].append({
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "symbol": sig["symbol"], "timeframe": sig["timeframe"],
        "direction": sig["direction"], "price": sig["price"],
        "members": [m["name"] for m in sig.get("members", [])],
        "note": sig.get("note", ""),
    })
    _state["log"] = _state["log"][-LOG_CAP:]
    _save()


def _save():
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_state, f, indent=1)
    os.replace(tmp, STATE_PATH)

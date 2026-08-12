"""
Run modes:

  python main.py            local 24/7 loop (polls every SCAN_INTERVAL_MINUTES)
  python main.py --once     single scan then exit  (used by GitHub Actions)

The --once mode is what the scheduled cloud workflow calls: GitHub triggers the
run on a cron, the bot does one pass over every symbol/timeframe, sends any
alerts, saves state.json, and exits. The workflow then commits state.json so the
next run remembers what it already alerted.
"""
import sys

import config
import data
import state
import scanner


def _resolve_and_scan():
    ex = data.build_exchange()
    symbols = data.resolve_symbols(ex)
    print(f"Watching {len(symbols)} symbols on {config.TIMEFRAMES}")
    scanner.run_scan(ex, symbols)
    return ex, symbols


def run_once():
    state.init()
    _resolve_and_scan()
    print("Single scan complete.")


def run_loop():
    from apscheduler.schedulers.blocking import BlockingScheduler

    state.init()
    ex = data.build_exchange()
    symbols = data.resolve_symbols(ex)
    print(f"Watching {len(symbols)} symbols on {config.TIMEFRAMES}")
    print("  " + ", ".join(symbols))

    def scan_job():
        try:
            scanner.run_scan(ex, symbols)
        except Exception as e:
            print("[scan] unexpected error:", e)

    def refresh_symbols_job():
        nonlocal symbols
        try:
            symbols = data.resolve_symbols(ex)
            print(f"[refresh] watchlist -> {len(symbols)} symbols")
        except Exception as e:
            print("[refresh] failed:", e)

    scan_job()
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(scan_job, "interval", minutes=config.SCAN_INTERVAL_MINUTES)
    if not config.WATCHLIST:
        sched.add_job(refresh_symbols_job, "interval", hours=24)
    print("Scheduler started. Ctrl-C to stop.")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nStopped.")


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        run_loop()

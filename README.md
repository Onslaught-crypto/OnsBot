# Crypto Setup Alert Bot (Telegram)

A signal *scanner*, not an auto-trader. It watches a list of coins across chosen
timeframes, evaluates a set of technical setups on each **closed** candle, and
sends you a Telegram alert when one triggers — so you can pull up the chart and
decide whether a long or short is worth taking. It never places orders and needs
no exchange API key.

## What's inside

| file | role |
|------|------|
| `config.py` | all settings — the only file you edit day to day |
| `indicators.py` | RSI, EMA, MACD, Bollinger, ATR, OBV, pivots (plain pandas) |
| `setups.py` | one detector per pattern; add your own here |
| `data.py` | fetches candles via ccxt, resolves the watchlist |
| `state.py` | JSON de-dup + recent-alert log (`state.json`) |
| `notifier.py` | sends the Telegram message |
| `scanner.py` | ties it together: fetch → detect → de-dup → notify |
| `main.py` | `python main.py` (24/7 loop) or `python main.py --once` (one scan) |
| `.github/workflows/scan.yml` | runs the bot free on GitHub's servers, on a schedule |

## First: create your Telegram bot (needed for both options)

1. In Telegram, message **@BotFather**, send `/newbot`, follow the prompts, copy
   the **token**.
2. Send any message to your new bot.
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and
   read `result[].message.chat.id` — that's your **chat id**. (For a channel, add
   the bot as admin and use the channel id.)

You can do all of this from your phone.

## Option A — run on GitHub Actions (free, no install)

Best if you can't or don't want to install Python. GitHub runs the scan on its
own servers on a schedule; your machine runs nothing.

1. Create a free account at github.com and click **New repository** (name it
   anything, e.g. `crypto-alerts`). Keep it **Public** for unlimited free
   minutes.
2. Upload every file in this folder — including the hidden `.github/` folder —
   via **Add file → Upload files** (drag them in), then **Commit**. If the web
   uploader drops the `.github` folder, use **Add file → Create new file**, type
   `.github/workflows/scan.yml` as the name, and paste the contents in.
3. Go to **Settings → Secrets and variables → Actions → New repository secret**
   and add two secrets:
   - `TELEGRAM_BOT_TOKEN` = your bot token
   - `TELEGRAM_CHAT_ID` = your chat id
4. Open the **Actions** tab, enable workflows if prompted, pick
   **crypto-alert-scan**, and click **Run workflow** to test immediately. After
   that it runs automatically every 15 minutes.

The workflow commits an updated `state.json` after each run — that's how it
remembers what it already alerted, so you don't get duplicates.

Notes: GitHub may delay or skip scheduled runs under heavy load, and it disables
schedules on a repo with no commits for 60 days (the state commits keep it
active). If Binance is unreachable from GitHub's servers, change `EXCHANGE` in
`config.py` to another venue such as `"bybit"`, `"okx"`, or `"kraken"`.

## Option B — run locally (Python required)

1. **Install** (Python 3.10+):
   ```bash
   pip install -r requirements.txt
   ```

2. **Fill in `config.py`:** paste your `TELEGRAM_BOT_TOKEN` and
   `TELEGRAM_CHAT_ID` (or leave them and set the same-named environment
   variables).

3. **Run:**
   ```bash
   python main.py
   ```
   Until you add the token, alerts print to the console — good for a dry run.

## How it works

- Polls every `SCAN_INTERVAL_MINUTES`, but only acts when a candle has **newly
  closed** (the still-forming candle is always dropped — no repainting).
- **Confluence gate:** a setup alone won't alert. The bot fires only when at
  least `MIN_CONFLUENCE` setups (default 3) agree on the **same direction**
  within the last `CONFLUENCE_WINDOW` candles (default 3), and a fresh signal
  completes the set on the current candle. The alert lists every contributing
  setup, how many candles ago each fired, and the indicator readings (RSI, EMAs,
  MACD, Bollinger %B, volume multiple) at the close. Set `MIN_CONFLUENCE = 1` to
  go back to one-alert-per-setup.
- Every alert is keyed by `symbol|timeframe` and stored, so a restart or an
  overlapping scan never double-sends, and a confluence that stays valid for
  several candles alerts once, not every bar.
- With `WATCHLIST` empty it auto-picks the top `TOP_N_BY_VOLUME` `/USDT` pairs by
  volume and refreshes that list daily. Set `WATCHLIST` to pin your own coins.

## Tuning

- Turn setups on/off in `ENABLED_SETUPS`. `rsi_extreme` is off by default because
  it's noisy alone — better as confluence.
- Adjust thresholds/periods in `PARAMS`.
- Change coins/timeframes at the top of `config.py`.

## Included setups

`ema_cross`, `macd_cross`, `rsi_extreme` (entry into OB/OS), `rsi_divergence`
(regular bullish/bearish via swing pivots), `bollinger_squeeze` (contraction →
breakout), `volume_spike`.

## Adding a setup

Write a function in `setups.py` that takes the enriched DataFrame (last row =
last closed candle) plus `PARAMS`, and returns
`{"direction": "long|short|neutral", "note": "..."}` or `None`. Register it in
`SETUP_REGISTRY`, then enable it in `config.ENABLED_SETUPS`. Good next
candidates: OBV divergence (reuse the pivot helpers), funding-rate extremes and
open-interest surges (pull from a perps market via ccxt).

## A note on use

These are alerts, not advice. Single indicators produce false positives — the
value is in confluence and in your own read of the chart. Paper-trade the alerts
first to see which setups actually fit how you trade before risking anything.

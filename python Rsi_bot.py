# RSI Alert Bot v3 — yfinance edition
# Real-time data, 5-min checks, duplicate protection, no API key needed

import yfinance as yf
import time
import json
import os
import requests
from datetime import datetime, timezone

# ── YOUR CONFIG ──────────────────────────────────────────
TELEGRAM_TOKEN = "8656898499:AAGcRU-wilwH4uewA4Uru1mTecKWYpGKG0s"
CHAT_ID        = "716797698"
RSI_PERIOD     = 14
OVERSOLD       = 30
OVERBOUGHT     = 70
CHECK_EVERY    = 60 * 5    # check every 5 minutes
STATE_FILE     = "bot_state.json"   # saves state so restarts don't cause duplicates
# ─────────────────────────────────────────────────────────

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id":    CHAT_ID,
            "text":       message,
            "parse_mode": "HTML"
        }, timeout=10)
        if r.status_code == 200:
            print(f"Telegram sent OK")
        else:
            print(f"Telegram error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Telegram failed: {e}")

def get_prices():
    """
    Fetch XAUUSD 15-min candles from Yahoo Finance.
    Free, no API key, near real-time (under 1 min delay).
    Uses XAUUSD=X which is spot gold price.
    """
    try:
        ticker = yf.Ticker("XAUUSD=X")   # Gold futures — most liquid, closest to spot
        df = ticker.history(period="5d", interval="15m")
        if df is None or df.empty:
            print("yfinance returned empty data, trying XAUUSD=X...")
            ticker = yf.Ticker("XAUUSD=X")
            df = ticker.history(period="5d", interval="15m")
        if df is None or df.empty:
            return None, None
        # Use only fully closed candles — drop the current live candle
        df = df.iloc[:-1]
        closes = list(df["Close"])
        price  = round(closes[-1], 2)
        print(f"Fetched {len(closes)} candles. Latest close: ${price}")
        return closes, price
    except Exception as e:
        print(f"Price fetch error: {e}")
        return None, None

def calculate_rsi(prices, period=14):
    """Wilder's Smoothed RSI — identical to TradingView"""
    if len(prices) < period + 2:
        return None
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains  = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def format_message(signal, rsi, price, note):
    emoji = "🟢" if "OVERSOLD" in signal else "🔴"
    t = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{emoji} <b>XAUUSD — {signal}</b>\n\n"
        f"RSI: <b>{rsi}</b>\n"
        f"Price: <b>${price}</b>\n"
        f"Timeframe: <b>15m</b>\n"
        f"Time: {t}\n\n"
        f"<i>{note}</i>\n"
        f"<i>Not financial advice.</i>"
    )

def save_state(signal):
    """Save last signal to file so bot survives Railway restarts"""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_signal": signal}, f)
    except Exception as e:
        print(f"State save error: {e}")

def load_state():
    """Load last signal from file on startup"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                sig = data.get("last_signal")
                print(f"Loaded saved state: last_signal = {sig}")
                return sig
    except Exception as e:
        print(f"State load error: {e}")
    return None

# ── STARTUP ───────────────────────────────────────────────
print("=" * 50)
print("RSI Bot v3 — yfinance real-time, 5-min checks")
print("=" * 50)

last_signal = load_state()
print(f"Starting with last_signal = {last_signal}")

send_telegram(
    "🤖 <b>RSI Bot v3 is LIVE</b>\n\n"
    "✅ Real-time data via yfinance\n"
    "✅ Checks every 5 minutes\n"
    "✅ Duplicate protection enabled\n"
    "✅ Wilder's RSI matches TradingView\n\n"
    "Watching XAUUSD 15m for RSI signals..."
)

# ── MAIN LOOP ─────────────────────────────────────────────
while True:
    try:
        prices, price = get_prices()

        if prices and price:
            rsi = calculate_rsi(prices, RSI_PERIOD)
            t   = datetime.now(timezone.utc).strftime("%H:%M")
            print(f"[{t} UTC] RSI = {rsi}  |  Price = ${price}  |  State = {last_signal}")

            if rsi is not None:

                # RSI crosses BELOW 30 — oversold entry
                if rsi < OVERSOLD and last_signal != "OVERSOLD":
                    msg = format_message(
                        "OVERSOLD_ENTRY", rsi, price,
                        f"RSI = {rsi} — below {OVERSOLD}. Potential buy zone on Gold!")
                    send_telegram(msg)
                    last_signal = "OVERSOLD"
                    save_state(last_signal)

                # RSI recovers ABOVE 30 from oversold
                elif rsi >= OVERSOLD and last_signal == "OVERSOLD":
                    msg = format_message(
                        "OVERSOLD_RECOVERY", rsi, price,
                        f"RSI recovered to {rsi} — momentum returning")
                    send_telegram(msg)
                    last_signal = None
                    save_state(last_signal)

                # RSI crosses ABOVE 70 — overbought entry
                elif rsi > OVERBOUGHT and last_signal != "OVERBOUGHT":
                    msg = format_message(
                        "OVERBOUGHT_ENTRY", rsi, price,
                        f"RSI = {rsi} — above {OVERBOUGHT}. Potential sell zone on Gold!")
                    send_telegram(msg)
                    last_signal = "OVERBOUGHT"
                    save_state(last_signal)

                # RSI drops BELOW 70 from overbought
                elif rsi <= OVERBOUGHT and last_signal == "OVERBOUGHT":
                    msg = format_message(
                        "OVERBOUGHT_RECOVERY", rsi, price,
                        f"RSI dropped to {rsi} — sell pressure easing")
                    send_telegram(msg)
                    last_signal = None
                    save_state(last_signal)

        else:
            print("No price data received — will retry next cycle")

    except Exception as e:
        print(f"Main loop error: {e}")
        send_telegram(f"⚠️ Bot error: {e}")

    time.sleep(CHECK_EVERY)

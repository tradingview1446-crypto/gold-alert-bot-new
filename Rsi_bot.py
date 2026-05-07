# RSI Alert Bot — runs free on Railway.app
# No MT5 needed. Checks XAUUSD RSI every 15 min and sends Telegram alerts.

import requests
import time
from datetime import datetime

# ── YOUR CONFIG ──────────────────────────────────────────
WEBHOOK_URL  = "https://gold-alert-bot-udij.onrender.com/webhook"
RSI_PERIOD   = 14
OVERSOLD     = 30
OVERBOUGHT   = 70
CHECK_EVERY  = 60 * 15   # check every 15 minutes (in seconds)
# ─────────────────────────────────────────────────────────

def get_xauusd_ohlcv():
    """Fetch XAUUSD 15-min candles from Twelve Data (free tier)"""
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol":     "XAU/USD",
        "interval":   "15min",
        "outputsize": 50,
        "apikey":     "3af6bad1a7be4b98a88e015a55e81775"   # replace with your free key from twelvedata.com
    }
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if "values" not in data:
        print(f"API error: {data}")
        return None
    return [float(c["close"]) for c in reversed(data["values"])]

def calculate_rsi(prices, period=14):
    """Calculate RSI from a list of closing prices"""
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def send_alert(signal, rsi, price, note):
    """Send webhook to your existing Render server"""
    payload = {
        "symbol": "XAUUSD",
        "signal": signal,
        "rsi":    str(rsi),
        "price":  str(price),
        "tf":     "15m",
        "note":   note
    }
    try:
        r = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"[{datetime.utcnow().strftime('%H:%M')}] Alert sent: {signal} RSI={rsi}")
        else:
            print(f"Webhook error: {r.status_code}")
    except Exception as e:
        print(f"Webhook failed: {e}")

# Track last alert to avoid duplicates
last_signal = None

print("RSI Bot started — checking XAUUSD every 15 minutes...")

# Send startup confirmation to Telegram
send_alert("BOT_STARTED", 0, 0,
    "Python RSI bot is live on Railway. No MT5 needed!")

while True:
    try:
        prices = get_xauusd_ohlcv()
        if prices:
            rsi   = calculate_rsi(prices, RSI_PERIOD)
            price = round(prices[-1], 2)
            now   = datetime.utcnow().strftime("%H:%M UTC")
            print(f"[{now}] XAUUSD RSI = {rsi}  Price = ${price}")

            if rsi is not None:
                # RSI enters oversold
                if rsi < OVERSOLD and last_signal != "OVERSOLD":
                    send_alert("OVERSOLD_ENTRY", rsi, price,
                        f"RSI = {rsi} — below {OVERSOLD}. Potential buy zone!")
                    last_signal = "OVERSOLD"

                # RSI recovers from oversold
                elif rsi >= OVERSOLD and last_signal == "OVERSOLD":
                    send_alert("OVERSOLD_RECOVERY", rsi, price,
                        f"RSI recovered to {rsi} — momentum returning")
                    last_signal = None

                # RSI enters overbought
                elif rsi > OVERBOUGHT and last_signal != "OVERBOUGHT":
                    send_alert("OVERBOUGHT_ENTRY", rsi, price,
                        f"RSI = {rsi} — above {OVERBOUGHT}. Potential sell zone!")
                    last_signal = "OVERBOUGHT"

                # RSI drops from overbought
                elif rsi <= OVERBOUGHT and last_signal == "OVERBOUGHT":
                    send_alert("OVERBOUGHT_RECOVERY", rsi, price,
                        f"RSI dropped to {rsi} — sell pressure easing")
                    last_signal = None

    except Exception as e:
        print(f"Error in main loop: {e}")

    time.sleep(CHECK_EVERY)
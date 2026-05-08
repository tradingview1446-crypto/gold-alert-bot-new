import requests
import time
from datetime import datetime

# ── YOUR CONFIG ──────────────────────────────────────────
TELEGRAM_TOKEN = "8656898499:AAGcRU-wilwH4uewA4Uru1mTecKWYpGKG0s"
CHAT_ID        = "716797698"
TWELVEDATA_KEY = "3af6bad1a7be4b98a88e015a55e81775"
RSI_PERIOD     = 14
OVERSOLD       = 30
OVERBOUGHT     = 70
CHECK_EVERY    = 60 * 15
# ─────────────────────────────────────────────────────────

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id":    CHAT_ID,
        "text":       message,
        "parse_mode": "HTML"
    }, timeout=10)

def get_prices():
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol":     "XAU/USD",
        "interval":   "15min",
        "outputsize": 150,       # ← increased for accurate RSI warmup
        "apikey":     TWELVEDATA_KEY
    }
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if "values" not in data:
        print(f"API error: {data}")
        return None
    return [float(c["close"]) for c in reversed(data["values"])]

def calculate_rsi(prices, period=14):
    """Wilder's Smoothed RSI — matches TradingView exactly"""
    if len(prices) < period + 2:
        return None

    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains  = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    # Seed with simple average
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder's smoothing for remaining candles
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs  = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def format_message(signal, rsi, price, note):
    emoji = "🟢" if "OVERSOLD" in signal else "🔴"
    t = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{emoji} <b>XAUUSD — {signal}</b>\n\n"
        f"RSI: <b>{rsi}</b>\n"
        f"Price: <b>${price}</b>\n"
        f"Timeframe: <b>15m</b>\n"
        f"Time: {t}\n\n"
        f"<i>{note}</i>\n"
        f"<i>Not financial advice.</i>"
    )

last_signal = None
print("RSI Bot started with Wilder's RSI — matches TradingView!")
send_telegram("🤖 <b>RSI Bot restarted with fixed Wilder's RSI calculation.</b>\n\nNow matches TradingView exactly.")

while True:
    try:
        prices = get_prices()
        if prices:
            rsi   = calculate_rsi(prices, RSI_PERIOD)
            price = round(prices[-1], 2)
            t     = datetime.utcnow().strftime("%H:%M")
            print(f"[{t} UTC] RSI = {rsi}  |  Price = ${price}")

            if rsi is not None:
                if rsi < OVERSOLD and last_signal != "OVERSOLD":
                    send_telegram(format_message(
                        "OVERSOLD_ENTRY", rsi, price,
                        f"RSI = {rsi} — below {OVERSOLD}. Potential buy zone on Gold!"))
                    last_signal = "OVERSOLD"

                elif rsi >= OVERSOLD and last_signal == "OVERSOLD":
                    send_telegram(format_message(
                        "OVERSOLD_RECOVERY", rsi, price,
                        f"RSI recovered to {rsi} — momentum returning"))
                    last_signal = None

                elif rsi > OVERBOUGHT and last_signal != "OVERBOUGHT":
                    send_telegram(format_message(
                        "OVERBOUGHT_ENTRY", rsi, price,
                        f"RSI = {rsi} — above {OVERBOUGHT}. Potential sell zone on Gold!"))
                    last_signal = "OVERBOUGHT"

                elif rsi <= OVERBOUGHT and last_signal == "OVERBOUGHT":
                    send_telegram(format_message(
                        "OVERBOUGHT_RECOVERY", rsi, price,
                        f"RSI dropped to {rsi} — sell pressure easing"))
                    last_signal = None

    except Exception as e:
        print(f"Error: {e}")
        send_telegram(f"⚠️ Bot error: {e}")

    time.sleep(CHECK_EVERY)

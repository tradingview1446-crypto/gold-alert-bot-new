import requests
import time
from datetime import datetime

# ── YOUR CONFIG ──────────────────────────────────────────
TELEGRAM_TOKEN = "8656898499:AAGcRU-wilwH4uewA4Uru1mTecKWYpGKG0s"
CHAT_ID        = "716797698"
TWELVEDATA_KEY = "3af6bad1a7be4b98a88e015a55e81775"   # from twelvedata.com
RSI_PERIOD     = 14
OVERSOLD       = 30
OVERBOUGHT     = 70
CHECK_EVERY    = 60 * 15   # 15 minutes
# ─────────────────────────────────────────────────────────

def send_telegram(message):
    """Send directly to Telegram — no Render needed"""
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
        "outputsize": 50,
        "apikey":     TWELVEDATA_KEY
    }
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if "values" not in data:
        return None
    return [float(c["close"]) for c in reversed(data["values"])]

def calculate_rsi(prices, period=14):
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
print("Bot started — direct Telegram, no Render needed!")
send_telegram("🤖 <b>XAUUSD RSI Bot is LIVE on Railway</b>\n\nWatching for RSI signals on 15m chart.\nNo laptop needed — running 24x7!")

while True:
    try:
        prices = get_prices()
        if prices:
            rsi   = calculate_rsi(prices, RSI_PERIOD)
            price = round(prices[-1], 2)
            print(f"[{datetime.utcnow().strftime('%H:%M')}] RSI={rsi} Price=${price}")

            if rsi is not None:
                if rsi < OVERSOLD and last_signal != "OVERSOLD":
                    send_telegram(format_message(
                        "OVERSOLD_ENTRY", rsi, price,
                        f"RSI dipped below {OVERSOLD} — potential buy zone on Gold!"))
                    last_signal = "OVERSOLD"

                elif rsi >= OVERSOLD and last_signal == "OVERSOLD":
                    send_telegram(format_message(
                        "OVERSOLD_RECOVERY", rsi, price,
                        f"RSI recovered above {OVERSOLD} — momentum returning"))
                    last_signal = None

                elif rsi > OVERBOUGHT and last_signal != "OVERBOUGHT":
                    send_telegram(format_message(
                        "OVERBOUGHT_ENTRY", rsi, price,
                        f"RSI crossed above {OVERBOUGHT} — potential sell zone on Gold!"))
                    last_signal = "OVERBOUGHT"

                elif rsi <= OVERBOUGHT and last_signal == "OVERBOUGHT":
                    send_telegram(format_message(
                        "OVERBOUGHT_RECOVERY", rsi, price,
                        f"RSI dropped below {OVERBOUGHT} — sell pressure easing"))
                    last_signal = None

    except Exception as e:
        print(f"Error: {e}")

    time.sleep(CHECK_EVERY)

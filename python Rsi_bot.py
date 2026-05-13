import requests, time, json, os
from datetime import datetime, timezone

TELEGRAM_TOKEN = "8656898499:AAGcRU-wilwH4uewA4Uru1mTecKWYpGKG0s"
CHAT_ID        = "716797698"
OANDA_API_KEY  = "8371ec819abdf35cc95648764fe7ca6e-5ae671445f9a9f57185f0954373e9c8a"
OANDA_URL      = "https://api-fxpractice.oanda.com/v3"

RSI_PERIOD  = 14
CHECK_EVERY = 60 * 5
STATE_FILE  = "bot_state.json"

WATCHLIST = [
    {"symbol": "XAU_USD", "name": "XAUUSD", "tf": "15m", "oversold": 30, "overbought": 70},
]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram failed: {e}")

def get_prices(instrument):
    try:
        url     = f"{OANDA_URL}/instruments/{instrument}/candles"
        headers = {"Authorization": f"Bearer {OANDA_API_KEY}"}
        params  = {"granularity": "M15", "count": 500, "price": "M"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 401:
            print("OANDA 401 — API key wrong or wrong URL (practice vs live)")
            return None, None
        if r.status_code != 200:
            print(f"OANDA error: HTTP {r.status_code}")
            return None, None
        data    = r.json()
        candles = [c for c in data.get("candles", []) if c.get("complete")]
        if not candles:
            return None, None
        closes = [float(c["mid"]["c"]) for c in candles]
        price  = round(closes[-1], 3)
        return closes, price
    except Exception as e:
        print(f"Fetch error {instrument}: {e}")
        return None, None

def calculate_rsi(prices, period=14):
    if len(prices) < period + 2:
        return None
    deltas   = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains    = [d if d > 0 else 0.0 for d in deltas]
    losses   = [-d if d < 0 else 0.0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def format_message(name, signal, rsi, price, tf, note):
    emoji = "🟢" if "OVERSOLD" in signal else "🔴"
    t = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{emoji} <b>{name} — {signal}</b>\n\n"
        f"RSI: <b>{rsi}</b>\n"
        f"Price: <b>{price}</b>\n"
        f"Timeframe: <b>{tf}</b>\n"
        f"Time: {t}\n\n"
        f"<i>{note}</i>\n"
        f"<i>Not financial advice.</i>"
    )

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except: pass

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except: pass
    return {}

def check_asset(asset, state):
    name   = asset["name"]
    symbol = asset["symbol"]
    tf     = asset["tf"]
    os_lvl = asset["oversold"]
    ob_lvl = asset["overbought"]

    prices, price = get_prices(symbol)
    if not prices or price is None:
        print(f"  {name}: no data")
        return state

    rsi  = calculate_rsi(prices, RSI_PERIOD)
    if rsi is None:
        print(f"  {name}: RSI not ready")
        return state

    last = state.get(name)
    print(f"  {name}: RSI={rsi} | Price={price} | State={last}")

    if rsi < os_lvl and last != "OVERSOLD":
        send_telegram(format_message(name, "OVERSOLD_ENTRY", rsi, price, tf,
            f"RSI = {rsi} — crossed below {os_lvl}. Potential buy zone!"))
        state[name] = "OVERSOLD"
        save_state(state)

    elif rsi >= os_lvl and last == "OVERSOLD":
        send_telegram(format_message(name, "OVERSOLD_RECOVERY", rsi, price, tf,
            f"RSI recovered to {rsi} — momentum returning"))
        state[name] = None
        save_state(state)

    elif rsi > ob_lvl and last != "OVERBOUGHT":
        send_telegram(format_message(name, "OVERBOUGHT_ENTRY", rsi, price, tf,
            f"RSI = {rsi} — crossed above {ob_lvl}. Potential sell zone!"))
        state[name] = "OVERBOUGHT"
        save_state(state)

    elif rsi <= ob_lvl and last == "OVERBOUGHT":
        send_telegram(format_message(name, "OVERBOUGHT_RECOVERY", rsi, price, tf,
            f"RSI dropped to {rsi} — sell pressure easing"))
        state[name] = None
        save_state(state)

    return state

print("RSI Bot v6 — XAUUSD only, OANDA data")
state = load_state()
send_telegram(
    "🤖 <b>RSI Bot v6 LIVE — XAUUSD only</b>\n\n"
    "Monitoring: XAUUSD 15m\n\n"
    "✅ OANDA data = matches TradingView\n"
    "✅ Checks every 2 minutes\n"
    "✅ 500 candle RSI warmup"
)

while True:
    t_now = datetime.now(timezone.utc).strftime("%H:%M")
    print(f"\n[{t_now}] Checking XAUUSD...")
    try:
        state = check_asset(WATCHLIST[0], state)
    except Exception as e:
        print(f"Error: {e}")
    print(f"Sleeping 2 min...")
    time.sleep(CHECK_EVERY)

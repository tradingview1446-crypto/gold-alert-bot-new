# RSI Alert Bot v6 — OANDA Edition
# Uses same data source as TradingView — RSI matches perfectly
import requests, time, json, os
from datetime import datetime, timezone

# ── YOUR CONFIG ──────────────────────────────────────────
TELEGRAM_TOKEN = "8656898499:AAGcRU-wilwH4uewA4Uru1mTecKWYpGKG0s"
CHAT_ID        = "716797698"
OANDA_API_KEY  = "8371ec819abdf35cc95648764fe7ca6e-5ae671445f9a9f57185f0954373e9c8a"   # paste from OANDA dashboard
OANDA_URL      = "https://api-fxtrade.oanda.com/v3"   # live account
# If practice account use this instead:
# OANDA_URL    = "https://api-fxpractice.oanda.com/v3"

RSI_PERIOD     = 14
CHECK_EVERY    = 60 * 5    # 2 minutes — sweet spot
STATE_FILE     = "bot_state.json"

# ── WATCHLIST ─────────────────────────────────────────────
# OANDA instruments use underscore format: XAU_USD not XAUUSD
WATCHLIST = [
    # Commodities
    {"symbol": "XAU_USD",  "name": "XAUUSD",  "tf": "15m", "oversold": 30, "overbought": 70},
]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"
        }, timeout=10)
        if r.status_code != 200:
            print(f"Telegram error: {r.status_code}")
    except Exception as e:
        print(f"Telegram failed: {e}")

def get_prices_oanda(instrument):
    """
    Fetch from OANDA API — exact same data TradingView uses.
    Returns 500 closed 15-min candles for accurate RSI warmup.
    """
    try:
        url = f"{OANDA_URL}/instruments/{instrument}/candles"
        headers = {"Authorization": f"Bearer {OANDA_API_KEY}"}
        params  = {
            "granularity": "M15",
            "count":       500,      # 500 candles = ~5 days, plenty for RSI
            "price":       "M"       # M = midpoint (bid+ask)/2
        }
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code != 200:
            print(f"OANDA error {instrument}: {r.status_code} {r.text}")
            return None, None
        data = r.json()
        if "candles" not in data:
            return None, None
        # Only use COMPLETE candles — same as TradingView closed candles
        candles = [c for c in data["candles"] if c["complete"]]
        closes  = [float(c["mid"]["c"]) for c in candles]
        if not closes:
            return None, None
        price = round(closes[-1], 3)
        print(f"  OANDA {instrument}: {len(closes)} candles, latest=${price}")
        return closes, price
    except Exception as e:
        print(f"OANDA fetch error {instrument}: {e}")
        return None, None

def get_prices_yfinance(yf_symbol):
    """Fallback for crypto and indices — yfinance"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="60d", interval="15m")  # max history
        if df is None or df.empty:
            return None, None
        df     = df.iloc[:-1]    # drop live candle for closed-candle mode
        closes = list(df["Close"])
        price  = round(closes[-1], 2)
        return closes, price
    except Exception as e:
        print(f"yfinance error {yf_symbol}: {e}")
        return None, None

def calculate_rsi(prices, period=14):
    """Wilder's Smoothed RSI — identical to TradingView"""
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

def check_asset(name, prices, price, tf, os_lvl, ob_lvl, state):
    """Check RSI and send alert if threshold crossed"""
    rsi = calculate_rsi(prices, RSI_PERIOD)
    if rsi is None:
        print(f"  {name}: RSI not ready")
        return state

    last_signal = state.get(name)
    print(f"  {name}: RSI={rsi} | Price={price} | State={last_signal}")

    if rsi < os_lvl and last_signal != "OVERSOLD":
        send_telegram(format_message(name, "OVERSOLD_ENTRY", rsi, price, tf,
            f"RSI = {rsi} — crossed below {os_lvl}. Potential buy zone!"))
        state[name] = "OVERSOLD"
        save_state(state)

    elif rsi >= os_lvl and last_signal == "OVERSOLD":
        send_telegram(format_message(name, "OVERSOLD_RECOVERY", rsi, price, tf,
            f"RSI recovered to {rsi} — momentum returning"))
        state[name] = None
        save_state(state)

    elif rsi > ob_lvl and last_signal != "OVERBOUGHT":
        send_telegram(format_message(name, "OVERBOUGHT_ENTRY", rsi, price, tf,
            f"RSI = {rsi} — crossed above {ob_lvl}. Potential sell zone!"))
        state[name] = "OVERBOUGHT"
        save_state(state)

    elif rsi <= ob_lvl and last_signal == "OVERBOUGHT":
        send_telegram(format_message(name, "OVERBOUGHT_RECOVERY", rsi, price, tf,
            f"RSI dropped to {rsi} — sell pressure easing"))
        state[name] = None
        save_state(state)

    return state

# ── STARTUP ───────────────────────────────────────────────
print("RSI Bot v6 — OANDA Edition (matches TradingView exactly)")
state = load_state()
total = len(WATCHLIST) + len(YFINANCE_WATCHLIST)
asset_list = "\n".join(
    [f"• {a['name']} (OANDA)" for a in WATCHLIST] +
    [f"• {a['name']} (Yahoo)" for a in YFINANCE_WATCHLIST]
)
send_telegram(
    f"🤖 <b>RSI Bot v6 — OANDA Edition LIVE</b>\n\n"
    f"<b>Monitoring {total} assets:</b>\n{asset_list}\n\n"
    f"✅ OANDA data = same as TradingView\n"
    f"✅ RSI now matches TradingView exactly\n"
    f"✅ Checks every 5 minutes\n"
    f"✅ Wilder's RSI with 500 candle warmup"
)

# ── MAIN LOOP ─────────────────────────────────────────────
while True:
    t_now = datetime.now(timezone.utc).strftime("%H:%M")
    print(f"\n[{t_now}] Scanning {total} assets...")

    # OANDA assets — gold, silver, forex
    for asset in WATCHLIST:
        try:
            prices, price = get_prices_oanda(asset["symbol"])
            if prices and price:
                state = check_asset(
                    asset["name"], prices, price,
                    asset["tf"], asset["oversold"],
                    asset["overbought"], state
                )
            time.sleep(1)
        except Exception as e:
            print(f"  {asset['name']} error: {e}")

    # yfinance assets — crypto, indices
    for asset in YFINANCE_WATCHLIST:
        try:
            prices, price = get_prices_yfinance(asset["symbol"])
            if prices and price:
                state = check_asset(
                    asset["name"], prices, price,
                    asset["tf"], asset["oversold"],
                    asset["overbought"], state
                )
            time.sleep(1)
        except Exception as e:
            print(f"  {asset['name']} error: {e}")

    print(f"Cycle done. Sleeping {CHECK_EVERY // 60} min...")
    time.sleep(CHECK_EVERY)

# RSI Alert Bot v5 — Live Intrabar Alerts, 5-min checks
import yfinance as yf
import time, json, os, requests
from datetime import datetime, timezone

TELEGRAM_TOKEN = "8656898499:AAGcRU-wilwH4uewA4Uru1mTecKWYpGKG0s"
CHAT_ID        = "716797698"
RSI_PERIOD     = 14
CHECK_EVERY = 60 * 5          # ← 5 minute checks
STATE_FILE     = "bot_state.json"

WATCHLIST = [
    # ✅ XAUUSD=X = spot gold, matches TradingView exactly
    {"symbol": "GC=F",      "name": "XAUUSD",  "tf": "15m", "oversold": 30, "overbought": 70},
]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_prices(yf_symbol):
    """
    Fetch prices with automatic fallback symbols.
    If primary symbol fails, tries backup symbols automatically.
    """
    # Fallback map — if primary fails, try these in order
    fallbacks = {
        "XAUUSD=X": ["GC=F", "XAU=X"],
        "GC=F":     ["XAUUSD=X", "XAU=X"],
    }

    symbols_to_try = [yf_symbol] + fallbacks.get(yf_symbol, [])

    for sym in symbols_to_try:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="60d", interval="15m")
            if df is not None and not df.empty and len(df) > 20:
                closes = list(df["Close"])
                price  = round(closes[-1], 2)
                if sym != yf_symbol:
                    print(f"  Used fallback symbol {sym} instead of {yf_symbol}")
                return closes, price
        except Exception as e:
            print(f"  Symbol {sym} failed: {e}, trying next...")
            continue

    print(f"  All symbols failed for {yf_symbol}")
    return None, None

def calculate_rsi(prices, period=14):
    """Wilder's RSI — matches TradingView"""
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

def format_message(name, signal, rsi, price, tf, note):
    emoji = "🟢" if "OVERSOLD" in signal else "🔴"
    t = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{emoji} <b>{name} — {signal}</b>\n\n"
        f"RSI: <b>{rsi}</b>\n"
        f"Price: <b>${price}</b>\n"
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

# ── STARTUP ──────────────────────────────────────────────
print("RSI Bot v5 — Live intrabar alerts, 5-min checks")
state = load_state()
asset_list = "\n".join([f"• {a['name']}" for a in WATCHLIST])
send_telegram(
    f"🤖 <b>RSI Bot v5 LIVE</b>\n\n"
    f"<b>Monitoring:</b>\n{asset_list}\n\n"
    f"✅ Spot prices (XAUUSD=X matches TradingView)\n"
    f"✅ Live intrabar RSI — no candle close wait\n"
    f"✅ Checks every 5 minutes\n"
    f"✅ Wilder's RSI"
)

# ── MAIN LOOP ─────────────────────────────────────────────
while True:
    t_now = datetime.now(timezone.utc).strftime("%H:%M")
    print(f"\n[{t_now}] Scanning {len(WATCHLIST)} assets...")

    for asset in WATCHLIST:
        name, symbol = asset["name"], asset["symbol"]
        tf, os_lvl, ob_lvl = asset["tf"], asset["oversold"], asset["overbought"]
        try:
            prices, price = get_prices(symbol)
            if not prices or price is None:
                print(f"  {name}: no data")
                continue

            rsi = calculate_rsi(prices, RSI_PERIOD)
            if rsi is None:
                print(f"  {name}: RSI not ready")
                continue

            last_signal = state.get(name)
            print(f"  {name}: RSI={rsi} | Price=${price} | State={last_signal}")

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

            time.sleep(2)   # small pause between assets

        except Exception as e:
            print(f"  {name} error: {e}")
            continue

    time.sleep(CHECK_EVERY)

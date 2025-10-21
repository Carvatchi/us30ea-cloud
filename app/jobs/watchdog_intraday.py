# app/jobs/watchdog_intraday.py — US30 only
import os
import requests
import datetime as dt

FMP_KEY = os.getenv("FMP_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

SYMBOL = "^DJI"
THRESHOLD_PIPS = 30.0  # same control threshold

def utc_now():
    return dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg},
            timeout=10
        )
    except Exception as e:
        print("TG error:", e)

def get_price():
    try:
        url = f"https://financialmodelingprep.com/api/v3/quote/{SYMBOL}?apikey={FMP_KEY}"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        j = r.json()
        return float(j[0]["price"]) if j else None
    except Exception as e:
        print("get_price error:", e)
        return None

def main():
    # watchdog rulează rapid (o singură execuție) — verifică ultima variație memorată în /tmp
    price = get_price()
    if price is None:
        print(utc_now(), "no price")
        return

    state_file = "/tmp/us30_prev_price.txt"
    try:
        prev = None
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                prev = float(f.read().strip() or "nan")
        with open(state_file, "w") as f:
            f.write(str(price))
    except Exception as e:
        print("state error:", e)
        prev = None

    if prev is None or prev != prev:  # NaN / first run
        print(utc_now(), "bootstrap prev")
        return

    delta = price - prev
    if abs(delta) >= THRESHOLD_PIPS:
        direction = "UP" if delta > 0 else "DOWN"
        tg(f"⚡ US30 watchdog spike {direction}\n• {utc_now()}\n• Δ: {delta:+.1f} pips\n• Price: {price:.2f}")
    else:
        print(utc_now(), f"no spikes >= {THRESHOLD_PIPS} (Δ {delta:+.1f})")

if __name__ == "__main__":
    main()

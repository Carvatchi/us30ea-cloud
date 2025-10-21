# app/jobs/volatility_worker.py — US30 only (fără GOLD/OIL)
import os
import time
import requests
import datetime as dt

FMP_KEY = os.getenv("FMP_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

SYMBOL = "^DJI"                # US30 index spot (FMP)
THRESHOLD_PIPS = 30.0          # trimite alertă la mișcări ≥ 30 pips / puncte într-un minut
INTERVAL_SEC = 60              # verificare la 60s

def utc_now():
    return dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg},
            timeout=15
        )
    except Exception as e:
        print("TG error:", e)

def get_price():
    try:
        url = f"https://financialmodelingprep.com/api/v3/quote/{SYMBOL}?apikey={FMP_KEY}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        j = r.json()
        if not j:
            return None
        return float(j[0]["price"])
    except Exception as e:
        print("get_price error:", e)
        return None

def main():
    last_price = None
    tg("✅ US30 volatility worker pornit (fără GOLD/OIL)")
    while True:
        price = get_price()
        if price is None:
            time.sleep(INTERVAL_SEC)
            continue

        if last_price is not None:
            delta = price - last_price
            if abs(delta) >= THRESHOLD_PIPS:
                direction = "UP" if delta > 0 else "DOWN"
                msg = (
                    f"⚡ US30 spike {direction}\n"
                    f"• {utc_now()}\n"
                    f"• Δ1m: {delta:+.1f} pips\n"
                    f"• Price: {price:.2f}"
                )
                tg(msg)

        last_price = price
        time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    main()

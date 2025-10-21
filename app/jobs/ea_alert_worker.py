# app/jobs/ea_alert_worker.py — US30 only (curat, fără GOLD/OIL)
import os
import time
import requests
import datetime as dt

# === Config ===
FMP_KEY = os.getenv("FMP_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

SYMBOL = "^DJI"          # US30 index (Dow Jones)
THRESHOLD_PIPS = 30.0    # alertă la mișcări ≥ 30 puncte
SLEEP_SEC = 60           # verificare la fiecare 60 secunde

# === Funcții utile ===
def utc_now():
    return dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def tg(msg: str):
    """Trimite mesaj pe Telegram."""
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg},
            timeout=10
        )
    except Exception as e:
        print("Telegram error:", e)

def get_price():
    """Citește ultimul preț pentru US30 din FMP."""
    try:
        url = f"https://financialmodelingprep.com/api/v3/quote/{SYMBOL}?apikey={FMP_KEY}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return float(data[0].get("price", 0))
    except Exception as e:
        print("get_price error:", e)
        return None

# === Worker principal ===
def main():
    last_price = None
    tg("🟢 EA Alert Worker pornit — US30 only (30 pips/min)")

    while True:
        try:
            price = get_price()
            if price is None:
                time.sleep(SLEEP_SEC)
                continue

            if last_price is not None:
                delta = price - last_price
                if abs(delta) >= THRESHOLD_PIPS:
                    direction = "UP" if delta > 0 else "DOWN"
                    msg = (
                        f"⚡ EA Alert — US30 {direction}\n"
                        f"🕒 {utc_now()}\n"
                        f"Δ1m: {delta:+.1f} pips\n"
                        f"Price: {price:.2f}"
                    )
                    tg(msg)

            last_price = price
            time.sleep(SLEEP_SEC)

        except Exception as e:
            print("Loop error:", e)
            time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()

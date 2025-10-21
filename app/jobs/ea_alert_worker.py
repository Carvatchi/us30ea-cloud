# app/jobs/ea_alert_worker.py — US30 only (fără GOLD/OIL)
import os
import time
import requests
import datetime as dt

# === Config ===
FMP_KEY   = os.getenv("FMP_API_KEY", "")
TG_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT   = os.getenv("TELEGRAM_CHAT_ID", "")

SYMBOL = "^DJI"                # US30 index (Dow Jones)
THRESHOLD_PIPS = 30.0          # alertă la mișcare ≥ 30 puncte
SLEEP_SEC = 60                 # verificare la 60 secunde

# === Funcții utile ===
def utc_now():
    return dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def tg(msg: str):
    """Trimite mesaj în Telegram."""
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
    """Citește ultimul preț al US30 din FMP."""
    try:
        url = f"https://financialmodelingprep.com/api/v3/quote/{SYMBOL}?apikey={FMP_KEY}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return float(data[0].get("price", 0) or 0)
    except Exception as e:
        print("get_price error:", e)
        return None

# === Worker principal ===
def main():
    last_price = None
    tg("🟢 EA Alert Worker pornit — US30 only (30 pips/min)")
    while True:
        try

# app/jobs/volatility_worker.py — doar US30
import os, time, requests, datetime as dt

FMP_KEY = os.getenv("FMP_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

SYMBOL = "^DJI"  # US30 index
THRESHOLD_PIPS = 30.0  # 30 pips / puncte
INTERVAL_SEC = 60

def get_price():
    try:
        url = f"https://financialmodelingprep.com/api/v3/quote/{SYMBOL}?apikey={FMP_KEY}"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        j = r.json()
        return float(j[0]["price"])
    except Exception as e:
        print("Eroare get_price:", e)
        return None

def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT: 
        return
    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id": TG_CHAT, "text": msg},
        timeout=10
    )

def utc_now():
    return dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def main():
    last_price = None
    tg("✅ US30 Volatility worker activ (fără GOLD)")
    while True:
        price = get_price()
        if price is None:
            time.sleep(INTERVAL_SEC)
            continue

        if last_price:
            delta = price - last_price
            if abs(delta) >= THRESHOLD_PIPS:
                direction = "UP" if delta > 0 else "DOWN"
                msg = (
                    f"⚡ US30 Spike {direction}\n"
                    f"{utc_now()}\n"
                    f"Δ1m: {delta:+.1f} pips\n"
                    f"Price: {price:.2f}"
                )
                tg(msg)

        last_price = price
        time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    main()

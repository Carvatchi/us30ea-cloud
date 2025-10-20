# app/jobs/ea_alert_worker.py
# Alerta DOAR pentru US30 (DJI) – prag 30 pips, anti-spam inclus

import os, time, requests
import datetime as dt

# === ENV ===
FMP_KEY = os.getenv("FMP_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

# === Config instrument (doar US30) ===
NAME       = "US30"
SYMBOL     = "^DJI"        # proxy pentru US30
PIP_SIZE   = 1.0           # 1 punct = 1 “pip” la index
STEP_PIPS  = 30            # trimitem alertă dacă mișcarea >= 30 pips
COOLDOWN_S = 180           # anti-spam: minim 3 minute între alerte

# ================= Helpers =================

def fmp_quote(symbol: str):
    """Citește ultimul quote de la FMP."""
    if not FMP_KEY:
        raise RuntimeError("Missing FMP_API_KEY")
    url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={FMP_KEY}"
    r = requests.get(url, timeout=12)
    r.raise_for_status()
    data = r.json()
    return data[0] if isinstance(data, list) and data else {}

def send_tg(text: str):
    if not (TG_TOKEN and TG_CHAT):
        print("Missing Telegram ENV; skipping send.")
        return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TG_CHAT, "text": text}, timeout=10)
    except Exception as e:
        print("TG error:", e)

def fmt_ts_utc():
    return dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

# ================= Main loop =================

def main():
    if not (FMP_KEY and TG_TOKEN and TG_CHAT):
        print("Missing ENV vars (FMP/Telegram).")
    prev_price = None
    last_alert = 0

    print("US30 alert worker started…")
    while True:
        try:
            q = fmp_quote(SYMBOL)
            price = float(q.get("price") or 0.0)
            if price <= 0:
                print("No price, resp:", q)
                time.sleep(10)
                continue

            if prev_price is not None:
                delta_points = price - prev_price
                pips = delta_points / PIP_SIZE
                now = time.time()

                if abs(pips) >= STEP_PIPS and (now - last_alert) >= COOLDOWN_S:
                    direction = "UP" if pips > 0 else "DOWN"
                    sign = "+" if pips > 0 else "-"
                    msg = (
                        f"⚡ EA Alert — {NAME}\n"
                        f"{fmt_ts_utc()}\n"
                        f"Move (last ~10s): {sign}{abs(int(pips))} pips ({direction})\n"
                        f"Price: {price:,.2f}"
                    )
                    print(msg.replace("\n", " | "))
                    send_tg(msg)
                    last_alert = now

            prev_price = price
        except Exception as e:
            print("Loop error:", e)

        # Polling rapid (≈ „instant”), dar cu anti-spam pe mesaj
        time.sleep(10)


if __name__ == "__main__":
    main()

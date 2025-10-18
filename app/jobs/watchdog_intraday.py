# app/jobs/watchdog_intraday.py
import os, time, datetime as dt, pytz, requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
FMP_KEY = os.getenv("FMP_KEY", "demo")  # pune cheia ta în Render

# Simboluri FMP (fallback YM=F/GC=F dacă DJI/Gold spot nu răspunde)
US30_TICKERS = ["^DJI", "YM=F"]
GOLD_TICKERS = ["GC=F", "XAUUSD"]

TZ_RO = pytz.timezone("Europe/Bucharest")

def send_tg(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg[:4000]})
    except Exception:
        pass

def fmp_quote(sym):
    url = f"https://financialmodelingprep.com/api/v3/quote/{sym}?apikey={FMP_KEY}"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        j = r.json()
        if isinstance(j, list) and j:
            return j[0]  # dict: price, changesPercentage, change, previousClose, etc.
    return None

def pick_first_ok(symbols):
    for s in symbols:
        q = fmp_quote(s)
        if q:
            return s, q
    return None, None

def within_session(now_ro: dt.datetime) -> bool:
    # Rulează doar 06:00–00:00 (ora României)
    h = now_ro.hour
    return (h >= 6) or (h == 0 and now_ro.minute == 0)

def main():
    now_ro = dt.datetime.now(TZ_RO)
    if not within_session(now_ro):
        return

    us30_sym, us30 = pick_first_ok(US30_TICKERS)
    gold_sym, gold = pick_first_ok(GOLD_TICKERS)

    lines = [f"[Watchdog] {now_ro:%Y-%m-%d %H:%M} RO"]
    alerts = []

    if us30:
        p = us30.get("price")
        chg = us30.get("changesPercentage")  # ex: -0.23
        lines.append(f"US30 {us30_sym}: {p} | {chg}%")
        if isinstance(chg, (int, float)) and abs(chg) >= 0.8:
            arrow = "⬆️" if chg > 0 else "⬇️"
            alerts.append(f"{arrow} US30 move {chg}% vs prev close")
    else:
        lines.append("US30: n/a")

    if gold:
        p = gold.get("price")
        chg = gold.get("changesPercentage")
        lines.append(f"GOLD {gold_sym}: {p} | {chg}%")
        if isinstance(chg, (int, float)) and abs(chg) >= 1.0:
            arrow = "🟡⬆️" if chg > 0 else "🟡⬇️"
            alerts.append(f"{arrow} GOLD move {chg}% vs prev close")
    else:
        lines.append("GOLD: n/a")

    if alerts:
        lines.append("")
        lines.extend(alerts)

    send_tg("\n".join(lines))

if __name__ == "__main__":
    main()

# app/jobs/volatility_worker.py
# Worker care rulează continuu și trimite alertă instant la mișcări ≥ 30 pips (US30) / 3$ (GOLD)

import os, time, requests, statistics
from datetime import datetime, timezone

FMP_KEY   = os.getenv("FMP_API_KEY", "")
TG_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT   = os.getenv("TELEGRAM_CHAT_ID", "")

# Simboluri (FMP)
US30 = "YM=F"      # Dow futures (proxy lichid pt US30)
GOLD = "GC=F"      # Gold futures
SYMBOLS = [US30, GOLD]

# Praguri "instant" (ajustezi după preferință)
THRESH_US30_POINTS = 30        # ≈ 30 pips/points
THRESH_GOLD_DOLLAR = 3.0       # ≈ 300 pips XAUUSD (0.01 = 1 pip)

# Fereastră de monitorizare (rolling) și pas de poll
ROLL_SEC  = 60
POLL_SEC  = 5

FMP_QUOTE = "https://financialmodelingprep.com/api/v3/quote/{sym}?apikey={key}"
FMP_HIST1 = "https://financialmodelingprep.com/api/v3/historical-chart/1min/{sym}?apikey={key}"

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def fmp_price(sym):
    r = requests.get(FMP_QUOTE.format(sym=sym, key=FMP_KEY), timeout=15)
    r.raise_for_status()
    j = r.json()
    if not j: return None
    return float(j[0].get("price") or 0.0)

def fmp_hist1(sym, limit=60):
    r = requests.get(FMP_HIST1.format(sym=sym, key=FMP_KEY), timeout=20)
    r.raise_for_status()
    j = r.json()[:limit]
    # listă de prețuri de la cel mai vechi la cel mai nou
    return [float(x["close"]) for x in reversed(j)]

def send_tg(text):
    if not (TG_TOKEN and TG_CHAT): 
        print("⚠️ Missing TELEGRAM envs")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT, "text": text}, timeout=20)

def estimate_tp(sym, last_price):
    """TP simplu: 1.5×ATR(14) 1-min, cu cap. Diferit pentru US30 vs GOLD."""
    try:
        prices = fmp_hist1(sym, limit=60)  # 60 min
        if len(prices) < 15: 
            return None, None
        # true range 1-min aproximat ca |Δ| pe 1-min
        diffs = [abs(prices[i]-prices[i-1]) for i in range(1, len(prices))]
        atr14 = sum(diffs[-14:]) / 14.0
        if sym == US30:
            tp = min(atr14*1.5, 160.0)   # limităm la 160 puncte
            unit = "pts"
        else:
            tp = min(atr14*1.5, 10.0)    # limităm la 10$ la GOLD
            unit = "$"
        return round(tp,2), unit
    except Exception as e:
        print("ATR/TP error:", e)
        return None, None

def run():
    if not (FMP_KEY and TG_TOKEN and TG_CHAT):
        print("❌ Missing ENV (FMP_API_KEY / TELEGRAM_*) — exiting.")
        return

    # rolling buffers
    buffers = {sym: [] for sym in SYMBOLS}
    last_alert_price = {sym: None for sym in SYMBOLS}  # ca să nu spamăm

    print("🚀 Volatility worker started @", now_utc())
    while True:
        for sym in SYMBOLS:
            try:
                p = fmp_price(sym)
                if not p: 
                    continue

                buf = buffers[sym]
                buf.append((time.time(), p))
                # ținem doar ultimele ROLL_SEC secunde
                t0 = time.time() - ROLL_SEC
                while buf and buf[0][0] < t0:
                    buf.pop(0)

                # mișcare în fereastră
                start_p = buf[0][1] if buf else p
                move = p - start_p
                move_abs = abs(move)

                # praguri pe simbol
                if sym == US30:
                    trigger = (move_abs >= THRESH_US30_POINTS)
                    unit = "pts"
                    label = "US30"
                else:
                    trigger = (move_abs >= THRESH_GOLD_DOLLAR)
                    unit = "$"
                    label = "GOLD"

                if trigger:
                    # evităm spam dacă nu s-a schimbat prea mult față de ultima alertă
                    lastp = last_alert_price[sym]
                    if lastp is None or abs(p - lastp) > (0.5 if sym==US30 else 0.3):
                        tp, tp_unit = estimate_tp(sym, p)
                        dir_txt = "UP" if move > 0 else "DOWN"
                        tp_txt = f" | TP est.: ~{tp}{tp_unit}" if tp else ""
                        text = (f"⚡ Volatility alert — {label}\n"
                                f"{now_utc()}\n"
                                f"Move (last {ROLL_SEC}s): {move:+.2f}{unit} ({dir_txt})\n"
                                f"Price: {p:.2f}{'' if sym==US30 else ' $'}{tp_txt}")
                        send_tg(text)
                        print("Alert:", text)
                        last_alert_price[sym] = p
            except Exception as e:
                print("loop error", sym, e)
        time.sleep(POLL_SEC)

if __name__ == "__main__":
    run()

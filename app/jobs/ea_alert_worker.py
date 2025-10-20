# app/jobs/ea_alert_worker.py
# ONE-FILE WORKER: Volatility alerts (US30/Gold/Oil) + News bias (FMP) în același mesaj.
# Rulează 24/7 în Render Background Worker.

import os, time, requests
from datetime import datetime, timezone

# =========================
# ENV (puse în Render → Environment)
# =========================
FMP_KEY  = os.getenv("FMP_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

if not FMP_KEY or not TG_TOKEN or not TG_CHAT:
    raise SystemExit("❌ Missing ENV: FMP_API_KEY / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

# =========================
# Config
# =========================
# Simboluri FMP
SYM_US30 = "YM=F"   # Dow futures (proxy US30)
SYM_OIL  = "CL=F"   # WTI Oil futures

WATCH = [SYM_US30, SYM_GOLD, SYM_OIL]

# Praguri mișcare "instant" pe fereastră ROLL_SEC
ROLL_SEC   = 60      # analizăm ultima fereastră de 60s
POLL_SEC   = 5       # frecvență interogare preț
# Praguri per instrument (puncte / $)
THRESH = {
    SYM_US30: 30.0,   # ~30 pips/points
    SYM_OIL : 1.0,    # $1
}
# Anti-spam: nu retrimitem dacă prețul nu s-a mutat suficient față de ultima alertă
RETRIGGER_GAP = {
    SYM_US30: 8.0,   # ~8 puncte
    SYM_OIL : 0.3,   # $0.3
}

# =========================
# Endpoints FMP
# =========================
URL_QUOTE = "https://financialmodelingprep.com/api/v3/quote/{sym}?apikey={key}"
URL_H1    = "https://financialmodelingprep.com/api/v3/historical-chart/1min/{sym}?apikey={key}"
URL_NEWS  = "https://financialmodelingprep.com/api/v3/stock_news?tickers={tick}&limit=24&apikey={key}"

# =========================
# Telegram
# =========================
def tg_send(text: str):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print("TG error:", e)

# =========================
# Utils
# =========================
def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def fmp_price(sym: str):
    r = requests.get(URL_QUOTE.format(sym=sym, key=FMP_KEY), timeout=15)
    r.raise_for_status()
    j = r.json()
    if not j:
        return None
    return float(j[0].get("price") or 0.0)

def fmp_hist1(sym: str, limit=60):
    r = requests.get(URL_H1.format(sym=sym, key=FMP_KEY), timeout=20)
    r.raise_for_status()
    j = r.json()[:limit]
    # returnăm listă [prețuri] de la vechi la nou
    return [float(x["close"]) for x in reversed(j)]

# ATR(14) pe 1-min aproximat cu |Δ| între close-uri succesive
def atr1m(sym: str, lookback=60):
    try:
        prices = fmp_hist1(sym, limit=max(lookback, 16))
        if len(prices) < 16:
            return None
        diffs = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
        # medie ultime 14 diferențe
        tr14 = sum(diffs[-14:]) / 14.0
        return tr14
    except Exception as e:
        print("ATR error:", sym, e)
        return None

# =========================
# News Lexicon (simplu)
# =========================
POS = {
    "beat earnings": 2.0, "beats estimates": 2.0, "upgrade": 1.5, "buyback": 1.2,
    "merger": 1.0, "acquisition": 1.0, "ai growth": 1.2, "soft landing": 1.0,
    "cut rates": 1.5, "dovish": 1.2
}
NEG = {
    "miss earnings": -2.0, "misses estimates": -2.0, "downgrade": -1.5,
    "guidance cut": -1.5, "layoffs": -1.0, "lawsuit": -1.0, "investigation": -1.2,
    "hawkish": -1.2, "raise rates": -1.5, "escalation": -1.2, "conflict": -1.2
}

def score_text(txt: str) -> float:
    t = (txt or "").lower()
    s = 0.0
    for k, w in POS.items():
        if k in t: s += w
    for k, w in NEG.items():
        if k in t: s += w
    return s

def news_bias():
    tickers = ["^DJI","YM=F","GC=F","CL=F","MSFT","AAPL","GS"]
    try:
        r = requests.get(URL_NEWS.format(tick=",".join(tickers), key=FMP_KEY), timeout=20)
        r.raise_for_status()
        items = r.json()[:24]
        total = sum(score_text((x.get("title","")+" "+x.get("text",""))) for x in items)
        if total > 0.8:  return "BULLISH", round(total, 2)
        if total < -0.8: return "BEARISH", round(total, 2)
        return "NEUTRAL", round(total, 2)
    except Exception as e:
        print("news_bias error:", e)
        return None, None

def label_of(sym: str):
    if sym == SYM_US30: return "US30"
    if sym == SYM_GOLD: return "GOLD"
    if sym == SYM_OIL : return "OIL"
    return sym

def unit_of(sym: str):
    # unitate de afișare
    return "pts" if sym == SYM_US30 else "$"

def tp_estimate(sym: str):
    """TP = 1.5 × ATR(14) 1-min, cu limitare superioară."""
    a = atr1m(sym, lookback=60)
    if a is None: 
        return None
    mul = 1.5
    if sym == SYM_US30:
        return round(min(a*mul, 160.0), 2)   # max 160 puncte
    if sym == SYM_GOLD:
        return round(min(a*mul, 10.0), 2)    # max $10
    if sym == SYM_OIL:
        return round(min(a*mul, 3.0), 2)     # max $3
    return round(a*mul, 2)

# =========================
# Main loop
# =========================
def run():
    print("🚀 EA Alert worker started @", now_utc())
    buffers = {sym: [] for sym in WATCH}            # listă de tuple (t, price)
    last_alert_px = {sym: None for sym in WATCH}    # anti-spam

    while True:
        tnow = time.time()
        for sym in WATCH:
            try:
                px = fmp_price(sym)
                if not px:
                    continue

                # update buffer
                buf = buffers[sym]
                buf.append((tnow, px))
                tmin = tnow - ROLL_SEC
                while buf and buf[0][0] < tmin:
                    buf.pop(0)

                start_px = buf[0][1] if buf else px
                move = px - start_px
                move_abs = abs(move)

                thr = THRESH.get(sym, 9999.0)
                hit = (move_abs >= thr)

                if hit:
                    # anti-spam: verificăm distanța față de ultima alertă
                    lastp = last_alert_px[sym]
                    retr = RETRIGGER_GAP.get(sym, thr/4)
                    if (lastp is None) or (abs(px - lastp) >= retr):
                        # calculează TP & news bias
                        tp  = tp_estimate(sym)
                        bias, bscore = news_bias()
                        dir_txt = "UP" if move > 0 else "DOWN"

                        tp_txt = f" | TP est.: ~{tp}{unit_of(sym)}" if tp else ""
                        bias_txt = f"\nNews bias: {bias} ({bscore:+.2f})" if bias else ""

                        text = (
                            f"⚡ EA Alert — {label_of(sym)}\n"
                            f"{now_utc()}\n"
                            f"Move (last {ROLL_SEC}s): {move:+.2f}{unit_of(sym)} ({dir_txt})\n"
                            f"Price: {px:.2f}{'' if sym==SYM_US30 else ' $'}"
                            f"{tp_txt}{bias_txt}"
                        )
                        tg_send(text)
                        print("ALERT:", text.replace("\n"," | "))

                        last_alert_px[sym] = px

            except Exception as e:
                print("loop error", sym, e)

        time.sleep(POLL_SEC)

if __name__ == "__main__":
    run()

# app/jobs/watchdog_intraday.py
import os, time, requests, datetime as dt

FMP_KEY = os.getenv("FMP_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID")

# Simboluri FMP (minute bars):
# DJIA futures (US30):  YM=F
# Gold futures:        GC=F
# WTI Oil futures:     CL=F
SYMBOLS = {
    "US30": "YM=F",
    "GOLD": "GC=F",
    "OIL":  "CL=F",
}

# Pragurile “30 pips” adaptate:
# - US30: 30 puncte
# - GOLD: ~3.0 (≈ 30 "pips" dacă considerăm 0.1 ca pip)
# - OIL:  0.3  (≈ 30 "ticks" de 0.01)
THRESHOLDS = {"US30": 30.0, "GOLD": 3.0, "OIL": 0.3}

def fmp_1min_last2(symbol: str):
    url = f"https://financialmodelingprep.com/api/v3/historical-chart/1min/{symbol}?limit=2&apikey={FMP_KEY}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list) or len(data) < 2:
        return None
    # ultimele două lumânări (FMP întoarce deja desc)
    a, b = data[0], data[1]
    return float(a["close"]), float(b["close"]), a.get("date")

def send_tg(text: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True}
    requests.post(url, json=payload, timeout=20)

def format_estimate(symbol_name: str, last: float, delta: float):
    direction = "UP" if delta > 0 else "DOWN"
    abs_delta = abs(delta)

    # “TP estimat”: proiectăm 1x–1.5x mișcarea observată
    tp_move = abs_delta * 1.2
    if symbol_name == "US30":
        tp_price = last + (tp_move if delta > 0 else -tp_move)
        units = "pts"
    elif symbol_name == "GOLD":
        tp_price = last + (tp_move if delta > 0 else -tp_move)
        units = ""
    else:  # OIL
        tp_price = last + (tp_move if delta > 0 else -tp_move)
        units = ""

    line1 = f"⚠️ {symbol_name} spike {direction}: {abs_delta:.2f}"
    if symbol_name == "US30":
        line1 += " pts"
    line2 = f"• Price: {last:.2f} | Est. TP: {tp_price:.2f}"
    return f"{line1}\n{line2}"

def main():
    if not (FMP_KEY and TG_TOKEN and TG_CHAT):
        print("Missing ENV (FMP_API_KEY / TELEGRAM_*).")
        return

    now = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    triggered = []

    for name, sym in SYMBOLS.items():
        try:
            last, prev, ts = fmp_1min_last2(sym)
            delta = last - prev
            thr = THRESHOLDS[name]
            if abs(delta) >= thr:
                msg = f"🕒 {now}\n{format_estimate(name, last, delta)}\n• Δ1m: {delta:.2f}"
                triggered.append(msg)
        except Exception as e:
            print(name, "error:", e)

    if triggered:
        send_tg("\n\n".join(triggered))
    else:
        # opțional, tăcut; sau trimite heartbeat rar
        print(f"{now} – no spikes >= thresholds")

if __name__ == "__main__":
    main()

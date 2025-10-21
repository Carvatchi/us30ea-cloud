# app/jobs/bias_preopen.py — pre-open bias (US30 only)
import os
import requests
import datetime as dt

FMP_KEY = os.getenv("FMP_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

# Rulează cu 5–10 minute înainte de cash open (16:20–16:25 RO → 13:20–13:25 UTC iarna / 14:20–14:25 vara).
# Îți trimite un bias orientativ pe baza schimbării agregate (index + futures).

TICKERS = ["^DJI", "YM=F"]  # index + futures

def utc_now():
    return dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print("TG error:", e)

def q(sym):
    url = f"https://financialmodelingprep.com/api/v3/quote/{sym}?apikey={FMP_KEY}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    j = r.json()
    return j[0] if j else None

def label(x):
    return "BULLISH" if x > 0 else ("BEARISH" if x < 0 else "NEUTRAL")

def arrow(x):
    return "🟢↑" if x > 0 else ("🔴↓" if x < 0 else "⚪→")

def main():
    lines = [f"🕒 {utc_now()} — Pre-open bias"]
    score = 0.0
    for s in TICKERS:
        d = q(s)
        if not d:
            continue
        chg = float(d.get("changesPercentage") or 0)
        score += chg
        lines.append(f"{s}: {d.get('price'):.2f} ({chg:.2f}%)")
    bias = label(score)
    lines.insert(1, f"US30 Bias: {arrow(score)} <b>{bias}</b> | score {abs(score):.2f}")
    tg("\n".join(lines))

if __name__ == "__main__":
    main()

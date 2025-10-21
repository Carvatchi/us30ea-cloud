# app/jobs/news_sentiment.py — fără GOLD/OIL
import os
import requests
import datetime as dt

FMP_KEY = os.getenv("FMP_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")
SENTI_MIN = 1.0  # trimite alertă doar dacă |sentiment| >= 1.0

# urmărește câteva simboluri relevante, fără GC=F / CL=F
TICKERS = ["^DJI", "YM=F", "MSFT", "AAPL", "GS"]

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

def news_sentiment():
    # simplu placeholder: folosește procentul de schimbare ca proxy sentiment (în lipsa altui feed)
    scores = []
    for s in TICKERS:
        try:
            url = f"https://financialmodelingprep.com/api/v3/quote/{s}?apikey={FMP_KEY}"
            r = requests.get(url, timeout=10); r.raise_for_status()
            j = r.json()
            if j:
                scores.append(float(j[0].get("changesPercentage") or 0))
        except Exception:
            pass
    return sum(scores)/len(scores) if scores else 0.0

def main():
    score = news_sentiment()
    if abs(score) >= SENTI_MIN:
        bias = "BULLISH" if score > 0 else "BEARISH"
        tg(f"📰 News sentiment {utc_now()} | Bias: <b>{bias}</b> | Score: {score:+.2f}")
    else:
        print(utc_now(), f"Sentiment small: {score:+.2f} | no TG alert")

if __name__ == "__main__":
    main()

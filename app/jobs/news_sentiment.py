# app/jobs/news_sentiment.py
import os, datetime as dt, pytz, requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

TZ_RO = pytz.timezone("Europe/Bucharest")

def send_tg(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg[:4000]})
    except Exception:
        pass

def main():
    now_ro = dt.datetime.now(TZ_RO)
    # TODO: Integrare reală sentiment news (Bloomberg/NewsAPI/alte surse)
    msg = f"📰 [NewsSentiment] {now_ro:%Y-%m-%d %H:%M} RO\nHeartbeat OK. (Sentiment engine to be wired here)"
    send_tg(msg)

if __name__ == "__main__":
    main()

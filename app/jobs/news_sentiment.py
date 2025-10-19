# app/jobs/news_sentiment.py
import os, time, json, requests, datetime as dt

FMP_KEY = os.getenv("FMP_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID")

# Ticker-ele relevante: index proxy + leaders (poți adăuga ușor)
TICKERS = ["^DJI", "YM=F", "GC=F", "CL=F", "MSFT", "AAPL", "GS"]

# Lexicon minimal (greutăți). Pozitive adaugă, negative scad.
POS_KEYS = {
    "beat earnings": 2.0, "beats estimates": 2.0, "upgrade": 1.5, "buyback": 1.2,
    "merger": 1.0, "acquisition": 1.0, "ai growth": 1.2, "soft landing": 1.0,
    "cut rates": 1.5, "dovish": 1.2
}
NEG_KEYS = {
    "miss earnings": -2.0, "misses estimates": -2.0, "downgrade": -1.5,
    "guidance cut": -1.5, "layoffs": -1.0, "lawsuit": -1.0, "investigation": -1.2,
    "hawkish": -1.2, "raise rates": -1.5, "escalation": -1.2, "conflict": -1.2
}
CEO_KEYS = { "ceo": 0.5, "cfo": 0.5, "resigns": -1.5, "appointed": +0.8 }

def fmp_news(limit=40):
    # FMP “stock_news” e stabil, dar poate rata unele surse – e ok ca MVP
    url = f"https://financialmodelingprep.com/api/v3/stock_news?tickers={','.join(TICKERS)}&limit={limit}&apikey={FMP_KEY}"
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    return r.json()

def score_text(txt: str) -> float:
    t = txt.lower()
    s = 0.0
    for k,w in POS_KEYS.items():
        if k in t: s += w
    for k,w in NEG_KEYS.items():
        if k in t: s += w
    for k,w in CEO_KEYS.items():
        if k in t: s += w
    return s

def summarize(items):
    # scor total + top 3 titluri relevante cu scor mare în absolut
    scored = []
    for x in items:
        title = x.get("title","")
        site  = x.get("site","")
        s = score_text(title + " " + x.get("text",""))
        scored.append((s, title, site))
    scored.sort(key=lambda z: abs(z[0]), reverse=True)
    total = sum(s for s,_,_ in scored)
    return total, scored[:3]

def send_tg(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True}, timeout=20)

def main():
    if not (FMP_KEY and TG_TOKEN and TG_CHAT):
        print("Missing ENV for news job.")
        return
    try:
        items = fmp_news(limit=40)
        total, top = summarize(items)
        bias = "BULLISH" if total>0.8 else ("BEARISH" if total<-0.8 else "NEUTRAL")
        now  = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        lines = [f"📰 News sentiment {now}", f"Bias: {bias} | Score: {total:+.2f}", "Top drivers:"]
        for s,title,site in top:
            lines.append(f"• {s:+.2f} — {title} [{site}]")

        # Trimite alertă doar dacă mișcă acul (|score| ≥ 1.5)
        if abs(total) >= 1.5:
            send_tg("\n".join(lines))
        else:
            print("Sentiment small:", total, "| no TG alert")
    except Exception as e:
        print("news job error:", e)

if __name__ == "__main__":
    main()

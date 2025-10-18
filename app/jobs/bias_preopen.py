import os, json, requests
from pathlib import Path
from datetime import datetime, timezone

FMP_KEY = os.getenv("FMP_API_KEY", "").strip()
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "").strip()

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
FUND_PATH = DATA_DIR / "fundamentals.json"
SENT_PATH = DATA_DIR / "sentiment.json"

LEADERS = ["MSFT", "UNH", "GS", "HD", "JPM"]

def read_json(p: Path):
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}

def get_quote(symbol: str):
    url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}"
    r = requests.get(url, params={"apikey": FMP_KEY}, timeout=15)
    if r.status_code == 200:
        arr = r.json()
        return arr[0] if arr else {}
    return {}

def combine_score(fund_s: float, sent: float, tech: float=0.0):
    f = (fund_s/50.0 - 1.0)  # 0..100 -> -1..+1
    return 0.55*f + 0.30*sent + 0.15*tech

def arrow(v: float):
    return "⬆️" if v >= 0.20 else "⬇️" if v <= -0.20 else "≈"

def label(v: float):
    if v >= 0.40: return "BULL (strong)"
    if v >= 0.20: return "BULL (mild)"
    if v <= -0.40: return "BEAR (strong)"
    if v <= -0.20: return "BEAR (mild)"
    return "NEUTRAL"

def pct(x): return f"{x*100:.0f}%"

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=15)
    print("Telegram:", r.status_code)
    return r.ok

def main():
    fund = read_json(FUND_PATH)
    sent = read_json(SENT_PATH)
    fund_items = fund.get("items") if isinstance(fund, dict) else {}

    per_ticker = []
    for t in LEADERS:
        fs = float(fund_items.get(t, {}).get("score", 50.0))
        ss = float(sent.get(t, 0.0)) if isinstance(sent, dict) else 0.0
        s = combine_score(fs, ss, 0.0)
        per_ticker.append((t, s, fs, ss))

    us30_bias = sum(x[1] for x in per_ticker)/len(per_ticker) if per_ticker else 0.0

    macro_sent = float(sent.get("Macro", 0.0)) if isinstance(sent, dict) else 0.0
    gold_bias = -0.5*us30_bias + -0.2*macro_sent

    gc = get_quote("GC=F"); ym = get_quote("YM=F")
    top_drivers = sorted(per_ticker, key=lambda x: x[1], reverse=True)
    best = ", ".join([f"{t}{'↑' if s>0 else '↓' if s<0 else '≈'}" for t,s,_,_ in top_drivers[:3]])

    lines = []
    lines.append(f"📊 <b>US30 — Pre-open Bias</b>  ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)")
    lines.append(f"US30: <b>{arrow(us30_bias)}</b>  {label(us30_bias)}  | score {pct(abs(us30_bias))}")
    lines.append(f"Drivers: {best if best else 'n/a'}")
    if ym and ym.get('price') is not None and ym.get('changesPercentage') is not None:
        lines.append(f"YM=F: {ym['price']:.0f}  ({ym['changesPercentage']:.2f}%)")
    lines.append("")
    lines.append(f"🟡 <b>GOLD Bias</b>: {arrow(gold_bias)}  {label(gold_bias)} | score {pct(abs(gold_bias))}")
    if gc and gc.get('price') is not None and gc.get('changesPercentage') is not None:
        lines.append(f"GC=F: {gc['price']:.0f}  ({gc['changesPercentage']:.2f}%)")
    det = " • ".join([f"{t}:fund={fs:.0f}/sent={ss:+.2f}" for t,_,fs,ss in per_ticker])
    if det:
        lines.append("")
        lines.append(f"<i>{det}</i>")

    text = "\n".join(lines)
    if TG_TOKEN and TG_CHAT:
        send_telegram(text)
    else:
        print(text)

if __name__ == "__main__":
    main()

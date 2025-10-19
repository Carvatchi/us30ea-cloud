# app/ui/app.py
import os, requests, time
import streamlit as st
from datetime import datetime, timezone

FMP_KEY = os.getenv("FMP_API_KEY")

SYMBOLS = {
    "US30": ("YM=F", "pts", 30.0),
    "GOLD": ("GC=F", "",    3.0),
    "OIL":  ("CL=F", "",    0.3),
}

def fmp_quote(symbol):
    url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={FMP_KEY}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data: return None
    x = data[0]
    return float(x["price"]), float(x.get("change", 0.0)), float(x.get("changesPercentage", 0.0))

def fmp_last2_1min(symbol):
    url = f"https://financialmodelingprep.com/api/v3/historical-chart/1min/{symbol}?limit=2&apikey={FMP_KEY}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data or len(data) < 2: return None
    a, b = data[0], data[1]
    return float(a["close"]), float(b["close"]), a.get("date")

st.set_page_config(page_title="EA Alert Dashboard", page_icon="🧠", layout="wide")

st.title("EA Alert Dashboard")
st.caption("🧠 Sistem de analiză pentru US30, Gold și Oil.\nVerifică știrile, sentimentul și semnalele generate de IA.")

colA, colB = st.columns([2,1])

with colA:
    st.subheader("Live Δ 1-min & praguri „30 pips”")
    rows = []
    for name, (sym, unit, thr) in SYMBOLS.items():
        try:
            last, prev, ts = fmp_last2_1min(sym)
            delta = last - prev
            hit = abs(delta) >= thr
            st.metric(
                label=f"{name} ({sym})  |  Δ1m threshold {thr}{(' ' + unit) if unit else ''}",
                value=f"{last:.2f}",
                delta=f"{delta:+.2f}{(' ' + unit) if unit else ''}",
                delta_color="normal" if not hit else "inverse"  # colorize when hit
            )
            if hit:
                st.success(f"⚠️ Spike ≥ prag detectat: {name} {delta:+.2f}{(' ' + unit) if unit else ''}  —  {ts}")
        except Exception as e:
            st.warning(f"{name}: {e}")

with colB:1
    st.subheader("Status & Info")
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    st.write(f"**Local time:** {now}")
    st.write("**Frecvență watchdog:** la 1 minut (cron).")
    st.write("Alertele se trimit pe Telegram când Δ1m ≥ prag.")

st.divider()
st.markdown("**Notă:** Alertele Telegram sunt trimise de job-ul `us30-watchdog` (Render). Acest dashboard verifică live ultimele 2 lumânări de 1 minut direct din FMP.")
import pandas as pd

LEADERS = ["MSFT","AAPL","GS"]

def fmp_quotes_many(symbols):
    url = f"https://financialmodelingprep.com/api/v3/quote/{','.join(symbols)}?apikey={FMP_KEY}"
    r = requests.get(url, timeout=20); r.raise_for_status()
    return r.json()

st.subheader("Leaders snapshot (US30 drivers)")
try:
    q = fmp_quotes_many(LEADERS + ["YM=F"])
    df = pd.DataFrame([{
        "symbol": x["symbol"],
        "price": x["price"],
        "chg%": x.get("changesPercentage", 0.0),
        "change": x.get("change", 0.0)
    } for x in q]).set_index("symbol").loc[LEADERS + ["YM=F"]]
    st.dataframe(df, use_container_width=True)
except Exception as e:
    st.warning(f"Leaders error: {e}")

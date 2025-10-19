 # app/ui/app.py  — US30/GOLD EA Alert (UI complet)
# -------------------------------------------------------------------
# Ce afișează:
# 1) Status sistem + chei ENV detectate (FMP + Telegram)
# 2) Leaders pentru US30 (MSFT/AAPL/GS + YM=F) din FMP /quote
# 3) Rezumat News Sentiment (ultimele articole FMP) cu scor + bias
# 4) Mini-calculator volatilitate (pips/%) pentru US30/Gold/Oil
# -------------------------------------------------------------------

import os
import time
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="US30/GOLD — EA Alert (Cloud)", layout="wide")
st.title("US30 / GOLD — EA Alert (Cloud)")

# ---------------------------
# Config din ENV
# ---------------------------
FMP_KEY = os.getenv("FMP_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

# tickere lideri + proxii index/commodities
LEADERS = ["MSFT", "AAPL", "GS", "YM=F"]        # YM=F = Dow futures
COMMS   = ["GC=F", "CL=F"]                      # Gold / Oil

# ---------------------------
# Helperi
# ---------------------------
def fmp_quotes_many(symbols):
    """Citește quotes pentru o listă de simboluri FMP."""
    if not FMP_KEY:
        raise RuntimeError("FMP_API_KEY lipsește din env.")
    url = f"https://financialmodelingprep.com/api/v3/quote/{','.join(symbols)}?apikey={FMP_KEY}"
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    return r.json()

def fmp_news(limit=40):
    """Știri FMP pentru index + leaders + commodities (ultimele N)."""
    if not FMP_KEY:
        raise RuntimeError("FMP_API_KEY lipsește din env.")
    tickers = "%5EDJI,YM%3DF,GC%3DF,CL%3DF,MSFT,AAPL,GS"
    url = f"https://financialmodelingprep.com/api/v3/stock_news?tickers={tickers}&limit={limit}&apikey={FMP_KEY}"
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    return r.json()

def quick_sentiment_score(text: str) -> float:
    """Lexicon minimal, rapid (pozitive +1, negative -1, ceo/cfo +/-0.3)."""
    t = (text or "").lower()
    pos = ("beat earnings","beats estimates","upgrade","buyback",
           "merger","acquisition","ai growth","soft landing",
           "cut rates","dovish")
    neg = ("miss earnings","misses estimates","downgrade","guidance cut",
           "layoffs","lawsuit","investigation","hawkish","raise rates",
           "escalation","conflict")
    ceo = ("ceo","cfo","resigns","appointed")

    s = 0.0
    for k in pos:
        if k in t: s += 1.0
    for k in neg:
        if k in t: s -= 1.0
    for k in ceo:
        if k in t: s += 0.3 if k in ("ceo","cfo","appointed") else -0.3
    return s

# ---------------------------
# 1) Status sistem
# ---------------------------
st.subheader("Status sistem")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("FMP_API_KEY", "OK" if bool(FMP_KEY) else "MISSING")
with col2:
    st.metric("Telegram token", "OK" if bool(TG_TOKEN) else "MISSING")
with col3:
    st.metric("Telegram chat", TG_CHAT if TG_CHAT else "MISSING")

st.caption("Dacă toate sunt **OK**, job-urile din Render (watchdog & news) pot rula și pot trimite alerte pe Telegram.")

# ---------------------------
# 2) Leaders (quotes live)
# ---------------------------
st.subheader("Leaders US30 & proxii")
q_err = None
try:
    data_leaders = fmp_quotes_many(LEADERS + COMMS)
    df = pd.DataFrame([{
        "symbol": x.get("symbol"),
        "price": x.get("price"),
        "change": x.get("change"),
        "chg_%": x.get("changesPercentage"),
        "prevClose": x.get("previousClose"),
        "dayLow": x.get("dayLow"),
        "dayHigh": x.get("dayHigh")
    } for x in data_leaders])

    # Ordonăm afișarea: leaders, apoi commodities
    order = LEADERS + COMMS
    df = df.set_index("symbol").loc[order].reset_index()

    st.dataframe(df, use_container_width=True)
except Exception as e:
    q_err = str(e)
    st.warning(f"Leaders quotes error: {q_err}")

# ---------------------------
# 3) News sentiment (rezumat)
# ---------------------------
st.subheader("News Sentiment (ultimele articole relevante)")
try:
    items = fmp_news(limit=40)
    scores = []
    for it in items:
        s = quick_sentiment_score((it.get("title","") + " " + it.get("text","")))
        scores.append((s, it.get("title",""), it.get("site","")))
    total = sum(s for s,_,_ in scores)
    bias = "BULLISH" if total > 0.8 else ("BEARISH" if total < -0.8 else "NEUTRAL")

    st.write(f"Bias curent: **{bias}**  |  Score agregat: **{total:+.2f}**")

    # Top 6 drivere (în ordinea scorului absolut)
    scores.sort(key=lambda z: abs(z[0]), reverse=True)
    for s, title, site in scores[:6]:
        st.markdown(f"- {s:+.2f} — **{title}**  _[{site}]_")

    st.caption("Alertele pe Telegram sunt trimise de job-ul cron **us30-news** când |score| ≥ pragul setat (ex. 1.5).")
except Exception as e:
    st.info(f"News sentiment indisponibil momentan: {e}")

# ---------------------------
# 4) Mini-calculator pips ↔ %
# ---------------------------
st.subheader("Mini-calculator volatilitate (pips ↔ %)")
with st.expander("Deschide calculator"):
    # Presupuneri pips (adaptabile):
    # US30 (indice) — 1 „pip” = 1 punct
    # Gold (GC=F)   — 1 „pip” = 0.1
    # Oil  (CL=F)   — 1 „pip” = 0.01
    colA, colB, colC = st.columns(3)
    with colA:
        st.markdown("**US30**")
        us30_price = st.number_input("Preț curent US30", value=float(df[df['symbol']=="YM=F"]["price"].iloc[0]) if 'df' in locals() and "YM=F" in df["symbol"].values else 35000.0, step=1.0)
        us30_pips  = st.number_input("Pips (puncte)", value=30.0, step=1.0)
        us30_pct   = (us30_pips / us30_price) * 100.0
        st.write(f"≈ **{us30_pct:.3f}%** pentru {us30_pips:.0f} pips")

    with colB:
        st.markdown("**Gold (GC=F)**")
        gold_price = st.number_input("Preț curent Gold", value=float(df[df['symbol']=="GC=F"]["price"].iloc[0]) if 'df' in locals() and "GC=F" in df["symbol"].values else 2400.0, step=0.1)
        gold_pips  = st.number_input("Pips (0.1)", value=30.0, step=0.1)
        gold_move  = gold_pips * 0.1
        gold_pct   = (gold_move / gold_price) * 100.0
        st.write(f"≈ **{gold_pct:.3f}%** pentru {gold_pips:.1f} pips (≈ {gold_move:.2f} $)")

    with colC:
        st.markdown("**Oil (CL=F)**")
        oil_price = st.number_input("Preț curent Oil", value=float(df[df['symbol']=="CL=F"]["price"].iloc[0]) if 'df' in locals() and "CL=F" in df["symbol"].values else 80.0, step=0.01)
        oil_pips  = st.number_input("Pips (0.01)", value=30.0, step=0.01)
        oil_move  = oil_pips * 0.01
        oil_pct   = (oil_move / oil_price) * 100.0
        st.write(f"≈ **{oil_pct:.3f}%** pentru {oil_pips:.2f} pips (≈ {oil_move:.3f} $)")

st.divider()
st.caption("UI rulează în Render (Streamlit). Job-urile cron *watchdog_intraday* și *news_sentiment* trimit alerte instant pe Telegram.")

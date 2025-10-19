import streamlit as st
import pandas as pd
import requests
import os
import re
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# ==============================
# CONFIG & CONSTANTS
# ==============================

FMP_KEY = os.getenv("FMP_API_KEY", "")
SYMBOLS = {
    "US30": "YM=F",    # Dow futures
    "GOLD": "GC=F",    # Gold futures
    "OIL":  "CL=F",    # WTI crude oil
}

KW = {
    "fed": ["fed", "powell", "fomc", "rate hike", "rate cut", "dot plot", "qe", "qt", "balance sheet"],
    "mgmt": ["ceo resign", "ceo steps down", "cfo resign", "appointed ceo", "management change", "board change"],
    "ma": ["merger", "acquisition", "takeover", "spin-off", "antitrust", "ftc", "doj", "regulatory probe"],
    "guidance": ["guidance cut", "guidance raised", "miss", "beat", "downgrade", "upgrade", "buyback", "dividend cut"],
    "geopol": ["escalation", "attack", "sanction", "ceasefire", "strait", "red sea", "hormuz", "missile"],
    "gold": ["safe haven", "flight to safety", "real yields", "inflation hedge"],
    "oil":  ["opec", "opec+", "production cut", "inventory draw", "inventory build", "refinery", "pipeline"],
    "usd":  ["dxy", "dollar index", "usd jumps", "usd falls", "treasury yield", "real yields"]
}

# ==============================
# HELPER FUNCTIONS
# ==============================

def get_last_price(sym: str) -> float:
    """Fetch last price from FMP"""
    url = f"https://financialmodelingprep.com/api/v3/quote/{sym}?apikey={FMP_KEY}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            return float(data[0].get("price") or data[0].get("previousClose") or 0.0)
    except Exception:
        pass
    return 0.0

def count_hits(text: str, words: list[str]) -> int:
    t = text.lower()
    return sum(1 for w in words if w in t)

def quick_extractive_bullets(text: str, max_bullets: int = 6) -> list[str]:
    sents = re.split(r'(?<=[\.\!\?])\s+', text.strip())
    scored = []
    KEYPOOL = set(sum(KW.values(), []))
    for s in sents:
        st = s.lower()
        hit = sum(1 for kw in KEYPOOL if kw in st)
        if 8 <= len(s.split()) <= 40:
            scored.append((hit, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:max_bullets]] or sents[:min(max_bullets, len(sents))]

def analyze_sentiment(text: str) -> float:
    an = SentimentIntensityAnalyzer()
    return an.polarity_scores(text).get("compound", 0.0)

def map_direction_and_instrument(text: str, sent: float) -> dict:
    t = text.lower()
    hits = {k: count_hits(t, v) for k, v in KW.items()}

    bias = {
        "US30":  1 if sent > 0.1 else (-1 if sent < -0.1 else 0),
        "GOLD": -1 if sent > 0.1 else ( 1 if sent < -0.1 else 0),
        "OIL":   1 if sent > 0.1 else (-1 if sent < -0.1 else 0),
    }

    if hits["fed"] or hits["usd"]:
        if any(w in t for w in ["hike", "qt", "hawk", "usd jumps", "yields"]):
            bias["US30"] = -1
            bias["GOLD"] = -1
        if any(w in t for w in ["cut", "qe", "usd falls", "dovish"]):
            bias["US30"] = +1
            bias["GOLD"] = +1
    if hits["geopol"]:
        bias["GOLD"] = +1
        bias["OIL"]  = +1
        bias["US30"] = -1
    if hits["oil"]:
        bias["OIL"] = +1
    if hits["gold"]:
        bias["GOLD"] = +1

    return {"bias": bias, "hits": hits}

def estimate_pips(text: str, sent: float, hits: dict) -> dict:
    base = 30
    strong = hits["fed"] + hits["ma"] + hits["mgmt"] + hits["geopol"]
    boost = min(1.0, abs(sent)) * 60 + min(60, strong * 20)
    est = int(min(165, base + boost))
    return {"US30": est, "GOLD": est, "OIL": est}

def derive_tp_levels(symbol: str, direction: int, est_pips: int) -> tuple[str, str]:
    last = get_last_price(SYMBOLS[symbol])
    if last <= 0:
        return ("n/a", "n/a")
    if symbol == "GOLD":
        tp1 = last + (direction * (est_pips * 0.1 * 0.5))
        tp2 = last + (direction * (est_pips * 0.1))
        return (f"{tp1:.1f}", f"{tp2:.1f}")
    if symbol == "OIL":
        tp1 = last + (direction * (est_pips * 0.01 * 0.5))
        tp2 = last + (direction * (est_pips * 0.01))
        return (f"{tp1:.2f}", f"{tp2:.2f}")
    tp1 = last + (direction * (est_pips * 0.5))
    tp2 = last + (direction * est_pips)
    return (f"{tp1:.0f}", f"{tp2:.0f}")

# ==============================
# PAGE FUNCTIONS
# ==============================

def page_dashboard():
    st.title("EA Alert Dashboard")
    st.write("🧠 Sistem de analiză pentru US30, Gold și Oil.")
    st.write("Verifică știrile, sentimentul și semnalele generate de IA.")

def page_rezumat_ai():
    st.title("Rezumat AI (știri + estimări pips)")
    st.markdown("Lipește textul din emailuri sau știri. Sistemul extrage esența, estimează direcția și propune TP-uri.")

    txt = st.text_area("Text de analizat", height=300, placeholder="Lipește aici textul...")
    min_move = st.number_input("Prag minim (pips)", 10, 200, 30, 5)
    if st.button("Analizează"):
        if not txt.strip():
            st.warning("Lipește un text pentru analiză.")
            return

        bullets = quick_extractive_bullets(txt, 6)
        sent = analyze_sentiment(txt)
        res = map_direction_and_instrument(txt, sent)
        est = estimate_pips(txt, sent, res["hits"])

        st.subheader("🧩 Esență din text")
        for b in bullets:
            st.markdown(f"- {b}")

        st.subheader("📊 Analiză de sentiment")
        st.write(f"**Scor sentiment:** {sent:+.2f}")

        rows = []
        for inst in ["US30", "GOLD", "OIL"]:
            d = res["bias"][inst]
            dir_lbl = "NEUTRAL" if d == 0 else ("LONG" if d > 0 else "SHORT")
            est_p = max(min_move, est[inst])
            tp1, tp2 = derive_tp_levels(inst, d if d != 0 else 1, est_p)
            rows.append({
                "Instrument": inst,
                "Direcție": dir_lbl,
                "Estimare (pips)": est_p,
                "TP1": tp1,
                "TP2": tp2
            })
        st.subheader("📈 Predicție (pips) + TP propus")
        st.table(pd.DataFrame(rows))
        st.info("Direcția derivată din sentiment + cuvinte-cheie (FED, CEO, M&A, geopolitic).")

# ==============================
# MAIN ROUTER
# ==============================

st.sidebar.title("Meniu")
page = st.sidebar.selectbox("Alege pagina:", ["Dashboard", "Rezumat AI"])

if page == "Dashboard":
    page_dashboard()
elif page == "Rezumat AI":
    page_rezumat_ai()

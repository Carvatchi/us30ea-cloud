import streamlit as st
import time
import os, re, time, json, requests
import pandas as pd
from datetime import datetime, timezone
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

FMP_KEY = os.getenv("FMP_API_KEY", "")

# Instrumente și feed simboluri FMP/Yahoo (quote endpoint)
SYMBOLS = {
    "US30": "YM=F",    # Dow futures
    "GOLD": "GC=F",    # Gold futures
    "OIL":  "CL=F",    # WTI futures
}

# Liste scurte de cuvinte-cheie, per categorie (expandăm ulterior)
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

def get_last_price(sym: str) -> float:
    """Quote simplu via FMP; fallback la Yahoo dacă vrei extindere."""
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
    c = 0
    for w in words:
        if w in t:
            c += 1
    return c

def quick_extractive_bullets(text: str, max_bullets: int = 6) -> list[str]:
    """Extrage 5-6 fraze relevante bazat pe cuvinte-cheie (simplu, rapid)."""
    # Split aproximativ pe propoziții
    sents = re.split(r'(?<=[\.\!\?])\s+', text.strip())
    # Scor per propoziție: câte cuvinte-cheie apar + lungime rezonabilă
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
    """Sentiment compound [-1..1] via VADER (neutral around 0)."""
    an = SentimentIntensityAnalyzer()
    return an.polarity_scores(text).get("compound", 0.0)

def map_direction_and_instrument(text: str, sent: float) -> dict:
    """
    Heuristică clară:
    - Negativ macro (hawkish FED, USD up, geopolitic) => US30↓, GOLD↑ (de obicei), OIL ? (dependență geopol/OPEC).
    - Pozitiv macro (dovish FED, USD down, risk-on) => US30↑, GOLD↓ (de obicei), OIL↑ (dacă cererea/riscul sus).
    - Chei sectoriale întăresc GOLD/OIL.
    """
    t = text.lower()
    hits = {
        "fed": count_hits(t, KW["fed"]),
        "mgmt": count_hits(t, KW["mgmt"]),
        "ma": count_hits(t, KW["ma"]),
        "guidance": count_hits(t, KW["guidance"]),
        "geopol": count_hits(t, KW["geopol"]),
        "gold": count_hits(t, KW["gold"]),
        "oil":  count_hits(t, KW["oil"]),
        "usd":  count_hits(t, KW["usd"]),
    }

    # Bias de bază din sentiment general:
    bias = {
        "US30":  1 if sent > 0.1 else (-1 if sent < -0.1 else 0),
        "GOLD": -1 if sent > 0.1 else ( 1 if sent < -0.1 else 0),  # risk-on → gold down, risk-off → gold up
        "OIL":   1 if sent > 0.1 else (-1 if sent < -0.1 else 0),
    }

    # Ajustări pe categorii
    if hits["fed"] or hits["usd"]:
        # USD up / hawkish FED: US30↓, GOLD↓ (rendamente reale ↑), OIL variabil
        if ("hike" in t or "qt" in t or "hawk" in t or "usd jumps" in t or "yields" in t):
            bias["US30"] = -1
            bias["GOLD"] = -1
        # USD down / dovish
        if ("cut" in t or "qe" in t or "usd falls" in t or "dovish" in t):
            bias["US30"] = +1
            bias["GOLD"] = +1  # (poate urca dacă USD scade / real yields scad)
    if hits["geopol"]:
        # Geopolitic tension → GOLD↑, OIL↑ frecvent; US30↓
        bias["GOLD"] = +1
        bias["OIL"]  = +1
        bias["US30"] = -1
    if hits["oil"] > 0:
        bias["OIL"] = +1
    if hits["gold"] > 0:
        bias["GOLD"] = +1

    return {"bias": bias, "hits": hits}

def estimate_pips(text: str, sent: float, hits: dict) -> dict:
    """
    Estimează amplitudinea a.i. să pornească de la 30 pips și să ajungă până la ~165 pips.
    Combinație: |sentiment| + categorie (fed/mgmt/ma/geopol) + context simpificat.
    """
    base = 30  # minim cerut
    strong = (hits["fed"] + hits["ma"] + hits["mgmt"] + hits["geopol"])  # evenimente grele
    boost = min(1.0, abs(sent)) * 60 + min(60, strong * 20)  # 0..~120
    # tăiem la 165 pips
    est = int(min(165, base + boost))
    # aceeași estimare pentru toate 3 instrumente ca “ordine de mărime”, adaptăm TP per preț
    return {"US30": est, "GOLD": est, "OIL": est}

def derive_tp_levels(symbol: str, direction: int, est_pips: int) -> tuple[str, str]:
    """
    Propune TP1/TP2 plecând de la prețul curent (fără nivele structurale).
    TP1 = ~0.5 * est, TP2 = est; returnează prețuri rotunjite.
    """
    last = get_last_price(SYMBOLS[symbol])
    if last <= 0:
        return ("n/a", "n/a")
    step = est_pips  # interpretăm “pips” ca unități de preț: US30=1, GOLD≈0.1, OIL≈0.01 (simplificăm)
    if symbol == "GOLD":
        tp1 = last + (direction * (est_pips * 0.1 * 0.5))
        tp2 = last + (direction * (est_pips * 0.1))
        return (f"{tp1:.1f}", f"{tp2:.1f}")
    if symbol == "OIL":
        tp1 = last + (direction * (est_pips * 0.01 * 0.5))
        tp2 = last + (direction * (est_pips * 0.01))
        return (f"{tp1:.2f}", f"{tp2:.2f}")
    # US30
    tp1 = last + (direction * (est_pips * 0.5))
    tp2 = last + (direction * est_pips)
    return (f"{tp1:.0f}", f"{tp2:.0f}")

st.set_page_config(page_title="US30/GOLD — EA Alert (Cloud)", layout="wide")
st.title("US30 / GOLD — EA Alert (Cloud MVP)")
st.info("✅ UI online. Urmează să adăugăm job-urile (watchdog & news) și baza de date.")

with st.expander("Status sistem"):
    st.write({
        "ui": "running",
        "jobs": "to be added",
        "db": "phase B"
    })

st.success("Dacă vezi această pagină pe Render după deploy, suntem OK.")

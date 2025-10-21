# app/ui/app.py — UI doar pentru US30
import os
import time
import requests
import streamlit as st
import pandas as pd

FMP_KEY = os.getenv("FMP_API_KEY", "")
SYMBOL = "^DJI"

st.set_page_config(page_title="US30 — EA Alert (Cloud)", layout="wide")
st.title("US30 — EA Alert (Cloud)")

@st.cache_data(ttl=30)
def get_quote(sym):
    url = f"https://financialmodelingprep.com/api/v3/quote/{sym}?apikey={FMP_KEY}"
    r = requests.get(url, timeout=10); r.raise_for_status()
    j = r.json()
    return j[0] if j else None

col1, col2 = st.columns(2)
with col1:
    st.subheader("Realtime quote")
    d = get_quote(SYMBOL)
    if d:
        st.metric("US30 price", f"{d['price']:.2f}", f"{d['changesPercentage']:+.2f}%")
    else:
        st.warning("No data")

with col2:
    st.subheader("Raw JSON")
    st.code(d, language="json")

st.divider()
st.caption("Refresh auto la 30s")
time.sleep(0.1)

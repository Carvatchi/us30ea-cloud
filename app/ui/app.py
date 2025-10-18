import streamlit as st
import time

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

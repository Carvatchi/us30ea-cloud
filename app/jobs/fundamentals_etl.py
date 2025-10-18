import os, json, math, time
from pathlib import Path
from datetime import datetime, timezone
import requests

FMP_KEY = os.getenv("FMP_API_KEY", "").strip()

TICKERS = ["MSFT", "UNH", "GS", "HD", "JPM"]

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = DATA_DIR / "fundamentals.json"

SESSION = requests.Session()
BASE = "https://financialmodelingprep.com/api/v3"

def fmp(path: str, **params):
    params = dict(params)
    params["apikey"] = FMP_KEY
    url = f"{BASE}/{path}"
    for _ in range(3):
        r = SESSION.get(url, params=params, timeout=20)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                pass
        time.sleep(1.0)
    return None

def safe(v):
    try:
        if v is None: return None
        return float(v)
    except Exception:
        return None

def nz(v, d=0.0): return d if v is None or (isinstance(v, float) and math.isnan(v)) else v
def clamp01(x): return 0.0 if x < 0 else 1.0 if x > 1 else x

def normalize_ratio(x, good, bad):
    if x is None: return 0.5
    if x <= bad: return 0.0
    if x >= good: return 1.0
    return (x - bad) / (good - bad)

def get_quarter(tkr):
    inc = fmp(f"income-statement/{tkr}", period="quarter", limit=2) or []
    bal = fmp(f"balance-sheet-statement/{tkr}", period="quarter", limit=1) or []
    cfs = fmp(f"cash-flow-statement/{tkr}", period="quarter", limit=2) or []
    quote = fmp(f"quote/{tkr}") or []
    if not inc or not bal or not cfs or not quote: return None

    cur_inc = inc[0]; prev_inc = inc[1] if len(inc) > 1 else {}
    cur_bal = bal[0]; cur_cfs = cfs[0]; prev_cfs = cfs[1] if len(cfs) > 1 else {}
    q0 = quote[0]

    revenue = safe(cur_inc.get("revenue")); revenue_prev = safe(prev_inc.get("revenue"))
    net = safe(cur_inc.get("netIncome"))
    equity = safe(cur_bal.get("totalStockholdersEquity"))
    total_debt = safe(cur_bal.get("totalDebt"))
    eps = safe(cur_inc.get("epsdiluted")); eps_prev = safe(prev_inc.get("epsdiluted"))
    fcf = safe(cur_cfs.get("freeCashFlow")); fcf_prev = safe(prev_cfs.get("freeCashFlow"))
    pe = safe(q0.get("pe")); price = safe(q0.get("price"))

    margin = None if revenue in (None, 0) else nz(net,0)/revenue
    roe = None if equity in (None,0) else nz(net,0)/equity

    rev_growth = None
    if revenue and revenue_prev and revenue_prev != 0:
        rev_growth = (revenue - revenue_prev)/abs(revenue_prev)

    eps_growth = None
    if eps is not None and eps_prev not in (None,0):
        eps_growth = (eps - eps_prev)/abs(eps_prev)

    de = None if equity in (None,0) else nz(total_debt,0)/equity

    fcf_growth = None
    if fcf is not None and fcf_prev not in (None,0):
        fcf_growth = (fcf - fcf_prev)/abs(fcf_prev)

    fcf_margin = None if revenue in (None,0) else nz(fcf,0)/revenue

    s_margin = normalize_ratio(nz(margin,0.0), good=0.25, bad=0.0)
    s_roe    = normalize_ratio(nz(roe,0.0),    good=0.25, bad=0.05)
    s_rev    = normalize_ratio(nz(rev_growth,0.0), good=0.10, bad=-0.10)
    s_eps    = normalize_ratio(nz(eps_growth,0.0), good=0.10, bad=-0.10)
    s_fcf    = normalize_ratio(nz(fcf_growth,0.0), good=0.15, bad=-0.10)
    s_fcfm   = normalize_ratio(nz(fcf_margin,0.0), good=0.15, bad=0.0)

    if de is None: s_de = 0.5
    elif de <= 0.5: s_de = 1.0
    elif de >= 2.0: s_de = 0.0
    else: s_de = clamp01((2.0 - de)/(2.0 - 0.5))

    if pe is None or pe <= 0: s_pe = 0.5
    elif pe <= 20: s_pe = 1.0
    elif pe >= 40: s_pe = 0.0
    else: s_pe = clamp01((40 - pe)/(40 - 20))

    score = (
        0.18*s_margin + 0.18*s_roe + 0.12*s_rev + 0.12*s_eps +
        0.12*s_fcf + 0.08*s_fcfm + 0.12*s_de + 0.08*s_pe
    ) * 100.0

    return {
        "ticker": tkr,
        "asof": cur_inc.get("date"),
        "price": price, "pe": pe,
        "margin": margin, "roe": roe,
        "rev_growth": rev_growth, "eps_growth": eps_growth,
        "debt_to_equity": de,
        "fcf": fcf, "fcf_growth": fcf_growth, "fcf_margin": fcf_margin,
        "score": round(score, 1)
    }

def main():
    out = {"updated": datetime.now(timezone.utc).isoformat(), "items": {}}
    for t in TICKERS:
        try:
            row = get_quarter(t)
            out["items"][t] = row if row else {"ticker": t, "error": "no_data"}
        except Exception as e:
            out["items"][t] = {"ticker": t, "error": str(e)}

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("SAVED:", OUT_PATH)

if __name__ == "__main__":
    main()

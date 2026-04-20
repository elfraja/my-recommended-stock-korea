import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import difflib
import google.generativeai as genai

# =====================
# 1. 앱 설정
# =====================
st.set_page_config(page_title="K-증시 AI 하이브리드 비서", layout="wide")
st.title("⚖️ K-증시 실전 매매 비서 with Gemini AI")

# --- Gemini API Key ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# =====================
# 2. 섹터 정의
# =====================
k_sectors = {
    "반도체": {"etf": "091160", "stocks": ["005930", "000660", "042700"]},
    "2차전지소재": {"etf": "373550", "stocks": ["247540", "391060", "003670"]},
    "2차전지셀": {"etf": "373550", "stocks": ["373220", "006400", "051910"]},
    "전력설비(변압기)": {"etf": "421320", "stocks": ["000880", "050710", "011760"]},
    "방위산업": {"etf": "381170", "stocks": ["012450", "047810", "272210"]},
    "조선/해운": {"etf": "445380", "stocks": ["010140", "042660", "010620"]},
    "바이오/의료": {"etf": "091150", "stocks": ["207940", "068270", "293480"]},
    "로봇": {"etf": "440760", "stocks": ["433320", "043340", "441270"]},
    "K-뷰티": {"etf": "228790", "stocks": ["192820", "019170", "131970"]},
    "자동차": {"etf": "091140", "stocks": ["005380", "000270", "012330"]},
}

# =====================
# 3. 유틸 함수
# =====================
@st.cache_data(ttl=3600)
def get_krx_names():
    df = fdr.StockListing("KRX")
    return dict(zip(df["Code"], df["Name"]))

def normalize_string(s):
    if not s:
        return ""
    return str(s).lower().replace(" ", "")

def smart_search_stock(query, names_dict):
    if query.isdigit() and query in names_dict:
        return query
    norm_query = normalize_string(query)
    norm_map = {code: normalize_string(name) for code, name in names_dict.items()}
    matches = difflib.get_close_matches(norm_query, norm_map.values(), n=1, cutoff=0.6)
    for code, norm in norm_map.items():
        if matches and norm == matches[0]:
            return code
    return None

# =====================
# 4. 지표 계산
# =====================
def calc_short_term_factors(df):
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    delta = df["Close"].diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df["RSI"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    df["STD20"] = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["MA20"] + df["STD20"] * 2
    df["Vol_Ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()

    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    return df.dropna()

def calc_mid_term_factors(df):
    df["MA60"] = df["Close"].rolling(60).mean()
    df["MA120"] = df["Close"].rolling(120).mean()
    df["High_6M"] = df["Close"].rolling(120).max()
    return df.dropna()

# =====================
# 5. 섹터 결론 생성
# =====================
def make_sector_conclusion(mode, score):
    if mode == "short":
        if score >= 70:
            return "🔥 단기 수급·돌파 동반, 집중 공략 구간"
        elif score >= 55:
            return "🟢 상승 추세 유지, 눌림목 대응"
        else:
            return "⚪ 모멘텀 약화, 관망 우위"
    else:
        if score >= 70:
            return "⭐ 실적선 위 안정적 상승, 중기 최우선"
        elif score >= 50:
            return "🌱 조정 국면, 분할 대응"
        else:
            return "⚠️ 추세 훼손, 비중 축소"

# =====================
# 6. 분석 엔진
# =====================
@st.cache_data(ttl=3600)
def run_analysis(mode):
    names = get_krx_names()
    results = []

    days = 120 if mode == "short" else 260
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    for sector, info in k_sectors.items():
        try:
            etf = fdr.DataReader(info["etf"], start)
            perf_5d = (etf["Close"].iloc[-1] / etf["Close"].iloc[-5] - 1) * 100

            stocks = []
            for code in info["stocks"]:
                df = fdr.DataReader(code, start)
                if len(df) < 130:
                    continue

                if mode == "short":
                    df = calc_short_term_factors(df)
                    last = df.iloc[-1]

                    score = 0
                    if last["MA5"] > last["MA20"] > last["MA60"]:
                        score += 20
                    if 50 <= last["RSI"] <= 70:
                        score += 20
                    if last["Vol_Ratio"] > 1.5:
                        score += 20
                    if last["MACD"] > last["Signal"]:
                        score += 20
                    if last["Close"] > last["BB_Upper"]:
                        score += 20

                    score = min(score, 80)

                    stocks.append({
                        "name": names.get(code, code),
                        "score": score,
                        "current": last["Close"],
                        "buy": last["MA20"],
                        "target": last["BB_Upper"],
                        "stop": last["MA60"],
                        "desc": "단기 모멘텀 종목"
                    })

                else:
                    df = calc_mid_term_factors(df)
                    last = df.iloc[-1]

                    score = 0
                    if last["Close"] > last["MA60"]:
                        score += 40
                    if last["MA60"] > last["MA120"]:
                        score += 30

                    drawdown = (last["Close"] / last["High_6M"] - 1) * 100
                    if drawdown < -15:
                        score += 30

                    stocks.append({
                        "name": names.get(code, code),
                        "score": score,
                        "current": last["Close"],
                        "buy": last["MA60"],
                        "target": last["High_6M"],
                        "stop": last["MA120"] * 0.95,
                        "extra": drawdown,
                        "desc": "중기 추세 종목"
                    })

            if stocks:
                sector_score = (
                    sum(s["score"] for s in stocks) / len(stocks) * 0.6
                    + perf_5d * 0.4
                )
                results.append({
                    "섹터명": sector,
                    "score": sector_score,
                    "stocks": stocks
                })
        except:
            continue

    return pd.DataFrame(results)

# =====================
# 7. 화면 구성
# =====================
tab1, tab2 = st.tabs(["⚡ 단기 스윙", "🌳 중기 추세"])

# -------- 단기 --------
with tab1:
    df = run_analysis("short")
    top7 = df.sort_values("score", ascending=False).head(7)

    cols = st.columns(3)
    for i in range(3):
        row = top7.iloc[i]
        with cols[i]:
            st.info(f"### {i+1}위 {row['섹터명']}")
            st.caption(make_sector_conclusion("short", row["score"]))
            for s in sorted(row["stocks"], key=lambda x: x["score"], reverse=True):
                with st.expander(s["name"]):
                    st.write(f"현재가 {int(s['current']):,}원")
                    st.write(f"매수 {int(s['buy']):,} / 목표 {int(s['target']):,}")

# -------- 중기 --------
with tab2:
    df = run_analysis("mid")
    top7 = df.sort_values("score", ascending=False).head(7)

    cols = st.columns(3)
    for i in range(3):
        row = top7.iloc[i]
        with cols[i]:
            st.success(f"### {i+1}위 {row['섹터명']}")
            st.caption(make_sector_conclusion("mid", row["score"]))
            for s in sorted(row["stocks"], key=lambda x: x["score"], reverse=True):
                with st.expander(s["name"]):
                    st.write(f"현재가 {int(s['current']):,}원")
                    st.write(f"고점대비 {s['extra']:.1f}%")
``

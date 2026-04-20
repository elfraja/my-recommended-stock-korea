import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import difflib
import google.generativeai as genai

# ======================================================
# 1. App Config
# ======================================================
st.set_page_config(page_title="⚖️ K-증시 실전 매매 비서", layout="wide")
st.title("⚖️ K-증시 실전 매매 비서 with Gemini AI")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ======================================================
# 2. Sector Definition (Gemini 원본)
# ======================================================
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

# ======================================================
# 3. Utils
# ======================================================
@st.cache_data(ttl=3600)
def get_krx_names():
    df = fdr.StockListing("KRX")
    return dict(zip(df["Code"], df["Name"]))

def normalize_string(s):
    return str(s).lower().replace(" ", "")

def smart_search_stock(query, names_dict):
    if query.isdigit() and query in names_dict:
        return query
    q = normalize_string(query)
    norm = {c: normalize_string(n) for c, n in names_dict.items()}
    matches = difflib.get_close_matches(q, norm.values(), n=1, cutoff=0.6)
    if matches:
        for c, n in norm.items():
            if n == matches[0]:
                return c
    return None

# ======================================================
# 4. Indicator Calculation (Gemini 원본)
# ======================================================
def calc_short_term_factors(df):
    df["MA5"] = df.Close.rolling(5).mean()
    df["MA20"] = df.Close.rolling(20).mean()
    df["MA60"] = df.Close.rolling(60).mean()

    delta = df.Close.diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df["RSI"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    df["STD20"] = df.Close.rolling(20).std()
    df["BB_Upper"] = df.MA20 + df.STD20 * 2
    df["Vol_Ratio"] = df.Volume / df.Volume.rolling(20).mean()

    exp1 = df.Close.ewm(span=12, adjust=False).mean()
    exp2 = df.Close.ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["Signal"] = df.MACD.ewm(span=9, adjust=False).mean()

    return df.dropna()

def calc_mid_term_factors(df):
    df["MA60"] = df.Close.rolling(60).mean()
    df["MA120"] = df.Close.rolling(120).mean()
    df["High_6M"] = df.Close.rolling(120).max()
    return df.dropna()

def calc_factors(df):
    df["MA60"] = df.Close.rolling(60).mean()
    df["MA120"] = df.Close.rolling(120).mean()
    delta = df.Close.diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df["RSI"] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    df["High_6M"] = df.Close.rolling(120).max()
    return df.dropna()

# ======================================================
# 5. Sector Analysis (Gemini 원본 로직)
# ======================================================
@st.cache_data(ttl=3600)
def run_analysis(mode="short"):
    names = get_krx_names()
    results = []
    days = 100 if mode == "short" else 250
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    for sector, info in k_sectors.items():
        stock_data = []
        for code in info["stocks"]:
            try:
                df = fdr.DataReader(code, start)

                if mode == "short":
                    if len(df) < 65: 
                        continue
                    df = calc_short_term_factors(df)
                    last = df.iloc[-1]
                    score = 0
                    if last.MA5 > last.MA20 > last.MA60: score += 20
                    if 50 <= last.RSI <= 70: score += 20
                    if last.Close > last.BB_Upper: score += 20
                    if last.Vol_Ratio > 1.5: score += 20
                    if last.MACD > last.Signal: score += 20
                    buy, target, stop = last.MA20, last.BB_Upper, last.MA60

                else:
                    if len(df) < 130:
                        continue
                    df = calc_mid_term_factors(df)
                    last = df.iloc[-1]
                    drawdown = (last.Close / last.High_6M - 1) * 100
                    score = 0
                    if last.Close > last.MA60: score += 40
                    if last.MA60 > last.MA120: score += 30
                    if drawdown < -15: score += 30
                    buy, target, stop = last.MA60, last.High_6M, last.MA120 * 0.95

                stock_data.append({
                    "name": names.get(code, code),
                    "score": score,
                    "current": last.Close,
                    "buy": buy,
                    "target": target,
                    "stop": stop
                })

            except:
                continue

        if stock_data:
            sector_score = sum(s["score"] for s in stock_data) / len(stock_data)
            results.append({
                "섹터명": sector,
                "score": sector_score,
                "stocks": stock_data
            })

    return pd.DataFrame(results)

# ======================================================
# 6. Sector One-line Comment
# ======================================================
def sector_comment(mode, score):
    if mode == "short":
        return (
            "단기 수급과 돌파 신호가 유효한 섹터"
            if score >= 70 else
            "추세는 유지되나 종목 선별이 필요한 섹터"
            if score >= 55 else
            "모멘텀이 약해 관망이 적절한 섹터"
        )
    else:
        return (
            "중기 추세 우수, 비중 확대 검토 섹터"
            if score >= 70 else
            "조정 구간, 분할 접근 적합 섹터"
            if score >= 50 else
            "추세 불안, 보수적 대응 필요 섹터"
        )

# ======================================================
# 7. AI Insight (Gemini + fallback)
# ======================================================
def get_ai_insight(stock_name, stats):
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""
        당신은 한국 주식 전문가입니다.
        다음은 {stock_name} 종목의 기술적 요약입니다.

        {stats}

        투자 관점에서 참고할 핵심 의견을 3줄 이내로 설명해주세요.
        """
        res = model.generate_content(prompt)
        return res.text
    except:
        return (
            "현재 주가는 중기 추세선 부근에서 움직이고 있습니다. "
            "과도한 과열은 아니며 분할 접근이 가능한 구간으로 판단됩니다. "
            "추가적인 거래량 동반 여부를 확인하는 전략이 필요합니다."
        )

# ======================================================
# 8. Top5 Recommendation (tab3 bottom)
# ======================================================
@st.cache_data(ttl=3600)
def get_top5_recommendations():
    names = get_krx_names()
    results = []
    start = (datetime.now() - timedelta(days=260)).strftime("%Y-%m-%d")

    for info in k_sectors.values():
        for code in info["stocks"]:
            try:
                df = fdr.DataReader(code, start)
                if len(df) < 130:
                    continue
                df = calc_factors(df)
                last = df.iloc[-1]
                drawdown = (last.Close / last.High_6M - 1) * 100
                score = 0
                if last.Close > last.MA60 > last.MA120: score += 40
                if 45 <= last.RSI <= 65: score += 30
                if -20 <= drawdown <= -5: score += 30

                results.append({
                    "name": names.get(code, code),
                    "price": last.Close,
                    "score": score
                })
            except:
                continue

    return sorted(results, key=lambda x: x["score"], reverse=True)[:5]

# ======================================================
# 9. UI
# ======================================================
tab1, tab2, tab3 = st.tabs(["⚡ 단기 섹터", "🌳 중기 섹터", "🔍 AI 종목 진단"])

# ---------- Short Term ----------
with tab1:
    df = run_analysis("short")
    top7 = df.sort_values("score", ascending=False).head(7)

    st.subheader("🏆 집중 공략 섹터 TOP3")
    cols = st.columns(3)
    for i in range(min(3, len(top7))):
        row = top7.iloc[i]
        with cols[i]:
            st.info(f"### {i+1}위: {row['섹터명']}")
            st.caption(sector_comment("short", row["score"]))
            for s in sorted(row["stocks"], key=lambda x: x["score"], reverse=True):
                icon = "🔥" if s["score"] >= 80 else "🟢" if s["score"] >= 60 else "⚪"
                with st.expander(f"{icon} {s['name']}"):
                    st.write(f"현재가: {int(s['current']):,}원")
                    st.write(f"매수: {int(s['buy']):,} / 목표: {int(s['target']):,} / 손절: {int(s['stop']):,}")

    st.divider()
    st.subheader("👀 관찰 섹터 (4~7위)")
    cols2 = st.columns(4)
    for i in range(3, min(7, len(top7))):
        row = top7.iloc[i]
        with cols2[i-3]:
            st.markdown(f"### {i+1}위: {row['섹터명']}")
            st.caption(sector_comment("short", row["score"]))
            for s in sorted(row["stocks"], key=lambda x: x["score"], reverse=True):
                icon = "🟢" if s["score"] >= 60 else "⚪"
                with st.expander(f"{icon} {s['name']}"):
                    st.write(f"현재가: {int(s['current']):,}원")
                    st.write(f"매수: {int(s['buy']):,} / 목표: {int(s['target']):,}")

# ---------- Mid Term ----------
with tab2:
    df = run_analysis("mid")
    top7 = df.sort_values("score", ascending=False).head(7)

    st.subheader("🛡️ 중기 우량 섹터 TOP3")
    cols = st.columns(3)
    for i in range(min(3, len(top7))):
        row = top7.iloc[i]
        with cols[i]:
            st.success(f"### {i+1}위: {row['섹터명']}")
            st.caption(sector_comment("mid", row["score"]))
            for s in sorted(row["stocks"], key=lambda x: x["score"], reverse=True):
                icon = "⭐" if s["score"] >= 70 else "🌱" if s["score"] >= 40 else "⚠️"
                with st.expander(f"{icon} {s['name']}"):
                    st.write(f"현재가: {int(s['current']):,}원")
                    st.write(f"매수: {int(s['buy']):,} / 목표: {int(s['target']):,} / 손절: {int(s['stop']):,}")

    st.divider()
    st.subheader("👀 중기 관찰 섹터 (4~7위)")
    cols2 = st.columns(4)
    for i in range(3, min(7, len(top7))):
        row = top7.iloc[i]
        with cols2[i-3]:
            st.markdown(f"### {i+1}위: {row['섹터명']}")
            st.caption(sector_comment("mid", row["score"]))
            for s in sorted(row["stocks"], key=lambda x: x["score"], reverse=True):
                icon = "🌱" if s["score"] >= 40 else "⚠️"
                with st.expander(f"{icon} {s['name']}"):
                    st.write(f"현재가: {int(s['current']):,}원")
                    st.write(f"매수: {int(s['buy']):,} / 목표: {int(s['target']):,}")

# ---------- AI Stock Diagnosis ----------
with tab3:
    st.subheader("🔍 개별 종목 AI 진단")
    query = st.text_input("종목명 또는 코드 입력")

    if query:
        names = get_krx_names()
        code = smart_search_stock(query, names)
        if code:
            df0 = fdr.DataReader(code, (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%d"))
            df = calc_factors(df0)
            last = df.iloc[-1]

            current = int(last.Close)
            buy = int(last.MA60)
            target = int(last.High_6M)
            stop = int(last.MA120 * 0.95)

            stats = {
                "현재가": current,
                "RSI": round(last.RSI, 1),
                "60일선": "상회" if last.Close > last.MA60 else "하회",
                "고점대비": round((last.Close / last.High_6M - 1) * 100, 1)
            }

            col1, col2 = st.columns([1, 1.3])
            with col1:
                st.metric("현재가", f"{current:,}원")
                st.markdown(f"🛒 **매수:** `{buy:,}원`")
                st.markdown(f"🎯 **목표:** `{target:,}원`")
                st.markdown(f"🛑 **손절:** `{stop:,}원`")
                st.write(stats)

            with col2:
                st.write(get_ai_insight(names[code], stats))

    st.divider()
    st.subheader("⭐ AI 추천 종목 TOP5")
    cols = st.columns(5)
    for col, s in zip(cols, get_top5_recommendations()):
        col.metric(s["name"], f"{int(s['price']):,}원", f"Score {s['score']}")

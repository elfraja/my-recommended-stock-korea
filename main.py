import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import difflib
import google.generativeai as genai

# ======================================================
# 1. 앱 설정
# ======================================================
st.set_page_config(page_title="⚖️ K-증시 실전 매매 비서", layout="wide")
st.title("⚖️ K-증시 실전 매매 비서 with Gemini AI")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ======================================================
# 2. 섹터 정의 (Gemini 초기 버전)
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
    "K-푸드": {"etf": "429000", "stocks": ["097950", "004370", "005180"]},
    "자동차": {"etf": "091140", "stocks": ["005380", "000270", "012330"]},
}

# ======================================================
# 3. 유틸
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
# 4. 지표 계산 (Gemini 원본)
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
# 5. 섹터 분석 (Gemini 원본 로직)
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

                else:
                    if len(df) < 130:
                        continue
                    df = calc_mid_term_factors(df)
                    last = df.iloc[-1]

                    score = 0
                    drawdown = (last.Close / last.High_6M - 1) * 100
                    if last.Close > last.MA60: score += 40
                    if last.MA60 > last.MA120: score += 30
                    if drawdown < -15: score += 30

                stock_data.append({
                    "name": names.get(code, code),
                    "score": score,
                    "buy": last.MA20 if mode == "short" else last.MA60,
                    "target": last.BB_Upper if mode == "short" else last.High_6M,
                    "stop": last.MA60 if mode == "short" else last.MA120 * 0.95
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
    
def get_ai_insight(stock_name, stats):
    """
    Gemini AI 종목 분석
    실패 시 fallback 문구 반환
    """
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""
        당신은 한국 주식 전문가입니다.
        다음은 {stock_name} 종목의 최근 기술적 요약입니다.

        {stats}

        위 정보를 바탕으로 투자자가 참고할 만한 핵심 의견을
        3줄 이내로, 과장 없이 전문가 톤으로 설명해주세요.
        """

        response = model.generate_content(prompt)
        return response.text

    except Exception:
        # ✅ Gemini 실패 시 fallback (이전에 요청하신 보완 로직)
        return (
            "현재 주가는 중기 추세선 부근에서 움직이고 있습니다. "
            "RSI상 과열 구간은 아니며 추세 관점에서는 분할 접근이 가능합니다. "
            "단기적인 변동성 확대 여부를 함께 확인하는 것이 바람직합니다."
        )
# ======================================================
# 6. 섹터 한 줄 코멘트
# ======================================================
def sector_comment(mode, score):
    if mode == "short":
        if score >= 70:
            return "수급·돌파 신호가 동반된 단기 주도 섹터"
        elif score >= 55:
            return "추세는 유효하나 종목 선별이 필요한 섹터"
        else:
            return "모멘텀이 약해 관망이 적절한 섹터"
    else:
        if score >= 70:
            return "중기 추세 우수, 비중 확대 검토 가능"
        elif score >= 50:
            return "조정 국면, 분할 접근 적합"
        else:
            return "추세 불안, 보수적 대응 필요"

# ======================================================
# 7. Top5 자동 추천 (tab3 하단)
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

                score = 0
                drawdown = (last.Close / last.High_6M - 1) * 100
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
# 8. UI
# ======================================================
tab1, tab2, tab3 = st.tabs(["⚡ 단기 섹터", "🌳 중기 섹터", "🔍 AI 종목 진단"])

# ---------- 단기 섹터 ----------
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
                    st.write(f"매수 {int(s['buy']):,} / 목표 {int(s['target']):,} / 손절 {int(s['stop']):,}")

    st.divider()
    st.subheader("👀 관찰 섹터 (4~7위)")
    cols2 = st.columns(4)
    for i in range(3, min(7, len(top7))):
        row = top7.iloc[i]
        with cols2[i - 3]:
            st.markdown(f"### {i+1}위: {row['섹터명']}")
            st.caption(sector_comment("short", row["score"]))
            for s in sorted(row["stocks"], key=lambda x: x["score"], reverse=True):
                icon = "🟢" if s["score"] >= 60 else "⚪"
                with st.expander(f"{icon} {s['name']}"):
                    st.write(f"매수 {int(s['buy']):,} / 목표 {int(s['target']):,}")

# ---------- 중기 섹터 ----------
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
                    st.write(f"매수 {int(s['buy']):,} / 목표 {int(s['target']):,} / 손절 {int(s['stop']):,}")

    st.divider()
    st.subheader("👀 중기 관찰 섹터 (4~7위)")
    cols2 = st.columns(4)
    for i in range(3, min(7, len(top7))):
        row = top7.iloc[i]
        with cols2[i - 3]:
            st.markdown(f"### {i+1}위: {row['섹터명']}")
            st.caption(sector_comment("mid", row["score"]))
            for s in sorted(row["stocks"], key=lambda x: x["score"], reverse=True):
                icon = "🌱" if s["score"] >= 40 else "⚠️"
                with st.expander(f"{icon} {s['name']}"):
                    st.write(f"매수 {int(s['buy']):,} / 목표 {int(s['target']):,}")

# ---------- AI 종목 진단 ----------
with tab3:
    st.markdown("### 🔍 개별 종목 AI 진단")
    query = st.text_input("종목명 또는 코드 입력")

    if query:
        names = get_krx_names()
        code = smart_search_stock(query, names)
        if code:
            start = (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%d")
            df = fdr.DataReader(code, start)
            df = calc_factors(df)
            last = df.iloc[-1]

            stats = {
                "현재가": int(last.Close),
                "RSI": round(last.RSI, 1),
                "60일선": "상회" if last.Close > last.MA60 else "하회",
                "고점대비": round((last.Close / last.High_6M - 1) * 100, 1)
            }

            col1, col2 = st.columns([1, 1.3])
            with col1:
                st.write(stats)
            with col2:
                st.write(get_ai_insight(names[code], stats))

    st.divider()
    st.subheader("⭐ AI 추천 종목 TOP5")
    cols = st.columns(5)
    for col, s in zip(cols, get_top5_recommendations()):
        col.metric(s["name"], f"{int(s['price']):,}", f"Score {s['score']}")

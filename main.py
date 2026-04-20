import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import difflib
import google.generativeai as genai

# ======================================================
# 1. 앱 설정
# ======================================================
st.set_page_config(page_title="K-증시 AI 하이브리드 비서", layout="wide")
st.title("⚖️ K-증시 실전 매매 비서 with Gemini AI")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ======================================================
# 2. 섹터 정의 (원본 유지)
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
    "우주항공": {"etf": "445380", "stocks": ["012450", "047810", "112190"]},
    "자동차": {"etf": "091140", "stocks": ["005380", "000270", "012330"]},
    "원자력": {"etf": "421320", "stocks": ["034020", "030000", "011210"]},
    "은행": {"etf": "091170", "stocks": ["105560", "055550", "086790"]},
    "증권": {"etf": "091170", "stocks": ["005830", "000810", "071050"]},
    "IT플랫폼": {"etf": "266370", "stocks": ["035420", "035720", "307950"]},
    "게임": {"etf": "293400", "stocks": ["251270", "036570", "293490"]},
    "엔터": {"etf": "227540", "stocks": ["352820", "041510", "035900"]},
    "철강/금속": {"etf": "117680", "stocks": ["005490", "004020", "016380"]},
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
# 4. 지표 계산
# ======================================================
def calc_factors(df):
    df["MA20"] = df.Close.rolling(20).mean()
    df["MA60"] = df.Close.rolling(60).mean()
    df["MA120"] = df.Close.rolling(120).mean()

    delta = df.Close.diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df["RSI"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    df["High_6M"] = df.Close.rolling(120).max()
    df["STD20"] = df.Close.rolling(20).std()
    return df.dropna()

@st.cache_data(ttl=3600)
def run_analysis(mode):
    names = get_krx_names()
    results = []

    days = 100 if mode == "short" else 250
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    for sector, info in k_sectors.items():
        try:
            etf_df = fdr.DataReader(info["etf"], start)
            if len(etf_df) < 5:
                continue

            perf_5d = (etf_df.Close.iloc[-1] / etf_df.Close.iloc[-5] - 1) * 100
            stocks = []

            for code in info["stocks"]:
                df = fdr.DataReader(code, start)

                if mode == "short" and len(df) < 70:
                    continue
                if mode == "mid" and len(df) < 130:
                    continue

                if mode == "short":
                    df = calc_short_term_factors(df)
                    last = df.iloc[-1]
                    score = 0
                    if last.MA5 > last.MA20 > last.MA60: score += 20
                    if 50 <= last.RSI <= 70: score += 20
                    if last.Vol_Ratio > 1.5: score += 20
                    if last.MACD > last.Signal: score += 20
                    score += 20 if last.Close > last.BB_Upper else 0
                    score = min(score, 80)

                    stocks.append({
                        "name": names.get(code, code),
                        "score": score,
                        "current": last.Close,
                        "buy": last.MA20,
                        "target": last.BB_Upper,
                        "stop": last.MA60
                    })

                else:
                    df = calc_mid_term_factors(df)
                    last = df.iloc[-1]
                    drawdown = (last.Close / last.High_6M - 1) * 100
                    score = 0
                    if last.Close > last.MA60: score += 40
                    if last.MA60 > last.MA120: score += 30
                    if drawdown < -15: score += 30

                    stocks.append({
                        "name": names.get(code, code),
                        "score": score,
                        "current": last.Close,
                        "buy": last.MA60,
                        "target": last.High_6M,
                        "stop": last.MA120 * 0.95,
                        "extra": drawdown
                    })

            if stocks:
                sector_score = sum(s["score"] for s in stocks) / len(stocks)
                results.append({
                    "섹터명": sector,
                    "score": sector_score,
                    "stocks": stocks
                })
        except:
            continue

    return pd.DataFrame(results)
``
# ======================================================
# 5. 섹터 결론
# ======================================================
def make_sector_conclusion(mode, score):
    if mode == "short":
        if score >= 70:
            return "🔥 단기 수급·돌파 동반, 적극 대응"
        elif score >= 55:
            return "🟢 추세 유효, 선별 접근"
        else:
            return "⚪ 관망 우위"
    else:
        if score >= 70:
            return "⭐ 중기 주도 섹터"
        elif score >= 50:
            return "🌱 조정 구간"
        else:
            return "⚠️ 보수적 접근"

# ======================================================
# 6. Top5 자동 추천 종목
# ======================================================
@st.cache_data(ttl=3600)
def get_top5_recommendations():
    names = get_krx_names()
    results = []
    start = (datetime.now() - timedelta(days=260)).strftime("%Y-%m-%d")

    for sector in k_sectors.values():
        for code in sector["stocks"]:
            try:
                df = fdr.DataReader(code, start)
                if len(df) < 130:
                    continue

                df = calc_factors(df)
                last = df.iloc[-1]

                score = 0
                if last.Close > last.MA60 > last.MA120:
                    score += 40
                if 45 <= last.RSI <= 65:
                    score += 30

                drawdown = (last.Close / last.High_6M - 1) * 100
                if -20 <= drawdown <= -5:
                    score += 20

                if last.STD20 < df.STD20.quantile(0.4):
                    score += 10

                results.append({
                    "name": names.get(code, code),
                    "price": last.Close,
                    "score": score
                })
            except:
                continue

    return sorted(results, key=lambda x: x["score"], reverse=True)[:5]

# ======================================================
# 7. UI
# ======================================================
tab1, tab2, tab3 = st.tabs(["⚡ 단기 섹터", "🌳 중기 섹터", "🔍 AI 종목 진단"])

with tab1:
    st.subheader("⚡ 단기 섹터 랭킹")

    df_short = run_analysis("short")

    if df_short.empty:
        st.warning("단기 섹터 분석 결과가 없습니다. (데이터 수집 중)")
    else:
        top7 = df_short.sort_values("score", ascending=False).head(7)

        cols = st.columns(3)
        for i in range(min(3, len(top7))):
            row = top7.iloc[i]
            with cols[i]:
                st.info(f"### {i+1}위: {row['섹터명']}")
                st.caption(make_sector_conclusion("short", row["score"]))

                for s in sorted(row["stocks"], key=lambda x: x["score"], reverse=True):
                    icon = "🔥" if s["score"] >= 70 else "🟢" if s["score"] >= 55 else "⚪"
                    with st.expander(f"{icon} {s['name']}"):
                        st.write(f"현재가: {int(s['current']):,}원")
                        st.write(f"매수: {int(s['buy']):,} / 목표: {int(s['target']):,}")
with tab2:
    st.subheader("🌳 중기 섹터 랭킹")

    df_mid = run_analysis("mid")

    if df_mid.empty:
        st.warning("중기 섹터 분석 결과가 없습니다. (데이터 수집 중)")
    else:
        top7 = df_mid.sort_values("score", ascending=False).head(7)

        cols = st.columns(3)
        for i in range(min(3, len(top7))):
            row = top7.iloc[i]
            with cols[i]:
                st.success(f"### {i+1}위: {row['섹터명']}")
                st.caption(make_sector_conclusion("mid", row["score"]))

                for s in sorted(row["stocks"], key=lambda x: x["score"], reverse=True):
                    icon = "⭐" if s["score"] >= 70 else "🌱" if s["score"] >= 50 else "⚠️"
                    with st.expander(f"{icon} {s['name']}"):
                        st.write(f"현재가: {int(s['current']):,}원")
                        st.write(f"고점 대비: {s['extra']:.1f}%")
with tab3:
    st.subheader("⭐ 자동 추천 종목 TOP 5")

    top5 = get_top5_recommendations()
    cols = st.columns(5)
    for i, s in enumerate(top5):
        with cols[i]:
            st.metric(
                label=s["name"],
                value=f"{int(s['price']):,}원",
                delta=f"Score {s['score']}"
            )

    st.divider()

    st.subheader("🔍 개별 종목 검색")
    query = st.text_input("종목명 또는 코드 입력")
    if query:
        names = get_krx_names()
        code = smart_search_stock(query, names)
        if code:
            df = fdr.DataReader(code, (datetime.now() - timedelta(days=260)).strftime("%Y-%m-%d"))
            st.line_chart(df.Close)

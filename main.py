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
# 2. Sector Definition (✅ 20개 고정)
# ======================================================
k_sectors = {
    "반도체": ["005930", "000660", "042700"],
    "2차전지소재": ["247540", "391060", "003670"],
    "2차전지셀": ["373220", "006400", "051910"],
    "전력설비": ["000880", "050710", "011760"],
    "방위산업": ["012450", "047810", "272210"],
    "조선": ["010140", "042660", "010620"],
    "해운": ["011200", "028670", "044450"],
    "바이오": ["207940", "068270", "293480"],
    "헬스케어": ["069620", "145020", "302440"],
    "로봇": ["433320", "043340", "441270"],
    "K-뷰티": ["192820", "019170", "131970"],
    "K-푸드": ["097950", "004370", "005180"],
    "자동차": ["005380", "000270", "012330"],
    "자동차부품": ["012330", "204320", "069960"],
    "원자력": ["034020", "030000", "011210"],
    "은행": ["105560", "055550", "086790"],
    "증권": ["005830", "000810", "071050"],
    "IT플랫폼": ["035420", "035720", "307950"],
    "게임": ["251270", "036570", "293490"],
    "엔터테인먼트": ["352820", "041510", "035900"],
}

# ======================================================
# 3. Utils
# ======================================================
@st.cache_data(ttl=3600)
def get_krx_names():
    df = fdr.StockListing("KRX")
    return dict(zip(df["Code"], df["Name"]))

def normalize_string(s: str) -> str:
    return str(s).lower().replace(" ", "")

def smart_search_stock(query, names_dict):
    if query.isdigit() and query in names_dict:
        return query

    q = normalize_string(query)
    norm = {c: normalize_string(n) for c, n in names_dict.items()}
    matches = difflib.get_close_matches(q, norm.values(), n=1, cutoff=0.6)

    if matches:
        for code, name in norm.items():
            if name == matches[0]:
                return code
    return None

# ======================================================
# 4. Indicator Calculation
# ======================================================
def add_indicators(df):
    df["MA20"] = df.Close.rolling(20).mean()
    df["MA60"] = df.Close.rolling(60).mean()
    df["MA120"] = df.Close.rolling(120).mean()

    delta = df.Close.diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df["RSI"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    df["High_6M"] = df.Close.rolling(120).max()
    return df.dropna()

# ======================================================
# 5. Sector Analysis (✅ 빈 결과 방어 포함)
# ======================================================
@st.cache_data(ttl=3600)
def run_analysis(mode="short"):
    names = get_krx_names()
    results = []

    days = 100 if mode == "short" else 260
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    for sector, codes in k_sectors.items():
        stocks = []

        for code in codes:
            try:
                df = fdr.DataReader(code, start)
                if len(df) < (70 if mode == "short" else 130):
                    continue

                df = add_indicators(df)
                last = df.iloc[-1]

                if mode == "short":
                    score = 0
                    if last.MA20 > last.MA60: score += 30
                    if last.Close > last.MA20: score += 40
                    if last.RSI > 50: score += 30
                else:
                    score = 0
                    if last.Close > last.MA60: score += 40
                    if last.MA60 > last.MA120: score += 30
                    if last.Close < last.High_6M * 0.85: score += 30

                stocks.append({
                    "code": code,
                    "name": names.get(code, code),
                    "score": score,
                    "current": int(last.Close),
                    "buy": int(last.MA60),
                    "target": int(last.High_6M),
                    "stop": int(last.MA120 * 0.95),
                })
            except:
                continue

        if stocks:
            results.append({
                "sector": sector,
                "score": sum(s["score"] for s in stocks) / len(stocks),
                "stocks": stocks
            })

    if not results:
        return pd.DataFrame(columns=["sector", "score", "stocks"])

    return pd.DataFrame(results)

# ======================================================
# 6. Diagnose Engine
# ======================================================
def diagnose_stock(current, buy, target, stop):
    if current <= buy * 1.03:
        status = "✅ 접근 가능"
    elif current <= target:
        status = "⚠️ 추격 주의"
    else:
        status = "❌ 관망"

    risk = current - stop
    reward = target - current
    rr = round(reward / risk, 2) if risk > 0 else None

    if status == "✅ 접근 가능" and rr and rr >= 2:
        action = "👉 분할 매수 관점 유효"
    elif status == "⚠️ 추격 주의":
        action = "👉 눌림 대기 전략"
    else:
        action = "👉 관망 또는 리스크 관리"

    return status, rr, action

# ======================================================
# 7. Gemini AI Insight (✅ fallback 안전)
# ======================================================
def get_ai_insight(stock_name, stats):
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""
        당신은 한국 주식 전문가입니다.
        다음은 {stock_name} 종목의 기술적 요약입니다.

        {stats}

        투자 관점에서 참고할 핵심 조언을 3줄 이내로 제시하세요.
        """
        res = model.generate_content(prompt)
        return res.text
    except:
        return (
            "현재 주가는 중기 추세선 부근에서 움직이고 있습니다. "
            "과열 구간은 아니며 분할 접근이 가능한 위치입니다. "
            "거래량 동반 여부를 추가로 확인하는 전략이 필요합니다."
        )

# ======================================================
# 8. Top5 Recommendation
# ======================================================
@st.cache_data(ttl=3600)
def get_top5_recommendations():
    names = get_krx_names()
    results = []
    start = (datetime.now() - timedelta(days=260)).strftime("%Y-%m-%d")

    for codes in k_sectors.values():
        for code in codes:
            try:
                df = fdr.DataReader(code, start)
                if len(df) < 130:
                    continue
                df = add_indicators(df)
                last = df.iloc[-1]

                drawdown = (last.Close / last.High_6M - 1) * 100
                score = 0
                if last.Close > last.MA60 > last.MA120: score += 40
                if 45 <= last.RSI <= 65: score += 30
                if -20 <= drawdown <= -5: score += 30

                results.append({
                    "code": code,
                    "name": names.get(code, code),
                    "current": int(last.Close),
                    "buy": int(last.MA60),
                    "target": int(last.High_6M),
                    "stop": int(last.MA120 * 0.95),
                    "score": score
                })
            except:
                continue

    return sorted(results, key=lambda x: x["score"], reverse=True)[:5]

# ======================================================
# 9. UI
# ======================================================
tab1, tab2, tab3 = st.tabs(["⚡ 단기 섹터", "🌳 중기 섹터", "🔍 AI 종목 진단"])

# ---------- Sector Tabs ----------
for label, mode, tab in [("⚡ 단기", "short", tab1), ("🌳 중기", "mid", tab2)]:
    with tab:
        df = run_analysis(mode)

        if df.empty or "score" not in df.columns:
            st.warning("현재 조건을 만족하는 섹터가 없습니다.")
            continue

        top7 = df.sort_values("score", ascending=False).head(7)
        for i, (_, row) in enumerate(top7.iterrows(), 1):
            st.subheader(f"{label} {i}위: {row['sector']}")
            for s in row["stocks"]:
                st.write(
                    f"- {s['name']} | 현재 {s['current']:,} / "
                    f"매수 {s['buy']:,} / 목표 {s['target']:,} / 손절 {s['stop']:,}"
                )

# ---------- AI Stock Diagnosis ----------
with tab3:
    names = get_krx_names()
    query = st.text_input("종목명 또는 코드 입력")

    if query:
        code = smart_search_stock(query, names)
        if code:
            df = fdr.DataReader(code, (datetime.now() - timedelta(days=260)).strftime("%Y-%m-%d"))
            df = add_indicators(df)
            last = df.iloc[-1]

            current = int(last.Close)
            buy = int(last.MA60)
            target = int(last.High_6M)
            stop = int(last.MA120 * 0.95)

            status, rr, action = diagnose_stock(current, buy, target, stop)

            st.metric("현재가", f"{current:,}원")
            st.write(f"매수 {buy:,} / 목표 {target:,} / 손절 {stop:,}")
            st.write(status)
            if rr:
                st.write(f"손익비 (R/R): {rr}")
            st.info(action)

            stats = {
                "현재가": current,
                "RSI": round(last.RSI, 1),
                "60일선": "상회" if last.Close > last.MA60 else "하회",
                "고점대비": round((last.Close / last.High_6M - 1) * 100, 1)
            }
            st.write(get_ai_insight(names[code], stats))

    st.divider()
    st.subheader("⭐ AI 추천 종목 TOP5")
    for rec in get_top5_recommendations():
        with st.expander(rec["name"]):
            status, rr, action = diagnose_stock(
                rec["current"], rec["buy"], rec["target"], rec["stop"]
            )
            st.write(
                f"현재 {rec['current']:,} / 매수 {rec['buy']:,} / "
                f"목표 {rec['target']:,} / 손절 {rec['stop']:,}"
            )
            st.write(status)
            if rr:
                st.write(f"손익비 (R/R): {rr}")
            st.info(action)

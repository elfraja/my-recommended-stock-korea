import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import difflib
import google.generativeai as genai

# 1. 앱 설정
st.set_page_config(page_title="K-증시 AI 실전 비서", layout="wide")
st.title("⚖️ K-증시 실전 매매 비서 with Gemini AI")

# --- Gemini API 키 설정 (Secrets 연동) ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("⚠️ 사이드바나 Settings에서 GEMINI_API_KEY를 설정해주세요.")

k_sectors = {
    "반도체": {"etf": "091160", "stocks": ["005930", "000660", "042700"]},
    "2차전지소재": {"etf": "373550", "stocks": ["247540", "391060", "003670"]},
    "2차전지셀": {"etf": "373550", "stocks": ["373220", "006400", "051910"]},
    "전력설비(변압기)": {"etf": "421320", "stocks": ["000880", "050710", "011760"]},
    "방위산업": {"etf": "381170", "stocks": ["012450", "047810", "272210"]},
    "조선/해운": {"etf": "445380", "stocks": ["010140", "042660", "010620"]},
    "바이오/의료": {"etf": "091150", "stocks": ["207940", "068270", "293480"]},
    "로봇": {"etf": "440760", "stocks": ["433320", "043340", "441270"]},
    "K-뷰티(화장품)": {"etf": "228790", "stocks": ["192820", "019170", "131970"]},
    "K-푸드": {"etf": "429000", "stocks": ["097950", "004370", "005180"]},
    "우주항공": {"etf": "445380", "stocks": ["012450", "047810", "112190"]},
    "자동차": {"etf": "091140", "stocks": ["005380", "000270", "012330"]},
    "원자력": {"etf": "421320", "stocks": ["034020", "030000", "011210"]},
    "은행(밸류업)": {"etf": "091170", "stocks": ["105560", "055550", "086790"]},
    "증권/보험": {"etf": "091170", "stocks": ["005830", "000810", "071050"]},
    "가상자산": {"etf": "417630", "stocks": ["040300", "036710", "060310"]},
    "IT플랫폼": {"etf": "266370", "stocks": ["035420", "035720", "307950"]},
    "게임": {"etf": "293400", "stocks": ["251270", "036570", "293490"]},
    "엔터": {"etf": "227540", "stocks": ["352820", "041510", "035900"]},
    "철강/금속": {"etf": "117680", "stocks": ["005490", "004020", "016380"]}
}

@st.cache_data(ttl=3600)
def get_krx_names():
    df = fdr.StockListing('KRX')
    return dict(zip(df['Code'], df['Name']))

def normalize_string(s):
    if not s: return ""
    s = str(s).lower().replace(" ", "")
    replace_dict = {
        "lg": "엘지", "sk": "에스케이", "cj": "씨제이", "kt": "케이티", "kakao": "카카오", "naver": "네이버", 
        "pay": "페이", "bank": "뱅크", "cns": "씨엔에스"
    }
    for eng, kor in replace_dict.items(): s = s.replace(eng, kor)
    return s

def smart_search_stock(query, names_dict):
    if query.isdigit() and query in names_dict: return query
    query_norm = normalize_string(query)
    norm_dict = {code: normalize_string(name) for code, name in names_dict.items()}
    for code, norm_name in norm_dict.items():
        if query_norm in norm_name or norm_name in query_norm: return code
    all_norm_names = list(norm_dict.values())
    closest_matches = difflib.get_close_matches(query_norm, all_norm_names, n=1, cutoff=0.5)
    if closest_matches:
        for code, norm_name in norm_dict.items():
            if norm_name == closest_matches[0]: return code
    return None

def calc_short_term_factors(df):
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['MA20'] + (df['STD20'] * 2)
    df['Vol_Ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    return df.dropna()

def calc_mid_term_factors(df):
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA120'] = df['Close'].rolling(window=120).mean()
    df['High_6M'] = df['Close'].rolling(window=120).max()
    return df.dropna()

@st.cache_data(ttl=3600)
def run_analysis(mode):
    results = []
    names = get_krx_names()
    days_to_fetch = 100 if mode == "short" else 250
    start_date = (datetime.now() - timedelta(days=days_to_fetch)).strftime('%Y-%m-%d')
    for name, info in k_sectors.items():
        try:
            etf_df = fdr.DataReader(info['etf'], start_date)
            perf_5d = ((etf_df['Close'].iloc[-1] / etf_df['Close'].iloc[-5]) - 1) * 100
            stock_data = []
            for s_code in info['stocks']:
                raw_df = fdr.DataReader(s_code, start_date)
                if len(raw_df) < (65 if mode == "short" else 130): continue
                if mode == "short":
                    s_df = calc_short_term_factors(raw_df)
                    if s_df.empty: continue
                    last = s_df.iloc[-1]
                    current = last['Close']
                    buy_price = current if current <= last['MA20'] else (current + last['MA20']) / 2
                    target_price = last['BB_Upper'] if last['BB_Upper'] > current else current * 1.07
                    stop_loss = max(last['MA60'], current * 0.95)
                    score = 0
                    if last['MA5'] > last['MA20'] > last['MA60']: score += 40
                    if 50 <= last['RSI'] <= 70: score += 30
                    if last['MACD'] > last['Signal']: score += 30
                    desc = "수급 안정" if score > 50 else "관망 필요"
                else:
                    s_df = calc_mid_term_factors(raw_df)
                    if s_df.empty: continue
                    last = s_df.iloc[-1]
                    current = last['Close']
                    ma60, ma120, high6m = last['MA60'], last['MA120'], last['High_6M']
                    drawdown = ((current - high6m) / high6m) * 100
                    buy_price, target_price, stop_loss = ma60, high6m, ma120 * 0.95
                    score = 40 if current > ma60 else 0
                    score += 30 if ma60 > ma120 else 0
                    score += 30 if drawdown < -15 else 0
                    desc = "중기 우상향" if score > 50 else "추세 확인중"
                stock_data.append({"name": names.get(s_code, s_code), "current": current, "buy": buy_price, "target": target_price, "stop": stop_loss, "score": score, "desc": desc, "extra": drawdown if mode == "mid" else None})
            if stock_data:
                sector_score = sum([s['score'] for s in stock_data]) / len(stock_data)
                results.append({"섹터명": name, "5일수익률": perf_5d, "score": sector_score, "stocks": stock_data})
        except: continue
    return pd.DataFrame(results)

def get_ai_insight(name, data_summary):
    try:
        # 모델명을 gemini-1.5-flash로 수정 (가장 안정적)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"당신은 주식 전문가입니다. {name}의 지표({data_summary})를 보고 투자 인사이트를 3줄 요약해주세요."
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 분석 실패: {str(e)}"

# --- UI 구현 ---
tab1, tab2, tab3 = st.tabs(["⚡ 단기 스윙", "🌳 중기 추세", "🔍 AI 종목 진단"])

with tab1:
    st.markdown("### 🏄‍♂️ 단기 모멘텀 분석")
    short_df = run_analysis("short")
    if not short_df.empty:
        top_7 = short_df.sort_values(by='score', ascending=False).head(7)
        for _, row in top_7.iterrows():
            with st.expander(f"🏆 {row['섹터명']}"):
                for s in row['stocks']:
                    st.write(f"**{s['name']}**: 현재 {int(s['current']):,}원 / 매수 {int(s['buy']):,}원 / 목표 {int(s['target']):,}원")

with tab2:
    st.markdown("### 🌳 중기 추세 분석")
    mid_df = run_analysis("mid")
    if not mid_df.empty:
        top_7 = mid_df.sort_values(by='score', ascending=False).head(7)
        for _, row in top_7.iterrows():
            with st.expander(f"🛡️ {row['섹터명']}"):
                for s in row['stocks']:
                    st.write(f"**{s['name']}**: {int(s['current']):,}원 (고점대비 {s['extra']:.1f}%)")

with tab3:
    st.markdown("### 🔍 개별 종목 정밀 진단")
    query = st.text_input("종목명 또는 코드를 입력하세요 (예: 카카오페이, 005930):")
    if query:
        names_dict = get_krx_names()
        code = smart_search_stock(query, names_dict)
        if code:
            st.success(f"'{names_dict[code]}' 분석 중...")
            df = fdr.DataReader(code, (datetime.now() - timedelta(days=250)).strftime('%Y-%m-%d'))
            if len(df) > 100:
                df = calc_short_term_factors(df) # RSI 등을 위해 계산
                last = df.iloc[-1]
                summary = f"현재가 {last['Close']}, RSI {last['RSI']:.1f}, 20일선 {last['MA20']}"
                st.metric("현재가", f"{int(last['Close']):,}원")
                st.subheader("🤖 AI 전문가 의견")
                st.write(get_ai_insight(names_dict[code], summary))

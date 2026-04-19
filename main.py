import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import difflib
import google.generativeai as genai # 제미나이 로드

# 1. 앱 설정
st.set_page_config(page_title="K-증시 AI 하이브리드 비서", layout="wide")
st.title("⚖️ K-증시 실전 매매 비서 with Gemini AI")

# --- [보안 팁] API 키 설정 ---
# 깃허브에 직접 키를 적으면 위험하므로, 나중에 스트림릿 설정에서 넣는 방식을 권장하지만
# 우선 작동 확인을 위해 아래 주석 부분에 키를 넣어 테스트해보세요.
# genai.configure(api_key="여기에_발급받은_API키를_넣으세요")

# 만약 스트림릿 Secrets를 사용한다면 아래 코드를 씁니다.
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

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
    replace_dict = {"lg": "엘지", "sk": "에스케이", "cj": "씨제이", "kt": "케이티", "kakao": "카카오", "naver": "네이버", "pay": "페이", "bank": "뱅크"}
    for eng, kor in replace_dict.items(): s = s.replace(eng, kor)
    return s

def smart_search_stock(query, names_dict):
    if query.isdigit() and query in names_dict: return query
    query_norm = normalize_string(query)
    norm_dict = {code: normalize_string(name) for code, name in names_dict.items()}
    for code, norm_name in norm_dict.items():
        if query_norm == norm_name: return code
    all_norm_names = list(norm_dict.values())
    closest_matches = difflib.get_close_matches(query_norm, all_norm_names, n=1, cutoff=0.6)
    if closest_matches:
        for code, norm_name in norm_dict.items():
            if norm_name == closest_matches[0]: return code
    return None

def calc_factors(df):
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA120'] = df['Close'].rolling(window=120).mean()
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
    df['High_6M'] = df['Close'].rolling(window=120).max()
    return df.dropna()

def get_ai_insight(name, data_summary):
    """제미나이 AI에게 종목 분석 요청"""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        당신은 대한민국 최고의 주식 투자 전략가입니다. 
        '{name}' 종목의 최근 데이터는 다음과 같습니다:
        {data_summary}
        
        이 데이터를 바탕으로 투자자가 참고할 만한 핵심 인사이트를 딱 3줄로 요약해서 말해주세요. 
        어투는 '전문가적인 조언' 느낌으로 해주세요.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 분석을 불러오지 못했습니다. (사유: {str(e)})"

# --- 화면 구현 ---
tab1, tab2, tab3 = st.tabs(["⚡ 단기 스윙", "🌳 중기 추세", "🔍 AI 종목 진단"])

# (1, 2탭 생략 - 이전과 동일한 로직)

with tab3:
    st.markdown("### 🔍 AI 개별 종목 정밀 진단")
    query = st.text_input("종목명 또는 코드를 입력하세요:", "").strip()
    
    if query:
        names_dict = get_krx_names()
        target_code = smart_search_stock(query, names_dict)
        
        if target_code:
            stock_name = names_dict[target_code]
            with st.spinner(f"AI가 {stock_name}의 차트와 수급을 정밀 분석 중..."):
                start_date = (datetime.now() - timedelta(days=250)).strftime('%Y-%m-%d')
                df = fdr.DataReader(target_code, start_date)
                
                if len(df) > 120:
                    df = calc_factors(df)
                    last = df.iloc[-1]
                    
                    # 데이터 요약 (AI에게 보낼 내용)
                    stats = {
                        "현재가": f"{int(last['Close']):,}원",
                        "RSI(강도)": f"{last['RSI']:.1f}",
                        "60일선 대비": "위" if last['Close'] > last['MA60'] else "아래",
                        "전고점 대비": f"{((last['Close']/last['High_6M'])-1)*100:.1f}%"
                    }
                    
                    # 화면 출력
                    st.divider()
                    col1, col2 = st.columns([1, 1.2])
                    
                    with col1:
                        st.subheader(f"📊 {stock_name} 기술적 지표")
                        st.metric("현재가", stats["현재가"])
                        st.write(f"**RSI 지수:** {stats['RSI(강도)']}")
                        st.write(f"**추세 상태:** 60일선 {stats['60일선 대비']}")
                        st.markdown(f"📉 **추천 매수:** `{int(last['MA60']):,}원` 부근")
                        st.markdown(f"🎯 **목표가:** `{int(last['High_6M']):,}원`")

                    with col2:
                        st.subheader("🤖 Gemini AI의 전문 의견")
                        insight = get_ai_insight(stock_name, str(stats))
                        st.write(insight)
                        st.caption("※ 본 분석은 AI의 견해이며 투자 판단의 책임은 본인에게 있습니다.")

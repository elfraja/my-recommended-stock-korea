import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import difflib
import google.generativeai as genai
import json
import re

# 1. 앱 설정
st.set_page_config(page_title="K-증시 실전 매매 비서 V5", page_icon="📡", layout="wide")

# CSS 스타일 (블록형 UI 및 2x2 가격 카드 디자인 최적화)
st.markdown("""
<style>
    /* 섹터 타이틀 블록 */
    .sector-title-top { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #38bdf8; border-radius: 10px; padding: 12px; margin-bottom: 12px; text-align: center; color: white; font-weight: bold; font-size: 18px; }
    .sector-title-norm { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 12px; margin-bottom: 12px; text-align: center; color: white; font-weight: bold; font-size: 16px; }
    
    /* 개별 종목 카드 */
    .normal-card { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 12px; margin-bottom: 10px; }
    
    /* 가격 박스 (좁은 세로 블록을 위해 2x2 배열로 변경) */
    .price-box { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-top: 10px; text-align: center; }
    .price-item { padding: 6px; border-radius: 6px; font-size: 12px; font-weight: bold; }
    .curr { background: #1e293b; color: #38bdf8; }
    .buy { background: #064e3b; color: #34d399; }
    .target { background: #78350f; color: #fbbf24; }
    .stop { background: #7f1d1d; color: #f87171; }
</style>
""", unsafe_allow_html=True)

# 2. Gemini 설정
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    GEMINI_READY = True
else:
    GEMINI_READY = False

# 3. 20대 핵심 테마 (ETF 맵핑 포함)
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

# 4. 유틸 및 지표 계산 함수
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
    closest_matches = difflib.get_close_matches(query_norm, list(norm_dict.values()), n=1, cutoff=0.5)
    if closest_matches:
        for code, norm_name in norm_dict.items():
            if norm_name == closest_matches[0]: return code
    return None

def calc_indicators(df):
    df = df.copy()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    df['MA120'] = df['Close'].rolling(120).mean()
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
    df['High_6M'] = df['Close'].rolling(120).max()
    return df.dropna()

@st.cache_data(ttl=3600)
def run_full_analysis(mode):
    results = []
    names = get_krx_names()
    start_date = (datetime.now() - timedelta(days=300)).strftime('%Y-%m-%d')
    for sec, info in k_sectors.items():
        try:
            etf = fdr.DataReader(info['etf'], start_date)
            perf = ((etf['Close'].iloc[-1] / etf['Close'].iloc[-5]) - 1) * 100
            stocks = []
            for code in info['stocks']:
                df = fdr.DataReader(code, start_date)
                if len(df) < 130: continue
                df = calc_indicators(df)
                last = df.iloc[-1]
                curr = last['Close']
                
                # 핵심: 매수가격 및 손절/익절가 세팅
                if mode == "short":
                    buy = curr if curr <= last['MA20'] else (curr + last['MA20']) / 2
                    stop = buy * 0.95
                    target = buy * 1.08
                    score = (100 - last['RSI']) * 0.6 + (curr / last['MA20']) * 40
                else:
                    buy = last['MA60']
                    stop = min(last['MA120'], buy * 0.95)
                    target = last['High_6M']
                    score = (curr / last['MA120']) * 100
                
                icon = "🔥" if score > 70 else "🟢" if score > 40 else "⚪"
                stocks.append({"name": names.get(code, code), "code": code, "curr": curr, "buy": buy, "target": target, "stop": stop, "score": score, "icon": icon})
            if stocks:
                results.append({"sector": sec, "perf": perf, "score": sum(s['score'] for s in stocks)/len(stocks), "stocks": stocks})
        except: continue
    return pd.DataFrame(results).sort_values("score", ascending=False).head(7)

def render_stock_ui(s):
    st.markdown(f"""
    <div class="normal-card">
        <div style="font-weight:bold; font-size:15px;">{s['icon']} {s['name']} <span style="font-size:11px;color:#8b949e;">{s['code']}</span></div>
        <div class="price-box">
            <div class="price-item curr">현재<br>{int(s['curr']):,}</div>
            <div class="price-item buy">매수<br>{int(s['buy']):,}</div>
            <div class="price-item target">익절<br>{int(s['target']):,}</div>
            <div class="price-item stop">손절<br>{int(s['stop']):,}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- 🛡️ 자체 알고리즘 폴백 (Fallback) ---
def get_fallback_insight(stats):
    curr = float(stats["현재가"].replace("원", "").replace(",", ""))
    ma60 = float(stats["MA60"].replace("원", "").replace(",", ""))
    rsi = float(stats["RSI"])
    trend = "상승 추세 (60일선 위)" if curr >= ma60 else "하락 추세 (60일선 아래)"
    energy = "단기 과매수(조정 주의)" if rsi >= 70 else "과매도(기술적 반등 기대)" if rsi <= 30 else "중립 방향성 탐색"
    advice = "현재 추세가 살아있으므로 눌림목 분할 매수 접근이 유효합니다." if curr >= ma60 else "추세가 무너진 상태이므로 섣부른 매수보다 하방 지지 확인이 우선입니다."
    opinion = "매수 관점" if curr >= ma60 and rsi < 70 else "관망" if curr < ma60 else "분할 매도 (수익 실현)"
    
    return f"⚠️ **AI 응답 지연으로 시스템 알고리즘 분석을 제공합니다.**\n\n1. 📊 **현재 상황:** 주가는 {trend}에 있으며, 에너지는 {energy}입니다.\n2. 🎯 **매매 전략:** {advice}\n3. 💡 **종합 의견:** {opinion}"

def get_ai_insight(name, stats):
    if not GEMINI_READY: 
        return get_fallback_insight(stats)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"주식 전문가로서 '{name}'의 지표({str(stats)})를 보고 투자 인사이트를 3줄 요약해주세요."
        return model.generate_content(prompt).text
    except Exception:
        return get_fallback_insight(stats)

# 5. UI 메인 (대시보드 블록형 레이아웃 3 & 4)
tab1, tab2, tab3 = st.tabs(["⚡ 단기 스윙 (Top 7)", "🌳 중기 추세 (Top 7)", "🔍 AI 종목 & ETF 추천"])

with tab1:
    st.header("⚡ 단기 반등 모멘텀 Top 7")
    st.caption("1~2주 보유 목적. 매수 대비 손절가 -5% 철저히 준수.")
    with st.spinner("단기 타점 분석 중..."):
        df_s = run_full_analysis("short")
        if not df_s.empty:
            # 상단 3개 블록 렌더링
            top3 = df_s.head(3)
            cols_top = st.columns(3)
            for i, (_, row) in enumerate(top3.iterrows()):
                with cols_top[i]:
                    st.markdown(f"<div class='sector-title-top'>🏆 {i+1}위: {row['sector']}</div>", unsafe_allow_html=True)
                    for s in row['stocks']: 
                        render_stock_ui(s)
            
            st.divider() # 위/아래 구분선
            
            # 하단 4개 블록 렌더링
            bot4 = df_s.iloc[3:7]
            cols_bot = st.columns(4)
            for i, (_, row) in enumerate(bot4.iterrows()):
                with cols_bot[i]:
                    st.markdown(f"<div class='sector-title-norm'>🏅 {i+4}위: {row['sector']}</div>", unsafe_allow_html=True)
                    for s in row['stocks']: 
                        render_stock_ui(s)

with tab2:
    st.header("🌳 중기 실적/추세 Top 7")
    st.caption("1~3개월 보유 목적. 60일선 매수, 120일선 이탈 시 손절.")
    with st.spinner("중기 타점 분석 중..."):
        df_m = run_full_analysis("mid")
        if not df_m.empty:
            # 상단 3개 블록 렌더링
            top3 = df_m.head(3)
            cols_top = st.columns(3)
            for i, (_, row) in enumerate(top3.iterrows()):
                with cols_top[i]:
                    st.markdown(f"<div class='sector-title-top'>🏆 {i+1}위: {row['sector']}</div>", unsafe_allow_html=True)
                    for s in row['stocks']: 
                        render_stock_ui(s)
            
            st.divider()
            
            # 하단 4개 블록 렌더링
            bot4 = df_m.iloc[3:7]
            cols_bot = st.columns(4)
            for i, (_, row) in enumerate(bot4.iterrows()):
                with cols_bot[i]:
                    st.markdown(f"<div class='sector-title-norm'>🏅 {i+4}위: {row['sector']}</div>", unsafe_allow_html=True)
                    for s in row['stocks']: 
                        render_stock_ui(s)

with tab3:
    st.header("🔍 정밀 분석 & 유망 ETF/주식 픽")
    
    st.subheader("💡 오늘의 단기 유망주 & ETF TOP 5")
    if st.button("🪄 시장 유망 종목 및 ETF 5개 추천받기"):
        with st.spinner("트렌드 분석 및 유망 ETF/개별주 선정 중..."):
            is_ai_success = False
            if GEMINI_READY:
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    prompt = "한국 주식 시장 단기 상승 유망 종목과 관련 ETF를 포함하여 딱 5개를 추천해줘. 반드시 JSON 형식으로만: [{'rank':1, 'name':'종목명 또는 ETF명', 'code':'코드', 'reason':'이유'}, ...]"
                    res = model.generate_content(prompt).text
                    clean_res = re.sub(r'```json|```', '', res).strip()
                    recs = json.loads(clean_res)
                    is_ai_success = True
                except Exception:
                    is_ai_success = False
            
            # --- 🛡️ 자체 알고리즘 폴백 (ETF 1개 + 개별주 4개 자동생성) ---
            if not is_ai_success:
                st.warning("⚠️ AI 응답 지연으로 자체 퀀트 알고리즘이 선정한 우량 종목과 ETF를 제공합니다.")
                recs = []
                cached_df = run_full_analysis("short")
                if not cached_df.empty:
                    # 1위 섹터의 주도 ETF 강제 추천 추가
                    best_sector = cached_df.iloc[0]
                    etf_code = k_sectors[best_sector['sector']]['etf']
                    recs.append({"rank": 1, "name": f"KODEX/TIGER {best_sector['sector']} 관련 ETF", "code": etf_code, "reason": f"{best_sector['sector']} 섹터 전반의 모멘텀 강세 (안정적 분산투자)"})
                    
                    # 나머지 4개는 섹터 내 우량주 추천
                    for _, row in cached_df.iterrows():
                        for s in row['stocks']:
                            if len(recs) < 5 and s['score'] > 50:
                                recs.append({"rank": len(recs)+1, "name": s['name'], "code": s['code'], "reason": f"{row['sector']} 주도주로서 수급 우수 및 정배열 초입"})

            # 결과 렌더링
            if recs:
                cols = st.columns(5)
                for idx, r in enumerate(recs):
                    if idx < 5:
                        with cols[idx]:
                            st.success(f"**{r['name']}**")
                            st.caption(f"{r['code']}")
                            st.write(f"_{r['reason']}_")

    st.divider()
    
    st.subheader("📊 개별 종목 정밀 진단")
    query = st.text_input("분석할 종목명 또는 코드를 입력하세요:", placeholder="예: 삼성전자, LGCNS, 카카오페이, 005930")
    
    if query:
        names_dict = get_krx_names()
        target_code = smart_search_stock(query, names_dict)
        
        if target_code:
            stock_name = names_dict[target_code]
            if query != stock_name and query != target_code:
                st.success(f"💡 '{query}' 검색어로 **'{stock_name}'** 종목을 찾아 분석합니다.")
                
            with st.spinner(f"'{stock_name}' 차트 데이터 정밀 분석 중..."):
                start_date = (datetime.now() - timedelta(days=250)).strftime('%Y-%m-%d')
                df = fdr.DataReader(target_code, start_date)
                
                if len(df) > 120:
                    df = calc_indicators(df)
                    last = df.iloc[-1]
                    curr_price = last['Close']
                    
                    stats = {
                        "현재가": f"{int(curr_price):,}원",
                        "RSI": f"{last['RSI']:.1f}",
                        "MA20": f"{int(last['MA20']):,}원",
                        "MA60": f"{int(last['MA60']):,}원",
                        "MA120": f"{int(last['MA120']):,}원"
                    }
                    
                    buy_p = curr_price if curr_price <= last['MA20'] else (curr_price + last['MA20']) / 2
                    stop_p = buy_p * 0.95
                    target_p = curr_price * 1.08
                    
                    st.markdown("---")
                    col1, col2 = st.columns([1, 1.2])
                    
                    with col1:
                        st.subheader(f"📈 {stock_name} 가격 타점 가이드")
                        s_data = {"name": stock_name, "code": target_code, "curr": curr_price, "buy": buy_p, "target": target_p, "stop": stop_p, "icon": "🔍"}
                        render_stock_ui(s_data)
                        
                        st.write(f"**RSI 지수 (추세 에너지):** {stats['RSI']}")
                        st.write(f"**60일선 (수급선):** {stats['MA60']}")

                    with col2:
                        st.subheader("🤖 종목 인사이트 리포트")
                        insight = get_ai_insight(stock_name, stats)
                        st.info(insight)
                else:
                    st.error("분석하기에 상장 기간이 너무 짧거나 데이터가 부족합니다.")
        else:
            st.error("입력하신 종목을 찾을 수 없습니다.")

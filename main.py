import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

# 1. 앱 설정
st.set_page_config(page_title="AI 하이브리드 주식 비서", layout="wide")
st.title("⚖️ AI 하이브리드 주식 비서")
st.caption("단기 모멘텀 파도타기와 장기 대세선 투자를 모두 지원하는 통합 분석기입니다.")

# 20대 핵심 테마
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

def calc_short_term_factors(df):
    """단기 매매용 5-Factor 지표"""
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

def calc_long_term_factors(df):
    """장기 보유용 지표 (대세선 및 52주 최고가)"""
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA120'] = df['Close'].rolling(window=120).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    df['High_52W'] = df['Close'].rolling(window=250).max() # 약 1년(250거래일) 최고가
    return df.dropna()

@st.cache_data(ttl=3600)
def run_analysis(mode):
    results = []
    names = get_krx_names()
    # 단기는 120일치 데이터, 장기는 200일선 계산을 위해 365일치 데이터 수집
    days_to_fetch = 120 if mode == "short" else 365
    start_date = (datetime.now() - timedelta(days=days_to_fetch)).strftime('%Y-%m-%d')
    
    for name, info in k_sectors.items():
        try:
            etf_df = fdr.DataReader(info['etf'], start_date)
            perf_5d = ((etf_df['Close'].iloc[-1] / etf_df['Close'].iloc[-5]) - 1) * 100
            stock_data = []
            
            for s_code in info['stocks']:
                raw_df = fdr.DataReader(s_code, start_date)
                if len(raw_df) < (60 if mode == "short" else 200): continue
                
                if mode == "short":
                    s_df = calc_short_term_factors(raw_df)
                    last = s_df.iloc[-1]
                    current = last['Close']
                    buy_price = current if current <= last['MA20'] else (current + last['MA20']) / 2
                    target_price = last['BB_Upper'] if last['BB_Upper'] > current else current * 1.05
                    stop_loss = max(last['MA60'], current * 0.95)
                    
                    score = 0
                    msg = []
                    if last['MA5'] > last['MA20'] > last['MA60']: score += 20; msg.append("정배열")
                    if 50 <= last['RSI'] <= 70: score += 20; msg.append("에너지 안정")
                    if current > last['BB_Upper']: score += 20; msg.append("밴드 돌파")
                    if last['Vol_Ratio'] > 1.5: score += 20; msg.append("수급 폭발")
                    if last['MACD'] > last['Signal']: score += 20; msg.append("추세 상승")
                    desc = " | ".join(msg) if msg else "모멘텀 대기"

                else: # 장기 모드
                    s_df = calc_long_term_factors(raw_df)
                    last = s_df.iloc[-1]
                    current = last['Close']
                    ma120 = last['MA120']
                    ma200 = last['MA200']
                    high52 = last['High_52W']
                    
                    # 52주 고점 대비 하락률
                    drawdown = ((current - high52) / high52) * 100
                    
                    # 장기 매수가: 200일선이나 120일선 부근에서 줍기
                    buy_price = ma200 if current > ma200 else current
                    # 장기 목표가: 52주 최고가 회복 또는 30% 상승
                    target_price = high52 if high52 > current * 1.1 else current * 1.3
                    # 장기 손절가: 200일선이 완전히 무너질 때 (-5% 여유)
                    stop_loss = ma200 * 0.95
                    
                    score = 0
                    msg = []
                    if current > ma200: score += 40; msg.append("장기 대세선(200일) 유지")
                    else: msg.append("장기 역배열 주의")
                    
                    if ma120 > ma200: score += 30; msg.append("중장기 정배열 우상향")
                    
                    if drawdown < -20 and current > ma200: score += 30; msg.append("고점대비 20% 할인(안전마진)")
                    elif drawdown >= -10: msg.append("신고가 돌파 시도")
                    
                    desc = " + ".join(msg)

                stock_data.append({
                    "name": names.get(s_code, s_code),
                    "current": current,
                    "buy": buy_price,
                    "target": target_price,
                    "stop": stop_loss,
                    "score": score,
                    "desc": desc,
                    "extra": drawdown if mode == "long" else None
                })
                
            if stock_data:
                # 섹터 점수는 종목 점수 평균으로 계산
                sector_score = sum([s['score'] for s in stock_data]) / len(stock_data)
                results.append({"섹터명": name, "5일수익률": perf_5d, "score": sector_score, "stocks": stock_data})
        except: continue
    return pd.DataFrame(results)

# 3. 화면 UI 구성 (두 개의 탭)
tab1, tab2 = st.tabs(["⚡ 단기 트레이딩 모드 (Swing)", "🛡️ 장기 가치투자 모드 (Buy & Hold)"])

with tab1:
    st.markdown("### 🏄‍♂️ 단기 파도타기: 수급과 모멘텀 중심")
    with st.spinner('단기 매매 최적 타점을 계산 중입니다...'):
        short_df = run_analysis("short")
        
    if not short_df.empty:
        top_short = short_df.sort_values(by='score', ascending=False).head(3)
        cols = st.columns(3)
        for i, (idx, row) in enumerate(top_short.iterrows()):
            with cols[i]:
                st.info(f"🏆 {i+1}위: {row['섹터명']}")
                for s in sorted(row['stocks'], key=lambda x: x['score'], reverse=True):
                    icon = "🔥" if s['score'] >= 80 else "🟢" if s['score'] >= 60 else "⚪"
                    with st.expander(f"{icon} {s['name']}"):
                        st.write(f"현재가: {int(s['current']):,}원")
                        st.markdown(f"📉 **추천 매수:** `{int(s['buy']):,}원`")
                        st.markdown(f"🎯 **단기 목표:** `{int(s['target']):,}원`")
                        st.markdown(f"🛑 **칼 손절가:** `{int(s['stop']):,}원`")
                        st.caption(f"사유: {s['desc']}")

with tab2:
    st.markdown("### 🌳 장기 나무심기: 대세선과 할인율 중심")
    st.info("💡 **장기 투자 전략:** 주가가 200일선(대세선) 위에 있는 건강한 종목이 120/200일선 부근으로 조정을 받을 때 분할 매수합니다.")
    
    with st.spinner('1년치 데이터를 바탕으로 장기 대세선과 안전마진을 분석 중입니다...'):
        long_df = run_analysis("long")
        
    if not long_df.empty:
        # 장기 모드는 점수(대세선 유지)가 높은 섹터를 보여줍니다.
        top_long = long_df.sort_values(by='score', ascending=False).head(3)
        cols2 = st.columns(3)
        for i, (idx, row) in enumerate(top_long.iterrows()):
            with cols2[i]:
                st.success(f"🛡️ 우량 섹터: {row['섹터명']}")
                for s in sorted(row['stocks'], key=lambda x: x['score'], reverse=True):
                    icon = "⭐" if s['score'] >= 70 else "🌱" if s['score'] >= 40 else "⚠️"
                    with st.expander(f"{icon} {s['name']}"):
                        st.write(f"현재가: {int(s['current']):,}원")
                        st.write(f"최고점 대비: **{s['extra']:.1f}%**")
                        st.write("---")
                        st.markdown(f"🛒 **적립식 매수가:** `{int(s['buy']):,}원` 이하에서 줍기")
                        st.markdown(f"🎯 **장기 목표가:** `{int(s['target']):,}원`")
                        st.markdown(f"🛑 **추세 붕괴(손절):** `{int(s['stop']):,}원` 이탈 시")
                        st.write("---")
                        st.caption(f"상태: {s['desc']}")

import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="K-증시 중단기 주식 비서", layout="wide")
st.title("⚖️ K-증시 실전 매매 비서")
st.caption("1~2주 단기 스윙과 1~3개월 중기 보유에 최적화된 한국 시장 맞춤형 퀀트입니다.")

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
    """한국 시장 1~3개월 보유에 최적화된 60일/120일선 기준 지표"""
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA120'] = df['Close'].rolling(window=120).mean()
    df['High_6M'] = df['Close'].rolling(window=120).max() # 6개월 최고가
    return df.dropna()

@st.cache_data(ttl=3600)
def run_analysis(mode):
    results = []
    names = get_krx_names()
    
    # 단기는 100일, 중기는 250일(약 1년) 데이터를 가져와 계산 오류를 방지합니다.
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
                    msg = []
                    if last['MA5'] > last['MA20'] > last['MA60']: score += 20; msg.append("정배열")
                    if 50 <= last['RSI'] <= 70: score += 20; msg.append("안정적 에너지")
                    if current > last['BB_Upper']: score += 20; msg.append("밴드 돌파")
                    if last['Vol_Ratio'] > 1.5: score += 20; msg.append("수급 폭발")
                    if last['MACD'] > last['Signal']: score += 20; msg.append("추세 상승")
                    desc = " | ".join(msg) if msg else "모멘텀 대기"

                else: # 중기 스윙 모드
                    s_df = calc_mid_term_factors(raw_df)
                    if s_df.empty: continue
                    last = s_df.iloc[-1]
                    current = last['Close']
                    ma60 = last['MA60']
                    ma120 = last['MA120']
                    high6m = last['High_6M']
                    
                    drawdown = ((current - high6m) / high6m) * 100
                    
                    # 중기 매매 타점 로직 (60일선 지지 기반)
                    buy_price = ma60 if current > ma60 else current
                    target_price = high6m if high6m > current * 1.05 else current * 1.2
                    stop_loss = ma120 * 0.95 # 120일 반기선 이탈 시 손절
                    
                    score = 0
                    msg = []
                    if current > ma60: score += 40; msg.append("60일(실적선) 유지")
                    else: msg.append("60일선 저항 주의")
                    
                    if ma60 > ma120: score += 30; msg.append("중기 정배열 우상향")
                    
                    if drawdown < -15 and current > ma120: score += 30; msg.append("고점대비 15% 할인")
                    elif drawdown >= -5: score += 10; msg.append("6개월 신고가 돌파 시도")
                    
                    desc = " + ".join(msg)

                stock_data.append({
                    "name": names.get(s_code, s_code),
                    "current": current,
                    "buy": buy_price,
                    "target": target_price,
                    "stop": stop_loss,
                    "score": score,
                    "desc": desc,
                    "extra": drawdown if mode == "mid" else None
                })
                
            if stock_data:
                sector_score = sum([s['score'] for s in stock_data]) / len(stock_data)
                results.append({"섹터명": name, "5일수익률": perf_5d, "score": sector_score, "stocks": stock_data})
        except: continue
    return pd.DataFrame(results)

# 화면 구현
tab1, tab2 = st.tabs(["⚡ 단기 스윙 (1~2주 보유)", "🌳 중기 추세 (1~3개월 보유)"])

with tab1:
    st.markdown("### 🏄‍♂️ 단기 모멘텀 파도타기")
    with st.spinner('1~2주 보유를 위한 단기 매매 타점을 계산 중입니다...'):
        short_df = run_analysis("short")
        
    if not short_df.empty:
        top_7_short = short_df.sort_values(by='score', ascending=False).head(7)
        st.subheader("🏆 집중 공략 섹터 (1~3위)")
        cols1 = st.columns(3)
        for i in range(3):
            if i < len(top_7_short):
                row = top_7_short.iloc[i]
                with cols1[i]:
                    st.info(f"### {i+1}위: {row['섹터명']}")
                    for s in sorted(row['stocks'], key=lambda x: x['score'], reverse=True):
                        icon = "🔥" if s['score'] >= 80 else "🟢" if s['score'] >= 60 else "⚪"
                        with st.expander(f"{icon} {s['name']}"):
                            st.write(f"현재가: {int(s['current']):,}원")
                            st.markdown(f"📉 **매수:** `{int(s['buy']):,}원`")
                            st.markdown(f"🎯 **목표:** `{int(s['target']):,}원`")
                            st.markdown(f"🛑 **손절:** `{int(s['stop']):,}원`")
                            st.caption(s['desc'])
        
        st.divider()
        st.subheader("🔍 추격 매수 가능 섹터 (4~7위)")
        cols2 = st.columns(4)
        for i in range(3, 7):
            if i < len(top_7_short):
                row = top_7_short.iloc[i]
                with cols2[i-3]:
                    st.success(f"**{i+1}위: {row['섹터명']}**")
                    for s in sorted(row['stocks'], key=lambda x: x['score'], reverse=True):
                        icon = "🟢" if s['score'] >= 60 else "⚪"
                        with st.expander(f"{icon} {s['name']}"):
                            st.markdown(f"📉 **매수:** `{int(s['buy']):,}원`")
                            st.markdown(f"🎯 **목표:** `{int(s['target']):,}원`")
                            st.caption(s['desc'])

with tab2:
    st.markdown("### 🌳 중기 실적/추세 따라가기")
    st.info("💡 **중기 투자 전략:** 주가가 60일(실적선) 위에 있는 종목이 지지받을 때 진입하며, 120일(반기선) 이탈 시 손절합니다.")
    
    with st.spinner('수개월 보유를 위한 60일/120일선 추세를 분석 중입니다...'):
        mid_df = run_analysis("mid")
        
    if not mid_df.empty:
        top_7_mid = mid_df.sort_values(by='score', ascending=False).head(7)
        st.subheader("🛡️ 중기 우량 섹터 (1~3위)")
        cols3 = st.columns(3)
        for i in range(3):
            if i < len(top_7_mid):
                row = top_7_mid.iloc[i]
                with cols3[i]:
                    st.success(f"### {i+1}위: {row['섹터명']}")
                    for s in sorted(row['stocks'], key=lambda x: x['score'], reverse=True):
                        icon = "⭐" if s['score'] >= 70 else "🌱" if s['score'] >= 40 else "⚠️"
                        with st.expander(f"{icon} {s['name']}"):
                            st.write(f"현재가: {int(s['current']):,}원")
                            st.write(f"6개월 고점대비: **{s['extra']:.1f}%**")
                            st.markdown(f"🛒 **매수(60일선 부근):** `{int(s['buy']):,}원`")
                            st.markdown(f"🎯 **목표(6개월 신고가):** `{int(s['target']):,}원`")
                            st.markdown(f"🛑 **추세 손절(120일 이탈):** `{int(s['stop']):,}원`")
                            st.caption(s['desc'])
                            
        st.divider()
        st.subheader("👀 중기 관심 섹터 (4~7위)")
        cols4 = st.columns(4)
        for i in range(3, 7):
            if i < len(top_7_mid):
                row = top_7_mid.iloc[i]
                with cols4[i-3]:
                    st.info(f"**{i+1}위: {row['섹터명']}**")
                    for s in sorted(row['stocks'], key=lambda x: x['score'], reverse=True):
                        icon = "🌱" if s['score'] >= 40 else "⚠️"
                        with st.expander(f"{icon} {s['name']}"):
                            st.markdown(f"🛒 **매수:** `{int(s['buy']):,}원`")
                            st.markdown(f"🎯 **목표:** `{int(s['target']):,}원`")
                            st.caption(s['desc'])

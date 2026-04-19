import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

# 1. 앱 설정
st.set_page_config(page_title="AI 5-Factor & 가격 타점 분석기", layout="wide")
st.title("🤖 AI 퀀트: 주도 섹터 & 매수/매도 타점 분석")
st.caption("5대 핵심 지표를 바탕으로 매수가, 목표가, 손절가를 자동으로 계산합니다.")

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

def calculate_5factor_score(df):
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

@st.cache_data(ttl=3600)
def run_ai_analysis():
    results = []
    names = get_krx_names()
    start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
    
    for name, info in k_sectors.items():
        try:
            etf_df = fdr.DataReader(info['etf'], start_date)
            perf_5d = ((etf_df['Close'].iloc[-1] / etf_df['Close'].iloc[-5]) - 1) * 100
            stock_data = []
            
            for s_code in info['stocks']:
                s_df = calculate_5factor_score(fdr.DataReader(s_code, start_date))
                if s_df.empty: continue
                last = s_df.iloc[-1]
                
                # 1. 가격 타점 계산
                current_price = last['Close']
                ma20 = last['MA20']
                ma60 = last['MA60']
                bb_upper = last['BB_Upper']
                
                # 매수가: 주가가 20일선보다 높으면 20일선 부근에서 대기, 낮으면 현재가부터 분할매수
                buy_price = current_price if current_price <= ma20 else (current_price + ma20) / 2
                # 목표가: 볼린저 밴드 상단
                target_price = bb_upper if bb_upper > current_price else current_price * 1.05
                # 손절가: 60일선 (단, 60일선이 너무 깊으면 현재가의 -5%로 방어)
                stop_loss = max(ma60, current_price * 0.95)

                # 2. AI 스코어 계산
                score = 0
                msg = []
                if last['MA5'] > last['MA20'] > last['MA60']: score += 20; msg.append("이평선 정배열")
                if 50 <= last['RSI'] <= 70: score += 20; msg.append("안정적 에너지")
                if current_price > bb_upper: score += 20; msg.append("밴드 돌파")
                if last['Vol_Ratio'] > 1.5: score += 20; msg.append("수급 폭발")
                if last['MACD'] > last['Signal']: score += 20; msg.append("추세 우상향")
                
                stock_data.append({
                    "name": names.get(s_code, s_code),
                    "current": current_price,
                    "buy": buy_price,
                    "target": target_price,
                    "stop": stop_loss,
                    "score": score,
                    "desc": " | ".join(msg) if msg else "관망"
                })
            results.append({"섹터명": name, "5일수익률": perf_5d, "score": perf_5d + (max([s['score'] for s in stock_data])/10), "stocks": stock_data})
        except: continue
    return pd.DataFrame(results)

# 분석 실행
with st.spinner('Top 7 섹터와 최적의 매매 타점을 계산 중입니다...'):
    analysis_df = run_ai_analysis()

if not analysis_df.empty:
    sorted_df = analysis_df.sort_values(by='score', ascending=False)
    top_7 = sorted_df.head(7)

    st.subheader("🏆 집중 공략 섹터 (1~3위)")
    cols1 = st.columns(3)
    for i in range(3):
        if i < len(top_7):
            row = top_7.iloc[i]
            with cols1[i]:
                st.info(f"### {i+1}위: {row['섹터명']}")
                st.metric("섹터 모멘텀", f"{row['5일수익률']:.2f}%")
                
                for s in sorted(row['stocks'], key=lambda x: x['score'], reverse=True):
                    icon = "🔥" if s['score'] >= 80 else "🟢" if s['score'] >= 60 else "⚪"
                    with st.expander(f"{icon} {s['name']} ({s['score']}점)"):
                        st.write(f"**현재가:** {int(s['current']):,}원")
                        st.write("---")
                        # 가격 가이드 (색상 강조)
                        st.markdown(f"📉 **추천 매수가:** `{int(s['buy']):,}원` 부근")
                        st.markdown(f"🎯 **1차 목표가:** `{int(s['target']):,}원`")
                        st.markdown(f"🛑 **안전 손절가:** `{int(s['stop']):,}원`")
                        st.write("---")
                        st.caption(f"💡 진단: {s['desc']}")

    st.divider()

    st.subheader("🔍 추격 매수 가능 섹터 (4~7위)")
    cols2 = st.columns(4)
    for i in range(3, 7):
        if i < len(top_7):
            row = top_7.iloc[i]
            with cols2[i-3]:
                st.success(f"**{i+1}위: {row['섹터명']}**")
                for s in sorted(row['stocks'], key=lambda x: x['score'], reverse=True):
                    icon = "🟢" if s['score'] >= 60 else "⚪"
                    with st.expander(f"{icon} {s['name']} ({s['score']}점)"):
                        st.markdown(f"**매수:** `{int(s['buy']):,}원`")
                        st.markdown(f"**목표:** `{int(s['target']):,}원`")
                        st.markdown(f"**손절:** `{int(s['stop']):,}원`")
                        st.caption(s['desc'])

    st.divider()
    
    st.warning("⚠️ **투자 유의사항:** 본 앱에서 제시하는 가격 타점은 기술적 지표(이동평균선, 볼린저밴드 등)를 기반으로 한 수학적 계산 값입니다. 실제 투자 시에는 거시 경제 상황과 기업 실적을 함께 고려하시기 바랍니다.")

else:
    st.error("데이터 로드 실패")

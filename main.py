import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import difflib
import google.generativeai as genai
import json
import re

# ───────────────────────────────────────────
# 1. 앱 설정
# ───────────────────────────────────────────
st.set_page_config(page_title="K-증시 실전 매매 비서 V6", page_icon="📡", layout="wide")

st.markdown("""
<style>
    .sector-title-top  { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #38bdf8; border-radius: 10px; padding: 12px; margin-bottom: 12px; text-align: center; color: white; font-weight: bold; font-size: 18px; }
    .sector-title-norm { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 12px; margin-bottom: 12px; text-align: center; color: white; font-weight: bold; font-size: 16px; }
    .normal-card  { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 12px; margin-bottom: 10px; }
    .stock-name   { color: #ffffff; font-weight: bold; font-size: 15px; }
    .price-box    { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-top: 10px; text-align: center; }
    .price-item   { padding: 6px; border-radius: 6px; font-size: 12px; font-weight: bold; }
    .curr   { background: #1e293b; color: #38bdf8; }
    .buy    { background: #064e3b; color: #34d399; }
    .target { background: #78350f; color: #fbbf24; }
    .stop   { background: #7f1d1d; color: #f87171; }

    /* 점수 바 */
    .score-bar-wrap { background:#1e293b; border-radius:4px; height:6px; margin:6px 0; }
    .score-bar-fill { height:6px; border-radius:4px; }

    /* 신호 태그 */
    .sig-tag { display:inline-block; background:#0f2027; border:1px solid #38bdf8; color:#38bdf8; border-radius:12px; padding:2px 8px; font-size:11px; margin:2px; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────
# 2. Gemini 설정
# ───────────────────────────────────────────
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    GEMINI_READY = True
else:
    GEMINI_READY = False

# ───────────────────────────────────────────
# 3. 섹터 데이터
# ───────────────────────────────────────────
k_sectors = {
    "반도체":        {"etf": "091160", "stocks": ["005930", "000660", "042700"]},
    "2차전지소재":   {"etf": "305540", "stocks": ["247540", "391060", "003670"]},
    "2차전지셀":     {"etf": "373550", "stocks": ["373220", "006400", "051910"]},
    "전력설비":      {"etf": "421320", "stocks": ["000880", "050710", "011760"]},
    "방위산업":      {"etf": "381170", "stocks": ["012450", "047810", "272210"]},
    "조선/해운":     {"etf": "445380", "stocks": ["010140", "042660", "010620"]},
    "바이오/의료":   {"etf": "091150", "stocks": ["207940", "068270", "293480"]},
    "로봇":          {"etf": "440760", "stocks": ["433320", "043340", "441270"]},
    "K-뷰티":        {"etf": "228790", "stocks": ["192820", "019170", "131970"]},
    "K-푸드":        {"etf": "429000", "stocks": ["097950", "004370", "005180"]},
    "우주항공":      {"etf": "445380", "stocks": ["012450", "047810", "112190"]},
    "자동차":        {"etf": "091140", "stocks": ["005380", "000270", "012330"]},
    "원자력":        {"etf": "421320", "stocks": ["034020", "030000", "011210"]},
    "은행(밸류업)":  {"etf": "091170", "stocks": ["105560", "055550", "086790"]},
    "증권/보험":     {"etf": "091170", "stocks": ["005830", "000810", "071050"]},
    "가상자산":      {"etf": "417630", "stocks": ["040300", "036710", "060310"]},
    "IT플랫폼":      {"etf": "266370", "stocks": ["035420", "035720", "307950"]},
    "게임":          {"etf": "293400", "stocks": ["251270", "036570", "293490"]},
    "엔터":          {"etf": "227540", "stocks": ["352820", "041510", "035900"]},
    "철강/금속":     {"etf": "117680", "stocks": ["005490", "004020", "016380"]},
}

# ───────────────────────────────────────────
# 4. 날짜 기반 캐싱 유틸
# ───────────────────────────────────────────
def today_str():
    """
    장마감(15:30) 이후면 오늘 날짜, 이전이면 전날 날짜를 반환.
    → 당일 장중/장마감 후 한 번만 API 호출하도록 캐시 키로 활용.
    """
    now = datetime.now()
    cutoff = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if now >= cutoff:
        return now.strftime("%Y-%m-%d")
    else:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")

# ───────────────────────────────────────────
# 5. KRX 종목명 캐싱 (하루 1회)
# ───────────────────────────────────────────
@st.cache_data(ttl=86400)   # 24시간 고정 (종목명은 자주 안 바뀜)
def get_krx_names():
    df = fdr.StockListing('KRX')
    return dict(zip(df['Code'], df['Name']))

# ───────────────────────────────────────────
# 6. 검색 유틸
# ───────────────────────────────────────────
def normalize_string(s):
    if not s: return ""
    s = str(s).lower().replace(" ", "")
    for eng, kor in [("lg","엘지"),("sk","에스케이"),("cj","씨제이"),
                     ("kt","케이티"),("kakao","카카오"),("naver","네이버"),
                     ("pay","페이"),("bank","뱅크"),("cns","씨엔에스")]:
        s = s.replace(eng, kor)
    return s

def smart_search_stock(query, names_dict):
    if query.isdigit() and query in names_dict: return query
    q = normalize_string(query)
    norm = {c: normalize_string(n) for c, n in names_dict.items()}
    for c, n in norm.items():
        if q in n or n in q: return c
    hits = difflib.get_close_matches(q, list(norm.values()), n=1, cutoff=0.5)
    if hits:
        for c, n in norm.items():
            if n == hits[0]: return c
    return None

# ───────────────────────────────────────────
# 7. 기술적 지표 계산
# ───────────────────────────────────────────
def calc_indicators(df):
    df = df.copy()

    # 이동평균 (min_periods로 초반 NaN 최소화)
    df['MA5']   = df['Close'].rolling(5,   min_periods=3).mean()
    df['MA20']  = df['Close'].rolling(20,  min_periods=10).mean()
    df['MA60']  = df['Close'].rolling(60,  min_periods=30).mean()
    df['MA120'] = df['Close'].rolling(120, min_periods=60).mean()

    # RSI
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))

    # 볼린저밴드 (20일)
    std20          = df['Close'].rolling(20, min_periods=10).std()
    df['BB_Upper'] = df['MA20'] + std20 * 2
    df['BB_Lower'] = df['MA20'] - std20 * 2
    df['BB_Pct']   = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'] + 1e-10)

    # MACD (12/26/9)
    ema12           = df['Close'].ewm(span=12, adjust=False).mean()
    ema26           = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD']      = ema12 - ema26
    df['Signal']    = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']

    # 거래량 비율
    df['Vol_Ratio'] = df['Volume'] / (df['Volume'].rolling(20, min_periods=5).mean() + 1e-10)

    # 6개월 고점/저점 (52주 제거 - 데이터 너무 많이 소모)
    df['High_6M'] = df['Close'].rolling(120, min_periods=20).max()
    df['Low_6M']  = df['Close'].rolling(120, min_periods=20).min()

    # 전체 dropna 대신 필수 컬럼만 체크
    required = ['MA5','MA20','MA60','MA120','RSI','BB_Upper','BB_Lower',
                'BB_Pct','MACD','Signal','MACD_Hist','Vol_Ratio','High_6M']
    return df.dropna(subset=required)

# ───────────────────────────────────────────
# 8. 단기 스코어링 (반등 목적에 맞게 전면 재설계)
#
#  핵심 철학: "낙폭이 있고, 반등 신호가 켜진 종목"
#
#  항목              가중치  설명
#  ─────────────────────────────────────────
#  RSI 30~50 구간     30pt   과매도 회복 구간
#  MACD 히스토그램 ↑  25pt   모멘텀 전환 (히스토 상승)
#  BB 하단 20% 이내   20pt   볼밴 하단 근접 = 기술적 지지
#  MA5 > MA20         15pt   단기 골든크로스
#  거래량 1.3x 이상   10pt   수급 뒷받침
#  ─────────────────────────────────────────
#  합계               100pt
# ───────────────────────────────────────────
def score_short(last):
    score   = 0
    signals = []

    rsi = last['RSI']
    if 30 <= rsi <= 50:
        score += 30
        signals.append("RSI 회복")
    elif rsi < 30:
        score += 20   # 극과매도는 오히려 낙폭 지속 가능
        signals.append("RSI 과매도")

    if last['MACD_Hist'] > 0 and last['MACD_Hist'] > last['Signal'] * -0.1:
        score += 25
        signals.append("MACD 전환")

    if last['BB_Pct'] <= 0.20:
        score += 20
        signals.append("볼밴 하단")
    elif last['BB_Pct'] <= 0.35:
        score += 10
        signals.append("볼밴 저위")

    if last['MA5'] > last['MA20']:
        score += 15
        signals.append("단기GC")

    if last['Vol_Ratio'] >= 1.3:
        score += 10
        signals.append("수급↑")

    return score, signals

# ───────────────────────────────────────────
# 9. 중기 스코어링 (추세 반등 목적)
#
#  항목                  가중치  설명
#  ─────────────────────────────────────────
#  고점대비 낙폭 -15% 이상  30pt  충분히 조정됨
#  MA60 위에서 지지         25pt  중기 추세 살아있음
#  MA60 > MA120 (정배열)    20pt  구조적 상승 추세
#  RSI 40~60 회복 구간      15pt  에너지 중립~회복
#  MACD 히스토 상승         10pt  모멘텀 전환 초기
#  ─────────────────────────────────────────
#  합계                    100pt
# ───────────────────────────────────────────
def score_mid(last):
    score   = 0
    signals = []

    drawdown = (last['Close'] - last['High_6M']) / last['High_6M'] * 100
    if drawdown <= -15:
        score += 30
        signals.append(f"낙폭{drawdown:.0f}%")
    elif drawdown <= -8:
        score += 15
        signals.append(f"낙폭{drawdown:.0f}%")

    if last['Close'] > last['MA60']:
        score += 25
        signals.append("60일선↑")

    if last['MA60'] > last['MA120']:
        score += 20
        signals.append("중기정배열")

    rsi = last['RSI']
    if 40 <= rsi <= 60:
        score += 15
        signals.append("RSI중립회복")
    elif 30 <= rsi < 40:
        score += 10
        signals.append("RSI회복중")

    if last['MACD_Hist'] > 0:
        score += 10
        signals.append("MACD전환")

    return score, signals

# ───────────────────────────────────────────
# 10. 매수/익절/손절 계산
# ───────────────────────────────────────────
def calc_trade_levels(last, mode):
    curr = last['Close']

    if mode == "short":
        # 매수: 현재가 또는 BB 하단 중 낮은 쪽 (유리한 진입가)
        buy    = min(curr, last['BB_Lower'] * 1.01)
        # 익절: BB 상단 (단기 오버슈팅 목표), 최소 +4% 보장
        target = last['BB_Upper'] if last['BB_Upper'] > curr * 1.04 else curr * 1.07
        # 손절: 반드시 현재가보다 낮게 — 매수가 -5% 또는 BB 하단 -2% 중 낮은 값
        stop   = min(buy * 0.95, last['BB_Lower'] * 0.98)

    else:  # mid
        # 매수: 60일선 지지 확인 후 진입
        buy    = last['MA60']
        # 익절: 6개월 고점 회복
        # 손절: 120일선 -3%, 단 반드시 현재가보다 낮아야 함
        stop   = min(last['MA120'] * 0.97, curr * 0.95)
        # 익절: 6개월 고점 회복 (원래 가치로 복귀)
        target = last['High_6M']

    return buy, target, stop

# ───────────────────────────────────────────
# 11. 전체 분석 실행 (날짜 기반 캐싱 적용)
# ───────────────────────────────────────────
@st.cache_data(ttl=86400)  # 24시간 상한 (today_str()가 실질 캐시 키)
def run_full_analysis(mode, cache_date):
    """
    cache_date: today_str() 결과를 인자로 받아 캐시 키로 활용.
    장마감(15:30) 전 = 전날 날짜 / 이후 = 오늘 날짜로 자동 구분.
    같은 날짜 내에서는 서버 재호출 없이 캐시 결과 반환.
    """
    results = []
    names   = get_krx_names()
    start   = (datetime.now() - timedelta(days=300)).strftime('%Y-%m-%d')

    for sec, info in k_sectors.items():
        try:
            etf_df = fdr.DataReader(info['etf'], start)
            # ETF 데이터 최소 25일 필요
            if etf_df is None or len(etf_df) < 25:
                continue

            # iloc 접근 전 길이 방어 (데이터 부족 시 가능한 최대 범위 사용)
            n = len(etf_df)
            perf_5d  = ((etf_df['Close'].iloc[-1] / etf_df['Close'].iloc[-min(5,  n-1)]) - 1) * 100
            perf_20d = ((etf_df['Close'].iloc[-1] / etf_df['Close'].iloc[-min(20, n-1)]) - 1) * 100

            stocks = []
            for code in info['stocks']:
                try:
                    raw = fdr.DataReader(code, start)
                    # dropna() 후 데이터 감소를 고려해 여유있게 체크
                    if raw is None or len(raw) < 90:
                        continue
                    df = calc_indicators(raw)
                    # 지표 계산 후 유효 행 재확인
                    if len(df) < 30:
                        continue
                    last = df.iloc[-1]
                    curr = last['Close']

                    if mode == "short":
                        score, signals = score_short(last)
                    else:
                        score, signals = score_mid(last)

                    buy, target, stop = calc_trade_levels(last, mode)
                    # 안전장치: 익절은 반드시 현재가 위, 손절은 반드시 현재가 아래
                    target   = max(target, curr * 1.03)
                    stop     = min(stop,   curr * 0.97)
                    upside   = (target - curr) / curr * 100
                    downside = (stop   - curr) / curr * 100
                    icon = "🔥" if score >= 70 else ("🟢" if score >= 45 else "⚪")

                    stocks.append({
                        "name":     names.get(code, code),
                        "code":     code,
                        "curr":     curr,
                        "buy":      buy,
                        "target":   target,
                        "stop":     stop,
                        "score":    score,
                        "signals":  signals,
                        "icon":     icon,
                        "upside":   upside,
                        "downside": downside,
                        "rsi":      last['RSI'],
                        "perf_5d":  perf_5d,
                    })
                except Exception as e:
                    st.session_state.setdefault("errs", []).append(f"{code}: {e}")

            if stocks:
                # 섹터 점수 = 종목 스코어 평균 + 낙폭 보너스
                avg_score = sum(s['score'] for s in stocks) / len(stocks)
                # 낙폭이 있는 섹터에 가산점 (단기: 5일, 중기: 20일)
                perf_bonus = max(0, -perf_5d * 2) if mode == "short" else max(0, -perf_20d * 1.5)
                final_score = avg_score + perf_bonus

                results.append({
                    "sector":  sec,
                    "perf":    perf_5d,
                    "perf_20": perf_20d,
                    "score":   final_score,
                    "stocks":  stocks,
                })

        except Exception as e:
            st.session_state.setdefault("errs", []).append(f"{sec}: {e}")

    df_out = pd.DataFrame(results)
    if not df_out.empty:
        df_out = df_out.sort_values("score", ascending=False)
    return df_out

# ───────────────────────────────────────────
# 12. 종목 UI 렌더링
# ───────────────────────────────────────────
def render_stock_ui(s):
    sig_html = "".join(f'<span class="sig-tag">{sig}</span>' for sig in s.get('signals', []))
    bar_w    = min(int(s['score']), 100)
    bar_col  = "#56d364" if s['score'] >= 70 else ("#f0883e" if s['score'] >= 45 else "#8b949e")

    st.markdown(f"""
    <div class="normal-card">
        <div class="stock-name">{s['icon']} {s['name']} <span style="font-size:11px;color:#8b949e;">{s['code']}</span></div>
        <div class="score-bar-wrap">
            <div class="score-bar-fill" style="width:{bar_w}%;background:{bar_col};"></div>
        </div>
        <div style="font-size:11px;color:#8b949e;margin-bottom:6px;">반등스코어 {s['score']:.0f}점 &nbsp; RSI {s['rsi']:.1f}</div>
        <div style="margin-bottom:4px;">{sig_html}</div>
        <div class="price-box">
            <div class="price-item curr">현재<br>{int(s['curr']):,}</div>
            <div class="price-item buy">매수<br>{int(s['buy']):,}</div>
            <div class="price-item target">익절<br>{int(s['target']):,}<br><span style="font-size:10px;">(+{s['upside']:.1f}%)</span></div>
            <div class="price-item stop">손절<br>{int(s['stop']):,}<br><span style="font-size:10px;">({s['downside']:.1f}%)</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ───────────────────────────────────────────
# 13. 폴백 지표 해석 (AI 없을 때)
# ───────────────────────────────────────────
def get_fallback_insight(stats):
    curr = float(stats["현재가"].replace("원","").replace(",",""))
    ma60 = float(stats["MA60"].replace("원","").replace(",",""))
    rsi  = float(stats["RSI"])

    trend  = "상승 추세 (60일선 위)" if curr >= ma60 else "하락 추세 (60일선 아래)"
    energy = ("단기 과매수 — 조정 주의" if rsi >= 70
              else "과매도 — 기술적 반등 기대" if rsi <= 30
              else "중립 — 방향성 탐색 중")
    advice = ("추세가 살아있으므로 눌림목 분할 매수 접근이 유효합니다."
              if curr >= ma60
              else "추세가 무너진 상태이므로 하방 지지 확인이 우선입니다.")
    opinion = ("매수 관점" if curr >= ma60 and rsi < 70
               else "관망" if curr < ma60
               else "분할 매도 (수익 실현)")

    return (
        f"⚠️ **시스템 알고리즘 분석 (AI 미연결)**\n\n"
        f"1. 📊 **현재 상황:** 주가는 {trend}이며 에너지는 {energy}입니다.\n"
        f"2. 🎯 **매매 전략:** {advice}\n"
        f"3. 💡 **종합 의견:** {opinion}"
    )

def get_ai_insight(name, stats):
    if not GEMINI_READY:
        return None, "GEMINI_API_KEY가 Secrets에 없습니다."
    try:
        model  = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        prompt = (
            f"한국 주식 전문 애널리스트로서 '{name}'의 지표({str(stats)})를 분석해주세요.\n"
            f"형식:\n"
            f"1. 📊 현재 상황 (1-2줄)\n"
            f"2. 🎯 매수 전략 (1-2줄)\n"
            f"3. ⚠️ 리스크 요인 (1줄)\n"
            f"4. 💡 종합 의견: [강력매수/매수/관망/매도] 중 하나"
        )
        return model.generate_content(prompt).text, None
    except Exception as e:
        return None, str(e)

# ───────────────────────────────────────────
# 14. Top5 추천 (폴백 포함)
# ───────────────────────────────────────────
def get_top5_recs(cached_df):
    """
    Gemini 없을 때: 분석된 섹터 데이터에서
    스코어 상위 종목 4개 + 1위 섹터 ETF 1개를 자동 선정.
    """
    recs = []
    if cached_df.empty:
        return recs

    # 1위 섹터 ETF 추천
    best = cached_df.iloc[0]
    etf_code = k_sectors[best['sector']]['etf']
    recs.append({
        "rank":   1,
        "name":   f"{best['sector']} 섹터 ETF",
        "code":   etf_code,
        "reason": f"반등 스코어 1위 섹터({best['sector']}) 분산 투자. 개별 종목 리스크 최소화.",
    })

    # 나머지 4개: 전체 종목 중 스코어 상위
    all_stocks = []
    for _, row in cached_df.iterrows():
        for s in row['stocks']:
            all_stocks.append({**s, "sector": row['sector']})
    all_stocks = sorted(all_stocks, key=lambda x: x['score'], reverse=True)

    seen = set()
    for s in all_stocks:
        if len(recs) >= 5: break
        if s['code'] in seen: continue
        seen.add(s['code'])
        recs.append({
            "rank":   len(recs) + 1,
            "name":   s['name'],
            "code":   s['code'],
            "reason": f"{s['sector']} 주도주 | 반등스코어 {s['score']:.0f}점 | 신호: {', '.join(s['signals']) if s['signals'] else '없음'}",
        })

    return recs

# ───────────────────────────────────────────
# 15. 탭 UI
# ───────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["⚡ 단기 스윙 Top7", "🌳 중기 추세 Top7", "🔍 AI 종목 & ETF 추천"])

TODAY = today_str()  # 장마감 기준 날짜 (캐시 키)

# ─ 탭1: 단기 ─
with tab1:
    st.header("⚡ 단기 반등 모멘텀 Top 7")
    st.caption(f"기준일: {TODAY}  |  RSI·MACD·볼밴·거래량 복합 스코어링  |  낙폭 섹터 가산점 적용")

    with st.spinner("단기 타점 분석 중... (첫 로딩 후 당일은 캐시 사용)"):
        df_s = run_full_analysis("short", TODAY)

    if df_s.empty:
        st.info("분석 결과가 없습니다.")
    else:
        top3 = df_s.head(3)
        cols_top = st.columns(3)
        for i, (_, row) in enumerate(top3.iterrows()):
            with cols_top[i]:
                st.markdown(f"<div class='sector-title-top'>🏆 {i+1}위: {row['sector']}</div>", unsafe_allow_html=True)
                for s in row['stocks']:
                    render_stock_ui(s)

        st.divider()

        bot4 = df_s.iloc[3:7]
        cols_bot = st.columns(4)
        for i, (_, row) in enumerate(bot4.iterrows()):
            with cols_bot[i]:
                st.markdown(f"<div class='sector-title-norm'>🏅 {i+4}위: {row['sector']}</div>", unsafe_allow_html=True)
                for s in row['stocks']:
                    render_stock_ui(s)

# ─ 탭2: 중기 ─
with tab2:
    st.header("🌳 중기 실적/추세 Top 7")
    st.caption(f"기준일: {TODAY}  |  낙폭·이동평균·RSI·MACD 복합 스코어링  |  60일선 매수 / 120일선 손절")

    with st.spinner("중기 타점 분석 중... (첫 로딩 후 당일은 캐시 사용)"):
        df_m = run_full_analysis("mid", TODAY)

    if df_m.empty:
        st.info("분석 결과가 없습니다.")
    else:
        top3 = df_m.head(3)
        cols_top = st.columns(3)
        for i, (_, row) in enumerate(top3.iterrows()):
            with cols_top[i]:
                st.markdown(f"<div class='sector-title-top'>🏆 {i+1}위: {row['sector']}</div>", unsafe_allow_html=True)
                for s in row['stocks']:
                    render_stock_ui(s)

        st.divider()

        bot4 = df_m.iloc[3:7]
        cols_bot = st.columns(4)
        for i, (_, row) in enumerate(bot4.iterrows()):
            with cols_bot[i]:
                st.markdown(f"<div class='sector-title-norm'>🏅 {i+4}위: {row['sector']}</div>", unsafe_allow_html=True)
                for s in row['stocks']:
                    render_stock_ui(s)

# ─ 탭3: AI 진단 ─
with tab3:
    st.header("🔍 정밀 분석 & 유망 ETF/주식 픽")

    # Top5 추천
    st.subheader("💡 오늘의 단기 유망주 & ETF TOP 5")
    if st.button("🪄 시장 유망 종목 및 ETF 5개 추천받기"):
        with st.spinner("트렌드 분석 중..."):
            recs = None
            if GEMINI_READY:
                try:
                    model  = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
                    prompt = (
                        "한국 주식 시장에서 단기 반등이 기대되는 종목과 관련 ETF를 포함해 5개를 추천해주세요. "
                        "반드시 JSON 형식으로만 답하세요 (코드블록 없이 순수 JSON):\n"
                        '[{"rank":1,"name":"종목명","code":"코드","reason":"이유"},...]'
                    )
                    raw   = model.generate_content(prompt).text
                    clean = re.sub(r'```json|```', '', raw).strip()
                    recs  = json.loads(clean)
                except Exception:
                    recs = None

            # 폴백: 자체 알고리즘
            if not recs:
                st.warning("⚠️ AI 미연결 — 자체 퀀트 알고리즘으로 선정합니다.")
                cached = run_full_analysis("short", TODAY)
                recs   = get_top5_recs(cached)

        if recs:
            cols = st.columns(5)
            for idx, r in enumerate(recs[:5]):
                with cols[idx]:
                    st.success(f"**{r['name']}**")
                    st.caption(r['code'])
                    st.write(f"_{r['reason']}_")

    st.divider()

    # 개별 종목 진단
    st.subheader("📊 개별 종목 정밀 진단")
    query = st.text_input("분석할 종목명 또는 코드:", placeholder="예: 삼성전자, 카카오, 005930")

    if query:
        names_dict  = get_krx_names()
        target_code = smart_search_stock(query, names_dict)

        if not target_code:
            st.error(f"'{query}' 종목을 찾을 수 없습니다.")
        else:
            stock_name = names_dict[target_code]
            if query not in (stock_name, target_code):
                st.success(f"💡 '{query}' → **'{stock_name}'** 으로 분석합니다.")

            with st.spinner(f"'{stock_name}' 데이터 분석 중..."):
                start  = (datetime.now() - timedelta(days=300)).strftime('%Y-%m-%d')
                raw_df = fdr.DataReader(target_code, start)

            if len(raw_df) < 130:
                st.error("상장 기간이 짧거나 데이터가 부족합니다.")
            else:
                df   = calc_indicators(raw_df)
                last = df.iloc[-1]
                curr = last['Close']

                buy, target, stop = calc_trade_levels(last, "short")
                upside   = (target - curr) / curr * 100
                downside = (stop   - curr) / curr * 100

                s_data = {
                    "name":     stock_name,
                    "code":     target_code,
                    "curr":     curr,
                    "buy":      buy,
                    "target":   target,
                    "stop":     stop,
                    "score":    score_short(last)[0],
                    "signals":  score_short(last)[1],
                    "icon":     "🔍",
                    "upside":   upside,
                    "downside": downside,
                    "rsi":      last['RSI'],
                    "perf_5d":  0,
                }

                stats = {
                    "현재가": f"{int(curr):,}원",
                    "RSI":    f"{last['RSI']:.1f}",
                    "MA20":   f"{int(last['MA20']):,}원",
                    "MA60":   f"{int(last['MA60']):,}원",
                    "MA120":  f"{int(last['MA120']):,}원",
                    "볼밴위치": f"{last['BB_Pct']*100:.0f}%",
                    "MACD":   f"{last['MACD']:.3f}",
                    "거래량비율": f"{last['Vol_Ratio']:.2f}x",
                }

                col1, col2 = st.columns([1, 1.2])
                with col1:
                    st.subheader(f"📈 {stock_name} 매매 가이드")
                    render_stock_ui(s_data)
                    st.write(f"**RSI:** {stats['RSI']}  |  **볼밴위치:** {stats['볼밴위치']}  |  **거래량비율:** {stats['거래량비율']}")
                    st.write(f"**MA20:** {stats['MA20']}  |  **MA60:** {stats['MA60']}  |  **MA120:** {stats['MA120']}")

                with col2:
                    st.subheader("🤖 종목 인사이트 리포트")
                    with st.spinner("Gemini AI 분석 중..."):
                        ai_text, ai_err = get_ai_insight(stock_name, stats)
                    if ai_text:
                        st.info(ai_text)
                    else:
                        # 에러 원인을 화면에 표시 후 폴백 분석 제공
                        st.warning(f"⚠️ AI 연결 실패: {ai_err}")
                        st.info(get_fallback_insight(stats))

# ───────────────────────────────────────────
# 16. 에러 로그
# ───────────────────────────────────────────
errs = st.session_state.get("errs", [])
if errs:
    with st.expander(f"⚠️ 수집 실패 항목 ({len(errs)}건)", expanded=False):
        for e in errs[-20:]:
            st.text(e)

st.divider()
st.markdown(
    "<p style='text-align:center;color:#484f58;font-size:12px;'>"
    "⚠️ 본 앱은 투자 참고용입니다. 투자 판단과 책임은 본인에게 있습니다."
    "</p>",
    unsafe_allow_html=True
)

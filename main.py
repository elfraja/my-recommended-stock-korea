import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import difflib
import google.generativeai as genai

# ───────────────────────────────────────────
# 1. 앱 설정
# ───────────────────────────────────────────
st.set_page_config(
    page_title="K-증시 반등 레이더",
    page_icon="📡",
    layout="wide"
)

# 커스텀 CSS
st.markdown("""
<style>
    /* 전체 배경 */
    .stApp { background-color: #0d1117; color: #e6edf3; }

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #161b22;
        border-radius: 12px;
        padding: 4px;
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #8b949e;
        font-weight: 600;
        font-size: 15px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f6feb !important;
        color: white !important;
    }

    /* 섹터 카드 */
    .sector-card {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        border: 1px solid #30363d;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        transition: border-color 0.2s;
    }
    .sector-card:hover { border-color: #1f6feb; }

    /* 섹터 헤더 */
    .sector-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 14px;
    }
    .sector-title {
        font-size: 18px;
        font-weight: 700;
        color: #e6edf3;
    }

    /* 점수 배지 */
    .badge-high   { background:#1a7f37; color:#56d364; padding:4px 12px; border-radius:20px; font-weight:700; font-size:13px; }
    .badge-mid    { background:#7d4e00; color:#f0883e; padding:4px 12px; border-radius:20px; font-weight:700; font-size:13px; }
    .badge-low    { background:#3d1f1f; color:#f85149; padding:4px 12px; border-radius:20px; font-weight:700; font-size:13px; }

    /* 수익률 칩 */
    .chip-up   { background:#1a3a2a; color:#56d364; padding:3px 10px; border-radius:12px; font-size:13px; font-weight:600; }
    .chip-down { background:#3d1f1f; color:#f85149; padding:3px 10px; border-radius:12px; font-size:13px; font-weight:600; }

    /* 종목 행 */
    .stock-row {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .stock-name { font-weight: 600; font-size: 15px; color: #e6edf3; }
    .stock-price { font-size: 18px; font-weight: 700; color: #58a6ff; }
    .stock-label { font-size: 11px; color: #8b949e; margin-bottom: 2px; }
    .stock-value { font-size: 13px; font-weight: 600; }
    .val-buy    { color: #56d364; }
    .val-target { color: #f0883e; }
    .val-stop   { color: #f85149; }

    /* AI 결과 박스 */
    .ai-box {
        background: linear-gradient(135deg, #0d1f35 0%, #0d2a1e 100%);
        border: 1px solid #1f6feb;
        border-radius: 16px;
        padding: 24px;
        margin-top: 16px;
    }
    .ai-title { color: #58a6ff; font-size: 16px; font-weight: 700; margin-bottom: 12px; }

    /* 지표 그리드 */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        margin: 12px 0;
    }
    .metric-item {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 12px;
        text-align: center;
    }
    .metric-label { font-size: 11px; color: #8b949e; margin-bottom: 4px; }
    .metric-value { font-size: 18px; font-weight: 700; color: #e6edf3; }

    /* 로딩 */
    .stSpinner > div { border-top-color: #1f6feb !important; }

    /* expander 숨기기 (커스텀 카드 사용) */
    .streamlit-expanderHeader { display: none !important; }

    h1 { color: #e6edf3 !important; }
    .stTextInput input { background: #161b22; color: #e6edf3; border-color: #30363d; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 📡 K-증시 반등 레이더")
st.markdown("<p style='color:#8b949e;margin-top:-10px;'>낙폭 섹터에서 반등 가능 종목을 탐색합니다</p>", unsafe_allow_html=True)
st.divider()

# ───────────────────────────────────────────
# 2. Gemini API 설정
# ───────────────────────────────────────────
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("⚠️ Streamlit Secrets에 GEMINI_API_KEY를 설정해주세요.")

# ───────────────────────────────────────────
# 3. 섹터 데이터 (ETF 코드 수정 포함)
# ───────────────────────────────────────────
k_sectors = {
    "반도체":         {"etf": "091160", "stocks": ["005930", "000660", "042700"]},
    "2차전지소재":    {"etf": "305540", "stocks": ["247540", "391060", "003670"]},  # ✅ ETF 수정
    "2차전지셀":      {"etf": "373550", "stocks": ["373220", "006400", "051910"]},
    "전력설비":       {"etf": "421320", "stocks": ["000880", "050710", "011760"]},
    "방위산업":       {"etf": "381170", "stocks": ["012450", "047810", "272210"]},
    "조선/해운":      {"etf": "445380", "stocks": ["010140", "042660", "010620"]},
    "바이오/의료":    {"etf": "091150", "stocks": ["207940", "068270", "293480"]},
    "로봇":           {"etf": "440760", "stocks": ["433320", "043340", "441270"]},
    "K-뷰티":         {"etf": "228790", "stocks": ["192820", "019170", "131970"]},
    "K-푸드":         {"etf": "429000", "stocks": ["097950", "004370", "005180"]},
    "자동차":         {"etf": "091140", "stocks": ["005380", "000270", "012330"]},
    "원자력":         {"etf": "421320", "stocks": ["034020", "030000", "011210"]},
    "은행":           {"etf": "091170", "stocks": ["105560", "055550", "086790"]},
    "증권/보험":      {"etf": "091170", "stocks": ["005830", "000810", "071050"]},
    "IT플랫폼":       {"etf": "266370", "stocks": ["035420", "035720", "307950"]},
    "게임":           {"etf": "293400", "stocks": ["251270", "036570", "293490"]},
    "엔터":           {"etf": "227540", "stocks": ["352820", "041510", "035900"]},
    "철강/금속":      {"etf": "117680", "stocks": ["005490", "004020", "016380"]},
}

# 섹터 아이콘
SECTOR_ICONS = {
    "반도체": "💾", "2차전지소재": "🔋", "2차전지셀": "⚡",
    "전력설비": "🔌", "방위산업": "🛡️", "조선/해운": "🚢",
    "바이오/의료": "🧬", "로봇": "🤖", "K-뷰티": "💄",
    "K-푸드": "🍜", "자동차": "🚗", "원자력": "☢️",
    "은행": "🏦", "증권/보험": "📊", "IT플랫폼": "🌐",
    "게임": "🎮", "엔터": "🎤", "철강/금속": "⚙️",
}

# ───────────────────────────────────────────
# 4. 유틸 함수
# ───────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_krx_names():
    df = fdr.StockListing('KRX')
    return dict(zip(df['Code'], df['Name']))

def normalize_string(s):
    if not s: return ""
    s = str(s).lower().replace(" ", "")
    replace_dict = {
        "lg": "엘지", "sk": "에스케이", "cj": "씨제이",
        "kt": "케이티", "kakao": "카카오", "naver": "네이버",
        "pay": "페이", "bank": "뱅크", "cns": "씨엔에스"
    }
    for eng, kor in replace_dict.items():
        s = s.replace(eng, kor)
    return s

def smart_search_stock(query, names_dict):
    if query.isdigit() and query in names_dict:
        return query
    query_norm = normalize_string(query)
    norm_dict = {code: normalize_string(name) for code, name in names_dict.items()}
    for code, norm_name in norm_dict.items():
        if query_norm in norm_name or norm_name in query_norm:
            return code
    all_norm_names = list(norm_dict.values())
    closest = difflib.get_close_matches(query_norm, all_norm_names, n=1, cutoff=0.5)
    if closest:
        for code, norm_name in norm_dict.items():
            if norm_name == closest[0]:
                return code
    return None

def score_badge(score):
    if score >= 70:
        return f'<span class="badge-high">🟢 강력 {score:.0f}점</span>'
    elif score >= 40:
        return f'<span class="badge-mid">🟡 보통 {score:.0f}점</span>'
    else:
        return f'<span class="badge-low">🔴 약세 {score:.0f}점</span>'

def perf_chip(val):
    if val >= 0:
        return f'<span class="chip-up">▲ +{val:.1f}%</span>'
    else:
        return f'<span class="chip-down">▼ {val:.1f}%</span>'

# ───────────────────────────────────────────
# 5. 기술적 지표 계산
# ───────────────────────────────────────────
def calc_short_term_factors(df):
    df = df.copy()
    df['MA5']  = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()

    # RSI (14일)
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))

    # 볼린저밴드 (상단 + 하단 모두)
    df['STD20']    = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['MA20'] + df['STD20'] * 2
    df['BB_Lower'] = df['MA20'] - df['STD20'] * 2   # ✅ 하단 추가

    # 거래량 비율
    df['Vol_Ratio'] = df['Volume'] / (df['Volume'].rolling(20).mean() + 1e-10)

    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD']   = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    return df.dropna()

def calc_mid_term_factors(df):
    df = df.copy()
    df['MA20']  = df['Close'].rolling(20).mean()
    df['MA60']  = df['Close'].rolling(60).mean()
    df['MA120'] = df['Close'].rolling(120).mean()
    df['High_6M'] = df['Close'].rolling(120).max()
    df['Low_6M']  = df['Close'].rolling(120).min()

    # RSI도 추가 (중기에도 활용)
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))

    return df.dropna()

# ───────────────────────────────────────────
# 6. 분석 실행 (낙폭 섹터 필터 포함)
# ───────────────────────────────────────────
@st.cache_data(ttl=3600)
def run_analysis(mode):
    results = []
    names = get_krx_names()
    days    = 120 if mode == "short" else 300
    start   = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    for sec_name, info in k_sectors.items():
        try:
            etf_df = fdr.DataReader(info['etf'], start)
            if len(etf_df) < 10:
                continue

            perf_5d  = ((etf_df['Close'].iloc[-1] / etf_df['Close'].iloc[-5])  - 1) * 100
            perf_20d = ((etf_df['Close'].iloc[-1] / etf_df['Close'].iloc[-20]) - 1) * 100

            # ✅ 핵심 필터: 낙폭이 있는 섹터만 선별
            # 단기: 5일 -1% 이하 / 중기: 20일 -3% 이하
            if mode == "short" and perf_5d > -1.0:
                continue
            if mode == "mid"   and perf_20d > -3.0:
                continue

            stock_data = []
            for s_code in info['stocks']:
                try:
                    raw_df = fdr.DataReader(s_code, start)
                    min_bars = 70 if mode == "short" else 140
                    if len(raw_df) < min_bars:
                        continue

                    if mode == "short":
                        s_df = calc_short_term_factors(raw_df)
                        if s_df.empty:
                            continue
                        last    = s_df.iloc[-1]
                        current = last['Close']

                        # 매수/목표/손절 계산
                        buy_price    = current
                        target_price = last['BB_Upper'] if last['BB_Upper'] > current * 1.03 else current * 1.07
                        stop_loss    = max(last['BB_Lower'], last['MA60'], current * 0.95)

                        # ✅ 반등 목적에 맞는 스코어링
                        score = 0
                        signals = []
                        if 30 <= last['RSI'] <= 55:             # 과매도 회복 구간
                            score += 30
                            signals.append("🟢 RSI 과매도 회복")
                        if last['MA5'] > last['MA20']:           # 단기 반등 시작
                            score += 25
                            signals.append("📈 단기 골든크로스")
                        if last['MACD'] > last['Signal']:        # 모멘텀 전환
                            score += 25
                            signals.append("⚡ MACD 상향전환")
                        if current <= last['BB_Lower'] * 1.03:  # 볼밴 하단 근접
                            score += 20
                            signals.append("📉 볼밴 하단 반등")

                        extra = {"drawdown": None, "rsi": last['RSI'],
                                 "macd_gap": last['MACD'] - last['Signal'],
                                 "vol_ratio": last['Vol_Ratio'], "signals": signals}

                    else:  # mid
                        s_df = calc_mid_term_factors(raw_df)
                        if s_df.empty:
                            continue
                        last    = s_df.iloc[-1]
                        current = last['Close']
                        ma60, ma120, high6m = last['MA60'], last['MA120'], last['High_6M']
                        drawdown = ((current - high6m) / high6m) * 100

                        buy_price    = ma60
                        target_price = high6m
                        stop_loss    = ma120 * 0.95

                        score   = 0
                        signals = []
                        if current > ma60:
                            score += 30
                            signals.append("📈 60일선 위")
                        if ma60 > ma120:
                            score += 25
                            signals.append("🟢 중기 골든크로스")
                        if drawdown < -15:
                            score += 25
                            signals.append(f"📉 고점대비 {drawdown:.1f}%")
                        if 30 <= last['RSI'] <= 55:
                            score += 20
                            signals.append("⚡ RSI 회복 중")

                        extra = {"drawdown": drawdown, "rsi": last['RSI'],
                                 "macd_gap": None, "vol_ratio": None, "signals": signals}

                    stock_data.append({
                        "code":    s_code,
                        "name":    names.get(s_code, s_code),
                        "current": current,
                        "buy":     buy_price,
                        "target":  target_price,
                        "stop":    stop_loss,
                        "score":   score,
                        "extra":   extra,
                    })

                except Exception as e:
                    st.session_state.setdefault("errors", []).append(f"{s_code}: {e}")
                    continue

            if stock_data:
                sector_score = sum(s['score'] for s in stock_data) / len(stock_data)
                results.append({
                    "섹터명":    sec_name,
                    "5일수익률": perf_5d,
                    "20일수익률": perf_20d,
                    "score":     sector_score,
                    "stocks":    stock_data,
                })

        except Exception as e:
            st.session_state.setdefault("errors", []).append(f"{sec_name}: {e}")
            continue

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values('score', ascending=False)
    return df

# ───────────────────────────────────────────
# 7. AI 인사이트
# ───────────────────────────────────────────
def get_ai_insight(name, data_summary):
    try:
        model  = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""당신은 한국 주식 전문 애널리스트입니다.
종목명: {name}
기술적 지표:
{data_summary}

위 지표를 바탕으로 아래 형식으로 분석해주세요:
1. 📊 현재 상황 (1-2줄)
2. 🎯 매수 전략 (1-2줄)
3. ⚠️ 리스크 요인 (1줄)
4. 💡 종합 의견: [강력매수 / 매수 / 관망 / 매도] 중 하나로 답변
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 분석 실패: {str(e)}"

# ───────────────────────────────────────────
# 8. 섹터 카드 렌더링
# ───────────────────────────────────────────
def render_sector_card(row, mode):
    icon      = SECTOR_ICONS.get(row['섹터명'], "📌")
    perf_key  = '5일수익률' if mode == "short" else '20일수익률'
    perf_val  = row[perf_key]
    perf_label = "5일" if mode == "short" else "20일"

    st.markdown(f"""
    <div class="sector-card">
        <div class="sector-header">
            <span class="sector-title">{icon} {row['섹터명']}</span>
            <span style="display:flex;gap:8px;align-items:center;">
                {perf_chip(perf_val)}&nbsp;{perf_label}
                &nbsp;&nbsp;
                {score_badge(row['score'])}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    for s in row['stocks']:
        upside = ((s['target'] - s['current']) / s['current']) * 100

        # 종목 신호 아이콘
        signal_html = " ".join(s['extra']['signals']) if s['extra']['signals'] else "—"

        # RSI 아이콘
        rsi = s['extra']['rsi']
        rsi_icon = "🔥" if rsi < 30 else ("✅" if rsi < 50 else ("⚠️" if rsi < 70 else "🚨"))

        # 업사이드 아이콘
        up_icon  = "🚀" if upside > 15 else ("📈" if upside > 7 else "➡️")

        st.markdown(f"""
        <div class="stock-row">
            <div>
                <div class="stock-name">🏢 {s['name']}</div>
                <div style="margin-top:6px;font-size:12px;color:#8b949e;">{signal_html}</div>
            </div>
            <div style="display:flex;gap:24px;align-items:center;">
                <div style="text-align:center;">
                    <div class="stock-label">현재가</div>
                    <div class="stock-price">{int(s['current']):,}원</div>
                </div>
                <div style="text-align:center;">
                    <div class="stock-label">💚 매수가</div>
                    <div class="stock-value val-buy">{int(s['buy']):,}원</div>
                </div>
                <div style="text-align:center;">
                    <div class="stock-label">{up_icon} 목표가</div>
                    <div class="stock-value val-target">{int(s['target']):,}원 (+{upside:.1f}%)</div>
                </div>
                <div style="text-align:center;">
                    <div class="stock-label">🛑 손절가</div>
                    <div class="stock-value val-stop">{int(s['stop']):,}원</div>
                </div>
                <div style="text-align:center;">
                    <div class="stock-label">{rsi_icon} RSI</div>
                    <div class="stock-value" style="color:#c9d1d9;">{rsi:.1f}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ───────────────────────────────────────────
# 9. 탭 UI
# ───────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["⚡ 단기 반등 (스윙)", "🌳 중기 추세 반등", "🔍 AI 종목 정밀 진단"])

# ─ 탭1: 단기 ─
with tab1:
    st.markdown("### ⚡ 단기 반등 레이더")
    st.markdown("<p style='color:#8b949e;font-size:13px;'>5일 수익률 -1% 이하 섹터 중 RSI·MACD·볼린저밴드 기반 반등 신호 탐지</p>", unsafe_allow_html=True)

    if st.button("🔄 단기 분석 시작", key="btn_short", use_container_width=True):
        with st.spinner("📡 데이터 수집 중... (약 1~2분 소요)"):
            short_df = run_analysis("short")

        if short_df.empty:
            st.info("📭 현재 낙폭이 두드러진 섹터가 없습니다. 기준(-1%)을 완화하거나 내일 다시 확인해보세요.")
        else:
            st.success(f"✅ {len(short_df)}개 섹터에서 반등 후보 발견!")
            for _, row in short_df.iterrows():
                render_sector_card(row, "short")
    else:
        st.info("👆 버튼을 눌러 분석을 시작하세요.")

# ─ 탭2: 중기 ─
with tab2:
    st.markdown("### 🌳 중기 추세 반등 레이더")
    st.markdown("<p style='color:#8b949e;font-size:13px;'>20일 수익률 -3% 이하 섹터 중 이동평균·고점대비 낙폭 기반 반등 후보 탐색</p>", unsafe_allow_html=True)

    if st.button("🔄 중기 분석 시작", key="btn_mid", use_container_width=True):
        with st.spinner("📡 데이터 수집 중... (약 1~2분 소요)"):
            mid_df = run_analysis("mid")

        if mid_df.empty:
            st.info("📭 현재 낙폭이 두드러진 섹터가 없습니다.")
        else:
            st.success(f"✅ {len(mid_df)}개 섹터에서 반등 후보 발견!")
            for _, row in mid_df.iterrows():
                render_sector_card(row, "mid")
    else:
        st.info("👆 버튼을 눌러 분석을 시작하세요.")

# ─ 탭3: AI 진단 ─
with tab3:
    st.markdown("### 🔍 AI 개별 종목 정밀 진단")
    st.markdown("<p style='color:#8b949e;font-size:13px;'>Gemini AI가 기술적 지표를 종합해 매매 전략을 제안합니다</p>", unsafe_allow_html=True)

    query = st.text_input(
        "종목명 또는 종목코드 입력",
        placeholder="예: 삼성전자, 카카오, 005930",
        label_visibility="collapsed"
    )

    if query:
        names_dict = get_krx_names()
        code = smart_search_stock(query, names_dict)

        if not code:
            st.error(f"❌ '{query}'에 해당하는 종목을 찾지 못했습니다.")
        else:
            stock_name = names_dict.get(code, code)
            st.markdown(f"**🏢 {stock_name}** `{code}` 분석 중...")

            with st.spinner("📊 지표 계산 중..."):
                df = fdr.DataReader(code, (datetime.now() - timedelta(days=300)).strftime('%Y-%m-%d'))

            if len(df) < 100:
                st.warning("⚠️ 데이터가 부족합니다.")
            else:
                df = calc_short_term_factors(df)
                last    = df.iloc[-1]
                current = last['Close']

                # 지표 그리드
                rsi_icon  = "🔥" if last['RSI'] < 30 else ("✅" if last['RSI'] < 50 else ("⚠️" if last['RSI'] < 70 else "🚨"))
                macd_icon = "📈" if last['MACD'] > last['Signal'] else "📉"
                bb_pct    = (current - last['BB_Lower']) / (last['BB_Upper'] - last['BB_Lower'] + 1e-10) * 100
                bb_icon   = "🟢" if bb_pct < 20 else ("🟡" if bb_pct < 80 else "🔴")
                vol_icon  = "🔊" if last['Vol_Ratio'] > 1.5 else ("🔉" if last['Vol_Ratio'] > 0.8 else "🔇")
                ma_icon   = "📈" if last['MA5'] > last['MA20'] else "📉"

                st.markdown(f"""
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-label">현재가</div>
                        <div class="metric-value" style="color:#58a6ff;">{int(current):,}원</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">{rsi_icon} RSI</div>
                        <div class="metric-value">{last['RSI']:.1f}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">{macd_icon} MACD</div>
                        <div class="metric-value">{last['MACD']:.2f}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">{bb_icon} 볼밴 위치</div>
                        <div class="metric-value">{bb_pct:.0f}%</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">{vol_icon} 거래량비율</div>
                        <div class="metric-value">{last['Vol_Ratio']:.2f}x</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">{ma_icon} MA5/MA20</div>
                        <div class="metric-value" style="font-size:13px;">
                            {int(last['MA5']):,} / {int(last['MA20']):,}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # AI 분석
                st.markdown("#### 🤖 Gemini AI 매매 전략")
                with st.spinner("🧠 AI 분석 중..."):
                    summary = f"""
현재가: {current:,.0f}원
RSI: {last['RSI']:.1f} (30이하=과매도, 70이상=과매수)
MACD: {last['MACD']:.3f} / Signal: {last['Signal']:.3f} ({'상향돌파' if last['MACD'] > last['Signal'] else '하향돌파'})
볼린저밴드: 상단 {last['BB_Upper']:,.0f} / 하단 {last['BB_Lower']:,.0f} / 현재 위치 {bb_pct:.0f}%
5일선: {last['MA5']:,.0f} / 20일선: {last['MA20']:,.0f} / 60일선: {last['MA60']:,.0f}
거래량: 20일 평균 대비 {last['Vol_Ratio']:.2f}배
"""
                    ai_result = get_ai_insight(stock_name, summary)

                st.markdown(f"""
                <div class="ai-box">
                    <div class="ai-title">🤖 {stock_name} AI 분석 리포트</div>
                    <div style="color:#c9d1d9;line-height:1.8;white-space:pre-line;">{ai_result}</div>
                </div>
                """, unsafe_allow_html=True)

# ───────────────────────────────────────────
# 10. 에러 로그 (디버깅용, 접어두기)
# ───────────────────────────────────────────
errors = st.session_state.get("errors", [])
if errors:
    with st.expander(f"⚠️ 수집 실패 항목 ({len(errors)}건)", expanded=False):
        for e in errors[-20:]:
            st.text(e)

# 하단 안내
st.divider()
st.markdown(
    "<p style='text-align:center;color:#484f58;font-size:12px;'>"
    "⚠️ 본 앱은 투자 참고용입니다. 투자 판단과 책임은 본인에게 있습니다."
    "</p>",
    unsafe_allow_html=True
)

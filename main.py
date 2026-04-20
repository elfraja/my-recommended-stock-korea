import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import difflib

# Gemini는 선택사항
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ───────────────────────────────────────────
# 1. 앱 설정
# ───────────────────────────────────────────
st.set_page_config(
    page_title="K-증시 반등 레이더",
    page_icon="📡",
    layout="wide"
)

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
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
    .sector-card {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        border: 1px solid #30363d;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
    }
    .sector-title { font-size: 18px; font-weight: 700; color: #e6edf3; }
    .badge-high { background:#1a7f37; color:#56d364; padding:4px 12px; border-radius:20px; font-weight:700; font-size:13px; }
    .badge-mid  { background:#7d4e00; color:#f0883e; padding:4px 12px; border-radius:20px; font-weight:700; font-size:13px; }
    .badge-low  { background:#3d1f1f; color:#f85149; padding:4px 12px; border-radius:20px; font-weight:700; font-size:13px; }
    .chip-up    { background:#1a3a2a; color:#56d364; padding:3px 10px; border-radius:12px; font-size:13px; font-weight:600; }
    .chip-down  { background:#3d1f1f; color:#f85149; padding:3px 10px; border-radius:12px; font-size:13px; font-weight:600; }

    /* 종목 카드 */
    .stock-card {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 10px;
    }
    .stock-name { font-weight: 700; font-size: 16px; color: #e6edf3; margin-bottom: 10px; }

    /* 매매 가이드 바 */
    .trade-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        margin: 10px 0 8px 0;
    }
    .trade-item {
        border-radius: 8px;
        padding: 10px 8px;
        text-align: center;
    }
    .trade-label { font-size: 11px; margin-bottom: 4px; font-weight: 600; }
    .trade-value { font-size: 15px; font-weight: 700; }
    .t-current { background:#1a2233; border:1px solid #30363d; }
    .t-current .trade-label { color:#8b949e; }
    .t-current .trade-value { color:#58a6ff; }
    .t-buy    { background:#0d2a1a; border:1px solid #238636; }
    .t-buy    .trade-label { color:#56d364; }
    .t-buy    .trade-value { color:#56d364; }
    .t-target { background:#2a1f0d; border:1px solid #b87d00; }
    .t-target .trade-label { color:#f0883e; }
    .t-target .trade-value { color:#f0883e; }
    .t-stop   { background:#2a0d0d; border:1px solid #da3633; }
    .t-stop   .trade-label { color:#f85149; }
    .t-stop   .trade-value { color:#f85149; }

    /* 지표 그리드 */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        margin: 10px 0;
    }
    .metric-item {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
    }
    .metric-label { font-size: 11px; color: #8b949e; margin-bottom: 3px; }
    .metric-value { font-size: 16px; font-weight: 700; color: #e6edf3; }

    /* AI 박스 */
    .ai-box {
        background: linear-gradient(135deg, #0d1f35 0%, #0d2a1e 100%);
        border: 1px solid #1f6feb;
        border-radius: 16px;
        padding: 20px;
        margin-top: 12px;
    }
    .ai-title { color: #58a6ff; font-size: 16px; font-weight: 700; margin-bottom: 12px; }

    /* 지표 설명 카드 */
    .indicator-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 10px;
    }
    .indicator-title { font-size: 15px; font-weight: 700; color: #58a6ff; margin-bottom: 8px; }
    .indicator-desc  { font-size: 13px; color: #c9d1d9; line-height: 1.7; }
    .indicator-tip   { font-size: 12px; color: #8b949e; margin-top: 6px; }

    /* 추천주 카드 */
    .rec-card {
        background: linear-gradient(135deg, #0d1f35 0%, #161b22 100%);
        border: 1px solid #1f6feb;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 10px;
    }
    .rec-rank  { font-size: 20px; font-weight: 900; color: #f0883e; margin-right: 8px; }
    .rec-name  { font-size: 16px; font-weight: 700; color: #e6edf3; }
    .rec-reason { font-size: 13px; color: #c9d1d9; margin-top: 8px; line-height: 1.6; }

    h1 { color: #e6edf3 !important; }
    .stTextInput input { background: #161b22 !important; color: #e6edf3 !important; border-color: #30363d !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 📡 K-증시 반등 레이더")
st.markdown("<p style='color:#8b949e;margin-top:-10px;'>낙폭 섹터에서 반등 가능 종목을 탐색합니다</p>", unsafe_allow_html=True)
st.divider()

# ───────────────────────────────────────────
# 2. Gemini API 설정
# ───────────────────────────────────────────
GEMINI_READY = False
if GEMINI_AVAILABLE:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            GEMINI_READY = True
        else:
            st.warning("⚠️ Streamlit Secrets에 GEMINI_API_KEY를 설정하면 AI 분석이 활성화됩니다.")
    except Exception:
        pass

# ───────────────────────────────────────────
# 3. 섹터 & 아이콘
# ───────────────────────────────────────────
k_sectors = {
    "반도체":      {"etf": "091160", "stocks": ["005930", "000660", "042700"]},
    "2차전지소재": {"etf": "305540", "stocks": ["247540", "391060", "003670"]},
    "2차전지셀":   {"etf": "373550", "stocks": ["373220", "006400", "051910"]},
    "전력설비":    {"etf": "421320", "stocks": ["000880", "050710", "011760"]},
    "방위산업":    {"etf": "381170", "stocks": ["012450", "047810", "272210"]},
    "조선/해운":   {"etf": "445380", "stocks": ["010140", "042660", "010620"]},
    "바이오/의료": {"etf": "091150", "stocks": ["207940", "068270", "293480"]},
    "로봇":        {"etf": "440760", "stocks": ["433320", "043340", "441270"]},
    "K-뷰티":      {"etf": "228790", "stocks": ["192820", "019170", "131970"]},
    "K-푸드":      {"etf": "429000", "stocks": ["097950", "004370", "005180"]},
    "자동차":      {"etf": "091140", "stocks": ["005380", "000270", "012330"]},
    "원자력":      {"etf": "421320", "stocks": ["034020", "030000", "011210"]},
    "은행":        {"etf": "091170", "stocks": ["105560", "055550", "086790"]},
    "증권/보험":   {"etf": "091170", "stocks": ["005830", "000810", "071050"]},
    "IT플랫폼":    {"etf": "266370", "stocks": ["035420", "035720", "307950"]},
    "게임":        {"etf": "293400", "stocks": ["251270", "036570", "293490"]},
    "엔터":        {"etf": "227540", "stocks": ["352820", "041510", "035900"]},
    "철강/금속":   {"etf": "117680", "stocks": ["005490", "004020", "016380"]},
}

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
    if not s:
        return ""
    s = str(s).lower().replace(" ", "")
    for eng, kor in [("lg","엘지"),("sk","에스케이"),("cj","씨제이"),
                     ("kt","케이티"),("kakao","카카오"),("naver","네이버"),
                     ("pay","페이"),("bank","뱅크"),("cns","씨엔에스")]:
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
    closest = difflib.get_close_matches(query_norm, list(norm_dict.values()), n=1, cutoff=0.5)
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

def rsi_icon(rsi):
    if rsi < 30:   return "🔥"
    if rsi < 50:   return "✅"
    if rsi < 70:   return "⚠️"
    return "🚨"

def upside_icon(pct):
    if pct > 15:  return "🚀"
    if pct > 7:   return "📈"
    return "➡️"

# ───────────────────────────────────────────
# 5. 기술적 지표 계산
# ───────────────────────────────────────────
def calc_short_term_factors(df):
    df = df.copy()
    df['MA5']  = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI']      = 100 - (100 / (1 + gain / (loss + 1e-10)))
    df['STD20']    = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['MA20'] + df['STD20'] * 2
    df['BB_Lower'] = df['MA20'] - df['STD20'] * 2
    df['Vol_Ratio'] = df['Volume'] / (df['Volume'].rolling(20).mean() + 1e-10)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD']   = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    return df.dropna()

def calc_mid_term_factors(df):
    df = df.copy()
    df['MA20']    = df['Close'].rolling(20).mean()
    df['MA60']    = df['Close'].rolling(60).mean()
    df['MA120']   = df['Close'].rolling(120).mean()
    df['High_6M'] = df['Close'].rolling(120).max()
    df['Low_6M']  = df['Close'].rolling(120).min()
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
    return df.dropna()

# ───────────────────────────────────────────
# 6. 분석 실행
# ───────────────────────────────────────────
@st.cache_data(ttl=3600)
def run_analysis(mode):
    results = []
    names = get_krx_names()
    days  = 120 if mode == "short" else 300
    start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    for sec_name, info in k_sectors.items():
        try:
            etf_df = fdr.DataReader(info['etf'], start)
            if len(etf_df) < 10:
                continue
            perf_5d  = ((etf_df['Close'].iloc[-1] / etf_df['Close'].iloc[-5])  - 1) * 100
            perf_20d = ((etf_df['Close'].iloc[-1] / etf_df['Close'].iloc[-20]) - 1) * 100

            stock_data = []
            for s_code in info['stocks']:
                try:
                    raw_df   = fdr.DataReader(s_code, start)
                    min_bars = 70 if mode == "short" else 140
                    if len(raw_df) < min_bars:
                        continue

                    if mode == "short":
                        s_df = calc_short_term_factors(raw_df)
                        if s_df.empty:
                            continue
                        last    = s_df.iloc[-1]
                        current = last['Close']

                        buy_price    = current
                        target_price = last['BB_Upper'] if last['BB_Upper'] > current * 1.03 else current * 1.07
                        stop_loss    = max(last['BB_Lower'], last['MA60'], current * 0.95)

                        score   = 0
                        signals = []
                        if 30 <= last['RSI'] <= 55:
                            score += 30
                            signals.append("🟢 RSI 과매도 회복")
                        if last['MA5'] > last['MA20']:
                            score += 25
                            signals.append("📈 단기 골든크로스")
                        if last['MACD'] > last['Signal']:
                            score += 25
                            signals.append("⚡ MACD 상향전환")
                        if current <= last['BB_Lower'] * 1.03:
                            score += 20
                            signals.append("📉 볼밴 하단 반등")

                        extra = {
                            "rsi": last['RSI'],
                            "macd": last['MACD'],
                            "signal_line": last['Signal'],
                            "bb_upper": last['BB_Upper'],
                            "bb_lower": last['BB_Lower'],
                            "vol_ratio": last['Vol_Ratio'],
                            "ma5": last['MA5'],
                            "ma20": last['MA20'],
                            "ma60": last['MA60'],
                            "drawdown": None,
                            "signals": signals,
                        }

                    else:
                        s_df = calc_mid_term_factors(raw_df)
                        if s_df.empty:
                            continue
                        last     = s_df.iloc[-1]
                        current  = last['Close']
                        ma60     = last['MA60']
                        ma120    = last['MA120']
                        high6m   = last['High_6M']
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

                        extra = {
                            "rsi": last['RSI'],
                            "macd": None,
                            "signal_line": None,
                            "bb_upper": None,
                            "bb_lower": None,
                            "vol_ratio": None,
                            "ma5": None,
                            "ma20": last['MA20'],
                            "ma60": ma60,
                            "ma60_val": ma60,
                            "ma120": ma120,
                            "drawdown": drawdown,
                            "signals": signals,
                        }

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

            if stock_data:
                sector_score = sum(s['score'] for s in stock_data) / len(stock_data)
                results.append({
                    "섹터명":     sec_name,
                    "5일수익률":  perf_5d,
                    "20일수익률": perf_20d,
                    "score":      sector_score,
                    "stocks":     stock_data,
                })

        except Exception as e:
            st.session_state.setdefault("errors", []).append(f"{sec_name}: {e}")

    df = pd.DataFrame(results)
    if not df.empty:
        perf_col = "5일수익률" if mode == "short" else "20일수익률"
        df = df.sort_values(["score", perf_col], ascending=[False, True])
    return df

# ───────────────────────────────────────────
# 7. 매매 가이드 렌더링 (공통)
# ───────────────────────────────────────────
def render_trade_guide(current, buy, target, stop):
    upside  = ((target - current) / current) * 100
    downside = ((stop - current) / current) * 100
    u_icon  = upside_icon(upside)
    st.markdown(f"""
    <div class="trade-grid">
        <div class="trade-item t-current">
            <div class="trade-label">💰 현재가</div>
            <div class="trade-value">{int(current):,}원</div>
        </div>
        <div class="trade-item t-buy">
            <div class="trade-label">💚 매수가</div>
            <div class="trade-value">{int(buy):,}원</div>
        </div>
        <div class="trade-item t-target">
            <div class="trade-label">{u_icon} 익절가</div>
            <div class="trade-value">{int(target):,}원<br><span style="font-size:11px;">(+{upside:.1f}%)</span></div>
        </div>
        <div class="trade-item t-stop">
            <div class="trade-label">🛑 손절가</div>
            <div class="trade-value">{int(stop):,}원<br><span style="font-size:11px;">({downside:.1f}%)</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ───────────────────────────────────────────
# 8. 섹터 카드 렌더링
# ───────────────────────────────────────────
def render_sector_card(row, mode):
    icon       = SECTOR_ICONS.get(row['섹터명'], "📌")
    perf_key   = "5일수익률" if mode == "short" else "20일수익률"
    perf_val   = row[perf_key]
    perf_label = "5일" if mode == "short" else "20일"

    st.markdown(f"""
    <div class="sector-card">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
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
        ri    = s['extra']['rsi']
        signal_html = " ".join(s['extra']['signals']) if s['extra']['signals'] else "신호 없음"

        st.markdown(f"""
        <div class="stock-card">
            <div class="stock-name">🏢 {s['name']} &nbsp;<span style="font-size:12px;color:#8b949e;">{s['code']}</span></div>
            <div style="font-size:12px;color:#8b949e;margin-bottom:8px;">{signal_html} &nbsp; {rsi_icon(ri)} RSI {ri:.1f}</div>
        </div>
        """, unsafe_allow_html=True)

        render_trade_guide(s['current'], s['buy'], s['target'], s['stop'])

# ───────────────────────────────────────────
# 9. AI 인사이트 (Gemini)
# ───────────────────────────────────────────
def get_ai_insight(name, summary):
    if not GEMINI_READY:
        return None
    try:
        model  = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""당신은 한국 주식 전문 애널리스트입니다.
종목명: {name}
기술적 지표:
{summary}

아래 형식으로 분석해주세요:
1. 📊 현재 상황 (1-2줄)
2. 🎯 매수 전략 (1-2줄)
3. ⚠️ 리스크 요인 (1줄)
4. 💡 종합 의견: [강력매수 / 매수 / 관망 / 매도] 중 하나"""
        return model.generate_content(prompt).text
    except Exception as e:
        return None

def get_ai_recommendations(name, summary):
    if not GEMINI_READY:
        return None
    try:
        model  = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""당신은 한국 주식 전문 애널리스트입니다.
사용자가 {name}에 관심 있습니다.
현재 지표: {summary}

이 종목과 유사하거나 대안이 될 수 있는 한국 상장 주식 5개를 추천해주세요.
반드시 아래 JSON 형식으로만 답하세요 (다른 텍스트 없이):
[
  {{"rank":1,"name":"종목명","code":"종목코드","reason":"추천 이유 1-2줄"}},
  {{"rank":2,"name":"종목명","code":"종목코드","reason":"추천 이유 1-2줄"}},
  {{"rank":3,"name":"종목명","code":"종목코드","reason":"추천 이유 1-2줄"}},
  {{"rank":4,"name":"종목명","code":"종목코드","reason":"추천 이유 1-2줄"}},
  {{"rank":5,"name":"종목명","code":"종목코드","reason":"추천 이유 1-2줄"}}
]"""
        import json, re
        raw  = model.generate_content(prompt).text
        clean = re.sub(r'```json|```', '', raw).strip()
        return json.loads(clean)
    except Exception:
        return None

# ───────────────────────────────────────────
# 10. 지표 설명 (Gemini 없을 때 폴백)
# ───────────────────────────────────────────
def render_indicator_explanation(last, current, bb_pct):
    rsi_val  = last['RSI']
    macd_val = last['MACD']
    sig_val  = last['Signal']
    vol_val  = last['Vol_Ratio']

    # RSI 해석
    if rsi_val < 30:
        rsi_interp = "🔥 과매도 구간 — 강한 반등 가능성이 높습니다."
        rsi_color  = "#f85149"
    elif rsi_val < 50:
        rsi_interp = "✅ 회복 진입 구간 — 저점 이탈 후 반등 신호입니다."
        rsi_color  = "#56d364"
    elif rsi_val < 70:
        rsi_interp = "⚠️ 중립 구간 — 추세 확인 후 진입을 권장합니다."
        rsi_color  = "#f0883e"
    else:
        rsi_interp = "🚨 과매수 구간 — 단기 조정 가능성이 있습니다."
        rsi_color  = "#f85149"

    # MACD 해석
    if macd_val > sig_val:
        macd_interp = "📈 MACD가 Signal선 위 — 상승 모멘텀이 살아있습니다."
    else:
        macd_interp = "📉 MACD가 Signal선 아래 — 하락 모멘텀이 우세합니다."

    # 볼린저밴드 해석
    if bb_pct < 20:
        bb_interp = "🟢 하단 근처 — 과매도 반등 구간입니다. 매수 우위."
    elif bb_pct > 80:
        bb_interp = "🔴 상단 근처 — 과매수 구간입니다. 익절 검토."
    else:
        bb_interp = "🟡 중간 구간 — 추가 신호 확인 후 판단하세요."

    # 거래량 해석
    if vol_val > 2.0:
        vol_interp = "🔊 급등 거래량 — 강한 수급 신호입니다."
    elif vol_val > 1.3:
        vol_interp = "🔉 평균 이상 거래량 — 매수세 유입 중입니다."
    else:
        vol_interp = "🔇 거래량 저조 — 수급 관망 상태입니다."

    st.markdown("""
    <div style="margin-top:16px;">
        <p style="color:#58a6ff;font-weight:700;font-size:15px;">📖 주요 지표 해석</p>
    </div>
    """, unsafe_allow_html=True)

    indicators = [
        {
            "title": f"RSI (상대강도지수)  {rsi_val:.1f}",
            "desc": rsi_interp,
            "tip": "RSI 30 이하 = 과매도(매수 고려) / 70 이상 = 과매수(익절 고려)",
        },
        {
            "title": f"MACD  {macd_val:.3f} / Signal  {sig_val:.3f}",
            "desc": macd_interp,
            "tip": "MACD > Signal 골든크로스 = 상승전환 신호",
        },
        {
            "title": f"볼린저밴드 위치  {bb_pct:.0f}%",
            "desc": bb_interp,
            "tip": "0% = 하단(과매도) / 100% = 상단(과매수)",
        },
        {
            "title": f"거래량 비율  {vol_val:.2f}x",
            "desc": vol_interp,
            "tip": "1.0 = 평균 / 2.0 이상 = 급등 수급",
        },
    ]

    for ind in indicators:
        st.markdown(f"""
        <div class="indicator-card">
            <div class="indicator-title">📌 {ind['title']}</div>
            <div class="indicator-desc">{ind['desc']}</div>
            <div class="indicator-tip">💡 {ind['tip']}</div>
        </div>
        """, unsafe_allow_html=True)

# ───────────────────────────────────────────
# 11. 탭 UI
# ───────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["⚡ 단기 반등 (스윙)", "🌳 중기 추세 반등", "🔍 AI 종목 정밀 진단"])

# ─ 탭1: 단기 ─
with tab1:
    st.markdown("### ⚡ 단기 반등 레이더")
    st.markdown("<p style='color:#8b949e;font-size:13px;'>전체 섹터를 반등 스코어 + 낙폭 순으로 정렬 — RSI·MACD·볼린저밴드 기반</p>", unsafe_allow_html=True)

    if st.button("🔄 단기 분석 시작", key="btn_short", use_container_width=True):
        with st.spinner("📡 데이터 수집 중... (약 1~2분 소요)"):
            short_df = run_analysis("short")
        if short_df.empty:
            st.info("📭 분석 결과가 없습니다. 잠시 후 다시 시도해주세요.")
        else:
            st.success(f"✅ {len(short_df)}개 섹터 분석 완료!")
            for _, row in short_df.iterrows():
                render_sector_card(row, "short")
    else:
        st.info("👆 버튼을 눌러 분석을 시작하세요.")

# ─ 탭2: 중기 ─
with tab2:
    st.markdown("### 🌳 중기 추세 반등 레이더")
    st.markdown("<p style='color:#8b949e;font-size:13px;'>전체 섹터를 반등 스코어 + 낙폭 순으로 정렬 — 이동평균·고점대비 낙폭 기반</p>", unsafe_allow_html=True)

    if st.button("🔄 중기 분석 시작", key="btn_mid", use_container_width=True):
        with st.spinner("📡 데이터 수집 중... (약 1~2분 소요)"):
            mid_df = run_analysis("mid")
        if mid_df.empty:
            st.info("📭 분석 결과가 없습니다. 잠시 후 다시 시도해주세요.")
        else:
            st.success(f"✅ {len(mid_df)}개 섹터 분석 완료!")
            for _, row in mid_df.iterrows():
                render_sector_card(row, "mid")
    else:
        st.info("👆 버튼을 눌러 분석을 시작하세요.")

# ─ 탭3: AI 진단 ─
with tab3:
    st.markdown("### 🔍 AI 개별 종목 정밀 진단")
    st.markdown("<p style='color:#8b949e;font-size:13px;'>종목명 또는 코드 입력 → 지표 해석 + AI 매매 전략 + 추천주 5선</p>", unsafe_allow_html=True)

    query = st.text_input(
        "종목 검색",
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
            st.markdown(f"<p style='color:#8b949e;'>🏢 <b style='color:#e6edf3;'>{stock_name}</b> ({code}) 분석 중...</p>", unsafe_allow_html=True)

            with st.spinner("📊 데이터 수집 및 지표 계산 중..."):
                raw = fdr.DataReader(code, (datetime.now() - timedelta(days=300)).strftime('%Y-%m-%d'))

            if len(raw) < 100:
                st.warning("⚠️ 데이터가 부족합니다.")
            else:
                df      = calc_short_term_factors(raw)
                last    = df.iloc[-1]
                current = last['Close']
                bb_pct  = (current - last['BB_Lower']) / (last['BB_Upper'] - last['BB_Lower'] + 1e-10) * 100

                # 매매 가이드
                buy_price    = current
                target_price = last['BB_Upper'] if last['BB_Upper'] > current * 1.03 else current * 1.07
                stop_loss    = max(last['BB_Lower'], last['MA60'], current * 0.95)

                st.markdown("#### 💰 매매 가이드")
                render_trade_guide(current, buy_price, target_price, stop_loss)

                # 지표 그리드
                macd_icon_str = "📈" if last['MACD'] > last['Signal'] else "📉"
                bb_icon_str   = "🟢" if bb_pct < 20 else ("🟡" if bb_pct < 80 else "🔴")
                vol_icon_str  = "🔊" if last['Vol_Ratio'] > 1.5 else ("🔉" if last['Vol_Ratio'] > 0.8 else "🔇")

                st.markdown(f"""
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-label">{rsi_icon(last['RSI'])} RSI</div>
                        <div class="metric-value">{last['RSI']:.1f}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">{macd_icon_str} MACD</div>
                        <div class="metric-value">{last['MACD']:.2f}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">{bb_icon_str} 볼밴 위치</div>
                        <div class="metric-value">{bb_pct:.0f}%</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">{vol_icon_str} 거래량비율</div>
                        <div class="metric-value">{last['Vol_Ratio']:.2f}x</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">📊 MA5/MA20</div>
                        <div class="metric-value" style="font-size:13px;">{int(last['MA5']):,} / {int(last['MA20']):,}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">📊 MA60</div>
                        <div class="metric-value" style="font-size:13px;">{int(last['MA60']):,}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                summary = f"""현재가: {current:,.0f}원 / RSI: {last['RSI']:.1f} / MACD: {last['MACD']:.3f} / Signal: {last['Signal']:.3f} / 볼밴위치: {bb_pct:.0f}% / 거래량비율: {last['Vol_Ratio']:.2f}x / MA5: {last['MA5']:,.0f} / MA20: {last['MA20']:,.0f} / MA60: {last['MA60']:,.0f}"""

                # AI 분석 OR 지표 설명
                st.markdown("#### 🤖 AI 매매 전략")
                if GEMINI_READY:
                    with st.spinner("🧠 Gemini AI 분석 중..."):
                        ai_result = get_ai_insight(stock_name, summary)
                    if ai_result:
                        st.markdown(f"""
                        <div class="ai-box">
                            <div class="ai-title">🤖 {stock_name} AI 분석 리포트</div>
                            <div style="color:#c9d1d9;line-height:1.8;white-space:pre-line;">{ai_result}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # AI 실패 시 지표 설명으로 폴백
                        st.warning("⚠️ AI 분석에 실패했습니다. 지표 해석으로 대체합니다.")
                        render_indicator_explanation(last, current, bb_pct)
                else:
                    # Gemini 없으면 지표 설명 표시
                    render_indicator_explanation(last, current, bb_pct)

                # 추천주 5선
                st.markdown("#### ⭐ 연관 추천주 5선")
                if GEMINI_READY:
                    with st.spinner("🔍 추천 종목 탐색 중..."):
                        recs = get_ai_recommendations(stock_name, summary)
                    if recs:
                        for r in recs:
                            st.markdown(f"""
                            <div class="rec-card">
                                <span class="rec-rank">#{r['rank']}</span>
                                <span class="rec-name">{r['name']}</span>
                                <span style="font-size:12px;color:#8b949e;margin-left:8px;">{r['code']}</span>
                                <div class="rec-reason">💬 {r['reason']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("추천 종목을 가져오지 못했습니다.")
                else:
                    st.info("💡 Gemini API 키를 설정하면 AI 기반 추천주 5선이 활성화됩니다.")

# ───────────────────────────────────────────
# 12. 에러 로그
# ───────────────────────────────────────────
errors = st.session_state.get("errors", [])
if errors:
    with st.expander(f"⚠️ 수집 실패 항목 ({len(errors)}건)", expanded=False):
        for e in errors[-20:]:
            st.text(e)

st.divider()
st.markdown(
    "<p style='text-align:center;color:#484f58;font-size:12px;'>"
    "⚠️ 본 앱은 투자 참고용입니다. 투자 판단과 책임은 본인에게 있습니다."
    "</p>",
    unsafe_allow_html=True
)

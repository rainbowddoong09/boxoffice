import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="FUTURE CINEMA | KOBIS DASHBOARD",
    page_icon="⚡",
    layout="wide"
)

# ---------------------------------------------------------
# 커스텀 CSS (SF / 사이버펑크 네온 테마)
# ---------------------------------------------------------
custom_css = """
<style>
    /* 배경 및 기본 폰트 색상 */
    .stApp {
        background-color: #0b0e14;
        color: #e0e6ed;
    }
    
    /* SF 스타일 Title */
    .futuristic-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00f3ff, #ff007f);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 15px rgba(0, 243, 255, 0.4);
        margin-bottom: 0px;
    }
    
    .futuristic-sub {
        color: #8892b0;
        font-family: monospace;
        letter-spacing: 2px;
        font-size: 0.9rem;
        margin-bottom: 25px;
    }

    /* 1위 영화 글래스모피즘 네온 카드 */
    .hero-card {
        background: rgba(16, 23, 38, 0.7);
        border: 1px solid rgba(0, 243, 255, 0.3);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 243, 255, 0.1);
        backdrop-filter: blur(8px);
        margin-bottom: 25px;
    }

    .hero-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff;
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
    }

    /* Metric 커스텀 styling */
    div[data-testid="stMetricValue"] {
        font-family: monospace;
        color: #00f3ff !important;
        font-size: 1.8rem !important;
        text-shadow: 0 0 8px rgba(0, 243, 255, 0.6);
    }
    
    /* Divider 스타일 */
    hr {
        border-color: rgba(0, 243, 255, 0.2) !important;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# 헤더 영역
st.markdown('<div class="futuristic-title">⚡ KOBIS BOXOFFICE SYSTEM</div>', unsafe_allow_html=True)
st.markdown('<div class="futuristic-sub">[ REAL-TIME CINEMATIC DATA MONITOR ]</div>', unsafe_allow_html=True)

# 1. API 키 확인
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.info("Streamlit Secrets에 `KOBIS_KEY`를 추가해 주세요.")
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 2. 날짜 선택기
kst_timezone = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst_timezone)
max_selectable_date = (now_kst - datetime.timedelta(days=1)).date()

selected_date = st.date_input(
    label="📡 DATA TARGET DATE",
    value=max_selectable_date,
    max_value=max_selectable_date
)

target_dt_str = selected_date.strftime("%Y%m%d")
formatted_date = selected_date.strftime("%Y.%m.%d")

# 3. KOBIS API 데이터 요청
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {"key": api_key, "targetDt": target_dt_str}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException:
    st.error("📡 NETWORK ERROR: 통신 장애가 발생했습니다.")
    st.stop()

# 4. 에러 처리
if "faultInfo" in data:
    st.error(f"❌ SYSTEM ERROR: {data['faultInfo'].get('message', '알 수 없는 오류')}")
    st.stop()

boxoffice_result = data.get("boxOfficeResult", {})
daily_list = boxoffice_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ DATA PENDING: 해당 날짜는 아직 집계 데이터가 수집되지 않았습니다.")
    st.stop()

# 5. 데이터 전처리
df = pd.DataFrame(daily_list)
numeric_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

df["displayMovieNm"] = df.apply(
    lambda r: f"{r['movieNm']} 🏆" if r["audiAcc"] >= 1_000_000 else r["movieNm"], axis=1
)

def format_rank_change(inten):
    if inten > 0:
        return f"🔺 +{inten}"
    elif inten < 0:
        return f"🔹 {inten}"
    return "-"

df["rankChange"] = df["rankInten"].apply(format_rank_change)

# 6. 1위 영화 네온 커스텀 카드
top_movie = df.iloc[0]

st.markdown(
    f"""
    <div class="hero-card">
        <div style="color: #ff007f; font-weight: bold; letter-spacing: 1px; font-family: monospace;">TOP RANKED MOVIE OF {formatted_date}</div>
        <div class="hero-title">🥇 {top_movie['displayMovieNm']}</div>
    </div>
    """,
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3)
col1.metric("당일 관객수", f"{top_movie['audiCnt']:,} 명")
col2.metric("누적 관객수", f"{top_movie['audiAcc']:,} 명")
col3.metric("스크린수", f"{top_movie['scrnCnt']:,} 개")

st.markdown("<br>", unsafe_allow_html=True)

# 7. 탭(Tab) 기반 인터페이스
tab1, tab2 = st.tabs(["📋 순위 보드 (RANKING BOARD)", "📊 관객 분석 (ANALYTICS)"])

with tab1:
    display_df = df[["rank", "rankChange", "displayMovieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
    display_df.columns = ["순위", "변동", "영화명", "개봉일", "당일 관객수", "누적 관객수", "스크린수"]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "당일 관객수": st.column_config.NumberColumn(format="%d명"),
            "누적 관객수": st.column_config.NumberColumn(format="%d명"),
            "스크린수": st.column_config.NumberColumn(format="%d개"),
        }
    )

with tab2:
    st.subheader("TOP 5 관객수 점유율")
    top5_df = df.head(5)
    st.bar_chart(data=top5_df, x="movieNm", y="audiCnt")

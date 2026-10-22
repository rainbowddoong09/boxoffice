import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

st.set_page_config(page_title="일별 박스오피스", page_icon="🎬", layout="wide")
st.title("🎬 일별 박스오피스 조회")

# 1. API 키 확인
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.info("Streamlit Secrets(App settings > Secrets)에 `KOBIS_KEY`를 추가해 주세요.")
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 2. 한국 시간 기준 날짜 선택 (최대 '어제'까지)
kst_timezone = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst_timezone)
max_selectable_date = (now_kst - datetime.timedelta(days=1)).date()

selected_date = st.date_input(
    label="📅 조회할 날짜를 선택하세요 (오늘 날짜는 집계 전입니다)",
    value=max_selectable_date,
    max_value=max_selectable_date
)

target_dt_str = selected_date.strftime("%Y%m%d")
formatted_date = selected_date.strftime("%Y년 %m월 %d일")

# 3. KOBIS API 데이터 요청
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {"key": api_key, "targetDt": target_dt_str}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException:
    st.error("📡 API 서버와의 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
    st.stop()

# 4. 에러 및 예외 처리
if "faultInfo" in data:
    st.error(f"❌ API 오류: {data['faultInfo'].get('message', '알 수 없는 오류')}")
    st.info("KOBIS_KEY가 올바른지 KOBIS 개발자 센터에서 확인해 주세요.")
    st.stop()

boxoffice_result = data.get("boxOfficeResult", {})
daily_list = boxoffice_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("그날은 아직 집계 전입니다")
    st.stop()

# 5. 데이터 전처리 (트로피 및 순위 증감 가공)
df = pd.DataFrame(daily_list)
numeric_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 100만 관객 이상 🏆 표기
df["displayMovieNm"] = df.apply(
    lambda r: f"{r['movieNm']} 🏆" if r["audiAcc"] >= 1_000_000 else r["movieNm"], axis=1
)

# 순위 증감 화살표 표기
def format_rank_change(inten):
    if inten > 0:
        return f"🔺 +{inten}"
    elif inten < 0:
        return f"🔹 {inten}"
    return "-"

df["rankChange"] = df["rankInten"].apply(format_rank_change)

# 6. 1위 영화 핵심 지표
top_movie = df.iloc[0]
st.subheader(f"🥇 {formatted_date} 1위: {top_movie['displayMovieNm']}")

col1, col2, col3 = st.columns(3)
col1.metric("당일 관객수", f"{top_movie['audiCnt']:,} 명")
col2.metric("누적 관객수", f"{top_movie['audiAcc']:,} 명")
col3.metric("스크린수", f"{top_movie['scrnCnt']:,} 개")

st.divider()

# 7. 관객수 상위 5편 막대그래프
st.subheader("📊 관객수 상위 5개 영화")
st.bar_chart(data=df.head(5), x="movieNm", y="audiCnt")

st.divider()

# 8. 전체 순위 표 출력
st.subheader(f"📋 {formatted_date} 박스오피스 순위")
display_df = df[["rank", "rankChange", "displayMovieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "순위 변동", "영화명", "개봉일", "당일 관객수", "누적 관객수", "스크린수"]

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

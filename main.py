import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="일별 박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스 조회")


# ---------------------------------------------------------
# 1. secrets에서 API 인증키 불러오기
# ---------------------------------------------------------
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.info(
        "Streamlit Cloud의 **App settings > Secrets** 메뉴에서 아래와 같이 인증키를 추가해 주세요.\n\n"
        "```toml\n"
        'KOBIS_KEY = "발급받은_KOBIS_키_입력"\n'
        "```"
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]


# ---------------------------------------------------------
# 2. 날짜 선택기 (가장 늦은 날짜는 한국 시간 기준 '어제')
# ---------------------------------------------------------
# 한국 시간(KST) 기준 어제 날짜 계산
kst_timezone = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst_timezone)
max_selectable_date = (now_kst - datetime.timedelta(days=1)).date()

# 달력 위젯 생성 (기본값: 어제, 선택 가능한 최대 날짜: 어제)
selected_date = st.date_input(
    label="📅 조회할 날짜를 선택하세요 (오늘 날짜는 아직 집계 전입니다)",
    value=max_selectable_date,
    max_value=max_selectable_date
)

target_dt_str = selected_date.strftime("%Y%m%d")      # API 요청용 (예: 20261020)
formatted_date = selected_date.strftime("%Y년 %m월 %d일")  # 화면 표시용


# ---------------------------------------------------------
# 3. KOBIS API 데이터 요청하기
# ---------------------------------------------------------
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_dt_str
}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException:
    st.error("📡 API 서버와의 통신 중 오류가 발생했습니다.")
    st.info(
        "- 인터넷 연결 상태를 확인해 주세요.\n"
        "- KOBIS OpenAPI 서버가 점검 중이거나 일시적 장애일 수 있습니다."
    )
    st.stop()


# ---------------------------------------------------------
# 4. API 응답 에러 및 예외 케이스 처리
# ---------------------------------------------------------
# [케이스 1] 인증키 오류 등으로 faultInfo 상자가 반환된 경우
if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 오류")
    st.error(f"❌ KOBIS API 오류가 발생했습니다: {fault_msg}")
    st.info(
        "💡 **확인해 주세요**\n"
        "1. Streamlit Secrets에 입력한 `KOBIS_KEY`가 올바른지 확인해 주세요.\n"
        "2. KOBIS 개발자 센터(www.kobis.or.kr/kobisopenapi)에서 키가 승인되었는지 확인해 주세요."
    )
    st.stop()

# [케이스 2] 정상 응답 구조가 없거나 영화 데이터 목록이 비어 있는 경우
boxoffice_result = data.get("boxOfficeResult", {})
daily_list = boxoffice_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("그날은 아직 집계 전입니다")
    st.stop()


# ---------------------------------------------------------
# 5. 데이터 전처리 (숫자 변환, 트로피 및 순위 증감 가공)
# ---------------------------------------------------------
df = pd.DataFrame(daily_list)

# 문자열 데이터를 정수형(int)으로 변환
numeric_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 1. 누적관객 100만 명 이상 영화 이름 옆에 트로피(🏆) 이모지 추가
def format_movie_name(row):
    name = row["movieNm"]
    if row["audiAcc"] >= 1_000_000:
        return f"{name} 🏆"
    return name

df["displayMovieNm"] = df.apply(format_movie_name, axis=1)

# 2. 순위 증감(rankInten) 화살표 기호 매핑
def format_rank_change(inten):
    if inten > 0:
        return f"🔺 +{inten}"  # 빨간 위 화살표 (상승)
    elif inten < 0:
        return f"🔹 {inten}"   # 파란 아래 화살표 (하강)
    else:
        return "-"            # 변동 없음

df["rankChange"] = df["rankInten"].apply(format_rank_change)


# ---------------------------------------------------------
# 6. 1위 영화 핵심 지표 (Metrics)
# ---------------------------------------------------------
top_movie = df.iloc[0]

st.subheader(f"🥇 {formatted_date} 1위: {top_movie['displayMovieNm']}")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        label="당일 관객수",
        value=f"{top_movie['audiCnt']:,} 명"
    )
with col2:
    st.metric(
        label="누적 관객수",
        value=f"{top_movie['audiAcc']:,} 명"
    )
with col3:
    st.metric(
        label="스크린수",
        value=f"{top_movie['scrnCnt']:,} 개"
    )

st.divider()


# ---------------------------------------------------------
# 7. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5개 영화")

top5_df = df.head(5)

st.bar_chart(
    data=top5_df,
    x="movieNm",
    y="audiCnt"
)

st.divider()


# ---------------------------------------------------------
# 8. 전체 순위 표 (Table) 출력
# ---------------------------------------------------------
st.subheader(f"📋 {formatted_date} 박스오피스 순위")

# 보여줄 컬럼 선택 및 이름 변경
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

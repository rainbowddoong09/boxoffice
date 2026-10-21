import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 타이틀
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="어제 박스오피스 순위",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제 일별 박스오피스 순위")

# -----------------------------------------------------------------------------
# 2. 날짜 및 API Key 설정
# -----------------------------------------------------------------------------
# 배포 서버가 해외에 있어도 정확한 한국 시간(Asia/Seoul) 기준으로 날짜를 계산합니다.
korea_tz = pytz.timezone('Asia/Seoul')
korea_now = datetime.datetime.now(korea_tz)
yesterday = korea_now - datetime.timedelta(days=1)
target_date_str = yesterday.strftime("%Y%m%d")  # YYYYMMDD 형식으로 변환

st.caption(f"📅 기준일자(어제): **{yesterday.strftime('%Y년 %m월 %d일')}** (한국 시간 기준)")

# Streamlit Cloud 비밀금고(Secrets)에서 KOBIS_KEY 가져오기
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 키가 설정되지 않았습니다.")
    st.info("""
    **해결 방법:**
    1. Streamlit Cloud 설정(Settings) -> **Secrets** 메뉴로 이동하세요.
    2. 아래와 같이 KOBIS 인증키를 등록해주세요:
       ```toml
       KOBIS_KEY = "발급받은_인증키_입력"
       ```
    """)
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# -----------------------------------------------------------------------------
# 3. KOBIS API 데이터 호출 함수 (캐시 적용)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)  # 1시간 동안 API 호출 결과를 저장(캐싱)
def get_box_office_data(key, target_dt):
    url = "http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": key,
        "targetDt": target_dt
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # HTTP status code가 200이 아닐 경우 예외 발생
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"네트워크 통신 오류가 발생했습니다: {e}"

# API 호출 실행
data, error_msg = get_box_office_data(api_key, target_date_str)

# -----------------------------------------------------------------------------
# 4. 예외 및 오류 처리
# -----------------------------------------------------------------------------
if error_msg:
    st.error(f"❌ 데이터 요청 실패")
    st.info(f"**확인 사항:** 인터넷 연결 상태를 확인해주시거나, KOBIS 서버 응답 상태를 확인해주세요.\n\n*상세 오류: {error_msg}*")
    st.stop()

# KOBIS API는 키가 잘못되어도 200 OK를 응답하고 내부에 'faultInfo'를 전달합니다.
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("❌ KOBIS API 오류가 발생했습니다.")
    st.warning(f"**오류 메시지:** {fault.get('message', '알 수 없는 오류')}")
    st.info("""
    **확인해야 할 사항:**
    1. Streamlit Secrets에 입력한 `KOBIS_KEY` 값이 정확한지 확인해 주세요.
    2. KOBIS 영화관입장권통합전산망 오픈API 사이트에서 인증키가 활성화 상태인지 확인해 주세요.
    """)
    st.stop()

# 정상 응답 내 박스오피스 결과 검증
boxoffice_result = data.get("boxOfficeResult", {})
daily_list = boxoffice_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ 어제자 일별 박스오피스 데이터가 존재하지 않습니다.")
    st.info("""
    **확인해야 할 사항:**
    1. 집계 시각 문제일 수 있습니다. (보통 새벽/아침 시간대에는 전날 집계가 진행 중일 수 있습니다)
    2. 조회된 날짜가 올바른지 확인해 주세요.
    """)
    st.stop()

# -----------------------------------------------------------------------------
# 5. 데이터 가공 (문자열 -> 숫자 변환)
# -----------------------------------------------------------------------------
df = pd.DataFrame(daily_list)

# API 응답의 문자열 숫자 데이터형 변환
df["rank"] = pd.to_numeric(df["rank"])
df["audiCnt"] = pd.to_numeric(df["audiCnt"])
df["audiAcc"] = pd.to_numeric(df["audiAcc"])
df["scrnCnt"] = pd.to_numeric(df["scrnCnt"])

# -----------------------------------------------------------------------------
# 6. 화면 구성: 1위 영화 주요 지표 카드
# -----------------------------------------------------------------------------
top1 = df.iloc[0]

st.subheader(f"🥇 1위: {top1['movieNm']}")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        label="어제 관객수", 
        value=f"{top1['audiCnt']:,} 명"
    )
with col2:
    st.metric(
        label="누적 관객수", 
        value=f"{top1['audiAcc']:,} 명"
    )
with col3:
    st.metric(
        label="상영 스크린수", 
        value=f"{top1['scrnCnt']:,} 개"
    )

st.divider()

# -----------------------------------------------------------------------------
# 7. 화면 구성: 관객수 상위 5편 막대그래프
# -----------------------------------------------------------------------------
st.subheader("📊 관객수 상위 5개 영화")

# 상위 5개 데이터 추출
top5_df = df.head(5)[["movieNm", "audiCnt"]].copy()

# 막대그래프 생성을 위해 영화명을 인덱스로 지정
top5_df.set_index("movieNm", inplace=True)
top5_df.columns = ["관객수(명)"]

st.bar_chart(top5_df)

st.divider()

# -----------------------------------------------------------------------------
# 8. 화면 구성: 전체 순위 데이터표
# -----------------------------------------------------------------------------
st.subheader("📋 전체 박스오피스 순위")

# 표에 출력할 컬럼 선택 및 이름 변경
display_df = df[[
    "rank", 
    "movieNm", 
    "openDt", 
    "audiCnt", 
    "audiAcc", 
    "scrnCnt"
]].copy()

display_df.columns = [
    "순위", 
    "영화명", 
    "개봉일", 
    "어제 관객수", 
    "누적 관객수", 
    "스크린수"
]

# 데이터 프레임 출력 (숫자 세 자릿수 콤마 포맷팅 포함)
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "어제 관객수": st.column_config.NumberColumn(format="%d 명"),
        "누적 관객수": st.column_config.NumberColumn(format="%d 명"),
        "스크린수": st.column_config.NumberColumn(format="%d 개")
    }
)

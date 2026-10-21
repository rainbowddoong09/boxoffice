import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

# Streamlit 페이지 기본 설정 (제목, 넓은 레이아웃)
st.set_page_config(page_title="어제 박스오피스", layout="wide")

st.title("🎬 어제 일별 박스오피스")

# 1. 한국 표준시(KST: UTC+9) 기준 날짜 계산
# Streamlit Cloud 서버 시계가 해외 기준(UTC)이더라도 한국 시간 기준으로 어제 날짜를 정확히 계산합니다.
kst = timezone(timedelta(hours=9))
yesterday = datetime.now(kst) - timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")  # KOBIS API 요구 형식: YYYYMMDD
formatted_date = yesterday.strftime("%Y년 %m월 %d일")

st.caption(f" 기준일: {formatted_date} (한국 시간 기준)")

# 2. 비밀 금고(st.secrets)에서 API 키 불러오기
try:
    api_key = st.secrets["KOBIS_KEY"]
except Exception:
    st.error("🔑 Secrets 설정에서 'KOBIS_KEY'를 찾을 수 없습니다.")
    st.info("Streamlit Cloud 설정(Secrets)에 `KOBIS_KEY = \"발급받은키\"` 형태로 입력했는지 확인해 주세요.")
    st.stop()

# 3. KOBIS API 호출
url = f"https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json?key={api_key}&targetDt={target_dt}"

try:
    response = requests.get(url, timeout=10)
    data = response.json()
except Exception as e:
    st.error("📡 API 요청 중 네트워크 오류가 발생했습니다.")
    st.info("인터넷 연결 상태를 확인하시거나 잠시 후 다시 시도해 주세요.")
    st.stop()

# 4. API 예외 및 오류 검증 (KOBIS는 인증키 오류 시에도 200 OK와 함께 faultInfo 반환)
if "faultInfo" in data:
    st.error("❌ API 인증 오류가 발생했습니다.")
    st.warning(f"오류 메시지: {data['faultInfo'].get('message', '알 수 없는 오류')}")
    st.info("Streamlit Secrets에 등록한 KOBIS API 키가 올바른지 확인해 주세요.")
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
movie_list = box_office_result.get("dailyBoxOfficeList", [])

# 영화 목록이 비어 있는 경우 처리
if not movie_list:
    st.warning("⚠️ 어제자 박스오피스 데이터가 비어 있습니다.")
    st.info("새벽 시간대에는 아직 집계가 끝나지 않았을 수 있습니다. 잠시 후 다시 확인해 주세요.")
    st.stop()

# 5. 데이터 프레임 변환 및 타입 정리 (API 응답 데이터는 모두 문자열 형태)
df = pd.DataFrame(movie_list)

# 숫자로 변환할 컬럼 리스트
numeric_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "rankInten"]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# 6. 1위 영화 지표 카드 시각화
top_movie = df.iloc[0]

# 순위 증감 텍스트 정리 (예: +2, -1, 변동없음)
rank_inten = int(top_movie["rankInten"])
if rank_inten > 0:
    rank_delta = f"▲ {rank_inten}"
elif rank_inten < 0:
    rank_delta = f"▼ {abs(rank_inten)}"
else:
    rank_delta = "변동 없음"

st.subheader("🥇 어제 박스오피스 1위")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="영화명 (개봉일)", value=top_movie["movieNm"], delta=f"개봉일: {top_movie['openDt']}")

with col2:
    st.metric(label="어제 관객수", value=f"{int(top_movie['audiCnt']):,} 명", delta=rank_delta)

with col3:
    st.metric(label="누적 관객수", value=f"{int(top_movie['audiAcc']):,} 명")

st.divider()

# 7. 관객수 상위 5편 막대그래프 시각화
st.subheader("📊 관객수 상위 5개 영화")
top5_df = df.head(5).copy()

# 막대그래프용 컬럼 정리 (영화명을 인덱스로 지정)
chart_data = top5_df.set_index("movieNm")[["audiCnt"]]
chart_data.columns = ["어제 관객수"]

st.bar_chart(chart_data)

st.divider()

# 8. 전체 박스오피스 순위 표 (1위 ~ 10위)
st.subheader("📋 전체 순위 목록")

# 표에 출력할 주요 컬럼 선택 및 이름 변경
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "어제 관객수", "누적 관객수", "스크린수"]

# 천 단위 쉼표(,) 포맷팅 적용
display_df["어제 관객수"] = display_df["어제 관객수"].apply(lambda x: f"{int(x):,} 명")
display_df["누적 관객수"] = display_df["누적 관객수"].apply(lambda x: f"{int(x):,} 명")
display_df["스크린수"] = display_df["스크린수"].apply(lambda x: f"{int(x):,} 개")

st.dataframe(display_df, use_container_width=True, hide_index=True)

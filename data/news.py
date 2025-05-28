import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# 네이버 OpenAPI 인증 정보 (건축동향 페이지 전용)
NAVER_CLIENT_ID = "GUljYZVXM5kfmsFW0Vlc"
NAVER_CLIENT_SECRET = "PJKBbGt2Ff"

# 고정 키워드 목록
KEYWORDS = ["광산구 건축", "광산구 사고", "건축 정책", "건축법령"]

# 뉴스 검색 함수
def search_news(query, display=20, sort="date"):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": query, "display": display, "sort": sort}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            items = res.json().get("items", [])
            return pd.DataFrame([
                {
                    "제목": item["title"].replace("<b>", "").replace("</b>", ""),
                    "링크": item["link"],
                    "날짜": pd.to_datetime(item["pubDate"]).date(),
                    "키워드": query
                }
                for item in items
            ])
        else:
            st.error(f"❌ API 오류: {res.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"❗ 요청 실패: {e}")
        return pd.DataFrame()


def main():
    # 홈(건축동향) 페이지 컨테이너 패딩 조정
    st.markdown(
        """
        <style>
            .block-container { padding-top: 1rem !important; }
        </style>
        """,
        unsafe_allow_html=True
    )

    # 페이지 제목
    st.markdown(
        f"""
        <p style=\"color:black; font-size:40px; font-weight:bold; text-align:center;\">
            최신 건축 트렌드
        </p>
        """,
        unsafe_allow_html=True
    )
    # 자동 갱신 안내
    st.markdown(
        f"""
        <p style=\"color:red; font-size:14px; font-weight:normal; text-align:center;\">
            ※ 뉴스 통계와 기사는 1시간 간격으로 자동 갱신됩니다.
        </p>
        """,
        unsafe_allow_html=True
    )

    # 뉴스 크롤링 및 통계
    all_df = []
    for kw in KEYWORDS:
        df = search_news(kw)
        if not df.empty:
            all_df.append(df)

    if all_df:
        full_df = pd.concat(all_df)
        grouped = full_df.groupby(["날짜", "키워드"]).size().reset_index(name="기사 수")

        # 시각화
        st.markdown(
            f"""
            <p style=\"color:black; font-size:20px; font-weight:bold; text-align:left;\">
                날짜별 키워드 뉴스 건수 통계
            </p>
            """,
            unsafe_allow_html=True
        )
        fig = px.bar(
            grouped,
            x="날짜", y="기사 수", color="키워드", barmode="group"
        )
        st.plotly_chart(fig, use_container_width=True)

        # 상세 뉴스 목록
        st.markdown(
            f"""
            <p style=\"color:black; font-size:20px; font-weight:bold; text-align:left;\">
                키워드별 뉴스 목록
            </p>
            """,
            unsafe_allow_html=True
        )
        cols = st.columns(2)
        for idx, kw in enumerate(KEYWORDS):
            col = cols[idx % 2]
            with col:
                st.markdown(f"#### 🔎 `{kw}`")
                df = full_df[full_df["키워드"] == kw].sort_values("날짜", ascending=False)
                if df.empty:
                    st.info("❗ 뉴스가 없습니다.")
                else:
                    for _, row in df.iterrows():
                        st.markdown(
                            f"- [{row['제목']}]({row['링크']})<br><sub>{row['날짜']}</sub>",
                            unsafe_allow_html=True
                        )
                st.markdown("---")
    else:
        st.info("❗ 뉴스 데이터가 없습니다.")

    # 수동 갱신 (관리자 전용)
    st.markdown("---")
    st.subheader("🔄 수동 뉴스 갱신 (관리자 전용)")
    ADMIN_PASSWORD = "gwangsan123"
    pw = st.text_input("비밀번호 입력", type="password", key="home_admin_pwd")
    if st.button("🔄 즉시 갱신", key="home_manual_refresh"):
        if pw == ADMIN_PASSWORD:
            st.success("✅ 수동 갱신 실행됨")
            # 여기에 수동 갱신 로직 추가
        else:
            st.error("❌ 비밀번호가 일치하지 않습니다.")
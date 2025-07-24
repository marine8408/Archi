import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime, timedelta

# 네이버 OpenAPI 인증 정보 (건축동향 페이지 전용)
NAVER_CLIENT_ID = "GUljYZVXM5kfmsFW0Vlc"
NAVER_CLIENT_SECRET = "PJKBbGt2Ff"

# 검색용 키워드와 화면 출력용 이름 분리
KEYWORD_MAP = {
    "광산구+건축": "광산구 건축",
    "광산구 사고|광산구 위험": "광산구 사고/위험",
    "건축+정책 건설+정책": "건축/건설 정책",
    "건설기술진흥법+개정 건설산업기본법+개정 주택법+개정 건축법+개정 건축물관리법+개정 공동주택관리법+개정 시특법+개정": "건축 관련 법령 개정"
}

# 뉴스 검색 함수
def search_news(query, display=20, sort="date", use_similarity_filter=True):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": display,
        "sort": sort,
        "start": 1
    }
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            items = res.json().get("items", [])
            raw_data = [
                {
                    "제목": item["title"].replace("<b>", "").replace("</b>", ""),
                    "링크": item["link"],
                    "날짜": pd.to_datetime(item["pubDate"]).date(),
                    "본문": item.get("description", "").replace("<b>", "").replace("</b>", ""),
                    "키워드": query
                }
                for item in items
            ]
            df = pd.DataFrame(raw_data)
            if not df.empty:
                today = datetime.today().date()
                start_date = today - timedelta(days=15)
                end_date = today + timedelta(days=15)
                df = df[(df["날짜"] >= start_date) & (df["날짜"] <= end_date)]

                if use_similarity_filter and not df.empty:
                    corpus = df["제목"] + " " + df["본문"]
                    if len(corpus) > 0:
                        vectorizer = TfidfVectorizer().fit(corpus.tolist() + [query])
                        vectors = vectorizer.transform(corpus.tolist())
                        keyword_vec = vectorizer.transform([query])
                        sims = cosine_similarity(vectors, keyword_vec).flatten()
                        df = df[sims >= 0.07].reset_index(drop=True)   #sims >= 0.08  값을 올릴 수록 정확도 올라감 내릴수록 정확도 낮아짐
            return df.drop(columns=["본문"], errors="ignore")
        else:
            st.error(f"❌ API 오류: {res.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"❗ 요청 실패: {e}")
        return pd.DataFrame()

def main():
    st.markdown("""
        <style>
            .block-container { padding-top: 1rem !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <p style=\"color:black; font-size:40px; font-weight:bold; text-align:center;\">
            최신 건축 트렌드
        </p>
    """, unsafe_allow_html=True)
    st.markdown("""
        <p style=\"color:red; font-size:14px; font-weight:normal; text-align:center;\">
            ※ 뉴스 통계와 기사는 1시간 간격으로 자동 갱신됩니다.
        </p>
    """, unsafe_allow_html=True)

    all_df = []
    for kw_query in KEYWORD_MAP:
        df = search_news(kw_query)
        if not df.empty:
            df["표시키워드"] = KEYWORD_MAP[kw_query]
            all_df.append(df)

    if all_df:
        full_df = pd.concat(all_df)
        grouped = full_df.groupby(["날짜", "표시키워드"]).size().reset_index(name="기사 수")

        st.markdown("""
            <p style=\"color:black; font-size:20px; font-weight:bold; text-align:left;\">
                날짜별 키워드 뉴스 건수 통계
            </p>
        """, unsafe_allow_html=True)
        fig = px.bar(
            grouped,
            x="날짜", y="기사 수", color="표시키워드", barmode="group"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("""
            <p style=\"color:black; font-size:20px; font-weight:bold; text-align:left;\">
                키워드별 뉴스 목록
            </p>
        """, unsafe_allow_html=True)
        cols = st.columns(2)
        for idx, (kw_query, kw_label) in enumerate(KEYWORD_MAP.items()):
            col = cols[idx % 2]
            with col:
                st.markdown(f"#### 🔎 `{kw_label}`")
                df = full_df[full_df["표시키워드"] == kw_label].sort_values("날짜", ascending=False)
                if df.empty:
                    st.info("뉴스가 없습니다.")
                else:
                    for _, row in df.iterrows():
                        st.markdown(
                            f"- [{row['제목']}]({row['링크']})<br><sub>{row['날짜']}</sub>",
                            unsafe_allow_html=True
                        )
                st.markdown("---")
    else:
        st.info("뉴스 데이터가 없습니다.")

    st.markdown("---")
    st.subheader("🔄 수동 뉴스 갱신 (관리자 전용)")
    ADMIN_PASSWORD = "gwangsan123"
    pw = st.text_input("비밀번호 입력", type="password", key="home_admin_pwd")
    if st.button("🔄 즉시 갱신", key="home_manual_refresh"):
        if pw == ADMIN_PASSWORD:
            st.success("✅ 수동 갱신 실행됨")
        else:
            st.error("❌ 비밀번호가 일치하지 않습니다.")

if __name__ == "__main__":
    main()
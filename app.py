import streamlit as st
import json
import xmltodict
import pandas as pd
import requests
import fitz  # PyMuPDF
import os
import re
import io
import html
from urllib.request import Request, urlopen 
from urllib.parse import urlencode, quote_plus
from PIL import Image
from io import BytesIO
import xml.etree.ElementTree as ET
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import plotly.express as px

    # 🔍 현재 쿼리 파라미터 확인
    #st.sidebar.markdown("### 🧪 디버깅 정보")
    #st.sidebar.write("📎 query_params:", st.query_params)

# ✅ 페이지 전체 설정
st.set_page_config(
    page_title="광산구 건축 사이버 상담센터",  # 탭 제목 설정
    page_icon="🏛️",                # (선택사항) 브라우저 탭 아이콘
    layout="wide"                  # (선택사항) 레이아웃 설정
)

# 페이지 우측 상단 메뉴 및 푸터 숨김
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ✅ 자동 새로고침: 1시간 간격 (3600000ms)
st_autorefresh(interval=3600000, key="auto_refresh")

# ✅ 네이버 OpenAPI 인증 정보
NAVER_CLIENT_ID = "GUljYZVXM5kfmsFW0Vlc"
NAVER_CLIENT_SECRET = "PJKBbGt2Ff"

# ✅ 고정 키워드 목록
KEYWORDS = ["광산구 건축", "광산구 사고", "건축 정책", "건축법령"]

# ✅ 뉴스 검색 함수
def search_news(query, display=20, sort="date"):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": display,
        "sort": sort
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            items = res.json().get("items", [])
            return pd.DataFrame([{
                "제목": item["title"].replace("<b>", "").replace("</b>", ""),
                "링크": item["link"],
                "날짜": pd.to_datetime(item["pubDate"]).date(),
                "키워드": query
            } for item in items])
        else:
            st.error(f"❌ API 오류: {res.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"❗ 요청 실패: {e}")
        return pd.DataFrame()

def main():
    menu_to_file = {
        "건축 규제 정보 확인": "data/archPermission.py",
        "건축사 무료 상담 신청": "data/counsel.py"
    }

    # 현재 메뉴 파라미터 감지
    query_menu = st.query_params.get("menu")
    selected = query_menu[0] if isinstance(query_menu, list) else query_menu

    # HTML과 CSS로 스타일 지정
    sidebar_title = """
        <div style='text-align: center; font-size: 18px; color: navy; margin-bottom: 20px; font-weight:bold;'>
            광산구 건축 사이버 상담센터
        </div>
        <hr style='margin-top: 0; margin-bottom: 30px;'>
    """

    # 사이드바에 삽입
    st.sidebar.markdown(sidebar_title, unsafe_allow_html=True)

    # 홈으로
    home_form = """
    <form action="/" method="get">
        <button type="submit" style="
            background: none;
            border: none;
            padding: 0;
            margin-bottom: 10px;
            color: red;
            font-size: 20px;
            font-weight: bold;
            text-decoration: none;
            cursor: pointer;
            display: block;
            width: 100%;
            text-align: center;
        ">🏠 처음 화면으로(뉴스)</button>
    </form>
    """
    st.sidebar.markdown(home_form, unsafe_allow_html=True)

    # 메뉴 항목을 텍스트처럼 보이도록 출력
    for menu_name in menu_to_file:
        menu_form = f"""
        <style>
            .menu-btn {{
                background: none;
                border: none;
                padding: 0;
                margin-bottom: 10px;
                color: black;
                cursor: pointer;
                font-size: 20px;
                font-family: inherit;
                display: block;
                width: 100%;
                text-align: center;
            }}
            .menu-btn:hover {{
                color: navy;
                font-weight: bold;
            }}
        </style>
        <form action="/" method="get">
            <input type="hidden" name="menu" value="{menu_name}">
            <button class="menu-btn">👉 {menu_name}</button>
        </form>
        """
        st.sidebar.markdown(menu_form, unsafe_allow_html=True)

    st.sidebar.markdown(
        """
        <hr style="margin-top: 0.5rem; margin-bottom: 0.5rem;">
        <p style="color:red; font-size:12px; font-weight:normal; text-align:center;">
            웹사이트에서 제공하는 모든 정보는
            국가 데이터에서 기계적으로 추출 가공된 정보로서
            참고용으로만 사용 또는 확인하시기 바랍니다.
        </p>
        """,
        unsafe_allow_html=True
    )
    st.sidebar.markdown(
        """
        <hr style="margin-top: 0.5rem; margin-bottom: 0.5rem;">
        <p style="color:black; font-size:14px; font-weight:normal; text-align:center;">
            광산구 건축 AI 동아리 제공<br>웹사이트 제작 장하종
        </p>
        """,
        unsafe_allow_html=True
    )

    # 본문 실행
    if selected and selected in menu_to_file:
        file_path = menu_to_file[selected]

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

            try:
                namespace = {}
                exec(code, namespace)
                if "main" in namespace and callable(namespace["main"]):
                    namespace["main"]()
                else:
                    st.warning("⚠️ main() 함수가 정의되어 있지 않습니다.")
            except Exception as e:
                st.error(f"🚫 코드 실행 중 오류 발생:\n\n{e}")
        else:
            st.error(f"❌ 파일을 찾을 수 없습니다: `{file_path}`")
    else:
        st.markdown(
            """
            <style>
                .block-container {
                    padding-top: 1rem !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.markdown(
        f"""
        <p style="color:black; font-size:40px; font-weight:normal; font-weight: bold; text-align:center;">
            건축 및 사고 언론보도
        </p>
        """,
        unsafe_allow_html=True
        )
        st.markdown(
        f"""
        <p style="color:red; font-size:14px; font-weight:normal; text-align:center;">
            ※ 뉴스 통계와 기사는 1시간 간격으로 자동 갱신됩니다.
        </p>
        """,
        unsafe_allow_html=True
        )

        # ✅ 뉴스 크롤링 + 날짜별 통계
        all_df = []
        for keyword in KEYWORDS:
            df = search_news(keyword)
            if not df.empty:
                all_df.append(df)

        if all_df:
            full_df = pd.concat(all_df)
            grouped = full_df.groupby(["날짜", "키워드"]).size().reset_index(name="기사 수")

            # ✅ 날짜별 키워드 뉴스 수 시각화
            st.markdown(
            f"""
            <p style="color:black; font-size:20px; font-weight:bold; text-align:left;">
                📊 날짜별 키워드 뉴스 건수 통계
            </p>
            """,
            unsafe_allow_html=True
            )
            fig = px.bar(
                grouped,
                x="날짜",
                y="기사 수",
                color="키워드",
                barmode="group",
                #title="날짜별 키워드 뉴스 건수"
            )
            st.plotly_chart(fig, use_container_width=True)

            # ✅ 뉴스 상세 목록 - 2열 구성
            st.markdown(
            f"""
            <p style="color:black; font-size:20px; font-weight:bold; text-align:left;">
                📰 키워드별 뉴스 목록
            </p>
            """,
            unsafe_allow_html=True
            )
            cols = st.columns(2)
            for idx, keyword in enumerate(KEYWORDS):
                col = cols[idx % 2]
                with col:
                    st.markdown(f"#### 🔎 `{keyword}`")
                    df = full_df[full_df["키워드"] == keyword].sort_values("날짜", ascending=False)
                    if df.empty:
                        st.info("❗ 뉴스가 없습니다.")
                    else:
                        for i, row in df.iterrows():
                            st.markdown(
                                f"- [{row['제목']}]({row['링크']})<br><sub>{row['날짜']}</sub>",
                                unsafe_allow_html=True
                            )
                    st.markdown("---")
        else:
            st.info("❗ 뉴스 데이터가 없습니다.")

        # ✅ [맨 하단] 수동 갱신 영역
        st.markdown("---")
        st.subheader("🔄 수동 뉴스 갱신 (관리자 전용)")
        ADMIN_PASSWORD = "gwangsan123"
        pw = st.text_input("비밀번호 입력", type="password")
        if st.button("🔄 즉시 갱신"):
            if pw == ADMIN_PASSWORD:
                st.success("✅ 수동 갱신 실행됨")
                manual_refresh = True
            else:
                st.error("❌ 비밀번호가 일치하지 않습니다.")
main()
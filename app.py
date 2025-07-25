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

# 메뉴 매핑 (전역)
MENU_TO_FILE = {
    "건축 규제 한눈에": "data/archPermission.py",
    "찾아가는 건축민원 지원센터": "data/counsel.py",
    "최신 건축 트렌드": "data/news.py",
    "설문조사": "data/survey.py"
}

# 페이지 설정 및 공통 스타일
def configure_page():
    st.set_page_config(
        page_title="광산구 건축정보 AI 플랫폼",
        page_icon="🏛️",
        layout="wide"
    )
    # 자동 새로고침: 1시간 간격
    st_autorefresh(interval=3600000, key="auto_refresh")
    # 숨김 스타일
    hide_style = """
        <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        </style>
    """
    st.markdown(hide_style, unsafe_allow_html=True)

# 사이드바 콘텐츠 렌더링
def render_sidebar():
    # 타이틀
    sidebar_title = """
    <style>
    @keyframes blink {0%,100%{opacity:1;}50%{opacity:0.4;}}
    .blink-blue{animation:blink 1.8s infinite;color:#0000FF;font-weight:bold;}
    .blink-red{animation:blink 1.8s infinite;color:#FF0000;font-weight:bold;}
    </style>
    <div style='text-align:center;font-size:24px;font-weight:bold;margin-bottom:20px;'>
        <span class='blink-blue'>광산구</span>
        <span class='blink-blue'>건축정보</span>
        <span class='blink-red'>AI</span>
        <span class='blink-blue'>플랫폼</span>
    </div>
    <hr style='margin:0 0 30px;'>
    """
    st.sidebar.markdown(sidebar_title, unsafe_allow_html=True)

    # 버튼 스타일
    menu_btn_style = """
    <style>
    .menu-btn{background:none;border:none;padding:0;margin:10px 0;color:black;cursor:pointer;
      font-size:20px;display:block;width:100%;text-align:center;transition:all .3s;}
    .menu-btn:hover{color:navy;font-weight:bold;transform:scale(1.05);}
    </style>
    """
    st.sidebar.markdown(menu_btn_style, unsafe_allow_html=True)

    # 메뉴 버튼
    for name in MENU_TO_FILE:
        form = f"""
        <form action='/' method='get'>
          <input type='hidden' name='menu' value='{name}'>
          <button class='menu-btn'>{name}</button>
        </form>
        """
        st.sidebar.markdown(form, unsafe_allow_html=True)

    # 마우스 hover 작동 + 밑줄 제거 + 색상 확정
    menu_btn_style2 = """
    <style>
    .menu-btn2 {
        background: none;
        border: none;
        padding: 0;
        margin: 10px 0;
        color: black !important;
        cursor: pointer;
        font-size: 14px;
        display: block;
        width: 100%;
        text-align: center;
        transition: all 0.3s;
        text-decoration: none !important;
    }
    .menu-btn2:hover {
        color: navy !important;
        font-weight: bold;
        transform: scale(1.05);
        text-decoration: none !important;
    }
    </style>
    """
    st.sidebar.markdown(menu_btn_style2, unsafe_allow_html=True)

    # 외부 링크 섹션
    external_link_html = """
    <div style='text-align:center; margin-top:150px; font-size:14px;'>
        <div style='font-weight:normal; font-size:14px; margin-bottom:10px;'>외부사이트 연결</div>
        <a href="https://www.gwangsan.go.kr" target="_blank" class="menu-btn2">광산구청</a>
        <a href="https://www.eais.go.kr" target="_blank" class="menu-btn2">건축행정시스템(세움터)</a>
        <a href="https://www.eum.go.kr" target="_blank" class="menu-btn2">토지이음</a>
    </div>
    """
    st.sidebar.markdown(external_link_html, unsafe_allow_html=True)

    # 푸터 (여러 개 사용 가능)
    footers = [
        """
        <div style='margin-top:30px;text-align:center;font-size:12px;color:red;'>
          웹사이트 정보는 국가 데이터망에서<br>
          추출 가공된 자료로 참고용으로만 사용가능
        </div>
        """,
        """
        <div style='margin-top:10px;text-align:center;font-size:14px;color:gray;'>
          제공: 광산구 건축 AI 동아리, 제작: 장하종
        </div>
        """
    ]
    for footer in footers:
        st.sidebar.markdown(footer, unsafe_allow_html=True)

# 선택 메뉴 가져오기
def get_selected_menu(default="건축 규제 한눈에"):
    param = st.query_params.get("menu")
    if param:
        return param[0] if isinstance(param, list) else param
    return default

# 선택된 페이지 로드
def load_selected_page(selected):
    path = MENU_TO_FILE.get(selected)
    if path and os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        namespace = {'st': st}
        try:
            exec(code, namespace)
            if 'main' in namespace and callable(namespace['main']):
                namespace['main']()
            else:
                st.warning('⚠️ main() 함수가 정의되어 있지 않습니다.')
        except Exception as e:
            st.error(f'🚫 코드 실행 중 오류 발생:\n{e}')
    else:
        st.error(f'❌ 메뉴 파일을 찾을 수 없습니다: {selected}')

# 앱 진입점
def main():
    configure_page()
    render_sidebar()
    selected = get_selected_menu()
    load_selected_page(selected)

if __name__ == "__main__":
    main()
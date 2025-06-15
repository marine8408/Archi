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
from uuid import uuid4
import math
from PIL import Image, ImageDraw

# 법령명에서 제X호Y목 파싱
def extract_ho_mok(text):
    """
    '제X호Y목'에서 X는 정수 또는 소수로 추출, Y는 한글 문자 (가~힣)
    """
    text = str(text)
    
    # 1. '제23.2호' or '제23-2호' → 23.2로 추출
    ho_match = re.search(r'제\s*(\d+(?:[.-]\d+)?)\s*호', text)
    ho = float(ho_match.group(1).replace('-', '.')) if ho_match else 999.9

    # 2. '가목', '나목' 등 추출
    mok_match = re.search(r'호\s*([가-힣])목', text)
    mok = mok_match.group(1) if mok_match else '힣'

    return ho, mok

# 텍스트 정리
def clean_text(text):
    # 특수 문자 제거: 전각 마침표, 괄호, 쉼표, 따옴표 등
    cleaned = re.sub(r'[。()\[\]{}<>「」‘’“”\',"]', '', str(text))
    # 양쪽 공백 제거
    return cleaned.strip()

# 제X호에서 숫자만 추출하는 함수
def extract_ho_number(text):
    """
    '제X호', '제X-Y호', '제X.Y호' → float 값으로 변환
    예) 제23호 → 23.0, 제23-2호 → 23.2, 제23.2호 → 23.2
    """
    match = re.search(r'제\s*(\d+(?:[.-]\d+)?)\s*호', str(text))
    if match:
        ho = match.group(1).replace('-', '.')
        try:
            return float(ho)
        except:
            return 999.99
    return 999.99

# 건폐율 및 용적률에서 숫자만 추출하는 코드
def parse_percent(value):
    if not value:
        return None
    try:
        # 숫자만 추출 (예: "60%", " 60 %", "육십%" → 60)
        numeric_part = re.findall(r"[\d.]+", str(value))
        return float(numeric_part[0]) if numeric_part else None
    except:
        return None

def render_tabs():
    tab_labels = [
        "건축행위 제한", "건축규모 제한", "기타 제한",
        "인허가 정보", "건축물대장", "토지 소유정보"
    ]
    # 1) 처음엔 0번 탭 선택
    if "current_tab" not in st.session_state:
        st.session_state.current_tab = 0

    # 2) 표시할 레이블에 ▶ 붙이기
    display_labels = []
    for i, label in enumerate(tab_labels):
        if st.session_state.current_tab == i:
            display_labels.append(f"▶ {label}")
        else:
            display_labels.append(label)

    # 3) 버튼 그리기
    cols = st.columns(len(tab_labels))
    for i, col in enumerate(cols):
        if col.button(display_labels[i], key=f"tab_btn_{i}", use_container_width=True):
            st.session_state.current_tab = i
            # 선택 직후 즉시 반영을 위해 rerun
            st.rerun()

    return st.session_state.current_tab

def main():
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

    pdf_path2 = "data/district.pdf"

    st.markdown(
    f"""
    <p style="color:black; font-size:40px; font-weight:normal; font-weight: bold; text-align:center;">
        건축 규제 한눈에
    </p>
    """,
    unsafe_allow_html=True
    )
    st.markdown(
    f"""
    <p style="color:red; font-size:14px; font-weight:normal; text-align:center;">
        ※ 이용방법: 1.토지이용계획 검색(주소 입력) ▶ 토지규제사항 및 하단 탭별 건축 정보 확인
    </p>
    """,
    unsafe_allow_html=True
    )

    geoParams()
    geoData()
    spaceMap()

    selected_tab = render_tabs()

    if selected_tab == 0:
        areaPermission()
    elif selected_tab == 1:
        spaceIndex()
    elif selected_tab == 2:
        districtAllow(pdf_path2)
    elif selected_tab == 3:
        archAllowInfo()
    elif selected_tab == 4:
        st.markdown('<div id="render-trigger" style="display:none;">trigger</div>', unsafe_allow_html=True)
        buildingInfo()
    elif selected_tab == 5:
        geoUser() 

# 토지속성 정보 처리 함수
def geoParams():
    bonbun_key = ''
    bubun_key = ''

    st.write(' ')
    #st.markdown(
        #f"""
        #<p style="color:blue; font-size:20px; font-weight:bold;">
            #1. 토지이용계획 검색(지목, 면적, 용도지역및지구, 위치도)
        #</p>
        #""",
        #unsafe_allow_html=True
    #)

    # 이전 선택값 저장 (최초 실행 시)
    if 'prev_umd' not in st.session_state:
        st.session_state.prev_umd = None
    if 'prev_umd2' not in st.session_state:
        st.session_state.prev_umd2 = None
                    
    if 'initialized' not in st.session_state:
        st.session_state['initialized'] = True
        # 필요한 초기 키만 제거
        for key in ['bonbun', 'bubun', 'other_temp']:
            st.session_state.pop(key, None)  # 없으면 무시
        
    # 세션 상태 초기화
    if "search_triggered" not in st.session_state:
        st.session_state.search_triggered = False

    key_prefix = st.session_state.get("selected_menu", "archPermission")

    # 검색 및 초기화 버튼 키 고유화
    search_btn_key = f"{key_prefix}_search_button"
    reset_btn_key = f"{key_prefix}_reset_button"

     # 결과 확인
    #st.write("🔍 검색 트리거 상태:", st.session_state.search_triggered)
    col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = st.columns([1.1, 0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.3, 0.4, 0.4])
    with col1:
        umd = st.selectbox(
            '법정동',
            ('고룡동', '광산동', '남산동', '내산동', '대산동', 
            '덕림동', '도덕동', '도산동', '도천동', '도호동', 
            '동림동', '동산동', '동호동', '두정동', '등임동', 
            '명도동', '명화동', '박호동', '복룡동', '본덕동', 
            '북산동', '비아동', '사호동', '산막동', '산수동', 
            '산월동', '산정동', '삼거동', '삼도동', '서봉동', 
            '선동', '선암동', '소촌동', '송대동', '송산동', 
            '송정동', '송촌동', '송치동', '송학동', '수완동', 
            '신동', '신가동', '신룡동', '신창동', '신촌동', 
            '쌍암동', '안청동', '양동', '양산동', '연산동', 
            '오산동', '오선동', '오운동', '옥동', '왕동', '요기동', 
            '용동', '용곡동', '용봉동', '우산동', '운남동', '운수동', 
            '월계동', '월곡동', '월전동', '유계동', '임곡동', '장덕동', 
            '장록동', '장수동', '지산동', '지정동', '지죽동', '지평동', 
            '진곡동', '하남동', '하산동', '황룡동', '흑석동'
            ),
            key=f"{key_prefix}_umd"
        )
            
    with col2:
        umd2 = st.selectbox(
            '산 유무',
            ('일반', '산'
            ),
            key=f"{key_prefix}_san_select"
        )
    with col3:
        bonbun = st.text_input('번지 본번', key=f"{key_prefix}_bonbun")
    with col4:
        bubun = st.text_input('번지 부번', key=f"{key_prefix}_bubun")
    with col5:
        st.write("")
    with col6:
        st.write("")
    with col7:
        st.write("")
    with col8:        
        #st.write('검색')
        st.markdown(
            """
            <div style="height: 27px; background-color: white; padding: 10px;">
            </div>
            """,
            unsafe_allow_html=True
            )
        if st.button("검색", type="primary", key=search_btn_key):
            # ✅ 1. 현재 입력값 임시 백업
            st.session_state["search_triggered"] = True
            st.session_state["umd"] = umd
            st.session_state["umd2"] = umd2
            st.session_state["bonbun"] = bonbun
            st.session_state["bubun"] = bubun

            # ✅ 2. 이전 검색 결과 초기화 (이 부분에서 clear() 대신 개별 삭제 권장)
            for key in ["vworld_x", "vworld_y", "address", "cutFGeoLnm_lndcgr_smbol", "fGeoPrpos_area_dstrc_nm_list", 'items_cleaned_fGeoPrpos_area_dstrc_nm_list', 'lndpcl_ar', 'pnu', 'land_info', 'block_other_functions', 'sigunguCd', 'bjdongCd', 'san','bun', 'ji']:
                if key in st.session_state:
                    del st.session_state[key]

            # 어떤 로직에서 필요할 때
            clear_layer_session("LT_C_DAMYOJ")
            clear_layer_session("LT_C_LHBLPN")


            # ✅ 3. 검색 결과는 리런 후 조건문에서 표시
            st.rerun()
    with col9:
        st.markdown(
            """
            <div style="height: 27px; background-color: white; padding: 10px;">
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("초기화", key=reset_btn_key):
            # ✅ '검색되지 않음' 상태 유지
            st.session_state["search_triggered"] = False
            st.session_state["invalid_address"] = True  # ❗ 메시지를 유지하고 싶다면 True로 초기화

            # ✅ 다른 키 전부 삭제 (단, 유지할 것들은 제외)
            for key in list(st.session_state.keys()):
                if key not in ("search_triggered", "invalid_address"):
                    del st.session_state[key]

            st.rerun()
    with col10:
        st.markdown(
            """
            <div style="height: 27px; background-color: white; padding: 10px;">
            </div>
            """,
            unsafe_allow_html=True
        )

        # HTML+JS로 파란색 팝업 버튼
        popup_html = """
        <script>
        function openCounsel() {
            window.open(
            "/?menu=무료%20건축사%20상담실",
            "상담신청",
            "width=800,height=1200,top=100,left=200,scrollbars=yes"
            );
        }
        </script>
        <button
        onclick="openCounsel()"
        style="
            position: relative;
            top: -9px;
            background-color: #1E90FF;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 16px;
            cursor: pointer;
        "
        >
        상담
        </button>
        """
        components.html(popup_html, height=60)

    # 👉 선택값 변경 감지
    #if st.session_state.prev_umd != umd or st.session_state.prev_umd2 != umd2:
        #keys_to_clear = [
            #'bonbun', 'bubun', 'search_triggered', 
            #'vworld_x', 'vworld_y', 'address', 
            #'cutFGeoLnm_lndcgr_smbol', 
            #'fGeoPrpos_area_dstrc_nm_list', 
            #'items_cleaned_fGeoPrpos_area_dstrc_nm_list'
        #]
        #for key in keys_to_clear:
            #st.session_state.pop(key, None)
        #st.session_state.prev_umd = umd
        #st.session_state.prev_umd2 = umd2
        #st.rerun()

        
    fumd = f'{umd}'
    fumd2 = f'{umd2}'
    fbonbun = f'{bonbun}'
    fbubun = f'{bubun}'
    
    if st.session_state.search_triggered:
        st.session_state.search_triggered = False
        apiurl = 'https://api.vworld.kr/req/address?'

        try:
            if not fbonbun or fbonbun.startswith('0'):     #bonbun 이 비어있거나 0으로 시작할 때
                st.session_state["invalid_address"] = True
                st.markdown("<span style='color:red; font-weight:bold;'>❗ 없는 주소입니다.</span>", unsafe_allow_html=True)
            else:
                if not fbubun:             #bubun 이 비어있으면
                    if fumd2.strip() == '일반':      
                        st.session_state["invalid_address"] = False                      
                        params = {
	                    'service': 'address',
	                    'request': 'getcoord',
	                    'crs': 'epsg:4326',
	                    'address': '광주광역시 광산구' + ' ' + fumd + ' ' + fbonbun,
	                    'format': 'json',
	                    'type': 'parcel',
	                    'key': 'AF338F49-6AAA-3F06-BD94-FB6CB6817323' }                        
                    else:
                        st.session_state["invalid_address"] = False
                        params = {
	                    'service': 'address',
	                    'request': 'getcoord',
	                    'crs': 'epsg:4326',
	                    'address': '광주광역시 광산구' + ' ' + fumd + ' ' + fumd2 + ' ' + fbonbun,
	                    'format': 'json',
	                    'type': 'parcel',
	                    'key': 'AF338F49-6AAA-3F06-BD94-FB6CB6817323' }
                else:   #부번이 있을 경우
                    if fbubun.strip().startswith('0'):
                        st.session_state["invalid_address"] = True
                        st.markdown("<span style='color:red; font-weight:bold;'>❗ 없는 주소입니다.</span>", unsafe_allow_html=True)
                        return
                    if fumd2.strip() == '일반':
                        st.session_state["invalid_address"] = False
                        params = {
	                    'service': 'address',
	                    'request': 'getcoord',
	                    'crs': 'epsg:4326',
	                    'address': '광주광역시 광산구' + ' ' + fumd + ' ' + fbonbun + '-' + fbubun,
	                    'format': 'json',
	                    'type': 'parcel',
	                    'key': 'AF338F49-6AAA-3F06-BD94-FB6CB6817323' }   
                    else:
                        st.session_state["invalid_address"] = False
                        params = {
	                    'service': 'address',
	                    'request': 'getcoord',
	                    'crs': 'epsg:4326',
	                    'address': '광주광역시 광산구' + ' ' + fumd + ' ' + fumd2 + ' ' + fbonbun + '-' + fbubun,
	                    'format': 'json',
	                    'type': 'parcel',
	                    'key': 'AF338F49-6AAA-3F06-BD94-FB6CB6817323' }   

                response = requests.get(apiurl, params=params, verify=True)
                    
                #st.write(response.json())
    
                if response.status_code == 200 and response.status_code:
                    print(response.json())
                    data = response.json()

                    # 시군구 및 법정동 코드 추출
                    level4LC = data["response"]["refined"]["structure"]["level4LC"]

                    # 시군구코드: 앞 5자리
                    sigunguCd = level4LC[:5]

                    # 법정동코드: 6~10번째
                    bjdongCd = level4LC[5:10]

                    # session_state에 저장, 다른 함수에서 시군구 및 법정동코드 활용하기
                    st.session_state['sigunguCd'] = sigunguCd
                    st.session_state['bjdongCd'] = bjdongCd

                    # 산번지 추출
                    text = data["response"]["refined"]["text"]

                    # "동" 다음에 "산"이 있고 그 뒤에 숫자가 오는지 검사
                    match = re.search(r"동\s*산\s*\d+", text)
                    san_indicator = "산" if match else None

                    # 산이 있으면 세션 스테이트에 저장
                    if san_indicator is not None:
                        st.session_state["san"] = san_indicator

                    # 번지 추출
                    level5 = data["response"]["refined"]["structure"]["level5"]

                    # 초기화
                    bun = None
                    ji = None

                    # 하이픈 여부 확인 및 분리
                    if "-" in level5:
                        bun, ji = level5.split("-")
                        st.session_state['bun'] = bun
                        st.session_state['ji'] = ji
                    else:
                        bun = level5
                        st.session_state['bun'] = bun

                    # 브이월드 서버 지오코더에서 받아온 데이타 중 좌표 x, y 값 출력
                    x = data['response']['result']['point']['x']
                    y = data['response']['result']['point']['y']

                    # session_state에 저장, 다른 함수에서 좌표 활용하기
                    st.session_state['vworld_x'] = x
                    st.session_state['vworld_y'] = y

                    address = data['response']['input']['address']   #입력한 주소 보여주기
                        
                    address1 = str(data['response']['input']['address'])
                    address2 = str(data['response']['refined']['text'])

                    if address1 != address2:         #산 번지 인식 마지막 제대로 판별하기
                        st.session_state["invalid_address"] = True
                        st.markdown("<span style='color:red; font-weight:bold;'>❗ 없는 주소입니다.</span>", unsafe_allow_html=True)
                        st.session_state["block_other_functions"] = True  # 🚫 별도 실행도 막기
                        return  # ✅ 이후 코드 실행 중단
                    else:
                        #여기부터 토지이용속성 조회
                        pbbox = f'{y},{x},{y},{x},EPSG:4326'    #pbbox 변수에 지오코더 좌표 값 문자열 받기

                        url = 'https://api.vworld.kr/ned/wfs/getLandUseWFS'
                        params = {
                            'key' : '86DD225C-DC5B-3B81-B9EB-FB135EEEB78C',
                            'typename' : 'dt_d154',
                            'bbox' : pbbox,
                            'maxFeatures' : '10',
                            'resultType' : 'results',
                            'srsName' : 'EPSG:4326',
                            'output' : 'application/json'}


                        response = requests.get(url, params=params, verify=True)
                        data = response.json()          
                        #st.write(data)           #json 구조 확인 중요

                        geoLnm_lndcgr_smbol = data['features'][0]['properties']['lnm_lndcgr_smbol']
                        fGeoLnm_lndcgr_smbol = f'{geoLnm_lndcgr_smbol}'
                        cutFGeoLnm_lndcgr_smbol = ''

                        for char in reversed(fGeoLnm_lndcgr_smbol):
                            if char.isdigit():
                                break
                            cutFGeoLnm_lndcgr_smbol = char + cutFGeoLnm_lndcgr_smbol


                        geoPrpos_area_dstrc_nm_list = data['features'][0]['properties']['prpos_area_dstrc_nm_list']
                        fGeoPrpos_area_dstrc_nm_list = f'{geoPrpos_area_dstrc_nm_list}'
                        #st.write(geopdata)

                        #pnu 코드 추출 차후 다른 함수에서 재사용 필요
                        pnu = data['features'][0]['properties']['pnu']
                        st.session_state['pnu'] = pnu

                        #print(fGeoPrpos_area_dstrc_nm_list)

                        # 1. 괄호 및 괄호 안 내용 제거 (중첩 포함)
                        fGeoPrpos_area_dstrc_nm_list = remove_parens_but_keep_exceptions(fGeoPrpos_area_dstrc_nm_list)

                        # 2. 쉼표 기준 항목 분리
                        area_items = fGeoPrpos_area_dstrc_nm_list.split(',')

                        # 3. 각 항목의 끝에서 숫자/기호 제거
                        cleaned_items = [
                            re.sub(r'[\d\s\-\–\.\~\+\=\!@\#\$%\^&\*\_]+$', '', item.strip()) 
                            for item in area_items
                        ]

                        # 4. 항목 사이 쉼표/공백 정리
                        cleaned_fGeoPrpos_area_dstrc_nm_list = ', '.join(cleaned_items)
                        cleaned_fGeoPrpos_area_dstrc_nm_list = re.sub(r'\s+', ' ', cleaned_fGeoPrpos_area_dstrc_nm_list).strip()

                        # ✅ 최종 결과
                        print(cleaned_fGeoPrpos_area_dstrc_nm_list)

                        # 괄호 안 제거 및 정제된 문자열에서 항목 분리
                        items_cleaned_fGeoPrpos_area_dstrc_nm_list = [
                            item.strip() for item in cleaned_fGeoPrpos_area_dstrc_nm_list.split(',')
                        ]

                        # 딕셔너리 형태로 만들기
                        area_dict = {f'item{i+1}': val for i, val in enumerate(items_cleaned_fGeoPrpos_area_dstrc_nm_list)}

                        # 분류 결과를 담을 딕셔너리 초기화. 3가지로 분류
                        classified_area_dict = {
                            '저촉': {},
                            '접합': {},
                            '포함': {}
                        }

                        # 2. 딕셔너리 순회하면서 조건 분류
                        for key, value in area_dict.items():
                            if '(저촉)' in value:
                                classified_area_dict['저촉'][key] = value
                            elif '(접합)' in value:
                                classified_area_dict['접합'][key] = value
                            else:
                                classified_area_dict['포함'][key] = value

                        # 세션 저장
                        st.session_state['address'] = address
                        st.session_state['cutFGeoLnm_lndcgr_smbol'] = cutFGeoLnm_lndcgr_smbol
                        st.session_state['fGeoPrpos_area_dstrc_nm_list'] = fGeoPrpos_area_dstrc_nm_list
                        st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list'] = area_dict

        except ZeroDivisionError:
            st.session_state["invalid_address"] = True
            st.markdown("<span style='color:red; font-weight:bold;'>❗ 없는 주소입니다.</span>", unsafe_allow_html=True)
            #st.error("주소를 다시 확인하여 주시기 바랍니다")
        except ValueError:
            st.session_state["invalid_address"] = True
            st.markdown("<span style='color:red; font-weight:bold;'>❗ 없는 주소입니다.</span>", unsafe_allow_html=True)
            #st.warning("주소를 다시 확인하여 주시기 바랍니다")
        except Exception as e:
            st.session_state["invalid_address"] = True
            st.markdown("<span style='color:red; font-weight:bold;'>❗ 없는 주소입니다.</span>", unsafe_allow_html=True)
            #st.exception(f"주소를 다시 확인하여 주시기 바랍니다")

    else:
        st.write("토지이용정보가 궁금하시면 주소를 입력 후 검색하시기 바랍니다")

    if 'address' in st.session_state and 'cutFGeoLnm_lndcgr_smbol' in st.session_state:

        geoInfo()
        if "land_info" not in st.session_state:
            st.warning("📌 토지 정보가 없습니다. 먼저 주소를 검색해주세요.")
            return    

        land_info = st.session_state["land_info"]

        lndcgrCodeNm = land_info.get("지목")
        #lndpclAr = land_info.get("면적")
        pblntfPclnd = land_info.get("공시지가")
        # 천 단위 구분 기호 추가
        formatted_price = f"{int(pblntfPclnd):,}"  # → '1,299,000'
        dateStandard = land_info.get("데이터 기준일자")

        if "lndpcl_ar" not in st.session_state:
            st.warning("📌 토지 정보가 없습니다. 먼저 주소를 검색해주세요.")
            return

        # 단순 값으로 할당 토지면적
        lndpclAr = st.session_state["lndpcl_ar"]
        # 천 단위 구분 기호 추가
        lndpclAr = float(lndpclAr)  # 숫자 변환 (문자열일 경우 대비)
        if lndpclAr.is_integer():
            lndpclAr = f"{int(lndpclAr):,}"  # 정수면 소수점 없이 출력
        else:
            lndpclAr = f"{lndpclAr:,.1f}"     # 소수점 있으면 소수점 첫째 자리까지


        st.markdown(f"""
        <style>
            .custom-table {{
                border-collapse: collapse;
                width: 100%;
                font-size: 14px;
                font-weight: normal;
            }}
            .custom-table th, .custom-table td {{
                text-align: center;
                padding: 10px;
                border: 1px solid #ccc;
                background-color: #fff;
                font-weight: normal;
                font-size: 14px;
            }}
            .custom-table th {{
                background-color: #f5f5f5;
                font-weight: bold;
                color: black;
            }}
        </style>

        <table class="custom-table">
            <tr>
                <th>검색 주소</th>
                <th>지목</th>
                <th>토지면적</th>
                <th>㎡당 개별공시지가 (기준일)</th>
            </tr>
            <tr>
                <td>{st.session_state["address"]}</td>
                <td>{lndcgrCodeNm}</td>
                <td>{lndpclAr}㎡</td>
                <td>{formatted_price}원 ({dateStandard})</td>
            </tr>
        </table>
        """, unsafe_allow_html=True)


    if 'items_cleaned_fGeoPrpos_area_dstrc_nm_list' in st.session_state:
        # 예: 좌측에 표시할 사용자 정의 레이블
        label1 = '포함'
        label2 = '저촉'
        label3 = '접합'
        area_dict = st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list']
        
        # ✅ 여기서 classified_area_dict 정의
        classified_area_dict = {'저촉': {}, '접합': {}, '포함': {}}
        for key, value in area_dict.items():
            if '(저촉)' in value:
                classified_area_dict['저촉'][key] = value
            elif '(접합)' in value:
                classified_area_dict['접합'][key] = value
            else:
                classified_area_dict['포함'][key] = value

        # 이제 안전하게 사용 가능
        joined_values1 = ', '.join(classified_area_dict['포함'].values())
        joined_values2 = ', '.join(classified_area_dict['저촉'].values())
        joined_values3 = ', '.join(classified_area_dict['접합'].values())

        html_table = f"""
        <style>
            .usezone-table {{
                border-collapse: collapse;
                width: 100%;
                font-size: 14px;
                border: 1px solid black;
            }}
            .usezone-table th {{
                background-color: #F4F4F4;
                font-weight: bold;
                text-align: center;
                color: black;
            }}
            .usezone-table td {{
                border: 1px solid #ccc;
                padding: 10px;
                text-align: left;
                background-color: #fff;
                font-weight: bold !important;  /* ✅ 우선순위 강제 적용 */
                font-size: 14px !important;      /* ✅ 글자 크기도 강제 적용 */
            }}
        </style>

        <table class="usezone-table">
            <tr>
                <th colspan="2">용도지역 및 용도지구</th>
            </tr>
            <tr>
                <td>{label1}</td>
                <td>{joined_values1}</td>
            </tr>
            <tr>
                <td>{label2}</td>
                <td>{joined_values2}</td>
            </tr>
            <tr>
                <td>{label3}</td>
                <td>{joined_values3}</td>
            </tr>
        </table>
        """

        # Streamlit에 출력
        st.markdown(html_table, unsafe_allow_html=True)

        st.markdown(
            """
            <p style="color:red; font-size:14px;">
            ※ 1. 포함(대지가 속해 있는 지역지구 등 정보 표기, 지역지구 등마다 건축제한 등 조건 확인), 2. 저촉(대지에 도로 등 면적이 포함될 경우 표기), 3. 접합(대지가 도로(소로, 중로, 대로 등) 등에 접할 경우 표기)<br>
            ※ 건축법 제44조에 따라 건축물은 대지에 2미터 이상 접도 의무(너비가 아닌 접한 길이), 다만, 도시계획도로 등이 아닌 옛 도로 등은 표기되지 않으니 건축법상 도로에 해당되는지 건축사와 별도 상담 확인
            </p>
            """,
            unsafe_allow_html=True
        )

def remove_parens_but_keep_exceptions(text, exceptions=None):
    if exceptions is None:
        exceptions = ['저촉', '접합', '폭']

    # 함수 내부에서 호출될 치환 함수 (정상 괄호쌍 처리)
    def replacer(match):
        inner = match.group(1).strip()
        if any(exc in inner for exc in exceptions):
            return f"({inner})"  # 예외 키워드는 그대로 유지
        else:
            return ''  # 나머지는 괄호 포함 제거

    # 1. 예외 괄호쌍만 남기고 나머지 괄호쌍 제거
    text = re.sub(r'\(([^()]*)\)', replacer, text)

    # 2. 닫히지 않은 여는 괄호 제거: 예) (유통산업발전
    text = re.sub(r'\([^\)]*$', '', text)

    return text

def clear_layer_session(layer):
    for suffix in ["zonename", "blocktype"]:
        key = f"{layer}_{suffix}"
        if key in st.session_state:
            del st.session_state[key]

def geoUser():
    if "land_info" not in st.session_state:
        return

    land_info = st.session_state["land_info"]

    posesnSeCodeNm = land_info.get("소유구분", "")
    nationInsttSeCodeNm = land_info.get("국가기관구분", "")
    ownshipChgCauseCodeNm = land_info.get("소유권 변동원인", "")
    ownshipChgDe = land_info.get("최근 소유권 변동일자", "")
    cnrsPsnCo = land_info.get("공유인수", "")
    lastUpdtDt = land_info.get("데이터 기준일자", "")

    html_table = f"""
    <style>
    .land-table {{
        width: 100%;
        border-collapse: collapse;
        text-align: center;
        margin: 20px auto;
        font-family: Arial, sans-serif;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        font-size: 14px;
        border: 1px solid black;
        table-layout: auto;
    }}
    .land-table th, .land-table td {{
        border: 1px solid #ccc;
        padding: 12px 15px;
        font-weight: bold;
    }}
    .land-table th {{
        background-color: #F4F4F4;
    }}
    .land-table tr:nth-child(even) {{
        background-color: #f9f9f9;
    }}
    .land-table tr:hover {{
        background-color: #e6f7ff;
    }}
    </style>

    <table class="land-table">
      <thead>
        <tr><th>항목</th><th>정보</th></tr>
      </thead>
      <tbody>
        <tr><td>소유구분</td><td>{posesnSeCodeNm}</td></tr>
        <tr><td>국가기관구분</td><td>{nationInsttSeCodeNm}</td></tr>
        <tr><td>소유권 변동원인</td><td>{ownshipChgCauseCodeNm}</td></tr>
        <tr><td>최근 소유권 변동일자</td><td>{ownshipChgDe}</td></tr>
        <tr><td>공유인수</td><td>{cnrsPsnCo}</td></tr>
        <tr><td>데이터 기준일자</td><td>{lastUpdtDt}</td></tr>
      </tbody>
    </table>
    """
    st.markdown(html_table, unsafe_allow_html=True)

# 산업단지 용지 조회 함수
def geoData():
    if st.session_state.get("block_other_functions"):
        return  # 🚫 차단된 경우 아무것도 하지 않음
    
    if 'vworld_x' not in st.session_state or 'vworld_y' not in st.session_state:
        return

    x = st.session_state['vworld_x']
    y = st.session_state['vworld_y']
    geom_filter = f"POINT({x} {y})"

    url = "https://api.vworld.kr/req/data"
    API_KEY = 'AF338F49-6AAA-3F06-BD94-FB6CB6817323'

    data_layers = ['LT_C_LHBLPN', 'LT_C_DAMYOJ']
    results = {}

    for layer in data_layers:
        params = {
            "service": "data",
            "version": "2.0",
            "request": "GetFeature",
            "key": API_KEY,
            "format": "json",
            "data": layer,
            "geomFilter": geom_filter,
            "geometry": "true",
            "attribute": "true",
            "crs": "EPSG:4326"
        }

        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            results[layer] = data
            #st.write(results[layer])
            # 필요한 키가 있는지 확인
            if 'response' in data and \
               'result' in data['response'] and \
               'featureCollection' in data['response']['result'] and \
               'features' in data['response']['result']['featureCollection']:

                features = data['response']['result']['featureCollection']['features']

                if not features:
                    st.warning(f"❗ '{layer}' 레이어에 해당 좌표의 정보가 없습니다.")
                    continue

                props = features[0].get('properties', {})
                
                # 레이어별로 키를 다르게 설정
                if layer == 'LT_C_DAMYOJ':  #산업단지일 경우
                    zonename = props.get('dan_name', '없음')
                    zonename = zonename +'산업단지'
                    blocktype = props.get('cat_nam', '없음')
                else:
                    zonename = props.get('zonename', '없음')
                    blocktype = props.get('blocktype', '없음')

               # ——— 국가산업단지인 경우 해당 표 출력 생략 ———
                if '광주첨단과학산업단지 개발사업' in zonename:
                   continue

                st.session_state[f'{layer}_zonename'] = zonename
                st.session_state[f'{layer}_blocktype'] = blocktype

                # ✅ HTML 표 출력
                html_table = f"""
                <table style="border-collapse: collapse; width: 100%; font-size: 14px;">
                    <thead>
                        <tr style="background-color: #E0ECFF;">
                            <th colspan="2" style="border: 1px solid #ccc; padding: 12px; background:#F4F4F4; text-align: center; font-size: 14px;">
                                {zonename} 정보
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="border: 1px solid #ccc; text-align:center; padding: 8px;">용도지구명</td>
                            <td style="border: 1px solid #ccc; text-align:center; padding: 8px; font-weight: bold;">{zonename}</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ccc; text-align:center; padding: 8px;">용지구분</td>
                            <td style="border: 1px solid #ccc; text-align:center; padding: 8px; font-weight: bold;">{blocktype}</td>
                        </tr>
                    </tbody>
                </table>
                """
                st.markdown(html_table, unsafe_allow_html=True)
        else:
            st.error(f"{layer} ❌ API 요청 실패: {response.status_code}")

    return results

def geoInfo():    
    geoUrl = 'https://api.vworld.kr/ned/data/getPossessionAttr'
    geoUrl2 = 'https://api.vworld.kr/ned/wfs/getPossessionWFS'    #토지면적 확인용 추가
    

    if 'pnu' not in st.session_state:
        st.warning("📌 PNU 정보가 없습니다. 주소를 먼저 검색하세요.")
        return

    geoPnu = st.session_state['pnu']

    geoParams = {
        "pnu": geoPnu,
        "format": "json",
        "numOfRows": "20",
        "pageNo": "1",
        "key": "51505128-E7A1-3BBE-A140-BBCF45FEF488",
        "domain": 'http://223.130.142.3:8501/'
    }

    try:
        response = requests.get(geoUrl, params=geoParams)

        if response.status_code == 200:
            result = response.json()            
            #st.json(result)

            try:
                fields = result.get("possessions", {}).get("field", [])  # ← 올바른 구조

                if isinstance(fields, list) and len(fields) > 0:
                    field = fields[0]
                else:
                    st.warning("❗ 토지 정보가 없습니다.")
                    return

                # 주요 항목 추출
                areaUse = field.get("lndcgrCodeNm", "없음")
                area = field.get("lndpclAr", "없음")
                landValue = field.get("pblntfPclnd", "없음")
                ownerType = field.get("posesnSeCodeNm", "없음")
                ownerNationtype = field.get("nationInsttSeCodeNm", "없음")
                ownReason = field.get("ownshipChgCauseCodeNm", "없음")
                ownDate = field.get("ownshipChgDe", "없음")
                ownNumber = field.get("cnrsPsnCo", "없음")
                dateStandard = field.get("lastUpdtDt", "없음")

                # ✅ land_info 저장
                st.session_state["land_info"] = {
                    "지목": areaUse,
                    "면적": area,
                    "공시지가": landValue,
                    "소유구분": ownerType,
                    "국가기관구분": ownerNationtype,
                    "소유권 변동원인": ownReason,
                    "최근 소유권 변동일자": ownDate,
                    "공유인수": ownNumber,
                    "데이터 기준일자": dateStandard
                }

                # 확인 출력
                #st.success("✅ 토지 정보가 성공적으로 불러와졌습니다.")
                #st.json(st.session_state["land_info"])

            except Exception as e:
                st.error(f"❗ 항목 추출 중 오류: {e}")

        else:
            st.error(f"❌ 요청 실패: {response.status_code}")
            st.text(response.text)

    except Exception as e:
        st.error(f"❗ 요청 중 오류 발생: {e}")

    geoParams2 = {
        "service": "WFS",                        # WFS 서비스 명시
        "version": "1.1.0",                      # WFS 버전
        "request": "GetFeature",                 # 요청 타입
        "typename": "dt_d160",                   # 피처 유형 (지목, 용도지역 등)
        "pnu": geoPnu,           # 필지고유번호 (19자리)
        "maxFeatures": "10",                     # 최대 결과 수
        "resultType": "results",                 # 전체 결과 반환 (또는 'hits' 가능)
        "srsName": "EPSG:4326",                  # 좌표계
        "output": "application/json",            # 응답 포맷 (GML2도 가능하지만 JSON 추천)
        "key": "AF66F589-DB7C-30FE-AFB5-C58D1C28B1A1",  # 발급받은 API 키
        "domain": "http://223.130.142.3:8501/"   # 호출 도메인
    }

    try:
        response = requests.get(geoUrl2, params=geoParams2)

        if response.status_code == 200:
            result = response.json()
            # st.json(result)  # 응답 구조 확인용 (필요 시 사용)

            try:
                # features 리스트에서 첫 번째 feature 추출
                features = result.get("features", [])
                
                if not features:
                    st.warning("❗ features 항목이 비어 있습니다.")
                    return

                properties = features[0].get("properties", {})
                lndpcl_ar = properties.get("lndpcl_ar", None)

                if lndpcl_ar is not None:
                    # ✅ 세션 상태에 저장
                    st.session_state["lndpcl_ar"] = lndpcl_ar
                    # st.success(f"✅ 토지면적 저장 완료: {lndpcl_ar}㎡")
                else:
                    st.warning("❗ 'lndpcl_ar' 항목이 존재하지 않습니다.")

            except Exception as e:
                st.error(f"❗ JSON 파싱 중 오류: {e}")

        else:
            st.error(f"❌ 요청 실패: {response.status_code}")
            st.text(response.text)

    except Exception as e:
        st.error(f"❗ 요청 중 예외 발생: {e}")



# 건축물 세부용도 정의 함수
def buildingIndex():
    
    url = "https://apis.data.go.kr/1613000/ebGuideBookListService/DTebGuideBookList"
    service_key = "zGvV1ra5mlbgyKU7qBkKuXDzKjjwKbVLsXdiNlXSPX0wCydBKmq6kgSEeAS3jtNYW85Kyp4vSv34AcdCGMu4CA=="

    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 10,
        "_type": "json"  # 적용되지 않아도 넣어둠
    }

    response = requests.get(url, params=params)

    # 1. EUC-KR로 디코딩
    try:
        decoded = response.content.decode("euc-kr", errors="replace")
    except UnicodeDecodeError as e:
        st.error("❌ 문자 인코딩 오류 발생")
        st.code(str(e))
        st.stop()

    # 2. XML 파싱
    try:
        root = ET.fromstring(decoded)
        items = root.findall(".//item")

        #st.success("✅ XML 파싱 성공!")
        if "guide_data" not in st.session_state:
            st.session_state.guide_data = []

        for idx, item in enumerate(items, 1):
            if idx > 315:
                break

            facil_name = item.findtext("FACIL_NM", "제목 없음")
            cate = item.findtext("CATE_NM", "카테고리 없음")
            desc = item.findtext("DESCRIPTION", "설명 없음")
            #url = item.findtext("ACCESS_URL", "#")

            # 딕셔너리 형태로 구성
            guide_info = {
                "idx": idx,
                "facil_name": facil_name,
                "cate": cate,
                "desc": desc
            }

            # 세션 상태에 저장 (누적)
            st.session_state.guide_data.append(guide_info)
    except ET.ParseError as e:
        st.error("❌ XML 파싱 오류 발생")
        st.code(decoded[:1000])

def areaPermission():
    pdf_path = "data/buildinguses.pdf"

    # 세션 상태 확인
    if 'items_cleaned_fGeoPrpos_area_dstrc_nm_list' not in st.session_state:
        #st.warning("검색 주소지의 정보가 없습니다.")
        return
    # 세션 상태에서 지역명 리스트 가져오기
    area_dict = st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list']
    area_list = [a.strip() for a in list(area_dict.values())]

    # ✅ 특정 문구가 포함된 경우 함수 중단
    block_keywords = ["국립공원", "군사시설", "개발제한구역"]
    found = [kw for kw in block_keywords if any(kw in area for area in area_list)]

    if found:
        st.markdown(
            f"""
            <p style="color:red; font-size:14px; font-weight:normal; text-align:left;">
                ➡️ 해당 지역({', '.join(found)})은 관련 규제로 인해 건축 행위가 제한됩니다. 자세한 사항은 담당 부서에 문의하세요.
            </p>
            """,
            unsafe_allow_html=True
        )
        return  # 🚫 아래 코드 실행 중단

    try:
        # 1. 호수 → 용도 매핑 딕셔너리 정의
        ho_to_category = {
            1: '단독주택', 2: '공동주택', 3: '제1종근린생활시설', 4: '제2종근린생활시설',
            5: '문화 및 집회시설', 6: '종교시설', 7: '판매시설', 8: '운수시설', 9: '의료시설',
            10: '교육연구시설(제2종근린생활시설 제외)', 11: '노유자시설', 12: '수련시설', 13: '운동시설',
            14: '업무시설', 15: '숙박시설', 16: '위락시설', 17: '공장',
            18: '창고시설(제2종근린생활시설, 위험물 저장 및 처리시설 또는 그 부속용도 제외)',
            19: '위험물 저장 및 처리시설', 20: '자동차 관련 시설', 21: '동물 및 식물 관련시설',
            22: '자원순환 관련시설', 23: '교정시설(제1종근린생활시설 제외)', 23.2: '국방군사시설',
            24: '방송통신시설(제1종근린생활시설 제외)', 25: '발전시설', 26: '묘지관련시설',
            27: '관광휴게시설', 28: '장례식장', 29: '야영장 시설',
        }

        df = pd.read_excel("data/areaPermission.xlsx")
        df.columns = df.columns.str.strip()
        df['용도지역지구명'] = df['용도지역지구명'].str.strip()

        # 세션 상태 확인
        if 'items_cleaned_fGeoPrpos_area_dstrc_nm_list' not in st.session_state:
            #st.warning("검색 주소지의 정보가 없습니다.")
            return

        # 세션 상태에서 지역명 리스트 가져오기
        area_dict = st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list']
        area_list = [a.strip() for a in list(area_dict.values())]

        target_keywords = ['농공단지', '국가산업단지', '일반산업단지', '지방산업단지', '도시첨단산업단지', '준산업단지', '제1종지구단위계획구역', '제2종지구단위계획구역', '지구단위계획구역', '택지개발지구']

        # 1. 안내 메시지 출력 (조건부)
        found = [kw for kw in target_keywords if kw in area_list]
        if found:
            # 1) 국가산업단지 + 상업지역 동시 포함
            if '국가산업단지' in found and any('상업지역' in a for a in area_list):
                st.markdown(
                    """
                    <p style="color:blue; font-size:14px; font-weight:bold;">
                    ➡️ 국가산업단지 내 상업지역은 아래 표에 따라 건축가능합니다.
                    </p>
                    """,
                    unsafe_allow_html=True
                )
            # 2) 국가산업단지만 있는 경우
            elif '국가산업단지' in found:
                st.markdown(
                    """
                    <p style="color:red; font-size:14px; font-weight:bold;">
                    ➡️ 국가산업단지인 경우, 상업지역을 제외한 지역은 국가산업단지 관리기준(주거지역 주택 및 상가 비율 6:4 제한, 층수, 용도 제한 등)과 관련된 제한사항을 반드시 확인하시기 바랍니다.
                    </p>
                    """,
                    unsafe_allow_html=True
                )

            # 3) 나머지 키워드 안내 (국가산업단지 제외)
            others = [kw for kw in found if kw != '국가산업단지']
            if others:
                st.markdown(
                    f"""
                    <p style="color:red; font-size:14px; font-weight:bold;">
                    ➡️ 해당 지구({', '.join(others)})에 대한 세부 용도 제한 정보는 단지, 구역, 지구별 세부계획 정보에 별도의 제한사항이 있으니 꼭 확인하시기 바랍니다.
                    </p>
                    """,
                    unsafe_allow_html=True
                )

        # 유효 지역 필터링
        valid_area_names = df['용도지역지구명'].dropna().unique().tolist()
        allowed_zones = ['자연경관지구', '자연특화지구', '시가지경관지구', '방재지구', '보호지구', '중요시설물보호지구', '중요시설물보호지구(공항)']
        valid_area_list = [a for a in area_list if a in valid_area_names and (a.endswith("지역") or a in allowed_zones)]

        if not valid_area_list:
            st.warning("❗ 조건에 맞는 유효한 지역이 없습니다.")
            return

        #st.success(f"✅ 확인이 필요한 용도지역/지구: {', '.join(valid_area_list)}")

        # 호번호 및 분류
        df['호번호'] = df['법률명'].apply(extract_ho_number)
        df['분류'] = df['호번호'].map(ho_to_category)
        df[['호번호', '목글자']] = df['법률명'].apply(lambda x: pd.Series(extract_ho_mok(x)))

        # 기준 지역 설정
        base_area = next((a for a in valid_area_list if a.endswith("지역")), None)
        if not base_area:
            st.warning("기준 지역이 없습니다.")
            return
        #st.subheader(f"📌 기준 지역: {base_area}")

        base_df = df[df['용도지역지구명'] == base_area][['분류', '토지이용명', '호번호', '목글자']].drop_duplicates()
        base_df['토지이용명'] = base_df['토지이용명'].apply(clean_text)
        base_df = base_df.sort_values(by=['호번호', '목글자'])

        # 최종 테이블 초기화
        final_df = base_df.copy()

        # 각 지역의 건축 가능 여부 및 법률명 매핑
        for area in valid_area_list:
            area_df = df[df['용도지역지구명'] == area][['분류', '토지이용명', '가능여부', '법률명', '조건제한예외사항']].copy()

            # ✅ 토지이용명 정제 추가 (중요!)
            area_df['토지이용명'] = area_df['토지이용명'].apply(clean_text)

            area_df.columns = ['분류', '토지이용명', f'{area}_가능여부', f'{area}_법률명', f'{area}_조건']
            final_df = final_df.merge(area_df, on=['분류', '토지이용명'], how='left')

        searchOn = False

        # 검색어 입력 필드 추가
        search_term = st.text_input("🔍 세부용도 검색", placeholder="예: 의원, 오피스텔 등")

        # 필터링된 테이블 준비
        filtered_df = final_df.copy()

        if search_term:
            filtered_df = filtered_df[filtered_df['토지이용명'].str.contains(search_term.strip(), na=False)]

        # PDF 파일 준비
        with open("data/gjcity24.pdf", "rb") as f1:
            gj_pdf = f1.read()

        with open("data/use.pdf", "rb") as f2:
            use_pdf = f2.read()

        # 📌 커스텀 CSS: 버튼 크기 축소
        st.markdown("""
        <style>
        .stDownloadButton button {
            font-size: 11px;
            padding: 2px 6px;
            height: 11px;
            line-height: 1;
            border-radius: 0px;
            margin-top: 0px;
        }
        </style>
        """, unsafe_allow_html=True)

        # 📂 열 구조: [범례(왼쪽), 도시계획조례 버튼, 시행령 버튼]
        col1, col2, col3 = st.columns([7.8, 1.2, 1])

        with col1:
            st.markdown(
                """
                <p style="font-size:15px; font-weight:bold; color:black; text-align: right; margin-bottom:0;">
                    <span style="color:black;">범례 : </span>
                    <span style="color:green;">&nbsp;&nbsp; ０ 건축 가능</span>, 
                    <span style="color:#ff5e00;"> &nbsp;&nbsp;▲ 조건부 건축 가능(마우스 포인터를 올리면 조건 보임)</span>, 
                    <span style="color:red;"> &nbsp;&nbsp;X 건축 불가능</span>
                </p>
                """,
                unsafe_allow_html=True
            )

        with col2:
            st.download_button(
                label="📄 시 도시계획조례 별표 24",
                data=gj_pdf,
                file_name="광주광역시_도시계획조례_별표24.pdf",
                mime="application/pdf",
                key="gjcity24_download"
            )

        with col3:
            st.download_button(
                label="📄 건축법 시행령 별표 1",
                data=use_pdf,
                file_name="건축법_시행령_별표1.pdf",
                mime="application/pdf",
                key="use_pdf_download"
            )

        # ✅ HTML 테이블 시작
        table_html = "<table style='width:100%; border-collapse: collapse; font-size:14px; border: 1px solid black;'>"

        # ✅ 헤더 생성
        table_html += "<thead><tr>"
        table_html += "<th style='border:1px solid #ddd; padding:6px; color:black; background:#F4F4F4;'>시설군</th>"
        table_html += "<th style='border:1px solid #ddd; padding:6px; color:black; background:#F4F4F4;'>세부용도</th>"
        for area in valid_area_list:
            table_html += f"<th style='border:1px solid #ddd; padding:6px; color:black; background:#F4F4F4;'>{area} 건축가능</th>"

        table_html += f"<th style='border:1px solid #ddd; padding:6px; color:black; background:#F4F4F4;'>건축물 용도 정의</th>"    
        #table_html += f"<th style='border:1px solid #ddd; padding:6px; background:#f0f0f0;'>{base_area} 법률명</th>"
        table_html += "</tr></thead>"

        # ✅ 데이터 본문
        table_html += "<tbody>"
        for _, row in filtered_df.iterrows():
            table_html += "<tr>"
            table_html += f"<td style='border:1px solid #ddd; text-align: center; padding:6px'>{html.escape(str(row['분류']))}</td>"
            table_html += f"<td style='border:1px solid #ddd; text-align: center; font-weight:bold; padding:6px'>{html.escape(str(row['토지이용명']))}</td>"

            for area in valid_area_list:
                g_col = f'{area}_가능여부'
                c_col = f'{area}_조건'

                g_raw = row.get(g_col, '')
                g_val = str(g_raw).strip() if pd.notna(g_raw) else ''

                cond_raw = row.get(c_col, '')
                cond = str(cond_raw).strip() if pd.notna(cond_raw) else ''
                cond = html.escape(cond).replace('\n', '&#10;')

                if g_val.startswith("건축가능"):
                    if cond:
                        status_display = f"<span title='{cond}' style='color:#ff5e00; font-weight:bold;'>▲</span>"
                    else:
                        status_display = "<span style='color:green; font-weight:bold;'>０</span>"
                elif g_val.startswith("건축금지"):
                    if cond:
                        status_display = f"<span title='{cond}' style='color:#ff5e00; font-weight:bold;'>▲</span>"
                    else:
                        status_display = "<span style='color:red; font-weight:bold;'>X</span>"
                elif g_val:
                    status_display = html.escape(g_val)
                else:
                    status_display = "-"

                table_html += f"<td style='border:1px solid #ddd; text-align:center; padding:6px'>{status_display}</td>"

            l_col = f'{base_area}_법률명'
            l_raw = row.get(l_col, '')
            l_val = str(l_raw) if pd.notna(l_raw) else ''

            table_html += f"<td style='border:1px solid #ddd; padding:6px'>{html.escape(l_val)}</td>"
            table_html += "</tr>"
        table_html += "</tbody></table>"

        # ✅ 렌더링
        components.html(table_html, height=800, scrolling=True)        
        zoningAllow(pdf_path)     

    except FileNotFoundError:
        st.error("❌ 'data/areaPermission.xlsx' 파일을 찾을 수 없습니다.")
    except KeyError as e:
        st.error(f"❌ 컬럼 오류: {e}")
    except Exception as e:
        st.error("❌ 알 수 없는 오류가 발생했습니다.")
        st.code(str(e))
        
# 건폐율 용적률 추출 함수
def spaceIndex():
    # 세션 상태 확인
    if 'items_cleaned_fGeoPrpos_area_dstrc_nm_list' not in st.session_state:
        #st.warning("검색 주소지의 정보가 없습니다.")
        return
    # 세션 상태에서 지역명 리스트 가져오기
    area_dict = st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list']
    area_list = [a.strip() for a in list(area_dict.values())]

    # ✅ 특정 문구가 포함된 경우 함수 중단
    block_keywords = ["국립공원", "군사시설", "개발제한구역"]
    found = [kw for kw in block_keywords if any(kw in area for area in area_list)]

    if found:
        st.markdown(
            f"""
            <p style="color:red; font-size:14px; font-weight:normal; text-align:left;">
                ➡️ 해당 지역({', '.join(found)})은 관련 규제로 인해 건축 행위가 제한됩니다. 자세한 사항은 담당 부서에 문의하세요.
            </p>
            """,
            unsafe_allow_html=True
        )
        return  # 🚫 아래 코드 실행 중단

    target_keywords = [
        '농공단지', '국가산업단지', '일반산업단지', '지방산업단지',
        '도시첨단산업단지', '준산업단지', '제1종지구단위계획구역',
        '제2종지구단위계획구역', '지구단위계획구역', '택지개발지구'
    ]

    found = [kw for kw in target_keywords if kw in area_list]
    if found:
        # 1) 국가산업단지 + 상업지역 동시 포함
        if '국가산업단지' in found and any('상업지역' in a for a in area_list):
            st.markdown(
                """
                <p style="color:blue; font-size:14px; font-weight:bold;">
                ➡️ 국가산업단지 내 상업지역은 아래 표에 따라 건축가능합니다.
                </p>
                """,
                unsafe_allow_html=True
            )
        # 2) 국가산업단지만 있는 경우
        elif '국가산업단지' in found:
            st.markdown(
                """
                <p style="color:red; font-size:14px; font-weight:bold;">
                ➡️ 국가산업단지인 경우, 상업지역을 제외한 지역은 국가산업단지 관리기준(주거지역 주택 및 상가 비율 6:4 제한, 층수, 용도 제한 등)과 관련된 제한사항을 반드시 확인하시기 바랍니다.
                </p>
                """,
                unsafe_allow_html=True
            )

        # 3) 나머지 키워드 안내 (국가산업단지 제외)
        others = [kw for kw in found if kw != '국가산업단지']
        if others:
            st.markdown(
                f"""
                <p style="color:red; font-size:14px; font-weight:bold;">
                ➡️ 해당 지구({', '.join(others)})에 대한 세부 용도 제한 정보는
                단지·구역별 세부계획에 별도 제한사항이 있으니 꼭 확인하세요.
                </p>
                """,
                unsafe_allow_html=True
            )

    building_index1 = {
    '제1종전용주거지역': ('40% 이하', '80% 이하'),   # 키 : 값 () 튜플 변경불가
    '제2종전용주거지역': ('40% 이하', '120% 이하'),
    '제1종일반주거지역': ('60% 이하', '150% 이하'),
    '제2종일반주거지역': ('60% 이하', '220% 이하'),
    '제3종일반주거지역': ('50% 이하', '250% 이하'),
    '준주거지역': ('60% 이하', '400% 이하'),
    '중심상업지역': ('70% 이하', '1300% 이하'),
    '일반상업지역': ('60% 이하', '1000% 이하'),
    '근린상업지역': ('60% 이하', '700% 이하'),
    '유통상업지역': ('60% 이하', '800% 이하'),
    '전용공업지역': ('70% 이하', '300% 이하'),
    '일반공업지역': ('70% 이하(다만, 공장, 창고, 자동차 관련 시설 이외의 용도를 포함 하는 경우 60% 이하)', '350% 이하'),
    '준공업지역': ('70% 이하(다만, 공장, 창고, 자동차 관련 시설 이외의 용도를 포함 하는 경우 60% 이하)', '400% 이하'),
    '보전녹지지역': ('20% 이하', '60% 이하'),
    '생산녹지지역': ('20% 이하', '60% 이하'),
    '자연녹지지역': ('20% 이하', '60% 이하'),
    '보전관리지역': ('20% 이하', '80% 이하'),
    '생산관리지역': ('20% 이하', '80% 이하'),
    '계획관리지역': ('40% 이하', '90% 이하'),
    '농림지역': ('20% 이하', '60% 이하'),
    '자연환경보전지역': ('20% 이하', '60% 이하'),
    '기타지역': ('20% 이하', '50% 이하'),
    }

    building_index2 = {    
    '자연취락지구': ('40% 이하', '80% 이하'),               # 여기 부터는 상기 지역과 중복 적용되는 지역임
    '방화지구': ('80% 이하(주요구조부와 외벽이 내화구조인 건축물)', ),                 # 다른 지역과 방화지구가 중첩될 시 건폐율은 방화지구 적용
    '자연경관지구': ('40% 이하', ),
    '특화경관지구': ('40% 이하', ),
    #'시가지경관지구': ( , ),
    }

    building_index3 = {    
    '농공단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    #'국가산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '일반산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '지방산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '도시첨단산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '준산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '제1종지구단위계획구역': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '지구단위계획구역': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    } 

    matching_data1 = {k: v for k, v in building_index1.items() if k in area_dict.values()}
    matching_data2 = {k: v for k, v in building_index2.items() if k in area_dict.values()}
    matching_data3 = {k: v for k, v in building_index3.items() if k in area_dict.values()}

    # 최종 결과를 담을 리스트
    final_results = []

    # matching_data1 처리
    if matching_data1:
        for k, v in matching_data1.items():
            건폐율 = v[0]
            용적률 = v[1] if len(v) == 2 else "정보 없음"
            final_results.append({"지역/지구": k, "건폐율": 건폐율, "용적률": 용적률})

    # matching_data2 처리
    if matching_data2:
        for k, v in matching_data2.items():
            건폐율 = v[0]
            # 용적률이 없으면 matching_data1의 것 활용
            용적률 = "정보 없음"
            for k1, v1 in matching_data1.items():
                if len(v1) == 2:
                    용적률 = v1[1]
                    break
            final_results.append({"지역/지구": k, "건폐율": 건폐율, "용적률": 용적률})

    # matching_data3 처리
    if matching_data3:
        for k, v in matching_data3.items():
            건폐율 = v[0]
            용적률 = v[1] if len(v) > 1 else "정보 없음"
            final_results.append({"지역/지구": k, "건폐율": 건폐율, "용적률": 용적률})

    # 📊 표로 시각화
    # 결과가 있다면 시각화
    if final_results:
        df_result = pd.DataFrame(final_results)

        # 인덱스 구분 설정
        if len(final_results) == 3:
            df_result.index = ["기준", "1차 강화/완화", "최종"]
        elif len(final_results) == 2:
            df_result.index = ["기준", "최종"]
        elif len(final_results) == 1:
            df_result.index = ["최종"]

        # 인덱스를 열로 변환
        df_result.reset_index(inplace=True)
        df_result.rename(columns={"index": "구분"}, inplace=True)

        # 열 순서 보장
        df_result = df_result[["구분", "지역/지구", "건폐율", "용적률"]]

        # ✅ 중간 확인용 출력
        #st.write("📋 최종 DataFrame 확인")
        #st.dataframe(df_result)

        # HTML 테이블 생성
        html_table = df_result.to_html(index=False, classes='styled-table', escape=False)

        # ✅ HTML 원본 코드 확인
        #st.code(html_table, language='html')
        
        #st.markdown(df_result.to_html(index=False), unsafe_allow_html=True)
        st.markdown(
            f"""
            <style>
                table.custom-table {{
                    border-collapse: collapse;
                    width: 100%;
                    font-size: 14px;
                    border: 1px solid black;
                }}
                table.custom-table th {{
                    background-color: #F4F4F4;
                    color: black;
                    text-align: center;
                    padding: 8px;
                }}
                table.custom-table td {{
                    border: 1px solid #dddddd;
                    text-align: center;
                    padding: 8px;
                    color: black;
                    font-size: 14px;
                    font-weight: bold;
                }}
                table.custom-table tr:nth-child(even) {{
                    background-color: #f2f2f2;
                }}
            </style>
            """,
            unsafe_allow_html=True
        )

        # 클래스명 명시하여 적용
        html_table = df_result.to_html(index=False, classes='custom-table', escape=False)

        # 다시 출력
        st.markdown(html_table, unsafe_allow_html=True)

        # ✅ 최종 행에서 건폐율/용적률 값 추출
        final_row = df_result[df_result["구분"] == "최종"]
        if not final_row.empty:
            final_coverage = final_row.iloc[0]["건폐율"]
            final_floor_area_ratio = final_row.iloc[0]["용적률"]

            if "제한사항" in final_coverage or "제한사항" in final_floor_area_ratio:
                st.markdown(
                    f"""
                    <p style="color: red; font-size:14px; font-weight: bold;">
                    ➡️ 해당 지구({', '.join(found)})에 대한 세부 용도 제한사항이 있어 건폐율·용적률 계산이 불가능합니다.\n 단지, 구역, 지구별 세부계획 정보에 별도의 제한사항이 있으니 꼭 확인하시기 바랍니다.
                    </p>
                    """,
                    unsafe_allow_html=True
                )
                return
        else:
            st.warning("⚠️ 최종 건폐율 또는 용적률 정보가 없습니다.")
            return

        # ✅ 대지면적 확인
        if "lndpcl_ar" not in st.session_state:
            st.warning("📌 토지 정보가 없습니다. 먼저 주소를 검색해주세요.")
            return

        # ✅ 값 변환
        coverage_rate = parse_percent(final_coverage)
        floor_area_ratio = parse_percent(final_floor_area_ratio)

        if coverage_rate is None or floor_area_ratio is None:
            st.error("📌 건폐율 또는 용적률 형식이 잘못되었습니다.")
            return

        try:
            lndpcl_ar = float(st.session_state["lndpcl_ar"])  # 예: 330.0
        except ValueError:
            st.error("📌 대지면적 형식이 잘못되었습니다.")
            return

        # ✅ 면적 계산
        building_area = round(lndpcl_ar * (coverage_rate / 100), 1)
        total_floor_area = round(lndpcl_ar * (floor_area_ratio / 100), 1)
        estimated_floors = int(total_floor_area // building_area) if building_area > 0 else 0

        # ✅ 평 단위 계산
        def to_pyung(area_sqm):
            return round(area_sqm / 3.305785, 1)

        lndpcl_py = to_pyung(lndpcl_ar)
        building_py = to_pyung(building_area)
        total_py = to_pyung(total_floor_area)

        # ✅ HTML 테이블 표시 (㎡ + 평)
        html_table = f"""
        <table style="width:100%; border-collapse:collapse; text-align:center; font-size:15px;">
            <thead>
                <tr style="background-color:#f2f2f2;">
                    <th colspan="3" style="
                        background-color:#f2f2f2;
                        padding:10px;
                        font-size:16px;
                        border:1px solid #ddd;
                        text-align:center;
                    ">
                    건축 가능 면적 및 층수 계산 결과<br>
                    <span style="font-size:14px; color:red;">
                        (대지에 건축물과 도로 등 저촉 부분이 없다는 가정(별도 계산 필요), 상업지역은 광주광역시 도시계획조례 별표24의 용도용적제 기준에 따라  
                        건축물 용도비율 및 용적률, 층수 등의 제한사항을 별도 확인하여야 함)
                    </span>
                    </th>
                </tr>
                <tr style="background-color:#f2f2f2;">
                    <th style="border:1px solid #ddd; padding:8px;">구분</th>
                    <th style="border:1px solid #ddd; padding:8px;">값 (㎡)</th>
                    <th style="border:1px solid #ddd; padding:8px;">값 (평)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="border:1px solid #ddd; padding:8px;">대지면적</td>
                    <td style="border:1px solid #ddd; padding:8px;">{lndpcl_ar:,.1f} ㎡</td>
                    <td style="border:1px solid #ddd; padding:8px;">{lndpcl_py:,.1f} 평</td>
                </tr>
                <tr>
                    <td style="border:1px solid #ddd; padding:8px;">최대 건축면적</td>
                    <td style="border:1px solid #ddd; padding:8px;">{building_area:,.1f} ㎡</td>
                    <td style="border:1px solid #ddd; padding:8px;">{building_py:,.1f} 평</td>
                </tr>
                <tr>
                    <td style="border:1px solid #ddd; padding:8px;">최대 연면적</td>
                    <td style="border:1px solid #ddd; padding:8px;">{total_floor_area:,.1f} ㎡</td>
                    <td style="border:1px solid #ddd; padding:8px;">{total_py:,.1f} 평</td>
                </tr>
                <tr>
                    <td style="border:1px solid #ddd; padding:8px;">예상 최대 층수</td>
                    <td colspan="2" style="border:1px solid #ddd; padding:8px;">{estimated_floors}층</td>
                </tr>
            </tbody>
        </table>
        """

        # ✅ 출력
        st.markdown(html_table, unsafe_allow_html=True)

# PDF 추출 함수
def extract_pdf_pages(original_path, page_range):
    start_page, end_page = page_range
    doc = fitz.open(original_path)
    
    new_pdf = fitz.open()  # 새 PDF 생성
    for i in range(start_page - 1, end_page):  # 0-based 인덱스 사용
        new_pdf.insert_pdf(doc, from_page=i, to_page=i)
    
    pdf_bytes = BytesIO()
    new_pdf.save(pdf_bytes)
    new_pdf.close()
    doc.close()
    
    pdf_bytes.seek(0)
    return pdf_bytes

def zoningAllow(pdf_path):
    #st.write(" ")
    #st.markdown(
        #f"""
        #<p style="color:blue; font-size:20px; font-weight:bold;">
            #3. 건축행위 제한사항
        #</p>
        #""",
        #unsafe_allow_html=True
    #)
    # ✅ 세션 상태 초기화
    if 'show_pdf' not in st.session_state:
        st.session_state['show_pdf'] = False

    # ✅ 토글 버튼
    if st.button("📄 도시계획조례 책자로 허용/불허 용도 확인"):
        st.session_state['show_pdf'] = not st.session_state['show_pdf']

    # ✅ 세션 상태 유지 시 PDF 표시
    if st.session_state['show_pdf']:
        # 지역 이름 매칭
        area_dict = st.session_state.get('items_cleaned_fGeoPrpos_area_dstrc_nm_list', {})
        pdf_page_ranges = {
            '제1종전용주거지역': (1, 6), '제2종전용주거지역': (1, 6),
            '제1종일반주거지역': (1, 6), '제2종일반주거지역': (1, 6),
            '제3종일반주거지역': (1, 6), '준주거지역': (1, 6),
            '중심상업지역': (7, 12), '일반상업지역': (7, 12),
            '근린상업지역': (7, 12), '유통상업지역': (7, 12),
            '전용공업지역': (13, 18), '일반공업지역': (13, 18),
            '준공업지역': (13, 18), '보전녹지지역': (19, 24),
            '생산녹지지역': (19, 24), '자연녹지지역': (19, 24),
            '보전관리지역': (25, 30), '생산관리지역': (25, 30),
            '계획관리지역': (25, 30),
        }

        matching = {k: v for k, v in pdf_page_ranges.items() if k in area_dict.values()}

        if not matching:
            st.warning("🔍 해당 지역에 대한 PDF 범위 정보가 없습니다.")
            return

        if len(matching) > 1:
            st.warning("⚠️ 중첩 지정된 지역이 여러 개입니다. 법령 확인이 필요합니다.")
            return

        import fitz
        from PIL import Image
        import io

        matched_name = list(matching.keys())[0]
        st.markdown(f"""
        <p style="font-size:14px; font-weight:normal; color:white; background-color:#000000">
            <span style="font-size:20px; font-weight:bold;">{matched_name}</span>의 건축물 허용/불허 용도는 도시계획조례 기준에 따릅니다.
        </p>
        """, unsafe_allow_html=True)

        try:
            doc = fitz.open(pdf_path)
            start, end = matching[matched_name]
            for i in range(start - 1, end):
                page = doc.load_page(i)
                pix = page.get_pixmap(dpi=150)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                st.image(img, use_container_width=True)
        except Exception as e:
            st.error(f"PDF 로딩 오류: {e}")

# districtAllow 함수
def districtAllow(pdf_path2):
    #st.write(' ')
    #st.markdown(
        #f"""
        #<p style="color:blue; font-size:20px; font-weight:bold;">
            #4. 용도지구의 건축물 불허 용도 및 건축 제한사항
        #</p>
        #""",
        #unsafe_allow_html=True
    #)

    pdf_page_ranges = {    
        '자연경관지구': (1, 2),
        '특화경관지구': (3, 4),
        '시가지경관지구': (5, 7),
        '특정용도제한지구': (8, 8),
        '중요시설물보호지구': (9, 9),
        '역사문화환경보호지구': (10, 10),
        '고도지구': (11, 11),
        '방재지구': (12, 12),
        '개발진흥지구': (13, 13),
    }

    if 'items_cleaned_fGeoPrpos_area_dstrc_nm_list' not in st.session_state:
        #st.write("검색 주소지의 정보가 없습니다.")
        return
    
    # geoParams 내 items_cleaned_fGeoPrpos_area_dstrc_nm_list_dict 변수 가져와 새 변수 적용해 사용
    area_dict = st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list']

    # pdf_page_ranges 내 키와 area_dict 내 값들이 일치하는 항목만 필터링
    matching_data3 = {k: v for k, v in pdf_page_ranges.items() if k in area_dict.values()}

    if len(matching_data3) >= 2:
        st.write("두 개 이상의 지구가 중첩 지정된 것으로 확인되었습니다. 자세한 사항은 국토의 계획 및 이용에 관한 법률 제84조를 검토 적용하여 주시기 바랍니다.")
    elif len(matching_data3) == 1:
        matched_name = list(matching_data3.keys())[0]
        st.markdown(
            f"""
            <p style="font-size:14px; font-weight:normal; color:black; background-color:white">
                <span style="font-size:20px; color:black; font-weight:bold; background-color:white">{matched_name}</span>의 건축 제한사항은 광주광역시 도시계획조례에 따라 아래와 같습니다.
            </p>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <p style="color:red; font-size:14px; font-weight:normal;">
                ※ 건축행위 제한의 용도지역의 건축물 허용 용도일지라도 용도지구의 건축물 불허 용도에 해당 될 시 해당 용도의 건축 불가
            </p>
            """,
            unsafe_allow_html=True
        )

        # PDF 로드 및 출력
        doc = fitz.open(pdf_path2)
        start_page, end_page = matching_data3[matched_name]
        for page_num in range(start_page - 1, end_page):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            st.image(img, use_container_width=True)

    else:  # 일치하는 지역이 전혀 없는 경우
        st.markdown(
            f"""
            <p style="font-size:14px; font-weight:normal; color:red;">
                선택한 주소지에는 도시계획조례에 따른 용도지구 제한사항이 존재하지 않거나 정보가 등록되어 있지 않습니다.
            </p>
            """,
            unsafe_allow_html=True
        )

# 건축 인허가 정보 공통 API 호출 함수 (JSON 응답)
def call_arch_pms_service_json(operation: str):
    base_url = f"https://apis.data.go.kr/1613000/ArchPmsHubService/{operation}"  
    service_key = "zGvV1ra5mlbgyKU7qBkKuXDzKjjwKbVLsXdiNlXSPX0wCydBKmq6kgSEeAS3jtNYW85Kyp4vSv34AcdCGMu4CA=="

    required_keys = ['sigunguCd', 'bjdongCd', 'bun']
    if any(k not in st.session_state for k in required_keys):
        #st.warning("📌 주소 정보가 없습니다. 먼저 주소를 검색해 주세요.")
        return None

    sigunguCd = st.session_state['sigunguCd']
    bjdongCd = st.session_state['bjdongCd']
    bun = st.session_state.get('bun', '').zfill(4)
    ji = st.session_state.get('ji', '').zfill(4)
    platGbCd = '1' if st.session_state.get('san') else '0'

    params = {
        "serviceKey": service_key,
        "sigunguCd": sigunguCd,
        "bjdongCd": bjdongCd,
        "platGbCd": platGbCd,
        "bun": bun,
        "ji": ji,
        "numOfRows": 30,
        "pageNo": 1,
        "_type": "json"
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"{operation} API 호출 실패")
        st.code(response.text)
        return None

# HTML 테이블 생성
def make_html_table_multi(title, items, field_map):
    if not items:
        return

    # ——— 6개 필드가 모두 빈값 or 0 이면 field_map 에서 제거 ———
    for key in ["platArea", "archArea", "totArea",
                "vlRatEstmTotArea", "bcRat", "vlRat"]:
        if key in field_map:
            remove = True
            for item in items:
                raw = item.get(key)
                # 빈값 또는 문자열 "0", 숫자 0 모두 허용
                if raw in (None, "", "0", 0):
                    continue
                # 숫자로 변환 후 0 체크
                try:
                    if float(raw) != 0:
                        remove = False
                        break
                except:
                    # 비숫자 값이 하나라도 있으면 유지
                    remove = False
                    break
            if remove:
                field_map.pop(key)

    # ——— 그 다음 column_count, header, rows 계산 ———
    column_count = len(items) + 1
    header = "".join(f"<th>정보 {i+1}</th>" for i in range(len(items)))

    # 천단위 쉼표 처리할 키 리스트
    number_keys = {'platArea', 'archArea', 'totArea', 'vlRatEstmTotArea',
                   'sumArchArea', 'sumTotArea', 'area', 'len', 'heit'}

    # 테이블 헤더
    header = "".join(f"<th>정보 {i+1}</th>" for i in range(len(items)))

    # 테이블 본문
    rows = ""
    for key, label in field_map.items():
        row = f"<tr><td>{label}</td>"
        for item in items:
            raw_value = item.get(key, "")
            if key in number_keys:
                try:
                    # 천단위 쉼표 + 소수점 2자리 유지, 불필요한 0 제거
                    value = f"{float(raw_value):,.2f}".rstrip("0").rstrip(".")
                except:
                    value = str(raw_value)
            else:
                value = str(raw_value).replace("\n", "<br>")
            row += f"<td>{value}</td>"
        row += "</tr>"
        rows += row

    # 전체 HTML 코드
    html_code = f"""
    <style>
    .scroll-wrap {{
        overflow-x: auto;
        border: 0px solid #333;
        margin-bottom: 1rem;
    }}
    .fixed-wrap-table {{
        border-collapse: collapse;
        table-layout: auto;
        width: 100%;
        font-size: 14px;
    }}
    .fixed-wrap-table th,
    .fixed-wrap-table td {{
        border: 1px solid #ddd;
        padding: 8px;
        min-width: 150px;
        max-width: 200px;
        word-wrap: break-word;
        word-break: break-word;
        white-space: normal;
        text-align: center;
        vertical-align: top;
    }}
    .fixed-wrap-table th {{
        background-color: #F4F4F4;
        color: black;
    }}
    </style>

    <div class="scroll-wrap">
      <table class="fixed-wrap-table">
        <thead>
          <tr><th colspan="{column_count}">{title}</th></tr>
          <tr><th>항목명</th>{header}</tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>
    """

    st.markdown(html_code, unsafe_allow_html=True)

# 전체 호출 로직
def archAllowInfo():    
    # ✅ (1) 스타일 주입: 반드시 가장 상단에 위치
    style_placeholder = st.empty()
    style_placeholder.markdown("""
    <style>
        .scroll-wrap, .scroll-wrapper {
            overflow-x: auto;
            margin-bottom: 1rem;
        }
        .fixed-wrap-table, .bld-table-html, .bld-table {
            border-collapse: collapse;
            font-size: 14px;
            font-weight: bold;
            table-layout: auto;
            width: 100%;
        }
        .fixed-wrap-table th, .fixed-wrap-table td,
        .bld-table-html th, .bld-table-html td,
        .bld-table th, .bld-table td {
            border: 1px solid #ccc;
            padding: 8px;
            text-align: center;
            vertical-align: middle;
            word-break: break-word;
            white-space: nowrap;
            min-width: 150px;
            max-width: 200px;
        }
        .fixed-wrap-table th, .bld-table-html th, .bld-table th {
            background-color: #f4f4f4;
        }
        .red-text {
            color: black;
            font-weight: normal;
        }
    </style>
    """, unsafe_allow_html=True)

    if st.session_state.get("block_other_functions"):
        return  # 🚫 차단된 경우 아무것도 하지 않음

    operations = [
        ("건축인허가 정보", "getApBasisOulnInfo", {
            "platArea": "대지면적(㎡)",
            "archArea": "건축면적(㎡)",
            "totArea": "연면적(㎡)",
            "vlRatEstmTotArea": "용적률 산정 연면적",
            "bcRat": "건폐율(%)",
            "vlRat": "용적률(%)",
            "mainPurpsCdNm": "주용도",
            "archGbCdNm": "건축구분",
            "archPmsDay": "건축허가일",
            "stcnsSchedDay": "착공일",
            "useAprDay": "사용승인일"
        }),
        ("공작물 정보", "getApHdcrMgmRgstInfo", {
            "len": "길이(㎡)",
            "heit": "높이(㎡)",
            "area": "면적(㎡)",
            "strctCdNm": "구조",
            "hdcrKindCdNm": "용도",
            "crtnDay": "신고일"
        }),
        ("가설건축물 정보", "getApTmpBldInfo", {
            "platArea": "대지면적(㎡)",
            "sumArchArea": "건축면적(㎡)",
            "sumTotArea": "연면적(㎡)",
            "strctCdNm": "구조",
            "mainPurpsCdNm": "용도",
            "crtnDay": "신고일",
            "tmpbidPrsvExpDay": "가설건축물 존치 만료일"
        })
    ]

    basis_items_cache = []  # 가설건축물 매칭용 원본 데이터 저장

    for title, operation, field_map in operations:
        data = call_arch_pms_service_json(operation)

        if data:
            items = (data or {}).get("response", {}) \
                .get("body", {}).get("items", {}).get("item")

            if isinstance(items, dict):
                items = [items]

            if operation == "getApBasisOulnInfo":
                all_basis_items = items  # 원본 전체 저장

                # ✅ 화면 출력용: 건폐율·용적률이 모두 0인 항목 제외
                visible_basis_items = []
                for it in all_basis_items:
                    try:
                        bc = float(it.get("bcRat", "0") or 0)
                        vl = float(it.get("vlRat", "0") or 0)
                        if bc != 0 or vl != 0:
                            visible_basis_items.append(it)
                    except:
                        visible_basis_items.append(it)

                items = visible_basis_items  # 테이블 출력용
                basis_items_cache = all_basis_items  # 가설건축물 비교용 캐시 저장

            if operation != "getApTmpBldInfo":
                if isinstance(items, list) and len(items) > 0:
                    if operation == "getApBasisOulnInfo":
                        items.sort(key=lambda x: x.get("archPmsDay", ""), reverse=True)
                    elif operation == "getApHdcrMgmRgstInfo":
                        items.sort(key=lambda x: x.get("crtnDay", ""), reverse=True)

                    make_html_table_multi(title, items, field_map)
                else:
                    st.markdown(f'<span style="color:red">❗ {title} 결과 없음</span>', unsafe_allow_html=True)

            else:
                # ✅ 가설건축물 정보 분기 처리
                tmp_items = items or []
                tmp_map = {t.get("sumArchArea"): t for t in tmp_items}

                # 원본 건축허가 정보 기준으로 건폐율·용적률 모두 0인 항목만 필터링
                zero_ratio_basis = []
                for b in basis_items_cache:
                    try:
                        bc = float(b.get("bcRat", "0") or 0)
                        vl = float(b.get("vlRat", "0") or 0)
                        if bc == 0 and vl == 0:
                            zero_ratio_basis.append(b)
                    except:
                        continue

                matched = []
                for b in zero_ratio_basis:
                    arch_area = b.get("archArea")
                    tmp_info = tmp_map.get(arch_area)
                    if tmp_info:
                        matched.append({
                            "platArea": b.get("platArea"),
                            "archArea": b.get("archArea"),
                            "totArea": b.get("totArea"),
                            "strctCdNm": tmp_info.get("strctCdNm"),
                            "mainPurpsCdNm": tmp_info.get("mainPurpsCdNm"),
                            "archPmsDay": b.get("archPmsDay")
                        })

                if matched:
                    # ✅ 레이블 매핑: 건축허가일을 맨 아래로 배치
                    merged_field_map = {
                        "platArea": "대지면적(㎡)",
                        "archArea": "건축면적(㎡)",
                        "totArea": "연면적(㎡)",
                        "strctCdNm": "구조",
                        "mainPurpsCdNm": "용도",
                        "archPmsDay": "신고일"
                    }

                    make_html_table_multi("가설건축물 정보", matched, merged_field_map)
                else:
                    st.markdown('<span style="color:red">❗ 가설건축물 결과 없음</span>', unsafe_allow_html=True)

        else:
            pass

# 건축물 대장 정보 공통 API 호출 함수 (JSON 응답)
def call_Bld_Rgst_service_json(operation: str, pageNo: int = 1, numOfRows: int = 30):
    base_url = f"https://apis.data.go.kr/1613000/BldRgstHubService/{operation}"
    service_key = "zGvV1ra5mlbgyKU7qBkKuXDzKjjwKbVLsXdiNlXSPX0wCydBKmq6kgSEeAS3jtNYW85Kyp4vSv34AcdCGMu4CA=="

    required_keys = ['sigunguCd', 'bjdongCd', 'bun']
    if any(k not in st.session_state for k in required_keys):
        #st.error("❗ 주소 정보가 누락되었습니다. 먼저 주소를 입력해 주세요.")
        return None

    sigunguCd = st.session_state['sigunguCd']
    bjdongCd = st.session_state['bjdongCd']
    bun = st.session_state.get('bun', '').zfill(4)
    ji = st.session_state.get('ji', '').zfill(4)
    platGbCd = '1' if st.session_state.get('san') else '0'

    params = {
        "serviceKey": service_key,
        "sigunguCd": sigunguCd,
        "bjdongCd": bjdongCd,
        "platGbCd": platGbCd,
        "bun": bun,
        "ji": ji,
        "numOfRows": numOfRows,
        "pageNo": pageNo,
        "_type": "json"
    }

    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"❗ {operation} API 호출 실패: HTTP {response.status_code}")
            st.code(response.text)
            return None
    except Exception as e:
        st.error(f"❗ API 요청 중 오류 발생: {e}")
        return None

def extract_main_type(value: str) -> str:
    """
    '표제부 (주건축물)' → '주건축물' 추출
    """
    if not isinstance(value, str):
        return "기타"

    match = re.search(r'\((.*?)\)', value)
    return match.group(1).strip() if match else "기타"

def regstr_priority(value: str) -> int:
    """
    총괄표제부(-1) < 주건축물(0) < 부속건축물(1) < 기타(2)
    """
    if "총괄" in value:
        return -1
    main_type = extract_main_type(value)
    return {"주건축물": 0, "부속건축물": 1}.get(main_type, 2)

def dong_sort_key_asc(dongNm):
    if not dongNm or not isinstance(dongNm, str) or dongNm.strip() == "":
        return (3, '', 0)

    dongNm = dongNm.strip()

    # 숫자 시작 (예: '101동')
    match = re.match(r'(\d+)', dongNm)
    if match:
        return (0, '', int(match.group(1)))

    # 영문 시작 (예: 'A동')
    if len(dongNm) > 0 and re.match(r'[a-zA-Z]', dongNm[0]):
        return (1, dongNm.upper(), 0)

    # 한글 기타 (예: '가동', '중앙동' 등)
    return (2, dongNm, 0)

def building_sort_key(item: dict):
    """
    최종 정렬 키: 대장종류 → 건물동명 오름차순
    """
    regstr = item.get("regstrKindCdNm", "")
    dong = item.get("dongNm", "")
    return (regstr_priority(regstr), dong_sort_key_asc(dong))

def sort_title_info_list(title_info_list):
    if not isinstance(title_info_list, list):
        return []

    # 주건축물/부속건축물 분리 및 정렬
    def is_main(x): return extract_main_type(x.get("regstrKindCdNm", "")) == "주건축물"
    def is_sub(x): return extract_main_type(x.get("regstrKindCdNm", "")) == "부속건축물"

    main_items = sorted([x for x in title_info_list if is_main(x)],
                        key=lambda x: dong_sort_key_asc(x.get("dongNm", "")))
    sub_items = sorted([x for x in title_info_list if is_sub(x)],
                        key=lambda x: dong_sort_key_asc(x.get("dongNm", "")))

    return main_items + sub_items

# 건축물대장 HTML 테이블 생성 (그룹화된 헤더 포함)
def make_html_table_grouped(title, items, field_map, group_headers):
    if not items:
        return

    number_keys = {
        "platArea", "archArea", "totArea", "vlRatEstmTotArea", "area",
        "heit", "bcRat", "vlRat",
        "indrMechUtcnt", "oudrMechUtcnt", "indrAutoUtcnt", "oudrAutoUtcnt"
    }

    column_count = len(field_map) + 1  # 항목명 + 항목 개수

    # ✅ 조건부 안내문
    warning_text = ""
    if title == "건축물대장 표제부":
        first_item = items[0]
        if first_item.get("regstrKindCdNm") == "일반건축물":
            warning_text = '<p style="color:red; font-weight:bold;"> </p>'

    # ✅ 그룹 헤더 행
    group_row = "<tr><th></th>"
    for group_name, group_keys in group_headers.items():
        colspan = sum(1 for key in group_keys if key in field_map)
        if colspan > 0:
            group_row += f'<th colspan="{colspan}">{group_name}</th>'
    group_row += "</tr>"

    # ✅ 항목명 행
    field_header_row = "<tr><th>항목명</th>"
    for group_keys in group_headers.values():
        for key in group_keys:
            if key in field_map:
                field_header_row += f"<th>{field_map[key]}</th>"
    field_header_row += "</tr>"

    # ✅ 데이터 행
    data_rows = ""
    for i, item in enumerate(items):
        row = f"<tr><td>정보 {i+1}</td>"
        for group_keys in group_headers.values():
            for key in group_keys:
                if key not in field_map:
                    continue
                raw_value = item.get(key, "")
                if key in number_keys:
                    try:
                        value = f"{float(raw_value):,.2f}".rstrip("0").rstrip(".")
                    except:
                        value = str(raw_value)
                else:
                    value = str(raw_value).replace("\n", "<br>")
                row += f"<td>{value}</td>"
        row += "</tr>"
        data_rows += row

    # ✅ HTML 생성 - 스타일 제한 (.grouped-table-scope 내부로만 적용)
    html_code = f"""
    <div class="grouped-table-scope">
    <style>
        .grouped-table-scope .scroll-wrap {{
            overflow-x: auto;
            border: 0px solid #333;
            margin-bottom: 1rem;
        }}
        .grouped-table-scope .fixed-wrap-table {{
            border-collapse: collapse;
            table-layout: auto;
            width: 100%;
            font-size: 14px;
            font-weight: bold;
        }}
        .grouped-table-scope .fixed-wrap-table th,
        .grouped-table-scope .fixed-wrap-table td {{
            border: 1px solid #ddd;
            padding: 8px;
            min-width: 120px;
            max-width: 150px;
            width: auto;
            text-align: center;
            vertical-align: top;
            word-break: break-word;
        }}
        .grouped-table-scope .fixed-wrap-table th {{
            background-color: #F4F4F4;
            font-weight: bold;
        }}
    </style>

    {warning_text}
    <div class="scroll-wrap">
      <table class="fixed-wrap-table">
        <thead>
          <tr><th colspan="{column_count}">{title}</th></tr>
          {group_row}
          {field_header_row}
        </thead>
        <tbody>
          {data_rows}
        </tbody>
      </table>
    </div>
    </div>
    """

    st.markdown(html_code, unsafe_allow_html=True)

def render_floor_outline(all_flr_items, title_info_list):
    if not isinstance(all_flr_items, list) or not all_flr_items:
        st.markdown('<p style="color:red; font-weight:bold;">❗ 층별개요 정보가 없습니다.</p>', unsafe_allow_html=True)
        return

    # ✅ 선택 가능한 동명 목록
    dong_options = [
        f"{item.get('dongNm', '') or '(미지정)'} - {item.get('bldNm', '') or '-'}"
        for item in title_info_list
    ]

    # ✅ 선택 위젯 (초기 선택은 0)
    selected_index = st.radio("층별개요 조회 대상 선택", options=range(len(dong_options)),
                               format_func=lambda i: dong_options[i], index=0)

    selected_dongNm = title_info_list[selected_index].get("dongNm", "")

    # ✅ 필터링된 층별개요 리스트
    filtered_items = [
        item for item in all_flr_items
        if item.get("dongNm", "").strip() == selected_dongNm.strip()
    ]

    # ✅ 출력 필드 매핑
    field_map_floor = [
        ("층별개요", {
            "flrGbCdNm": "구분",
            "flrNoNm": "층별",
            "etcStrct": "구조",
            "mainPurpsCdNm": "용도",
            "etcPurps": "기타용도",
            "area": "면적(㎡)"
        })
    ]
    field_map = {}
    group_headers = {}
    for group_name, group_fields in field_map_floor:
        field_map.update(group_fields)
        group_headers[group_name] = list(group_fields.keys())

    # ✅ 테이블 출력
    if filtered_items:
        make_html_table_grouped(f"층별개요 - {selected_dongNm}", filtered_items, field_map, group_headers)
    else:
        st.info(f"❗ 선택된 동({selected_dongNm})에 대한 층별개요 정보가 없습니다.")

def render_dual_building_header(recap_info, title_info_list):
    # ✅ 리스트 유효성 검증
    if not isinstance(title_info_list, list) or not title_info_list:
        return

    # ✅ 총괄표제부 정보 추출
    g_regstr = recap_info.get("regstrKindCdNm", "").strip() if recap_info else ""
    g_bldNm = recap_info.get("bldNm", "").strip() if recap_info else "-"
    g_purps = recap_info.get("mainPurpsCdNm", "").strip() if recap_info else "-"

    # ✅ 총괄표제부 행 생성
    if g_regstr:
        g_row = (
            f"<tr>"
            f"<td class='red-text'>{g_regstr}</td>"
            f"<td class='red-text'>{g_bldNm}</td>"
            f"<td class='red-text'>-</td>"
            f"<td class='red-text'>{g_purps}</td>"
            f"</tr>"
        )
        row_count = 1
    else:
        g_row = ""
        row_count = 0

    # ✅ 일반 표제부 필터링
    filtered_list = [
        item for item in title_info_list
        if "총괄" not in item.get("regstrKindCdNm", "")
    ]

    # ✅ 표제부 행 생성
    title_rows = ""
    for title_info in filtered_list:
        regstr = str(title_info.get("regstrKindCdNm", "")).strip() or "-"
        mainAtch = str(title_info.get("mainAtchGbCdNm", "")).strip() or "-"
        bldNm = str(title_info.get("bldNm", "")).strip() or "-"
        dongNm = str(title_info.get("dongNm", "")).strip() or "-"
        purps = str(title_info.get("mainPurpsCdNm", "")).strip()
        etcPurps = str(title_info.get("etcPurps", "")).strip()

        purps_combined = f"{purps}, {etcPurps}" if etcPurps and etcPurps != purps else purps or "-"

        title_rows += (
            f"<tr>"
            f"<td class='red-text'>{regstr} ({mainAtch})</td>"
            f"<td class='red-text'>{bldNm}</td>"
            f"<td class='red-text'>{dongNm}</td>"
            f"<td class='red-text'>{purps_combined}</td>"
            f"</tr>"
        )
        row_count += 1

    # ✅ 상단 정보
    plat = str(title_info_list[0].get("platPlc", "")).strip() or "-"
    bylots = str(title_info_list[0].get("bylotCnt", "")).strip() or "-"

    # ✅ 높이 계산
    row_height = 50
    base_height = 180
    total_height = base_height + (row_height * row_count)

    # ✅ HTML 생성 (스타일 함수 범위로 제한)
    html = f"""
    <div class="custom-wrap">
    <style>
        .custom-wrap .bld-table {{
            border-collapse: collapse;
            font-size: 14px;
            font-weight: bold;
            width: 100%;
            margin-bottom: 1rem;
            table-layout: auto;
        }}
        .custom-wrap .bld-table th,
        .custom-wrap .bld-table td {{
            border: 1px solid #999;
            padding: 6px 10px;
            text-align: center;
            vertical-align: middle;
            word-break: keep-all;
            white-space: normal;
        }}
        .custom-wrap .bld-table th {{
            background-color: #f9f9f9;
        }}
        .custom-wrap .red-text {{
            color: black;
            font-weight: normal;
        }}
    </style>

    <!-- 상단 표 -->
    <table class="bld-table">
        <thead>
        <tr><th colspan="2">건축물대장 정보</th></tr>
        <tr><th>소재지</th><th>외필지수</th></tr>
        </thead>
        <tbody>
        <tr><td class="red-text">{plat}</td><td class="red-text">{bylots}</td></tr>
        </tbody>
    </table>

    <!-- 하단 표 -->
    <table class="bld-table">
        <thead>
        <tr>
            <th>대장종류</th>
            <th>건물명</th>
            <th>건물동명</th>
            <th>주용도</th>
        </tr>
        </thead>
        <tbody>
        {g_row}
        {title_rows}
        </tbody>
    </table>
    </div>
    """

    # ✅ 출력
    components.html(html, height=total_height)

def buildingInfo():
    if st.session_state.get("block_other_functions"):
        return    

    if st.session_state.get("invalid_address"):
        return  # 혹은 오류 메시지 유지 및 buildingInfo 등 차단
    
    # ✅ 스타일 먼저 삽입 (데이터 없어도 항상 삽입되도록)
    style_placeholder = st.empty()
    style_placeholder.markdown("""
    <style>
        .scroll-wrap, .scroll-wrapper {
            overflow-x: auto;
            margin-bottom: 1rem;
        }
        .fixed-wrap-table, .bld-table-html, .bld-table {
            border-collapse: collapse;
            font-size: 14px;
            font-weight: bold;
            table-layout: auto;
            width: 100%;
        }
        .fixed-wrap-table th, .fixed-wrap-table td,
        .bld-table-html th, .bld-table-html td,
        .bld-table th, .bld-table td {
            border: 1px solid #ccc;
            padding: 8px;
            text-align: center;
            vertical-align: middle;
            word-break: break-word;
            white-space: nowrap;
        }
        .fixed-wrap-table th, .bld-table-html th, .bld-table th {
            background-color: #f4f4f4;
        }
        .red-text {
            color: black;
            font-weight: normal;
        }
    </style>
    """, unsafe_allow_html=True)

    field_map_title = [
        ("기본정보", {
            "regstrKindCdNm": "대장종류",
            "mainAtchGbCdNm": "주건축물구분",
            "bldNm": "건물명",
            "dongNm": "건물동명",
            "mainPurpsCdNm": "주용도",
            "etcPurps": "기타용도"
        }),
        ("면적정보", {
            "platArea": "대지면적(㎡)",
            "archArea": "건축면적(㎡)",
            "totArea": "연면적(㎡)",
            "vlRatEstmTotArea": "용적률산정 연면적(㎡)",
            "bcRat": "건폐율(%)",
            "vlRat": "용적률(%)"
        }),
        ("건축개요", {
            "etcStrct": "구조",
            "grndFlrCnt": "지상층수",
            "ugrndFlrCnt": "지하층수",
            "heit": "높이(m)"
        }),
        ("주차대수", {
            "indrMechUtcnt": "기계식주차(내부)",
            "oudrMechUtcnt": "기계식주차(외부)",
            "indrAutoUtcnt": "자주식주차(내부)",
            "oudrAutoUtcnt": "자주식주차(외부)"
        }),
        ("인허가정보", {
            "pmsnoGbCdNm": "허가구분",
            "pmsDay": "허가일자",
            "stcnsDay": "착공일자",
            "useAprDay": "사용승인일자"
        })
    ]

    recap_info = call_Bld_Rgst_service_json("getBrRecapTitleInfo")
    title_data = call_Bld_Rgst_service_json("getBrTitleInfo")

    title_info_list = title_data.get("response", {}).get("body", {}).get("items", {}).get("item", []) if title_data else []
    # item이 없거나 빈 경우
    if not title_info_list:
        st.markdown('<span style="color:red">❗ 건축물대장 정보 없음(국가나 지자체 보안시설 포함)</span>', unsafe_allow_html=True)
        return

    if isinstance(title_info_list, dict):
        title_info_list = [title_info_list]

    # ✅ 검색이 명시적으로 실행된 경우 + 결과가 없으면 경고
    if st.session_state.get("search_triggered") and not title_info_list:
        st.markdown('<span style="color:red">❗ 건축물대장 정보 없음</span>', unsafe_allow_html=True)
        return

    st.markdown(
        f"""
        <p style="color:red; font-size:14px; font-weight:normal;">
            ※ 건축물대장은 총괄표제부(하나의 대지에 2 이상의 건축물(부속건축물 제외)이 있는 경우)<br> 
            -> 표제부(「집합건물의 소유 및 관리에 관한 법률」에 따라 1동의 건물이 구조상 구분되어 여러 개의 부분으로 독립된 건물로서 사용되어 각각의 소유권이 있는 건축물) 또는 일반건축물(집합건축물 외 건축물)<br> 
            -> 층별개요(건축물 동별 상세 층별 현황 - 동별 선택 필수) 순서로 제공됩니다. 집합건축물 전유부 보기 기능은 제공하지 않으니 참고하시기 바랍니다.
        </p>
        """,
        unsafe_allow_html=True
    )

    # 총괄표제부 추가 (선택적)
    recap_item = None
    if recap_info:
        recap_item = recap_info.get("response", {}).get("body", {}).get("items", {}).get("item")
        if recap_item:
            if isinstance(recap_item, list):
                recap_item = recap_item[0]
            recap_item["regstrKindCdNm"]
            title_info_list.insert(0, recap_item)

    title_info_list.sort(key=building_sort_key)

    # ——— 천단위 콤마 표시용 숫자 키 세트 ———
    number_keys = {
        "platArea", "archArea", "totArea", "vlRatEstmTotArea",
        "bcRat", "vlRat", "grndFlrCnt", "ugrndFlrCnt", "heit",
        "indrMechUtcnt", "oudrMechUtcnt", "indrAutoUtcnt", "oudrAutoUtcnt"
    }

    # ✅ 요약 테이블 호출 (총괄포함 요약표 렌더링)
    preview_list = [i for i in title_info_list if "총괄" not in i.get("regstrKindCdNm", "")]
    if preview_list:
        render_dual_building_header(recap_item if recap_info else None, preview_list)

    flat_fields = {k: v for group in field_map_title for k, v in group[1].items()}
    dong_labels = [f"{i.get('dongNm', '') or '-'} - {i.get('bldNm', '') or '-'}" for i in title_info_list]

    if not dong_labels:
        st.warning("❗ 동 건축물대장 정보가 없습니다.")
        return

    if "selected_dong_index" not in st.session_state:
        st.session_state.selected_dong_index = 0

    if st.session_state.selected_dong_index >= len(dong_labels):
        st.session_state.selected_dong_index = 0

    if len(dong_labels) > 1:
        # 1) 원하는 스타일의 레이블을 HTML로 출력
        st.markdown(
            """
            <div style="
                font-size:18px;
                color:red;
                font-weight: bold;
                margin-bottom:4px;
            ">
                동 층별개요 보기(열람하고 싶은 동을 선택하면 표 하단에 층별현황 표가 별도 출력)
            </div>
            """,
            unsafe_allow_html=True
        )
        # 2) 실제 라디오 버튼에는 빈 문자열 레이블
        selected_radio = st.radio(
            "",
            options=range(len(dong_labels)),
            format_func=lambda i: dong_labels[i],
            horizontal=True,
            index=st.session_state.selected_dong_index
        )
        if selected_radio != st.session_state.selected_dong_index:
            st.session_state.selected_dong_index = selected_radio
            st.rerun()

    selected_index = st.session_state.selected_dong_index
    selected_item = title_info_list[selected_index]

    # 표제부 테이블 출력 (함수 내부 스타일로 제한)
    table_html = """
    <div class="bld-scope">
    <style>
        .bld-scope .bld-table-html {
            border-collapse: collapse;
            width: 100%;
            table-layout: auto;
            font-size: 14px;
            font-weight: bold;
        }
        .bld-scope .bld-table-html th,
        .bld-scope .bld-table-html td {
            border: 1px solid #ccc;
            padding: 6px 10px;
            text-align: center;
            vertical-align: middle;
            white-space: nowrap;
        }
        .bld-scope .bld-table-html th {
            background-color: #f0f0f0;
        }
        .bld-scope .scroll-wrapper {
            overflow-x: auto;
        }
    </style>

    <div class="scroll-wrapper">
        <table class="bld-table-html">
        <thead>
            <tr><th>선택</th>""" + ''.join(f"<th>{flat_fields[k]}</th>" for k in flat_fields) + """</tr>
        </thead>
        <tbody>
    """

    for idx, item in enumerate(title_info_list):
        checked = "✔" if idx == selected_index else ""
        table_html += f"<tr><td>{checked}</td>"
        for key in flat_fields:
            raw = item.get(key, "")
            if key in number_keys and raw not in (None, "", "-"):
                try:
                    num = float(raw)
                    val = f"{num:,.2f}".rstrip("0").rstrip(".")
                except:
                    val = str(raw)
            else:
                val = raw or "-"
            table_html += f"<td>{val}</td>"
        table_html += "</tr>"

    table_html += "</tbody></table></div></div>"

    # ✅ 출력
    st.markdown(table_html, unsafe_allow_html=True)

    # 층별개요 API 호출 및 출력
    all_flr_items = []
    base_data = call_Bld_Rgst_service_json("getBrFlrOulnInfo", pageNo=1)
    if base_data:
        body = base_data.get("response", {}).get("body", {})
        total = int(body.get("totalCount", 0))
        num = int(body.get("numOfRows", 30))
        pages = math.ceil(total / num)

        for p in range(1, pages + 1):
            page_data = call_Bld_Rgst_service_json("getBrFlrOulnInfo", pageNo=p)
            items = page_data.get("response", {}).get("body", {}).get("items", {}).get("item")
            if isinstance(items, dict):
                all_flr_items.append(items)
            elif isinstance(items, list):
                all_flr_items.extend(items)

    clicked_dong = selected_item.get("dongNm", "")

    if clicked_dong and all_flr_items:
        filtered = [i for i in all_flr_items if i.get("dongNm", "").strip() == clicked_dong.strip()]

        def flr_sort_key(item):
            flr = item.get("flrNoNm", "").strip()
            match = re.match(r"(-?\d+)", flr.replace("B", "-").replace("지하", "-").replace("지상", ""))
            return int(match.group(1)) if match else float('inf')

        filtered.sort(key=flr_sort_key)

        field_map_floor = [
            ("층별개요", {
                "flrGbCdNm": "구분",
                "flrNoNm": "층별",
                "etcStrct": "구조",
                "mainPurpsCdNm": "용도",
                "etcPurps": "기타용도",
                "area": "면적(㎡)"
            })
        ]
        field_map = {}
        group_headers = {}
        for group_name, group_fields in field_map_floor:
            field_map.update(group_fields)
            group_headers[group_name] = list(group_fields.keys())

        if filtered:
            make_html_table_grouped(f"층별개요 - {clicked_dong}", filtered, field_map, group_headers)
        else:
            st.info(f"❗ 선택된 동({clicked_dong})에 대한 층별개요 정보가 없습니다.")

    # ✅ 강제 렌더 트리 트리거 (렌더링 타이밍 이슈 해결용)
    st.markdown('<div style="display:none">render_trigger</div>', unsafe_allow_html=True)

# 연속지적도
def spaceMap():
    if st.session_state.get("block_other_functions"):
        return
    if 'vworld_x' not in st.session_state or 'vworld_y' not in st.session_state:
        return

    lon = float(st.session_state['vworld_x'])
    lat = float(st.session_state['vworld_y'])

    # bbox 생성 (간단히 동일)
    delta = 0.001
    xmin, ymin = lon - delta, lat - delta
    xmax, ymax = lon + delta, lat + delta
    bbox = f"{ymin},{xmin},{ymax},{xmax}"

    # WMS 호출
    url = "http://api.vworld.kr/ned/wms/CtnlgsSpceService"
    params = {
        "key":       "12C86633-0613-3EC6-A8EF-0D8D474C8608",
        "domain":    "https://광산에이아이.com",
        "layers":    "dt_d002",
        "crs":       "EPSG:4326",
        "bbox":      bbox,
        "width":     "915",
        "height":    "700",
        "format":    "image/png",
        "transparent": "false",
        "bgcolor":   "0xFFFFFF",
        "exceptions": "blank"
    }
    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200 or len(r.content) == 0:
        st.error("연속지적도 조회 실패 또는 빈 이미지 반환")
        return

    # PIL로 변환 + 마커 그리기
    img = Image.open(io.BytesIO(r.content))
    w, h = img.size
    dx, dy = (xmax - xmin), (ymax - ymin)
    x_pct = (lon - xmin) / dx if dx != 0 else 0.5
    y_pct = (ymax - lat) / dy if dy != 0 else 0.5
    x_px, y_px = int(x_pct * w), int(y_pct * h)

    draw = ImageDraw.Draw(img)
    r_ = 6
    draw.ellipse(
        [(x_px - r_, y_px - r_), (x_px + r_, y_px + r_)],
        outline="red", width=2
    )

    # ─────────────────────
    # Streamlit Expander 사용
    with st.expander("연속지적도 보기/숨기기", expanded=False):
        st.image(img, caption="검색 위치 마커 포함", use_container_width=True)
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

# main 함수
def main():
    #st.set_page_config(page_title="PDF 뷰어", layout="wide")
    # PDF 파일 열기
    pdf_path = "data/buildinguses.pdf"
    pdf_path2 = "data/district.pdf"

    st.header('광산구 건축 도우미(광산AI 동아리 제작)')
    st.markdown(
    f"""
    <p style="color:red; font-size:14px; font-weight:normal;">
        ※ 이용방법: 1.토지이용계획 검색(주소 입력) ▶ 2 ~ 4 검색 주소지의 건축제한 사항 결과 출력물 확인
    </p>
    """,
    unsafe_allow_html=True
    )
    #buildingIndex()
    geoParams()
    geoData()
    
        # ✅ 3개 탭 생성
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["건폐율·용적률", "건축행위 제한사항", "기타 제한사항", "건축물 정보 등", "토지 소유정보"])

    st.markdown("""
    <style>
    /* 탭 기본 폰트 및 배경 */
    [data-testid="stTabs"] button {
        font-size: 18px;
        padding: 12px 16px;
        border-radius: 5px 5px 0 0;
        background-color: #f0f2f6;
        color: black;
        font-weight: 600;
    }

    /* 선택된 탭 강조 */
    [data-testid="stTabs"] button[aria-selected="true"] {
        background-color: #2C6BED;
        color: white;
        font-weight: bold;
        font-size: 20px;
        border-bottom: 2px solid white;
    }
    </style>
    """, unsafe_allow_html=True)

    with tab1:
        spaceIndex()

    with tab2:
        areaPermission()
        zoningAllow(pdf_path)

    with tab3:
        districtAllow(pdf_path2)

    with tab4:
        st.write('')
    with tab5:
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

     # 결과 확인
    #st.write("🔍 검색 트리거 상태:", st.session_state.search_triggered)
    col1, col2, col3, col4, col5, col6 = st.columns([1.2, 1, 1, 1, 1, 0.8])
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
            '진곡동', '하남동', '하산동', '황룡동', '흑석동'))
            
    with col2:
        umd2 = st.selectbox(
            '산 유무',
            ('일반', '산'))
    with col3:
        bonbun = st.text_input('번지 본번', bonbun_key)
    with col4:
        bubun = st.text_input('번지 부번', bubun_key)
    with col5:        
        #st.write('검색')
        st.markdown(
            """
            <div style="height: 27px; background-color: white; padding: 10px;">
            </div>
            """,
            unsafe_allow_html=True
            )
        if st.button("주소 검색", type='primary'):
            # ✅ 1. 현재 입력값 임시 백업
            st.session_state["search_triggered"] = True
            st.session_state["umd"] = umd
            st.session_state["umd2"] = umd2
            st.session_state["bonbun"] = bonbun
            st.session_state["bubun"] = bubun

            # ✅ 2. 이전 검색 결과 초기화 (이 부분에서 clear() 대신 개별 삭제 권장)
            for key in ["vworld_x", "vworld_y", "address", "cutFGeoLnm_lndcgr_smbol", "fGeoPrpos_area_dstrc_nm_list", 'items_cleaned_fGeoPrpos_area_dstrc_nm_list', 'lndpcl_ar', 'pnu', 'land_info', 'block_other_functions']:
                if key in st.session_state:
                    del st.session_state[key]

            # 어떤 로직에서 필요할 때
            clear_layer_session("LT_C_DAMYOJ")
            clear_layer_session("LT_C_LHBLPN")


            # ✅ 3. 검색 결과는 리런 후 조건문에서 표시
            st.rerun()

    with col6:
        st.markdown(
            """
            <div style="height: 27px; background-color: white; padding: 10px;">
            </div>
            """,
            unsafe_allow_html=True
            )
        if st.button("초기화"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            #st.session_state[bonbun_key]   # 변수 초기화
            #st.session_state[bubun_key] = ''
            st.rerun()               # main() 재시작   

    # 👉 선택값 변경 감지
    if st.session_state.prev_umd != umd or st.session_state.prev_umd2 != umd2:
        keys_to_clear = [
            'bonbun', 'bubun', 'search_triggered', 
            'vworld_x', 'vworld_y', 'address', 
            'cutFGeoLnm_lndcgr_smbol', 
            'fGeoPrpos_area_dstrc_nm_list', 
            'items_cleaned_fGeoPrpos_area_dstrc_nm_list'
        ]
        for key in keys_to_clear:
            st.session_state.pop(key, None)
        st.session_state.prev_umd = umd
        st.session_state.prev_umd2 = umd2
        st.rerun()

        
    fumd = f'{umd}'
    fumd2 = f'{umd2}'
    fbonbun = f'{bonbun}'
    fbubun = f'{bubun}'
    
    if st.session_state.search_triggered:
        st.session_state.search_triggered = False
        apiurl = 'https://api.vworld.kr/req/address?'

        try:
            if not fbonbun or fbonbun.startswith('0'):     #bonbun 이 비어있거나 0으로 시작할 때
                st.write('없는 주소입니다.')
            else:
                if not fbubun:             #bubun 이 비어있으면
                    if fumd2.strip() == '일반':      #아직까지 일반과 산 번지를 제대로 인식 못함 나중에 고치자
                        params = {
	                    'service': 'address',
	                    'request': 'getcoord',
	                    'crs': 'epsg:4326',
	                    'address': '광주광역시 광산구' + ' ' + fumd + ' ' + fbonbun,
	                    'format': 'json',
	                    'type': 'parcel',
	                    'key': 'AF338F49-6AAA-3F06-BD94-FB6CB6817323' }                        
                    else:
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
                        st.write('없는 주소입니다.')   
                        return
                    if fumd2.strip() == '일반':
                        params = {
	                    'service': 'address',
	                    'request': 'getcoord',
	                    'crs': 'epsg:4326',
	                    'address': '광주광역시 광산구' + ' ' + fumd + ' ' + fbonbun + '-' + fbubun,
	                    'format': 'json',
	                    'type': 'parcel',
	                    'key': 'AF338F49-6AAA-3F06-BD94-FB6CB6817323' }   
                    else:
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
                        st.write('없는 주소입니다.')
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
            st.write("없는 주소입니다.")
            #st.error("주소를 다시 확인하여 주시기 바랍니다")
        except ValueError:
            st.write("없는 주소입니다.")
            #st.warning("주소를 다시 확인하여 주시기 바랍니다")
        except Exception as e:
            st.write("없는 주소입니다.")
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

    if 'fGeoPrpos_area_dstrc_nm_list' in st.session_state:
        # 예: 좌측에 표시할 사용자 정의 레이블
        label1 = '포함'
        label2 = '저촉'
        label3 = '접합'

        # 기타 항목의 값들을 쉼표로 연결하여 한 줄 출력
        joined_values1 = ', '.join(classified_area_dict['포함'].values())
        joined_values2 = ', '.join(classified_area_dict['저촉'].values())
        joined_values3 = ', '.join(classified_area_dict['접합'].values())

        html_table = f"""
        <style>
            .usezone-table {{
                border-collapse: collapse;
                width: 100%;
                font-size: 14px;
                border: 2px solid black;
            }}
            .usezone-table th {{
                background-color: #FFA500;
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
        #st.warning("📌 토지 정보가 없습니다. 먼저 주소를 검색해주세요.")
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
    table {{
        width: 100%;
        border-collapse: collapse;
        text-align:center;
        margin: 20px auto;
        font-family: Arial, sans-serif;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        font-size: 14px;
        border: 2px solid black;
    }}
    th, td {{
        border: 1px solid #ccc;
        padding: 12px 15px;
        text-align:center;
        font-weight: bold;
    }}
    th {{
        background-color: #FFA500;
        font-weight: bold;
    }}
    tr:nth-child(even) {{
        background-color: #f9f9f9;
    }}
    tr:hover {{
        background-color: #e6f7ff;
    }}
    </style>

    <table>
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

                st.session_state[f'{layer}_zonename'] = zonename
                st.session_state[f'{layer}_blocktype'] = blocktype

                # ✅ HTML 표 출력
                html_table = f"""
                <table style="border-collapse: collapse; width: 100%; font-size: 14px;">
                    <thead>
                        <tr style="background-color: #E0ECFF;">
                            <th colspan="2" style="border: 1px solid #ccc; padding: 12px; background:orange; text-align: center; font-size: 14px;">
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

        target_keywords = ['농공단지', '국가산업단지', '일반산업단지', '도시첨단산업단지', '준산업단지', '제1종지구단위계획구역', '제2종지구단위계획구역', '지구단위계획구역', '택지개발지구']

        # 1. 안내 메시지 출력 (조건부)
        found = [kw for kw in target_keywords if kw in area_list]
        if found:
            st.write(f"➡️ 해당 지구({', '.join(found)})에 대한 용도 제한 정보는 제공하지 않으니 별도 확인하시기 바랍니다")
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

        # 검색어 입력 필드 추가
        search_term = st.text_input("🔍 세부용도 검색", placeholder="예: 의원, 오피스텔 등")

        # 필터링된 테이블 준비
        filtered_df = final_df.copy()

        if search_term:
            filtered_df = filtered_df[filtered_df['토지이용명'].str.contains(search_term.strip(), na=False)]

        # ✅ HTML 테이블 시작
        table_html = "<table style='width:100%; border-collapse: collapse; font-size:14px; border: 2px solid black;'>"

        # ✅ 헤더 생성
        table_html += "<thead><tr>"
        table_html += "<th style='border:1px solid #ddd; padding:6px; color:black; background:orange;'>시설군</th>"
        table_html += "<th style='border:1px solid #ddd; padding:6px; color:black; background:orange;'>세부용도</th>"
        for area in valid_area_list:
            table_html += f"<th style='border:1px solid #ddd; padding:6px; color:black; background:orange;'>{area} 건축가능</th>"

        table_html += f"<th style='border:1px solid #ddd; padding:6px; color:black; background:orange;'>건축물 용도 정의</th>"    
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

    except FileNotFoundError:
        st.error("❌ 'data/areaPermission.xlsx' 파일을 찾을 수 없습니다.")
    except KeyError as e:
        st.error(f"❌ 컬럼 오류: {e}")
    except Exception as e:
        st.error("❌ 알 수 없는 오류가 발생했습니다.")
        st.code(str(e))
        
# 건폐율 용적률 추출 함수
def spaceIndex():
    #st.write(' ')
    #st.markdown(
        #f"""
        #<p style="color:blue; font-size:20px; font-weight:bold;">
            #2. 건축물의 건폐율 및 용적률 제한사항
        #</p>
        #""",
        #unsafe_allow_html=True
    #)

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
    '국가산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '일반산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '도시첨단산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '준산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '제1종지구단위계획구역': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '지구단위계획구역': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    }

    if 'items_cleaned_fGeoPrpos_area_dstrc_nm_list' not in st.session_state:
        #st.write("검색 주소지의 정보가 없습니다.")
        return
    
    # geoParams 내 items_cleaned_fGeoPrpos_area_dstrc_nm_list_dict 변수 가져와 새 변수 적용해 사용
    area_dict = st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list']

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
                    border: 2px solid black;
                }}
                table.custom-table th {{
                    background-color: orange;
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

    else:
        st.warning("❗ 조건에 맞는 건폐율/용적률 정보가 없습니다. 주소지가 올바른지 확인해 주세요.")    

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
                ※ 3. 용도지역의 건축물 허용 용도일지라도 4. 용도지구의 건축물 불허 용도에 해당 될 시 해당 용도의 건축 불가
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

main()
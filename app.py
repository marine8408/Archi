import streamlit as st
import json
import xmltodict
import pandas as pd
import requests
import fitz  # PyMuPDF
import os
import re
import io
from urllib.request import Request, urlopen 
from urllib.parse import urlencode, quote_plus
from PIL import Image
from io import BytesIO

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

    geoParams()
    spaceIndex()
    zoningAllow(pdf_path)
    districtAllow(pdf_path2)

# 토지속성 정보 처리 함수
def geoParams():
    bonbun_key = ''
    bubun_key = ''

    st.write(' ')
    st.markdown(
        f"""
        <p style="color:blue; font-size:20px; font-weight:bold;">
            1. 토지이용계획 검색(지목, 면적, 용도지역및지구, 위치도)
        </p>
        """,
        unsafe_allow_html=True
    )

                    
    for key in list(st.session_state.keys()):    #키 값 초기화
        del st.session_state[key]
        
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
            st.session_state.search_triggered = True

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
                if fbubun.startswith('0'):
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
                    else:
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
                        address = data['response']['input']['address']   #입력한 주소 보여주기
                        
                        address1 = str(data['response']['input']['address'])
                        address2 = str(data['response']['refined']['text'])

                        if address1 != address2:         #산 번지 인식 마지막 제대로 판별하기
                            st.write('없는 주소입니다.')
                        else:                
                            #st.write(data)
                            #st.write(address)

                            #print(x, y)

        
                            # Extracting data for table
                            #result_info = data['response']['result']
                            #point_info = result_info['point']

                            #df = pd.DataFrame([
                            #['Service Address', result_info['point']],
                            #['Longitude', point_info['x']],
                            #['Latitude', point_info['y']]
                            #], columns=['Key', 'Value'])
                            #print(df)

                            #print("좌표추출끝")
        
                            #st.write(data)          #json 구조 확인 중요


                            #여기부터 토지이용속성 조회
                            pbbox = f'{y},{x},{y},{x},EPSG:4326'    #pbbox 변수에 지오코더 좌표 값 문자열 받기

                            url = 'https://api.vworld.kr/ned/wfs/getLandUseWFS'

        
                            #queryParams = '?' + urlencode({
                            #    'key' : '86DD225C-DC5B-3B81-B9EB-FB135EEEB78C',
                            #    'typename' : 'dt_d154',
                            #    'bbox' : pbbox,
                            #    'maxFeatures' : '10',
                            #    'resultType' : 'results',
                            #    'srsName' : 'EPSG:4326',
                            #    'output' : 'text/xml; subtype=gml/2.1.2'})   

                            #request = Request(url + queryParams)
                            #request.get_method = lambda: 'GET'
                            #response_body = urlopen(request).read()
                            #print(response_body.decode('utf-8'))
        

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

                            # 1. 괄호 및 괄호 안 내용 제거 (중첩 포함)
                            while re.search(r'[\(\（][^()\（\）]*[\)\）]', fGeoPrpos_area_dstrc_nm_list):
                                fGeoPrpos_area_dstrc_nm_list = re.sub(r'[\(\（][^()\（\）]*[\)\）]', '', fGeoPrpos_area_dstrc_nm_list)

                            # 2. 쉼표 기준 항목 분리
                            area_items = fGeoPrpos_area_dstrc_nm_list.split(',')

                            # 3. 각 항목의 끝에서 숫자/기호 제거
                            cleaned_items = [
                                re.sub(r'[\d\s\-\–\.\~\+\=\!@\#\$%\^&\*\(\)_]+$', '', item.strip()) 
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
        col1, col2 = st.columns(2)

        with col1:
            st.write('검색하신 주소는')
            st.markdown(
                f'<p style="color:white; font-size:20px; font-weight:bold; background-color:#000000;">{st.session_state["address"]}</p>', 
                unsafe_allow_html=True
            )

        with col2:
            st.write('지목은')        
            st.markdown(
                f'<p style="color:white; font-size:20px; font-weight:bold; background-color:#000000;">{st.session_state["cutFGeoLnm_lndcgr_smbol"]}</p>', 
                unsafe_allow_html=True
            )

    if 'fGeoPrpos_area_dstrc_nm_list' in st.session_state:
        st.write('용도지역 및 용도지구 ')                
        # 세션에 저장된 리스트 항목을 쉼표로 구분하여 문자열로 변환
        area_list_str = ', '.join(st.session_state["items_cleaned_fGeoPrpos_area_dstrc_nm_list"].values())

        # 마크다운을 사용하여 스타일 적용
        st.markdown(f'<p style="color:white; font-size:20px; font-weight:bold; background-color:#000000;">{area_list_str}</p>', unsafe_allow_html=True)

# 건폐율 용적률 추출 함수
def spaceIndex():
    st.write(' ')
    st.markdown(
        f"""
        <p style="color:blue; font-size:20px; font-weight:bold;">
            2. 건축물의 건폐율 및 용적률 제한사항
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
    '국가산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '일반산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '도시첨단산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '준산업단지': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '제1종지구단위계획구역': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    '지구단위계획구역': ('지구단위계획 등 제한사항 확인 필요', '지구단위계획 등 제한사항 확인 필요'),
    }

    if 'items_cleaned_fGeoPrpos_area_dstrc_nm_list' not in st.session_state:
        st.write("검색 주소지의 정보가 없습니다.")
        return
    
    # geoParams 내 items_cleaned_fGeoPrpos_area_dstrc_nm_list_dict 변수 가져와 새 변수 적용해 사용
    area_dict = st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list']

    matching_data1 = {k: v for k, v in building_index1.items() if k in area_dict.values()}
    matching_data2 = {k: v for k, v in building_index2.items() if k in area_dict.values()}
    matching_data3 = {k: v for k, v in building_index3.items() if k in area_dict.values()}

    if len(matching_data1) >= 2:
        st.write("두 개 이상의 지역이 중첩 지정된 것으로 확인되었습니다. 자세한 사항은 국토의 계획 및 이용에 관한 법률 제84조를 검토 적용하여 주시기 바랍니다.")
    else:
        #st.write("🔍 area_dict 키 목록:", list(area_dict.keys()))
        #st.write("matching_data1:", matching_data1)
        if matching_data1:
            for k, v in matching_data1.items():
                if len(v) == 2:
                    건폐율, 용적률 = v
                    st.markdown(
                        f"""
                        <p style="font-size:14px; font-weight:normal; color:white; background-color:#000000">
                            <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{k}</span>은 건폐율: <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{건폐율}</span>
                            , 용적률: <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{용적률}</span> 입니다.
                        </p>
                        """,
                        unsafe_allow_html=True
                    )                
                    #st.write(f"{k}은 ")
                    #st.write(f"건폐율: {건폐율},")
                    #st.write(f"용적률: {용적률}입니다.")
                else:             #나올일 없음
                    건폐율 = v[0]
                    st.markdown(
                        f"""
                        <p style="font-size:14px; font-weight:normal; color:white; background-color:#000000">
                            <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{k}</span>은 건폐율: <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{건폐율}</span>
                            , 용적률: <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">정보 없음</span> 입니다.
                        </p>
                        """,
                        unsafe_allow_html=True
                    )      
        if matching_data1 and matching_data2:
            for k, v in matching_data2.items():
                # matching_data2의 값이 2개이면 그대로 사용, 아니면 matching_data1의 용적률 사용
                if len(v) == 2:
                    건폐율, 용적률 = v
                else:
                    for k1, v1 in matching_data1.items():
                        print("matching_data1[k]:", matching_data1[k1])
                        print("length of matching_data1[k]:", len(matching_data1[k1]))
                        건폐율 = v[0]
                        # matching_data1에 해당 키가 있고, 값이 2개일 경우 용적률 가져오기
                        용적률 = matching_data1[k1][1] if (k1 in matching_data1 and len(matching_data1[k1]) == 2) else "정보 없음"

                st.markdown(
                    f"""
                    <p style="font-size:14px; font-weight:normal; color:white; background-color:#000000">
                         또한 <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{k}</span>에 속하여 건폐율 및 용적률을 완화 받은 결과, 최종 건폐율: <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{건폐율}</span>
                        , 용적률: <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{용적률}</span> 입니다.
                    </p>
                    """,
                    unsafe_allow_html=True
                )   

        if matching_data3:
            for k, v in matching_data3.items():
                st.markdown(
                    f"""
                    <p style="font-size:14px; font-weight:normal; color:white; background-color:#000000">
                         하지만 <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{k}</span>으로 지정된 결과, 최종 건폐율: <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{v[0]}</span>
                        , 용적률: <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{v[1]}</span> 입니다.
                    </p>
                    """,
                    unsafe_allow_html=True
                )   

        st.write(' ')
        st.markdown(
            f"""
            <p style="color:black; font-size:14px; font-weight:normal;">
                ※ 건폐율(대지면적에 대한 건축면적의 비율의 최대 한도): 건축면적 / 대지면적 * 100%
            </p>
            <p style="color:black; font-size:14px; font-weight:normal;">
                ※ 용적률(대지면적에 대한 연면적의 비율의 최대 한도): 연면적 / 대지면적 * 100%
            </p>
            """,
            unsafe_allow_html=True
        )                

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

# zoningAllow 함수
def zoningAllow(pdf_path):
    st.write(' ')
    st.markdown(
        f"""
        <p style="color:blue; font-size:20px; font-weight:bold;">
            3. 용도지역의 건축물 허용 용도 또는 불허 용도
        </p>
        """,
        unsafe_allow_html=True
    )

    pdf_page_ranges = {
    '제1종전용주거지역': (1, 6),   # 페이지 지정
    '제2종전용주거지역': (1, 6),   
    '제1종일반주거지역': (1, 6), 
    '제2종일반주거지역': (1, 6), 
    '제3종일반주거지역': (1, 6), 
    '준주거지역': (1, 6), 
    '중심상업지역': (7, 12), 
    '일반상업지역': (7, 12), 
    '근린상업지역': (7, 12), 
    '유통상업지역': (7, 12), 
    '전용공업지역': (13, 18), 
    '일반공업지역': (13, 18), 
    '준공업지역': (13, 18), 
    '보전녹지지역': (19, 24), 
    '생산녹지지역': (19, 24), 
    '자연녹지지역': (19, 24), 
    '보전관리지역': (25, 30), 
    '생산관리지역': (25, 30), 
    '계획관리지역': (25, 30), 
    }

    if 'items_cleaned_fGeoPrpos_area_dstrc_nm_list' not in st.session_state:
        st.write("검색 주소지의 정보가 없습니다.")
        return
    
    # geoParams 내 items_cleaned_fGeoPrpos_area_dstrc_nm_list_dict 변수 가져와 새 변수 적용해 사용
    area_dict = st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list']

    matching_data1 = {k: v for k, v in pdf_page_ranges.items() if k in area_dict.values()}

    if len(matching_data1) >= 2:
        st.write("두 개 이상의 지역이 중첩 지정된 것으로 확인되었습니다. 자세한 사항은 국토의 계획 및 이용에 관한 법률 제84조를 검토 적용하여 주시기 바랍니다.")
    else:
        matched_name = list(matching_data1.keys())[0]
        st.markdown(
            f"""
            <p style="font-size:14px; font-weight:normal; color:white; background-color:#000000">
                <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{matched_name}</span>의 <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">건축물 허용 용도 또는 불허 용도</span>
                는 광주광역시 도시계획조례에 따라 아래와 같습니다.
            </p>
            """,
            unsafe_allow_html=True
        )

        for key, val in area_dict.items():
            #st.write(f"{key}: {val}")
    
            if val in pdf_page_ranges:          # pdf_page_ranges 딕셔너리 안에 area_dict 내 딕셔너리 값과 일치하는 사항이 있으면
                doc = fitz.open(pdf_path)

                start_page, end_page = pdf_page_ranges[val]  # 해당 키에 해당하는 값(튜플)을 언패킹

                for page_num in range(start_page - 1, end_page):  # PyMuPDF는 0-based index
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap(dpi=150)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    st.image(img, use_container_width=True)

# districtAllow 함수
def districtAllow(pdf_path2):
    st.write(' ')
    st.markdown(
        f"""
        <p style="color:blue; font-size:20px; font-weight:bold;">
            4. 용도지구의 건축물 불허 용도 및 건축 제한사항
        </p>
        """,
        unsafe_allow_html=True
    )

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
        st.write("검색 주소지의 정보가 없습니다.")
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
            <p style="font-size:14px; font-weight:normal; color:white; background-color:#000000">
                <span style="font-size:20px; color:white; font-weight:bold; background-color:#000000">{matched_name}</span>의 건축 제한사항은 광주광역시 도시계획조례에 따라 아래와 같습니다.
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
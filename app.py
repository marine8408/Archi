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

# main 함수
def main():
    #st.set_page_config(page_title="PDF 뷰어", layout="wide")
    # PDF 파일 열기
    pdf_path = "data/buildinguses.pdf"

    st.header('광산구 건축 도우미(광산AI 동아리 제작)')

    geoParams()
    pdfViewer(pdf_path)

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

    # 세션 상태 초기화
    if "search_triggered" not in st.session_state:
        st.session_state.search_triggered = False

     # 결과 확인
    #st.write("🔍 검색 트리거 상태:", st.session_state.search_triggered)
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
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
        bonbun = st.text_input('번지 본번', bonbun_key)
    with col3:
        bubun = st.text_input('번지 부번', bubun_key)
    with col4:        
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

    with col5:
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
    fbonbun = f'{bonbun}'
    fbubun = f'{bubun}'

    
    if st.session_state.search_triggered:
        st.session_state.search_triggered = False
        apiurl = 'https://api.vworld.kr/req/address?'

        try:
            if bonbun.startswith('0') and len(bubun) > 1:
                st.write('')
            else:
                if bonbun =='':
                    st.write('')
                else:
                    if bubun.startswith('0') and len(bubun) > 1:
                        st.write('잘못 입력하셨습니다')
                    else:
                        if bubun =='':
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
	                        'address': '광주광역시 광산구' + ' ' + fumd + ' ' + fbonbun + '-' + fbubun,
	                        'format': 'json',
	                        'type': 'parcel',
	                        'key': 'AF338F49-6AAA-3F06-BD94-FB6CB6817323' }

            response = requests.get(apiurl, params=params, verify=True)
    
            if response.status_code == 200 and response.status_code:
                print(response.json())
                data = response.json()

                # 브이월드 서버 지오코더에서 받아온 데이타 중 좌표 x, y 값 출력
                x = data['response']['result']['point']['x']
                y = data['response']['result']['point']['y']
                address = data['response']['input']['address']   #입력한 주소 보여주기

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

                # 정규표현식으로 숫자 제거
                cleaned_fGeoPrpos_area_dstrc_nm_list = re.sub(r'[\d\-\[\]\{\}~!@#$%^&*_=+<>?/\\|]', '', fGeoPrpos_area_dstrc_nm_list)
                items_cleaned_fGeoPrpos_area_dstrc_nm_list = cleaned_fGeoPrpos_area_dstrc_nm_list.split(',')

                items_cleaned_fGeoPrpos_area_dstrc_nm_list_dict = {f'item{i+1}': val for i, val in enumerate(items_cleaned_fGeoPrpos_area_dstrc_nm_list)}

                st.session_state['address'] = address
                st.session_state['cutFGeoLnm_lndcgr_smbol'] = cutFGeoLnm_lndcgr_smbol
                st.session_state['fGeoPrpos_area_dstrc_nm_list'] = fGeoPrpos_area_dstrc_nm_list
                st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list_dict'] = items_cleaned_fGeoPrpos_area_dstrc_nm_list_dict
                
        except ZeroDivisionError:
            st.write("주소를 다시 확인하여 주시기 바랍니다")
            #st.error("주소를 다시 확인하여 주시기 바랍니다")
        except ValueError:
            st.write("주소를 다시 확인하여 주시기 바랍니다")
            #st.warning("주소를 다시 확인하여 주시기 바랍니다")
        except Exception as e:
            st.write("주소를 다시 확인하여 주시기 바랍니다")
            #st.exception(f"주소를 다시 확인하여 주시기 바랍니다")

    else:
        st.write("토지이용정보가 궁금하시면 주소를 입력 후 검색하시기 바랍니다")
    
    if 'address' in st.session_state:
        st.write('검색하신 주소는')
        st.markdown(f'<p style="color:red; font-size:20px; font-weight:bold;">{st.session_state["address"]}</p>', unsafe_allow_html=True)

    if 'cutFGeoLnm_lndcgr_smbol' in st.session_state:
        st.write('지목은')        
        st.markdown(f'<p style="color:red; font-size:20px; font-weight:bold;">{st.session_state["cutFGeoLnm_lndcgr_smbol"]}</p>', unsafe_allow_html=True) 

    if 'fGeoPrpos_area_dstrc_nm_list' in st.session_state:
        st.write('용도지역 및 용도지구 검색결과는')                
        st.markdown(f'<p style="color:red; font-size:20px; font-weight:bold;">{st.session_state["fGeoPrpos_area_dstrc_nm_list"]}</p>', unsafe_allow_html=True)

    # 확인
    if 'items_cleaned_fGeoPrpos_area_dstrc_nm_list_dict' in st.session_state:
        for key, val in st.session_state['items_cleaned_fGeoPrpos_area_dstrc_nm_list_dict'].items():
            st.write(f"{key}: {val}")

# pdfViewer 함수
def pdfViewer(pdf_path):
    st.write(' ')
    st.markdown(
        f"""
        <p style="color:blue; font-size:20px; font-weight:bold;">
            2. 검색 주소의 용도지역별 건축 제한 사항
        </p>
        """,
        unsafe_allow_html=True
    )


    # 🔓 PDF 열기
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # 🎚 슬라이더로 범위 지정
    page_range = st.slider(
        "👈 페이지 범위 선택 👉",
        min_value=1,
        max_value=total_pages,
        value=(1, min(3, total_pages)),  # 기본값: 1~3
        step=1
    )

    start_page, end_page = page_range

    # 🖼 선택한 페이지 범위 이미지로 출력
    for page_num in range(start_page - 1, end_page):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)  # 해상도 조정 가능
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        st.image(img, caption=f"📄 {page_num + 1} 페이지", use_container_width=True)


main()
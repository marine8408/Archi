import streamlit as st
import json
import xmltodict
import pandas as pd
import requests
from urllib.request import Request, urlopen 
from urllib.parse import urlencode, quote_plus

def main():
    bonbun_key = ''
    bubun_key = ''

    st.header('광산구 건축 도우미(광산AI 동아리 제작)')
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
    
    bonbun = st.text_input('번지 본번', bonbun_key)
    bubun = st.text_input('번지 부번', bubun_key)
    
    fumd = f'{umd}'
    fbonbun = f'{bonbun}'
    fbubun = f'{bubun}'
    
    if st.button("검색"):
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
                st.write('검색하신 주소는')
                st.markdown(f'<p style="color:red;"> {address}</p>', unsafe_allow_html=True)
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

                geodata = data['features'][0]['properties']['prpos_area_dstrc_nm_list']
                geopdata = f'{geodata}'
                st.write('토지이용속성 검색결과는')
                st.markdown(f'<p style="color:red;"> {geopdata}</p>', unsafe_allow_html=True)
                #st.write(geopdata)
                
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
    
    if st.button("초기화"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        #st.session_state[bonbun_key]   # 변수 초기화
        #st.session_state[bubun_key] = ''
        st.rerun()               # main() 재시작
        
main()
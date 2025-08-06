import pandas as pd
import requests
import urllib3
import hmac
import hashlib
import secrets
import json
import os
from datetime import datetime, timezone
import streamlit as st

# ================================
# 1. API 및 파일 설정
# ================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CRISIS_API_URL = "https://www.safetydata.go.kr/V2/api/DSSP-IF-10701"
CRISIS_API_KEY = "192615ST7J88M9W9"

SOLAPI_API_KEY = "NCSKK7ZAKFX2IDMP"
SOLAPI_API_SECRET = "ZEBZKU2ZOW7QVHGJSVMMFSLBAOKCAFQB"
KAKAO_PFID = "KA01PF250728092820158gOr5ll9nb18"

CRISIS_EXCEL_FILE = "data/crisis.xlsx"
RECIPIENTS_EXCEL_FILE = "data/recipients.xlsx"
ADMIN_PASSWORD = "gwangsan123"

# ================================
# 2. 공통 함수들
# ================================
def generate_solapi_headers():
    date = datetime.now(timezone.utc).isoformat()
    salt = secrets.token_hex(32)
    message = date + salt
    signature = hmac.new(SOLAPI_API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {
        "Authorization": f"HMAC-SHA256 apiKey={SOLAPI_API_KEY}, date={date}, salt={salt}, signature={signature}",
        "Content-Type": "application/json"
    }

def save_uploaded_file(uploaded_file, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"'{filename}' 파일 업로드 완료")

def load_crisis_codes():
    if not os.path.exists(CRISIS_EXCEL_FILE):
        st.error(f"{CRISIS_EXCEL_FILE} 파일이 존재하지 않습니다.")
        return []
    sheet1 = pd.read_excel(CRISIS_EXCEL_FILE, sheet_name=0)
    return sheet1.iloc[:, 0].dropna().astype(str).tolist()

def load_recipients_and_templates():
    if not os.path.exists(RECIPIENTS_EXCEL_FILE):
        st.error(f"{RECIPIENTS_EXCEL_FILE} 파일이 존재하지 않습니다.")
        return pd.DataFrame(), pd.DataFrame()
    recipients_df = pd.read_excel(RECIPIENTS_EXCEL_FILE, sheet_name=0)
    recipients = recipients_df[["공사현장명", "현장관리자", "휴대폰연락처"]].dropna()
    template_df = pd.read_excel(RECIPIENTS_EXCEL_FILE, sheet_name=1)
    return recipients, template_df

def fetch_crisis_data(show_raw=False):
    payloads = {
        "serviceKey": CRISIS_API_KEY,
        "returnType": "json",
        "pageNo": "30",
        "numOfRows": "30"
    }
    try:
        response = requests.get(CRISIS_API_URL, params=payloads, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if show_raw:
                st.subheader("위기징후관리 API JSON 응답")
                st.json(data)
            return data if isinstance(data, dict) else None
        else:
            st.error(f"위기징후 API 호출 실패: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"API 요청 중 오류 발생: {e}")
        return None

def send_kakao_alert(phone_number, template_id, crisis_info, site_name, manager_name):
    url = "https://api.solapi.com/messages/v4/send"
    headers = generate_solapi_headers()

    data = {
        "message": {
            "to": phone_number,
            "from": "발신번호",
            "kakaoOptions": {
                "pfId": KAKAO_PFID,
                "templateId": template_id,
                "variables": {
                    "#{현장명}": site_name,
                    "#{관리자}": manager_name,
                    "#{재난명}": crisis_info["name"],
                    "#{위기형태코드}": crisis_info["code"],
                    "#{경보단계코드}": crisis_info["level"],
                    "#{최종수정일시}": crisis_info["modified"]
                }
            }
        }
    }
    res = requests.post(url, headers=headers, data=json.dumps(data))
    return res.status_code == 200

def get_current_disasters():
    matched_list = []
    crisis_codes = load_crisis_codes()
    recipients, template_df = load_recipients_and_templates()
    crisis_data = fetch_crisis_data()
    if not crisis_data:
        return matched_list

    items = crisis_data.get("body", {}).get("items", [])
    for item in items:
        crisis_code = str(item.get("MRGNCY_SHP_CD", ""))
        level_code = str(item.get("WRN_STEP_CD", ""))
        modified_dt = item.get("LAST_MDFCN_DT", "")

        if crisis_code in crisis_codes and level_code != "00":
            matched = template_df[
                (template_df["위기징후 코드"].astype(str) == crisis_code) &
                (template_df["경계단계 코드"].astype(str) == level_code)
            ]
            if not matched.empty:
                matched_list.append({
                    "위기형태코드": crisis_code,
                    "경보단계": level_code,
                    "재난명": matched.iloc[0]["재난명"],
                    "템플릿ID": matched.iloc[0]["템플릿 ID"],
                    "최종수정일시": modified_dt
                })
    return matched_list

def manual_dispatch():
    recipients, _ = load_recipients_and_templates()
    disasters = get_current_disasters()
    send_count = 0
    phones_sent = set()

    for disaster in disasters:
        template_id = disaster["템플릿ID"]
        crisis_info = {
            "name": disaster["재난명"],
            "code": disaster["위기형태코드"],
            "level": disaster["경보단계"],
            "modified": disaster["최종수정일시"]
        }
        for _, row in recipients.iterrows():
            phone = str(row["휴대폰연락처"]).strip()
            if send_kakao_alert(phone, template_id, crisis_info, row["공사현장명"], row["현장관리자"]):
                send_count += 1
                phones_sent.add(phone)
    return send_count, len(phones_sent)

# ================================
# main()
# ================================
def main():
    st.markdown("<h2 style='text-align:center;'>준비중입니다.</h2>", unsafe_allow_html=True)
    password = st.text_input("관리자 비밀번호 입력", type="password")

    if password == ADMIN_PASSWORD:
        st.success("인증 완료! 전체 페이지 표시됩니다.")

        st.markdown("<h1 style='text-align:center;'>광산구 재난경보 알림톡 시스템</h1>", unsafe_allow_html=True)

        if st.button("위기징후관리 API 결과(JSON) 보기"):
            fetch_crisis_data(show_raw=True)

        st.markdown("현재 카카오 알림 발송 대상 재난")
        disasters = get_current_disasters()
        if disasters:
            st.dataframe(pd.DataFrame(disasters))
        else:
            st.info("현재 발령 중인 재난이 없습니다.")

        st.markdown("---")
        st.subheader("📂 파일 업로드")
        crisis_file = st.file_uploader("Crisis 엑셀 파일 업로드", type=["xlsx"])
        if crisis_file:
            save_uploaded_file(crisis_file, CRISIS_EXCEL_FILE)

        recipients_file = st.file_uploader("Recipients 엑셀 파일 업로드", type=["xlsx"])
        if recipients_file:
            save_uploaded_file(recipients_file, RECIPIENTS_EXCEL_FILE)

        st.subheader("수동 알림톡 발송")
        if st.button("카카오 알림 수동 발송 실행"):
            count, people = manual_dispatch()
            st.success(f"총 {people}명에게 {count}건의 메시지를 발송했습니다.")

    elif password:  
        st.error("비밀번호가 올바르지 않습니다.")

if __name__ == "__main__":
    main()
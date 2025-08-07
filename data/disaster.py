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
import shutil

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

CRISIS_STATE_FILE = "data/crisis_state.xlsx"
SEND_LOG_FILE = "logs/send_log.xlsx"

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
    # 📦 기존 파일 백업
    if os.path.exists(filename):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{filename}.bak_{timestamp}"
        shutil.copy(filename, backup_path)
        st.info(f"기존 파일 백업됨: {backup_path}")

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
    """위기징후관리 API에서 마지막 2페이지(최신 200건) 가져오기"""
    payloads_meta = {
        "serviceKey": CRISIS_API_KEY,
        "returnType": "json",
        "pageNo": "1",
        "numOfRows": "1"
    }

    try:
        response_meta = requests.get(CRISIS_API_URL, params=payloads_meta, verify=False, timeout=10)
        if response_meta.status_code != 200:
            st.error(f"위기징후 API 호출 실패: {response_meta.status_code}")
            return None

        meta_data = response_meta.json()
        total_count = meta_data.get("totalCount", 0)
        num_of_rows = 100
        last_page = (total_count // num_of_rows) + 1

        all_items = []
        seen_ids = set()

        for page in [last_page - 1, last_page]:
            if page < 1:
                continue  # 예외처리
            payload = {
                "serviceKey": CRISIS_API_KEY,
                "returnType": "json",
                "pageNo": str(page),
                "numOfRows": str(num_of_rows)
            }
            res = requests.get(CRISIS_API_URL, params=payload, verify=False, timeout=10)
            if res.status_code == 200:
                data = res.json()
                items = data.get("response", {}).get("body", {}).get("items", [])
                for item in items:
                    uid = item.get("MRGNCY_SN")
                    if uid and uid not in seen_ids:
                        all_items.append(item)
                        seen_ids.add(uid)

        if show_raw:
            st.subheader("위기징후관리 API JSON 응답 (최신 2페이지 합산)")
            st.json(all_items)

        return {"body": {"items": all_items}}

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
    """crisis.xlsx 매칭 및 최근 1년 기준 필터링된 재난 목록 추출"""
    matched_list = []
    crisis_codes = load_crisis_codes()
    recipients, template_df = load_recipients_and_templates()
    crisis_data = fetch_crisis_data()

    if not crisis_data:
        return matched_list

    body = crisis_data.get("body", [])
    items = body if isinstance(body, list) else (body.get("items", []) if isinstance(body, dict) else [])

    # ✅ 최근 1년 기준일 계산
    today = datetime.now()
    cutoff_date = today.replace(year=today.year - 1)

    for item in items:
        crisis_code = str(item.get("MRGNCY_SHP_CD", ""))
        level_code = str(item.get("WRN_STEP_CD", ""))  # 경보단계코드
        modified_dt = item.get("LAST_MDFCN_DT", "")
        rpt_ymd = item.get("RPT_YMD", "")

        # ✅ 보고일자 최근 1년 기준 필터링
        if rpt_ymd:
            try:
                rpt_date = datetime.strptime(rpt_ymd, "%Y%m%d")
                if rpt_date < cutoff_date:
                    continue
            except Exception:
                continue  # 잘못된 날짜는 스킵

        # ✅ crisis.xlsx 매칭 (경보단계코드 00 포함)
        if crisis_code in crisis_codes:
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
                    "최종수정일시": modified_dt,
                    "보고일자": rpt_ymd
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

def load_crisis_state():
    """이전 위기 상태를 엑셀에서 불러옴"""
    if not os.path.exists(CRISIS_STATE_FILE):
        return pd.DataFrame(columns=["위기형태코드", "경보단계", "보고일자", "최종수정일시"])
    return pd.read_excel(CRISIS_STATE_FILE, dtype=str)

def save_crisis_state(df):
    """현재 위기 상태를 엑셀에 저장"""
    os.makedirs(os.path.dirname(CRISIS_STATE_FILE), exist_ok=True)
    df.to_excel(CRISIS_STATE_FILE, index=False)

def detect_and_dispatch_updates():
    """변경된 위기 상태 감지 및 알림톡 발송"""
    previous_df = load_crisis_state()
    current_list = get_current_disasters()
    if not current_list:
        return 0, 0

    current_df = pd.DataFrame(current_list)

    merged = pd.merge(
        current_df,
        previous_df,
        on="위기형태코드",
        suffixes=("_new", "_old"),
        how="left"
    )

    # ✅ 경보단계가 변경된 기존 위기코드만 필터링
    changed_df = merged[
        merged["경보단계_old"].notna() &
        (merged["경보단계_new"] != merged["경보단계_old"])
    ]

    if changed_df.empty:
        return 0, 0

    recipients, _ = load_recipients_and_templates()
    send_count = 0
    phones_sent = set()

    for _, row in changed_df.iterrows():
        template_id = row["템플릿ID"]
        crisis_info = {
            "name": row["재난명"],
            "code": row["위기형태코드"],
            "level": row["경보단계_new"],
            "modified": row["최종수정일시_new"]
        }
        for _, rec in recipients.iterrows():
            phone = str(rec["휴대폰연락처"]).strip()
            if send_kakao_alert(phone, template_id, crisis_info, rec["공사현장명"], rec["현장관리자"]):
                send_count += 1
                phones_sent.add(phone)

    # ✅ 발송 이력 로그 저장
    log_df = changed_df[[
        "위기형태코드",
        "경보단계_old",
        "경보단계_new",
        "최종수정일시_new"
    ]].copy()
    log_df["발송일시"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_sent_alerts(log_df)

    # ✅ 최신 상태 저장
    save_crisis_state(current_df)

    return send_count, len(phones_sent)

def log_sent_alerts(log_df):
    """자동 발송된 위기코드 및 경보단계 변경 로그 저장"""
    if os.path.exists(SEND_LOG_FILE):
        existing_log = pd.read_excel(SEND_LOG_FILE, dtype=str)
        log_df = pd.concat([existing_log, log_df], ignore_index=True)

    os.makedirs(os.path.dirname(SEND_LOG_FILE), exist_ok=True)
    log_df.to_excel(SEND_LOG_FILE, index=False)

# ================================
# main()
# ================================
def main():
    st.markdown("<h2 style='text-align:center;'>8월 중 서비스예정입니다.</h2>", unsafe_allow_html=True)
    password = st.text_input("관리자 비밀번호 입력", type="password")

    if password == ADMIN_PASSWORD:
        st.success("인증 완료! 전체 페이지 표시됩니다.")
        st.markdown("<h1 style='text-align:center;'>광산구 재난대응 알림톡 시스템</h1>", unsafe_allow_html=True)

        # ✅ 1시간마다 자동 실행: 위기단계 변경 감지 및 발송
        now = datetime.now()
        if "last_run" not in st.session_state:
            st.session_state["last_run"] = now
            st.info("⏱️ 처음 실행합니다. 자동감지 발송이 아직 수행되지 않았습니다.")
        else:
            elapsed_seconds = (now - st.session_state["last_run"]).total_seconds()
            if elapsed_seconds >= 43200:  # ✅ 12시간 = 43,200초
                st.markdown("### 🔁 12시간 경과됨: 자동으로 알림톡 발송 수행 중...")
                count, people = detect_and_dispatch_updates()
                st.session_state["last_run"] = now  # 시간 갱신

                if count > 0:
                    st.success(f"✅ 변경된 위기징후 {people}명에게 {count}건의 메시지를 자동 발송했습니다.")
                else:
                    st.info("변경된 위기징후가 없어 발송하지 않았습니다.")
            else:
                remain = int((43200 - elapsed_seconds) // 60)
                st.info(f"⏳ 자동 알림톡 발송까지 약 {remain}분 남았습니다.")

        # ✅ 위기징후 JSON 보기
        if st.button("위기징후관리 API 결과(JSON) 보기"):
            fetch_crisis_data(show_raw=True)

        # ✅ 현재 발령 중인 재난 보기
        st.markdown("현재 카카오 알림 발송 대상 재난")
        disasters = get_current_disasters()
        if disasters:
            st.dataframe(pd.DataFrame(disasters))
        else:
            st.info("현재 발령 중인 재난이 없습니다.")

        st.markdown("---")
        st.subheader("📋 자동 발송 이력 로그")

        if os.path.exists(SEND_LOG_FILE):
            log_df = pd.read_excel(SEND_LOG_FILE)
            with st.expander("자동 발송된 경보단계 변경 이력 보기", expanded=False):
                st.dataframe(log_df)
        else:
            st.info("아직 발송된 이력이 없습니다.")

        # ✅ 파일 상태 및 다운로드
        st.subheader("재난유형 및 현장 파일 상태 및 다운로드")
        if os.path.exists(CRISIS_EXCEL_FILE):
            st.success("✅ Crisis 엑셀 파일이 존재합니다.")
            with open(CRISIS_EXCEL_FILE, "rb") as f:
                st.download_button("Crisis 엑셀 파일 다운로드", data=f, file_name="crisis.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("❌ Crisis 엑셀 파일이 존재하지 않습니다.")

        if os.path.exists(RECIPIENTS_EXCEL_FILE):
            st.success("✅ Recipients 엑셀 파일이 존재합니다.")
            with open(RECIPIENTS_EXCEL_FILE, "rb") as f:
                st.download_button("Recipients 엑셀 파일 다운로드", data=f, file_name="recipients.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("❌ Recipients 엑셀 파일이 존재하지 않습니다.")

        st.subheader("발송 로그 다운로드")
        if os.path.exists(SEND_LOG_FILE):
            with open(SEND_LOG_FILE, "rb") as f:
                st.download_button("자동 발송 로그 다운로드", data=f, file_name="send_log.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("자동 발송 로그 파일이 존재하지 않습니다.")

        # ✅ 파일 업로드
        st.subheader("📂 파일 업로드")
        crisis_file = st.file_uploader("Crisis 엑셀 파일 업로드", type=["xlsx"])
        if crisis_file:
            save_uploaded_file(crisis_file, CRISIS_EXCEL_FILE)

        recipients_file = st.file_uploader("Recipients 엑셀 파일 업로드", type=["xlsx"])
        if recipients_file:
            save_uploaded_file(recipients_file, RECIPIENTS_EXCEL_FILE)

        # ✅ 수동 발송
        # Streamlit 내 선택 UI
        st.subheader("🔎 위기징후 코드 선택")
        all_codes = load_crisis_codes()
        selected_codes = st.multiselect("발송할 위기징후 코드를 선택하세요", options=all_codes, default=[])

        # ✅ 수동 발송만 선택 적용
        st.subheader("수동 알림톡 발송")
        if st.button("카카오 알림 수동 발송 실행"):
            count, people = manual_dispatch(selected_codes)
            st.success(f"총 {people}명에게 {count}건의 메시지를 발송했습니다.")

        st.subheader("변경된 위기 상태 감지 및 수동 발송")
        if st.button("변경 감지 후 알림 수동 발송 실행"):
            count, people = detect_and_dispatch_updates(selected_codes)
            if count > 0:
                st.success(f"⚠️ 변경된 위기징후 {people}명에게 {count}건의 메시지를 수동 발송했습니다.")
            else:
                st.info("변경된 위기징후가 없어 발송하지 않았습니다.")

    elif password:
        st.error("비밀번호가 올바르지 않습니다.")

if __name__ == "__main__":
    main()
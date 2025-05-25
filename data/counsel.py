import streamlit as st
from datetime import datetime, timedelta
import os
import pandas as pd
import sys

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "counsel_log.xlsx")


def get_next_wednesdays(n=4):
    today = datetime.today()
    wednesdays = []
    date = today
    while len(wednesdays) < n:
        if date.weekday() == 2:
            wednesdays.append(date)
        date += timedelta(days=1)
    return wednesdays


def get_time_slots():
    base = datetime.strptime("14:00", "%H:%M")
    return [(base + timedelta(minutes=20 * i)).strftime("%H:%M") for i in range(6)]


def save_to_excel(entry):
    os.makedirs(LOG_DIR, exist_ok=True)
    if os.path.exists(LOG_FILE):
        df = pd.read_excel(LOG_FILE, dtype=str)
        df["상담일시"] = df["상담일시"].astype(str).str.strip()
    else:
        df = pd.DataFrame(columns=["신청일시", "이름", "연락처", "상담일시", "상담유형", "내용"])
    df.loc[len(df)] = entry
    df.to_excel(LOG_FILE, index=False)


def is_slot_taken(date_str, time_str):
    if not os.path.exists(LOG_FILE):
        return False
    df = pd.read_excel(LOG_FILE, dtype=str)
    df["상담일시"] = df["상담일시"].astype(str).str.strip()
    return f"{date_str} {time_str}" in df["상담일시"].values


def delete_existing_entry(name, contact, consult_datetime):
    if not os.path.exists(LOG_FILE):
        return False
    df = pd.read_excel(LOG_FILE, dtype=str)
    df["상담일시"] = df["상담일시"].astype(str).str.strip()
    match = (
        df["이름"].astype(str).str.strip().str.lower() == name.strip().lower()
    ) & (
        df["연락처"].astype(str).str.strip() == contact.strip()
    ) & (
        df["상담일시"] == consult_datetime
    )
    if match.any():
        df = df[~match]
        df.to_excel(LOG_FILE, index=False)
        return True
    else:
        return False


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
    #st.title("📝 상담 신청 / 삭제 / 다운로드")
    st.markdown(
    f"""
    <p style="color:black; font-size:40px; font-weight:normal; font-weight: bold; text-align:center;">
        찾아가는 건축민원 지원센터 상담 신청
    </p>
    """,
    unsafe_allow_html=True
    )
    st.markdown(
    f"""
    <p style="color:red; font-size:14px; font-weight:normal; text-align:center;">
        ※ 매주 수요일 14:00~16:00, 광산구청 5층 건축과, 상주 건축사 상담, 현장 방문 상담은 건축사와 1차 상담 후 조율
    </p>
    """,
    unsafe_allow_html=True
    )
    # ✅ 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["📩 상담 예약", "❌ 신청 조회 및 삭제", "📥 상담 건축사 목록", "📥 상담 목록 다운로드(관리자용)"])
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

    # 상담 신청 탭
    with tab1:
        with st.form("counsel_form", clear_on_submit=True):
            name = st.text_input("성함", placeholder="예: 홍길동")
            contact = st.text_input("연락처", placeholder="010-1234-5678")
            date_options = [d.strftime("%Y-%m-%d") for d in get_next_wednesdays()]
            consult_date = st.selectbox("상담 날짜 (수요일만 가능)", date_options)
            consult_time = st.selectbox("상담 시간 (20분 간격)", get_time_slots())
            category = st.selectbox("상담 유형", ["건축 법령", "건축 인허가", "위반건축물", "기타"])
            content = st.text_area("상담 내용", height=200)

            slot_taken = is_slot_taken(consult_date, consult_time)
            if slot_taken:
                st.warning(f"❌ 이미 {consult_date} {consult_time} 상담이 예약되어 있습니다.")

            submitted = st.form_submit_button("상담 신청하기")
            if submitted:
                if not name or not contact or not content:
                    st.error("❌ 모든 입력 항목을 작성해 주세요.")
                elif slot_taken:
                    st.error("🚫 이미 신청된 상담 시간입니다. 다른 시간대를 선택해 주세요.")
                else:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    consult_dt = f"{consult_date} {consult_time}"
                    entry = [now, name, contact, consult_dt, category, content]
                    save_to_excel(entry)
                    st.success("✅ 상담 신청이 완료되었습니다.")

    # 기존 신청 삭제 탭
    with tab2:
        st.info("기존에 신청한 상담 정보를 정확히 입력한 후 확인을 눌러 주세요.")
        del_name = st.text_input("신청자 성함")
        del_contact = st.text_input("신청자 연락처")

        if 'consult_options' not in st.session_state:
            st.session_state.consult_options = []

        confirm = st.button("✅ 확인")
        if confirm:
            if os.path.exists(LOG_FILE):
                df = pd.read_excel(LOG_FILE, dtype=str)
                df["상담일시"] = df["상담일시"].astype(str).str.strip()
                df_filtered = df[
                    (df["이름"].astype(str).str.strip().str.lower() == str(del_name).strip().lower()) &
                    (df["연락처"].astype(str).str.strip() == str(del_contact).strip())
                ]
                if not df_filtered.empty:
                    st.session_state.consult_options = df_filtered["상담일시"].tolist()
                    st.success("✅ 신청 내역을 불러왔습니다.")
                else:
                    st.session_state.consult_options = []
                    st.error("❌ 일치하는 신청 내역이 없습니다.")

        if st.session_state.consult_options:
            del_consult_dt = st.selectbox("삭제할 상담 일시", st.session_state.consult_options)
            if st.button("신청 내역 삭제하기"):
                result = delete_existing_entry(del_name, del_contact, del_consult_dt)
                if result:
                    st.success("🗑️ 상담 신청이 성공적으로 삭제되었습니다.")
                    st.session_state.consult_options = []
                    st.rerun()
                else:
                    st.error("❌ 일치하는 상담 내역을 찾을 수 없습니다.")

    # 상담 로그 다운로드 탭
    with tab3:
        st.write("준비중 입니다.")
    # 상담 로그 다운로드 탭
    with tab4:
        st.info("비밀번호를 입력하면 상담 기록을 다운로드할 수 있습니다.")
        password_input = st.text_input("비밀번호 입력", type="password")
        if password_input == "gwangsan123":
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "rb") as f:
                    st.download_button(
                        label="📥 상담 기록 엑셀 다운로드",
                        data=f,
                        file_name="counsel_log.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.warning("📄 저장된 상담 기록이 없습니다.")
        elif password_input:
            st.error("❌ 비밀번호가 틀렸습니다.")
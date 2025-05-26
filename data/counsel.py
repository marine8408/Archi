import streamlit as st
from datetime import datetime, timedelta
import os
import pandas as pd
import sys

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "counsel_log.xlsx")

def excel_full_table_html(file_path):
    # ✅ 엑셀 파일에서 1열~7열까지만 읽기 (전체를 데이터로 처리)
    df = pd.read_excel(file_path, dtype=str, header=None).iloc[:, 0:7]

    # ✅ HTML 테이블 시작
    html = '''
    <table border="1" style="border-collapse: collapse; width: 100%;">
      <tbody>
    '''

    for i, (_, row) in enumerate(df.iterrows()):
        # 첫 번째 행: 배경색 지정
        row_style = ' style="background-color: #F4F4F4;"' if i == 0 else ''
        html += f'    <tr{row_style}>\n'
        for cell in row:
            html += f'      <td style="text-align: center; padding: 8px;">{cell}</td>\n'
        html += '    </tr>\n'

    html += '  </tbody>\n</table>'
    return html

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

def get_next_wednesdays(n=4):
    today = datetime.today()
    wednesdays = []
    date = today
    while len(wednesdays) < n:
        if date.weekday() == 2:
            wednesdays.append(date)
        date += timedelta(days=1)
    return wednesdays

def get_available_time_slots(selected_date):
    all_slots = ["14:00", "14:20", "14:40", "15:00", "15:20", "15:40"]
    if not os.path.exists(LOG_FILE):
        return all_slots
    df = pd.read_excel(LOG_FILE, dtype=str)
    df["상담일시"] = df["상담일시"].astype(str).str.strip()
    booked_slots = df[df["상담일시"].str.startswith(selected_date)]["상담일시"].str[-5:].tolist()
    return [slot for slot in all_slots if slot not in booked_slots]

def main():
    st.markdown("""
        <style>
            .block-container { padding-top: 1rem !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <p style="color:black; font-size:40px; font-weight:bold; text-align:center;">
        찾아가는 건축민원 지원센터 상담 신청
    </p>
    <p style="color:red; font-size:14px; text-align:center;">
        ※ 매주 수요일 14:00~16:00, 광산구청 5층 건축과, 상주 건축사 상담, 현장 방문 상담은 건축사와 1차 상담 후 조율
    </p>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📩 상담 예약", 
        "❌ 신청 조회 및 삭제", 
        "📥 상담 건축사 현황", 
        "📥 상담 목록 다운로드(관리자용)"
    ])

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

    # 📩 상담 신청 탭
    with tab1:
        date_options = [d.strftime("%Y-%m-%d") for d in get_next_wednesdays()]

        name = st.text_input(
            "성함", placeholder="예: 홍길동",
            value=st.session_state.get("name_input", ""),
            key="name_input"
        )

        contact = st.text_input(
            "연락처", placeholder="010-1234-5678",
            value=st.session_state.get("contact_input", ""),
            key="contact_input"
        )

        # 🟢 상담 날짜 먼저 선택
        consult_date = st.selectbox(
            "상담 날짜 (수요일만 가능)",
            date_options,
            key="date_input"
        )

        # ⏰ 날짜에 따른 시간대 계산
        available_slots = get_available_time_slots(consult_date)

        # ⏱ 상담 시간 선택
        if available_slots:
            consult_time = st.selectbox("상담 시간 (20분 간격)", available_slots, key="time_input")
        else:
            st.warning(f"{consult_date} 날짜는 모두 예약되었습니다.")
            st.session_state["time_input"] = ""

        # 🏷 상담 유형 선택
        category = st.selectbox(
            "상담 유형",
            ["건축 법령", "건축 인허가", "위반건축물", "기타"],
            key="category_input"
        )

        # 📄 상담 내용 입력
        content = st.text_area(
            "상담 내용",
            height=200,
            value=st.session_state.get("content_input", ""),
            key="content_input"
        )

        # ✅ 신청 버튼
        if st.button("✅ 상담 신청하기"):
            if not name or not contact or not content:
                st.error("❌ 모든 입력 항목을 작성해 주세요.")
            elif not st.session_state["time_input"]:
                st.error("❌ 상담 시간이 선택되지 않았습니다.")
            else:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                consult_dt = f"{consult_date} {st.session_state['time_input']}"
                entry = [
                    now,
                    name,
                    contact,
                    consult_dt,
                    st.session_state["category_input"],
                    content,
                ]
                save_to_excel(entry)
                st.success("✅ 상담 신청이 완료되었습니다.")

                # 🔄 상태 초기화
                for k in ["name_input", "contact_input", "content_input", "time_input", "category_input"]:
                    if k in st.session_state:
                        del st.session_state[k]

                st.rerun()

    # ❌ 신청 조회 및 삭제 탭
    with tab2:
        st.info("기존에 신청한 상담 정보를 정확히 입력한 후 확인을 눌러 주세요.")
        del_name = st.text_input("신청자 성함")
        del_contact = st.text_input("신청자 연락처")

        if 'consult_options' not in st.session_state:
            st.session_state.consult_options = []

        if st.button("✅ 확인"):
            if os.path.exists(LOG_FILE):
                df = pd.read_excel(LOG_FILE, dtype=str)
                df["상담일시"] = df["상담일시"].astype(str).str.strip()
                df_filtered = df[
                    (df["이름"].astype(str).str.strip().str.lower() == del_name.strip().lower()) &
                    (df["연락처"].astype(str).str.strip() == del_contact.strip())
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

    # 📥 상담 건축사 목록 탭
    with tab3:
        # ⬅️ 엑셀 파일 경로는 함수 외부에서 지정
        file_path = "data/architect.xlsx"

        # HTML 테이블 생성
        html_table = excel_full_table_html(file_path)

        # Streamlit에 표시
        st.markdown(html_table, unsafe_allow_html=True)

    # 📥 관리자 다운로드 탭
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
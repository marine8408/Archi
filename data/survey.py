import streamlit as st
import pandas as pd
import os
import requests
from datetime import datetime, date
from io import BytesIO
import plotly.express as px
import time

# 파일 경로
BASE_DIR = "data"
QUESTIONS_XLSX = os.path.join(BASE_DIR, "survey_questions.xlsx")
RESPONSES_XLSX = os.path.join(BASE_DIR, "survey_responses.xlsx")
IP_XLSX = os.path.join(BASE_DIR, "submitted_ips.xlsx")
ADMIN_PASSWORD = "gwangsan123"

# 클라이언트 IP 확인
def get_client_ip():
    try:
        response = requests.get("https://api64.ipify.org?format=json", timeout=2)
        return response.json().get("ip", "unknown")
    except Exception:
        return "unknown"

# 날짜 파싱
def parse_date(raw):
    try:
        if raw is None or pd.isna(raw):
            return None
        if hasattr(raw, 'to_pydatetime'):
            raw = raw.to_pydatetime()
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        if isinstance(raw, str):
            raw = raw.strip()
            try:
                return datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                try:
                    return pd.to_datetime(raw, errors="coerce").date()
                except Exception:
                    return None
    except Exception:
        return None
    return None

# 파일 초기화
def ensure_files_exist():
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
    if not os.path.exists(QUESTIONS_XLSX):
        with pd.ExcelWriter(QUESTIONS_XLSX, engine="openpyxl") as writer:
            pd.DataFrame(columns=["문항"]).to_excel(writer, sheet_name="문항", index=False)
            pd.DataFrame(columns=["설문제목", "시작일", "종료일"]).to_excel(writer, sheet_name="메타정보", index=False)
    if not os.path.exists(RESPONSES_XLSX):
        pd.DataFrame(columns=["IP", "제출시각"]).to_excel(RESPONSES_XLSX, index=False)
    if not os.path.exists(IP_XLSX):
        pd.DataFrame(columns=["IP"]).to_excel(IP_XLSX, index=False)

# 질문 및 메타 불러오기
def load_questions():
    if not os.path.exists(QUESTIONS_XLSX):
        return [], {}
    try:
        q_df = pd.read_excel(QUESTIONS_XLSX, sheet_name="문항")
        meta_df = pd.read_excel(QUESTIONS_XLSX, sheet_name="메타정보")

        questions = [str(q) for q in q_df["문항"].dropna().tolist()]
        if meta_df.empty:
            return questions, {}

        meta = {
            "title": meta_df.at[0, "설문제목"],
            "start": parse_date(meta_df.at[0, "시작일"]),
            "end": parse_date(meta_df.at[0, "종료일"])
        }
        return questions, meta
    except:
        return [], {}

# 질문 저장
def save_questions(questions, title, start_date, end_date):
    questions = [str(q) for q in questions]
    with pd.ExcelWriter(QUESTIONS_XLSX, engine="openpyxl") as writer:
        pd.DataFrame(questions, columns=["문항"]).to_excel(writer, sheet_name="문항", index=False)
        pd.DataFrame({
            "설문제목": [title],
            "시작일": [start_date.strftime("%Y-%m-%d")],
            "종료일": [end_date.strftime("%Y-%m-%d")]
        }).to_excel(writer, sheet_name="메타정보", index=False)

# IP 불러오기
def load_ip_list():
    if os.path.exists(IP_XLSX):
        df = pd.read_excel(IP_XLSX)
        return df["IP"].astype(str).dropna().str.strip().tolist()
    return []

# IP 저장
def save_ip_list(ip_list):
    df = pd.DataFrame({"IP": ip_list})
    df.to_excel(IP_XLSX, index=False)

# 응답 저장
def save_response(row_dict):
    df = pd.DataFrame([row_dict])
    if os.path.exists(RESPONSES_XLSX):
        old = pd.read_excel(RESPONSES_XLSX)
        pd.concat([old, df], ignore_index=True).to_excel(RESPONSES_XLSX, index=False)
    else:
        df.to_excel(RESPONSES_XLSX, index=False)

# 메인 함수
def main():
    ensure_files_exist()
    st.markdown(
        """
        <style>
            .block-container { padding-top: 1rem !important; }
        </style>
        """, unsafe_allow_html=True
    )

    st.markdown("""
    <p style="color:black; font-size:40px; font-weight:bold; text-align:center;">
        설문조사
    </p>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    button[data-baseweb="tab"] {
        font-size: 18px;
        padding: 12px 16px;
        border-radius: 5px 5px 0 0;
        background-color: #f0f2f6;
        color: black;
        font-weight: 600;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #2C6BED;
        color: white;
        font-weight: bold;
        font-size: 20px;
        border-bottom: 2px solid white;
    }
    </style>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["설문 참여", "설문 생성(관리자용)", "설문 통계(관리자용)"])
    questions, meta = load_questions()
    title = meta.get("title", "제목 없음")
    start = meta.get("start")
    end = meta.get("end")

    # tab1: 설문 참여
    with tab1:
        if not questions or not meta:
            st.info("진행 중인 설문이 없습니다.")
        else:
            st.subheader(f"{title}")
            st.caption(f"설문 기간: {start} ~ {end}")

            if not (isinstance(start, date) and isinstance(end, date)):
                st.warning("⏳ 설문 날짜 정보가 올바르지 않습니다.")
            elif not (start <= date.today() <= end):
                st.warning("⏳ 현재는 설문 응답 기간이 아닙니다.")
            else:
                user_ip = get_client_ip().strip()
                ip_list = [ip.strip() for ip in load_ip_list()]
                if user_ip == "unknown":
                    st.warning("⚠️ IP 확인 실패")
                elif user_ip in ip_list:
                    st.warning("이미 참여하셨습니다.")
                else:
                    with st.form("survey_form"):
                        answers = {}
                        for q in questions:
                            text, qtype = q.split(":") if ":" in q else (q, "객관식")
                            if qtype == "주관식":
                                answers[text] = st.text_input(text, key=f"text_{text}")
                            else:
                                answers[text] = st.radio(text, ["그렇다", "보통", "아니다"], key=f"radio_{text}")
                        submitted = st.form_submit_button("✅ 제출")
                        if submitted:
                            now = datetime.now()
                            save_response({"IP": user_ip, "제출시각": now.strftime("%Y-%m-%d %H:%M:%S"), **answers})
                            ip_list.append(user_ip)
                            save_ip_list(ip_list)
                            st.success("설문 제출 완료!")
                            time.sleep(2)
                            st.rerun()

    # tab2: 설문 생성
    with tab2:
        pw = st.text_input("비밀번호 입력", type="password")
        if pw == ADMIN_PASSWORD:
            st.success("인증 성공!")

            existing_qs, _ = load_questions()
            if existing_qs:
                st.warning("기존 설문이 존재합니다.")
                with st.expander("🗑 기존 설문만 삭제하기"):
                    st.warning("⚠️ 이 작업은 되돌릴 수 없습니다.\n\n모든 설문 문항, 응답, IP 기록이 삭제됩니다.")
                    confirm_delete = st.checkbox("정말 삭제하시겠습니까?")
                    if st.button("삭제 실행"):
                        if confirm_delete:
                            for path in [QUESTIONS_XLSX, RESPONSES_XLSX, IP_XLSX]:
                                if os.path.exists(path): os.remove(path)
                            st.success("✅ 기존 설문이 모두 삭제되었습니다.")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("삭제를 진행하려면 확인란에 체크해 주세요.")
                confirm = st.checkbox("⚠️ 기존 설문을 삭제하고 새 설문을 저장합니다. 모든 설문 문항, 응답, IP 기록이 삭제됩니다.")
            else:
                confirm = True

            title = st.text_input("설문 제목")
            col1, col2 = st.columns(2)
            start = col1.date_input("시작일")
            end = col2.date_input("종료일")

            st.markdown("설문조사 문항 입력(객관식/주관식)")
            new_questions = []
            for i in range(10):
                q_col1, q_col2 = st.columns([3, 1])
                q_text = q_col1.text_input(f"문항 {i+1}", key=f"q_{i}")
                q_type = q_col2.selectbox("유형", ["객관식", "주관식"], key=f"qtype_{i}")
                if q_text:
                    new_questions.append(f"{q_text}:{q_type}")

            if st.button("저장"):
                if not title or not new_questions:
                    st.error("제목과 최소 1개 문항이 필요합니다.")
                elif not confirm:
                    st.warning("기존 설문 삭제 동의가 필요합니다.")
                else:
                    save_questions(new_questions, title, start, end)
                    for path in [RESPONSES_XLSX, IP_XLSX]:
                        if os.path.exists(path): os.remove(path)
                    st.success("설문 저장 완료")
                    time.sleep(2)
                    st.rerun()
        elif pw:
            st.error("비밀번호가 틀렸습니다.")

    # tab3: 통계
    with tab3:
        pw2 = st.text_input("비밀번호 입력", type="password", key="pw2")
        if pw2 == ADMIN_PASSWORD:
            if os.path.exists(RESPONSES_XLSX):
                df = pd.read_excel(RESPONSES_XLSX)
                st.success(f"응답 수: {len(df)}명")
                questions, _ = load_questions()

                chart_data, subjective_data = [], []

                for q in questions:
                    text, qtype = q.split(":") if ":" in q else (q, "객관식")
                    if text in df.columns:
                        if qtype == "주관식":
                            subjective_data.append({"문항": text, "답변": df[text].dropna().tolist()})
                        else:
                            counts = df[text].value_counts().sort_index()
                            for resp, count in counts.items():
                                chart_data.append({
                                    "문항": text,
                                    "응답": resp,
                                    "응답 수": count
                                })

                chart_df = pd.DataFrame(chart_data)
                if not chart_df.empty and set(["문항", "응답", "응답 수"]).issubset(chart_df.columns):
                    fig = px.bar(chart_df, x="문항", y="응답 수", color="응답", barmode="group",
                                 title="전체 설문 응답 통계 (객관식 항목)", height=600)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("시각화할 수 있는 객관식 응답 데이터가 없습니다.")

                if subjective_data:
                    st.markdown("주관식 응답 보기")
                    for item in subjective_data:
                        st.markdown(f"**{item['문항']}**")
                        for idx, ans in enumerate(item['답변'], 1):
                            st.markdown(f"- {idx}. {ans}")

                output = BytesIO()
                df.to_excel(output, index=False, engine="openpyxl")
                output.seek(0)
                st.download_button(
                    label="설문 결과 엑셀파일 다운로드",
                    data=output,
                    file_name="설문_결과.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("응답 데이터가 없습니다.")
        elif pw2:
            st.error("비밀번호가 틀렸습니다.")

if __name__ == "__main__":
    main()
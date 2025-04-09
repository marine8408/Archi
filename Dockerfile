# 베이스 이미지로 Python 3.9 사용
FROM python:3.9.13

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 파일들을 이미지로 복사
COPY requirements.txt ./

# 캐시 방지를 위해 requirements.txt 이름 변경 (빌드 캐시 우회)
COPY requirements.txt ./requirements.txt

# 패키지 설치 (강제 클린 설치)
RUN rm -rf /root/.cache/pip && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 앱 파일을 이미지로 복사
COPY . .

# Streamlit 환경 변수 설정
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# API 키를 위한 환경 변수 설정 (기본값은 빈 문자열)
ENV CLOVASTUDIO_API_KEY=""
ENV APIGW_API_KEY=""

# Streamlit 애플리케이션 실행 (API 키 환경 변수를 전달)
CMD ["sh", "-c", "CLOVASTUDIO_API_KEY=$CLOVASTUDIO_API_KEY APIGW_API_KEY=$APIGW_API_KEY streamlit run app.py"]
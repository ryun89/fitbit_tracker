# ベースイメージ（軽量な Python 3.10）
FROM python:3.10-slim

# 作業ディレクトリを設定
WORKDIR /app

# 必要なライブラリをインストール
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# アプリのソースコードをコピー
COPY . .

# 環境変数（Streamlit を公開用に設定）
ENV PORT 8080
ENV STREAMLIT_SERVER_PORT 8080
ENV STREAMLIT_SERVER_HEADLESS true
ENV STREAMLIT_SERVER_ENABLECORS false

# Streamlit アプリを起動
CMD ["streamlit", "run", "gui.py", "--server.port=8080", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]

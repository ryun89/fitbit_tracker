import requests
import webbrowser

# Fitbit API情報
CLIENT_ID = ""
CLIENT_SECRET = ""
REDIRECT_URI = "http://localhost:8501/callback"  # ローカル環境でテスト用

# 認証URL生成
def generate_auth_url():
    auth_url = (
        f"https://www.fitbit.com/oauth2/authorize?"
        f"response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=activity"
    )
    return auth_url

# トークン取得
def get_access_token(auth_code):
    url = "https://api.fitbit.com/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": auth_code,
    }
    response = requests.post(url, headers=headers, data=data, auth=(CLIENT_ID, CLIENT_SECRET))
    if response.status_code == 200:
        return response.json()
    else:
        print("トークン取得エラー:", response.json())
        return None

if __name__ == "__main__":
    # 認証URL生成＆ブラウザで開く
    auth_url = generate_auth_url()
    print("ブラウザで以下のURLを開いてログインしてください：")
    print(auth_url)
    webbrowser.open(auth_url)

    # 認証コードを入力
    auth_code = input("リダイレクトURLから認証コードをコピーして貼り付けてください: ")
    token_response = get_access_token(auth_code)

    if token_response:
        print("アクセストークン取得成功:", token_response)

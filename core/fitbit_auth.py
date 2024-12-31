import requests
from firebase_auth import initialize_firestore
from firebase_admin import firestore
from urllib.parse import quote


# 認証URL生成
def generate_auth_url(CLIENT_ID, REDIRECT_URI):
    # Fitbit認証URLの生成
    auth_url = (
        f"https://www.fitbit.com/oauth2/authorize?"
        f"response_type=code&client_id={CLIENT_ID}&redirect_uri={quote(REDIRECT_URI)}&scope={quote('activity heartrate profile')}"
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


# Fitbit APIのエンドポイントをリストで管理
ENDPOINTS = [
    {
        "data_type": "steps",  # データの種類
        "endpoint": "/1/user/-/activities/steps/date/today/1d/1min.json"
    },
]

# Fitbit APIからデータを取得
def fetch_fitbit_activity_data(access_token, endpoint):
    url = f"https://api.fitbit.com{endpoint}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        return "token_expired"
    else:
        print(f"エラー: {endpoint} のデータ取得に失敗しました")
        print("ステータスコード:", response.status_code)
        print("レスポンス内容:", response.json())
        return None

# トークンの更新処理
def refresh_access_token(refresh_token, client_id, client_secret):
    url = "https://api.fitbit.com/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()
    else:
        print("トークン更新エラー:", response.json())
        return None

# データを整形してFirestoreに保存
def save_data_to_firestore(db, user_id, experiment_id, data_type, activity_data):
    try:
        dataset = activity_data.get(f"activities-{data_type}-intraday", {}).get("dataset", [])
        date = activity_data.get(f"activities-{data_type}", [{}])[0].get("dateTime", "unknown_date")

        batch = db.batch()
        for data_point in dataset:
            doc_ref = db.collection("activity_data").document()
            batch.set(doc_ref, {
                "user_id": user_id,
                "experiment_id": experiment_id,
                "data_type": data_type,
                "date": date,
                "time": data_point["time"],
                "value": data_point["value"],
                "timestamp": firestore.SERVER_TIMESTAMP
            })
        batch.commit()
        print(f"ユーザー {user_id} の {data_type} データを保存しました。")
    except Exception as e:
        print(f"Firestoreの保存中にエラーが発生しました: {e}")

# 全ユーザーのデータを取得
def process_all_users():
    db = initialize_firestore()
    users = db.collection("users").stream()

    for user_doc in users:
        user_data = user_doc.to_dict()
        user_id = user_doc.id
        access_token = user_data["fitbit_access_token"]
        refresh_token = user_data["refresh_token"]
        client_id = user_data["client_id"]
        client_secret = user_data["client_secret"]
        experiment_id = user_data.get("experiment_id", "default_experiment")

        for endpoint_info in ENDPOINTS:
            data_type = endpoint_info["data_type"]
            endpoint = endpoint_info["endpoint"]

            # Fitbit APIからデータを取得
            activity_data = fetch_fitbit_activity_data(access_token, endpoint)

            if activity_data == "token_expired":
                # トークンが期限切れの場合は更新
                token_response = refresh_access_token(refresh_token, client_id, client_secret)
                if token_response:
                    # Firestoreに新しいトークンを保存
                    db.collection("users").document(user_id).update({
                        "fitbit_access_token": token_response["access_token"],
                        "refresh_token": token_response["refresh_token"]
                    })
                    access_token = token_response["access_token"]
                    # 再度データ取得を試みる
                    activity_data = fetch_fitbit_activity_data(access_token, endpoint)

            if activity_data and activity_data != "token_expired":
                # Firestoreにデータを保存
                save_data_to_firestore(db, user_id, experiment_id, data_type, activity_data)

# メイン処理
if __name__ == "__main__":
    process_all_users()

import requests
from firebase_auth import initialize_firestore
from firebase_admin import firestore
from datetime import datetime, timedelta, timezone
import base64

# 日本時間のタイムゾーン
JST = timezone(timedelta(hours=9))

# 現在の日本時間
now_jst = datetime.now(JST)

# 1時間前の時刻を取得
one_hour_ago = now_jst - timedelta(hours=1)

# 日付、開始時刻、終了時刻を指定
date = one_hour_ago.strftime("%Y-%m-%d")  # 日付
start_time = one_hour_ago.strftime("%H:%M")  # 1時間前の時刻 (HH:MM形式)
end_time = now_jst.strftime("%H:%M")  # 現在の時刻 (HH:MM形式)

# Fitbit APIのエンドポイントをリストで管理
# Fitbit APIのエンドポイントをリストで管理
ENDPOINTS = [
    {
        "data_type": "steps",  # 歩数
        "endpoint": f"/1/user/-/activities/steps/date/{date}/1d/1min/time/{start_time}/{end_time}.json",
        "start_time": start_time,
        "end_time": end_time
    },
    {
        "data_type": "heart",  # 心拍数 (5秒おきに変更)
        "endpoint": f"/1/user/-/activities/heart/date/{date}/1d/1sec/time/{start_time}/{end_time}.json",
        "start_time": start_time,
        "end_time": end_time
    },
    {
        "data_type": "calories",  # 消費カロリー
        "endpoint": f"/1/user/-/activities/calories/date/{date}/1d/1min/time/{start_time}/{end_time}.json",
        "start_time": start_time,
        "end_time": end_time
    },
    {
        "data_type": "distance",  # 距離
        "endpoint": f"/1/user/-/activities/distance/date/{date}/1d/1min/time/{start_time}/{end_time}.json",
        "start_time": start_time,
        "end_time": end_time
    },
    {
        "data_type": "floors",  # 上った階数
        "endpoint": f"/1/user/-/activities/floors/date/{date}/1d/1min/time/{start_time}/{end_time}.json",
        "start_time": start_time,
        "end_time": end_time
    },
    {
        "data_type": "active_minutes",  # アクティブな時間
        "endpoint": f"/1/user/-/activities/minutesFairlyActive/date/{date}/1d/1min/time/{start_time}/{end_time}.json",
        "start_time": start_time,
        "end_time": end_time
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
    # client_id と client_secret を Base64 エンコード
    auth_string = f"{client_id}:{client_secret}"
    auth_header = base64.b64encode(auth_string.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}",  # ここでAuthorizationヘッダーを追加
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
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
        print(f"データの日付: {date}, データ数: {len(dataset)}") # デバッグ用
        print(f"data-type:{data_type}, activity_data:{activity_data}") # デバッグ用

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
def process_all_users(data, context):
    db = initialize_firestore()
    users = db.collection("users").stream()

    for user_doc in users:
        user_data = user_doc.to_dict()
        user_id = user_doc.id
        access_token = user_data["fitbit_access_token"]
        refresh_token = user_data["refresh_token"]
        client_id = user_data["fitbit_client_id"]
        client_secret = user_data["fitbit_client_secret"]
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

        print("データの取得および保存が完了しました。")

# メイン処理
if __name__ == "__main__":
    process_all_users(data, context)

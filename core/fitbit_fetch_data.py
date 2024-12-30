import requests
from firebase_auth import initialize_firestore
from firebase_admin import firestore  # タイムスタンプ用

# Fitbit APIのエンドポイントをリストで管理
ENDPOINTS = [
    {
        "data_type": "steps",  # データの種類
        "endpoint": "/1/user/-/activities/steps/date/today/1d.json"
    },
    # 他のデータタイプを追加する場合は以下のようにリストに追加
    # {
    #     "data_type": "heart_rate",
    #     "endpoint": "/1/user/-/activities/heart/date/today/1d/1min.json"
    # },
]

# Fitbit APIからデータを取得
def fetch_fitbit_activity_data(access_token, endpoint):
    url = f"https://api.fitbit.com{endpoint}"
    headers = {
        "Authorization": f"Bearer {access_token}"  # アクセストークンをヘッダーに追加
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"エラー: {endpoint} のデータ取得に失敗しました")
        print("ステータスコード:", response.status_code)
        print("レスポンス内容:", response.json())
        return None

# データを整形してFirestoreに保存
def save_data_to_firestore(db, user_id, experiment_id, data_type, activity_data):
    # データを時系列形式に変換して保存
    data_points = activity_data.get(f"activities-{data_type}", [])
    for entry in data_points:
        db.collection("activity_data").add({
            "user_id": user_id,
            "experiment_id": experiment_id,
            "data_type": data_type,
            "timestamp": entry["dateTime"],  # 日付をそのままタイムスタンプとして保存
            "value": int(entry["value"]),  # データ値（例: 歩数）
        })
    print(f"ユーザー {user_id} の {data_type} データがFirestoreに保存されました。")

# メイン処理
def main():
    db = initialize_firestore()

    # Firestoreからユーザー情報を取得
    user_doc = db.collection("users").document("test_user").get()
    if user_doc.exists:
        user_data = user_doc.to_dict()
        access_token = user_data["fitbit_access_token"]
        experiment_id = user_data["experiment_id"]

        # Fitbit APIから各エンドポイントのデータを取得してFirestoreに保存
        for endpoint_info in ENDPOINTS:
            data_type = endpoint_info["data_type"]
            endpoint = endpoint_info["endpoint"]
            activity_data = fetch_fitbit_activity_data(access_token, endpoint)
            if activity_data:
                save_data_to_firestore(db, "test_user", experiment_id, data_type, activity_data)
    else:
        print("ユーザー情報がFirestoreに存在しません。")

if __name__ == "__main__":
    main()

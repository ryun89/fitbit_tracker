import requests
from firebase_auth import initialize_firestore
from firebase_admin import firestore  # Firestoreでのタイムスタンプ保存に使用

# Fitbit APIのエンドポイントをリストで管理
ENDPOINTS = [
    {
        "data_type": "steps",  # データの種類
        "endpoint": "/1/user/-/activities/steps/date/today/1d/1min.json"
    },
    # 他のデータタイプを追加する場合は以下のようにリストに追加
    # {
    #     "data_type": "heart_rate",
    #     "endpoint": "/1/user/-/activities/heart/date/today/1d/1min.json"
    # },
]

# Fitbit APIからデータを取得
def fetch_fitbit_activity_data(access_token, endpoint):
    """
    Fitbit APIから指定したエンドポイントのデータを取得する。
    """
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
    """
    データをFirestoreに保存する。データは時系列形式で整理される。
    """
    try:
        dataset = activity_data.get(f"activities-{data_type}-intraday", {}).get("dataset", [])
        date = activity_data.get(f"activities-{data_type}", [{}])[0].get("dateTime", "unknown_date")

        batch = db.batch() # バッチ初期化
        
        # Firestoreに保存
        for data_point in dataset:
            doc_ref = db.collection("activity_data").document()  # ドキュメント参照を生成
            batch.set(doc_ref, {
                "user_id": user_id,
                "experiment_id": experiment_id,
                "data_type": data_type,
                "date": date,
                "time": data_point["time"],
                "value": data_point["value"],
                "timestamp": firestore.SERVER_TIMESTAMP
            })

        batch.commit()  # バッチコミットで一括保存
        print(f"ユーザー {user_id} の {data_type} データをバッチ保存しました。")
    except Exception as e:
        print(f"Firestoreのバッチ保存中にエラーが発生しました: {e}")

# メイン処理
def main():
    """
    Firestoreからユーザー情報を取得し、Fitbit APIからデータを取得してFirestoreに保存する。
    """
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

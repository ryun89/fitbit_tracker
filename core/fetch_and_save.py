import requests
from firebase_auth import initialize_firestore
from firebase_admin import firestore
from datetime import datetime, timedelta, timezone
import base64
import pandas as pd

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
        "data_type": "minutesSedentary",  # 静止時間
        "endpoint": f"/1/user/-/activities/minutesSedentary/date/{date}/1d/1min/time/{start_time}/{end_time}.json",
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
    
# 座位時間を1時間ごとに集計する関数
def aggregate_sedentary_data(dataset):
    df = pd.DataFrame(dataset)
    if df.empty:
        return None  # データがない場合

    # 時間をdatetime型に変換
    df["datetime"] = pd.to_datetime(df["time"], format="%H:%M:%S").apply(lambda x: x.replace(tzinfo=JST))

    # 1時間ごとに集計 (valueを合計)
    df_resampled = df.set_index("datetime").resample("1H")["value"].sum().reset_index()
    
    # 時間を文字列形式に変換 (HH:MM:SS 形式)
    df_resampled["time"] = df_resampled["datetime"].dt.strftime("%H:00:00")
    
    # 必要な列だけを抽出
    return df_resampled[["time", "value"]].to_dict(orient="records")

# データを整形してFirestoreに保存
def save_data_to_firestore(db, user_id, experiment_id, data_type, activity_data, slack_dm_id):
    try:
        dataset = activity_data.get(f"activities-{data_type}-intraday", {}).get("dataset", [])
        date = activity_data.get(f"activities-{data_type}", [{}])[0].get("dateTime", "unknown_date")
        print(f"データの日付: {date}, データ数: {len(dataset)}") # デバッグ用
        print(f"data-type:{data_type}, activity_data:{activity_data}") # デバッグ用
        
        # heart_rateの場合は5秒ごとのデータを取得
        if data_type == "heart":
            df = pd.DataFrame(dataset)
            df_resampled = resample_to_5s(df)
            dataset = df_resampled.to_dict(orient="records") # レコードのリストに変換
            
        # sedentaryの場合は1時間ごとに集計
        if data_type == "minutesSedentary":
            dataset = aggregate_sedentary_data(dataset)
            if dataset is None:
                print("座位時間のデータがありません。")
                return

        batch = db.batch()
        for data_point in dataset:
            doc_ref = db.collection("activity_data") \
                .document(experiment_id) \
                .collection(data_type) \
                .document()
                
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
        
# 5秒ごとにリサンプリングする関数（線形補間）
def resample_to_5s(df: pd.DataFrame) -> pd.DataFrame:
    """
    心拍数データを5秒ごとに補間し、`time` 列をHH:MM:SS形式のみに統一する関数
    """
    # `time` を明示的に datetime 型に変換（ダミー日付を設定）
    df["datetime"] = pd.to_datetime("2000-01-01 " + df["time"])

    # インデックスを datetime に設定
    df.set_index("datetime", inplace=True)

    # 5秒ごとのデータに線形補間
    df_resampled = df.resample("5S").interpolate(method="linear").reset_index()

    # `time` カラムを HH:MM:SS 形式に戻し、datetime は削除
    df_resampled["time"] = df_resampled["datetime"].dt.strftime("%H:%M:%S")

    return df_resampled.drop(columns=["datetime"])
    
# 全ユーザーのデータを取得
def process_all_users(data, context=None):
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
        slack_dm_id = user_data["slack_dm_id"]

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
                save_data_to_firestore(db, user_id, experiment_id, data_type, activity_data, slack_dm_id)

        return("データの取得および保存が完了しました。", 200)

# メイン処理
if __name__ == "__main__":
    process_all_users()

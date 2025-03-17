import requests
from firebase_auth import initialize_firestore
from firebase_admin import firestore
from datetime import datetime, timedelta, timezone
import base64
import pandas as pd

SLACK_TOKEN = ""  # Botのトークン ベタガキなのはセキュリティ上の理由でよくない
user_id = ""  # 送信先ユーザーのSlack ID
message = ""

# 日本時間のタイムゾーン
JST = timezone(timedelta(hours=9))

# 現在の日本時間
now_jst = datetime.now(JST)

# 1時間前の時刻を取得
one_hour_ago = now_jst - timedelta(hours=1)

# 1週間前の日付を取得
one_week_ago = (now_jst - timedelta(days=7)).strftime("%Y-%m-%d")

# 日付、開始時刻、終了時刻を指定
date = one_hour_ago.strftime("%Y-%m-%d")  # 日付
start_time = one_hour_ago.strftime("%H:%M")  # 1時間前の時刻 (HH:MM形式)
end_time = now_jst.strftime("%H:%M")  # 現在の時刻 (HH:MM形式)

# 指定の時間帯に介入を行うようにする関数
def should_intervene():
    intervene_hours = [9, 14, 20]
    return now_jst.hour in intervene_hours

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
        {
        "data_type": "sedentary_minutes",  # 静止時間
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
            
        # 歩数だった場合介入を行うかを判定する
        if data_type == "steps" and should_intervene():
            df = pd.DataFrame(dataset)
            hourly_step_mean = df["value"].mean()
            
            # 直近１週間の歩数データの平均値と標準偏差を計算
            mean_steps, std_steps = calculate_weekly_mean_and_std(experiment_id)
            
            # 直近1週間の平均値から0.5標準偏差以上離れた場合は介入
            if hourly_step_mean < mean_steps - 0.5 * std_steps:
                print("歩数が平均値よりも0.5標準偏差以上低いため、介入が必要です。")
                message = "最近のペースよりも歩数が少なめですね！少し体を動かしてみませんか？🏃‍♂️"
                # 介入処理を行う
                send_dm(SLACK_TOKEN, experiment_id, slack_dm_id, message)
            elif hourly_step_mean > mean_steps + 0.5 * std_steps:
                print("歩数が平均値よりも0.5標準偏差以上高いため、介入が必要です。")
                message = "今日はよく動いていますね！少し休憩をとるのも大事ですよ ☕"
                # 介入処理を行う
                send_dm(SLACK_TOKEN, experiment_id, slack_dm_id, message)
            else:
                print("歩数は平均値の範囲内です。")
                message = "歩数は平均値の範囲内です。"
                send_dm(SLACK_TOKEN, experiment_id, slack_dm_id, message)

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

def calculate_weekly_mean_and_std(experiment_id: str):
    """
    指定したユーザの週次の平均値と標準偏差を計算して返す
    """
    # Firestoreの初期化
    db = initialize_firestore()
    # 日本時間のタイムゾーン
    JST = timezone(timedelta(hours=9))
    # 現在の日本時間
    now_jst = datetime.now(JST)
    # 1週間前の日付を取得
    one_week_ago = (now_jst - timedelta(days=7)).strftime("%Y-%m-%d")
    # データ取得時間帯の範囲（8:00〜24:00）
    start_time = "08:00:00"
    end_time = "23:59:59"  # 24:00はFirestoreのクエリで指定できないため 23:59:59 を使用
    
    # 実験IDからユーザ情報を取得
    user_doc = db.collection("users").document(experiment_id).get()
    if not user_doc.exists:
        raise ValueError(f"ユーザ {experiment_id} が見つかりませんでした。")
        return None, None
    
    # 過去1週間の歩数データを取得
    steps_data = db.collection("activity_data") \
                    .document(experiment_id) \
                    .collection("steps") \
                    .where("date", ">=", one_week_ago) \
                    .stream()
                   
    data = [doc.to_dict() for doc in steps_data]
    
    # Python 側で `time` フィルタリング（8:00 ~ 24:00 の範囲）
    filtered_data = [d for d in data if "08:00:00" <= d["time"] <= "23:59:59"]

    if not filtered_data:
        print(f"{experiment_id}: 過去1週間の歩数データがありません。")
        return None, None

    # DataFrameに変換
    df = pd.DataFrame(filtered_data)

    # 平均値と標準偏差を計算
    mean_steps = df["value"].mean()
    std_steps = df["value"].std()

    print(f"{experiment_id}: 1週間の平均歩数: {mean_steps}, 標準偏差: {std_steps}")

    return mean_steps, std_steps

def send_dm(token, experiment_id, channel, text):
    """
    Botから指定のIDのDMに対してメッセージを送る
    """
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "channel": channel,
        "text": text
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    # レスポンスの内容をログに出力
    print("Slack response:", response.json())
    add_intervention(experiment_id=experiment_id, message=text)
    print("介入ログを保存しました。")

    return response.json()  # APIのレスポンスを返す

def add_intervention(experiment_id, message):
    """
    介入ログをFirestoreに保存する
    """
    db = initialize_firestore()
    now_jst = datetime.now(JST) # 最新の日本時間を取得
    date = now_jst.strftime("%Y-%m-%d")  # YYYY-MM-DD 形式
    interventions_ref = db.collection("interventions").document(experiment_id).collection(date).document()
    interventions_ref.set({
        "date": date,
        "time": now_jst.strftime("%H:%M:%S"),  # HH:MM:SS 形式
        "message": message,
        "timestamp": firestore.SERVER_TIMESTAMP  # Firestoreのサーバー時間も一応保存
    })
    
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
    calculate_weekly_mean_and_std(experiment_id="EX02")

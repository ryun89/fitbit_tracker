import pandas as pd
from firebase_admin import firestore
from datetime import datetime, timedelta, timezone
from firebase_auth import initialize_firestore

# Firestoreの初期化
db = initialize_firestore()

# 日本時間のタイムゾーン
JST = timezone(timedelta(hours=9))

# 現在の日本時間
now_jst = datetime.now(JST)

# 前日の日付を取得
yesterday = (now_jst - timedelta(days=1)).strftime("%Y-%m-%d")

# 保存先のコレクション名
DAILY_SUMMARY = "daily_summary"

# 取得するデータタイプ
DATA_TYPES = ["steps", "heart", "calories", "distance", "floors", "active_minutes"]

def calculate_and_store_daily_mean(data, context=None):
    """
    日次の平均値を計算してFirestoreに保存する
    """
    # 全ユーザを取得する
    users = list(db.collection("users").stream())
    
    for user_doc in users:
        user_data = user_doc.to_dict()
        experiment_id = user_data.get("experiment_id")
        print(f"実験ID: {experiment_id}")
        
        for data_type in DATA_TYPES:
            print(f"データタイプ: {data_type}")
            # Firestoreから前日のデータを取得
            activity_data_yesterday = db.collection("activity_data") \
                                        .document(experiment_id) \
                                        .collection(data_type) \
                                        .where("date", "==", yesterday) \
                                        .stream()
            data = [doc.to_dict() for doc in activity_data_yesterday]
            print(f"取得データ数: {len(data)}")  # ここでデータ件数を出力
            
            if not data:
                print(f"{experiment_id} - {data_type}: データが見つかりませんでした。")
                continue
            
            # dfに変換する
            df = pd.DataFrame(data)
            # 平均値の計算を行う
            average_value = df["value"].mean()
            
            # 結果をFirestoreに保存
            summury_ref = db.collection(DAILY_SUMMARY) \
                            .document(experiment_id) \
                            .collection(data_type) \
                            .document()
            summury_ref.set({
                "date": yesterday,
                "average_value": average_value,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            print(f"{experiment_id} - {data_type}: 平均値 {average_value} を保存しました。")
            
    return "ok", 200

if __name__ == "__main__":
    calculate_and_store_daily_mean()
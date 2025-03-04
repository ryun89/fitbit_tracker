import pandas as pd
from firebase_admin import firestore
from datetime import datetime, timedelta, timezone
from firebase_auth import initialize_firestore

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

    if not data:
        print(f"{experiment_id}: 過去1週間の歩数データがありません。")
        return None, None

    # DataFrameに変換
    df = pd.DataFrame(data)

    # 平均値と標準偏差を計算
    mean_steps = df["value"].mean()
    std_steps = df["value"].std()

    print(f"{experiment_id}: 1週間の平均歩数: {mean_steps}, 標準偏差: {std_steps}")

    return mean_steps, std_steps

if __name__ == "__main__":
    calculate_weekly_mean_and_std(experiment_id="EX02")
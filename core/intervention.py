from enum import Enum
import requests
from firebase_admin import firestore
from datetime import datetime, timedelta, timezone
from firebase_auth import initialize_firestore
import pandas as pd

# 日本時間のタイムゾーン
JST = timezone(timedelta(hours=9))
SLACK_TOKEN = ""

class StepResult(Enum):
    BELOW_THRESHOLD = "Below Threshold"
    WITHIN_THRESHOLD = "Within Threshold"
    ABOVE_THRESHOLD = "Above Threshold"

class SedentaryResult(Enum):
    BELOW_THRESHOLD = "Below Threshold"
    WITHIN_THRESHOLD = "Within Threshold"
    ABOVE_THRESHOLD = "Above Threshold"

class InterventionMessage(Enum):
    WALK_MORE = "最近のペースよりも歩数が少なく、座位時間が長くなっています。軽く歩いてリフレッシュしましょう！🏃‍♂️"
    TOO_ACTIVE = "歩数が多く、座位時間が短いため、休憩をとりましょう ☕"
    NORMAL = "順調です！この調子で続けていきましょう 💪😊"

# 介入スケジュールを取得する関数
def get_intervention_schedule(date_str):
    db = initialize_firestore()
    doc_ref = db.collection("intervene_schedule").document(date_str)
    doc = doc_ref.get()

    if doc.exists:
        data = doc.to_dict()
        print(f"{date_str} の介入時刻:", data.get("hours"))
        return data.get("hours")
    else:
        print(f"{date_str} の介入スケジュールは存在しません。")
        return None

# 指定の時間帯に介入を行うかを判定する関数
def should_intervene():
    now_jst = datetime.now(JST)
    date_str = now_jst.strftime("%Y-%m-%d")
    current_hour = now_jst.hour

    intervene_hours = get_intervention_schedule(date_str)
    if intervene_hours:
        return current_hour in intervene_hours
    return False

# 直近1時間の平均を計算
def calculate_recent_mean(experiment_id: str, data_type: str):
    db = initialize_firestore()
    now_jst = datetime.now(JST)
    one_hour_ago = now_jst - timedelta(hours=1)
    
    # 現在の時刻の直前の1時間の範囲を指定
    end_time = now_jst.replace(minute=0, second=0, microsecond=0)  # 直前の00分の時刻 (例: 10:00)
    start_time = end_time - timedelta(hours=1)  # 1時間前 (例: 09:00)
    print(f"取得対象: {start_time} 〜 {end_time}")

    docs = db.collection("activity_data") \
        .document(experiment_id) \
        .collection(data_type) \
        .where("timestamp", ">=", start_time) \
        .where("timestamp", "<", end_time) \
        .stream()
    
    data = [doc.to_dict() for doc in docs]
    if not data:
        return None

    df = pd.DataFrame(data)
    return df["value"].mean()

# 過去1週間の平均と標準偏差を計算
def calculate_weekly_mean_and_std(experiment_id: str, data_type: str):
    db = initialize_firestore()
    now_jst = datetime.now(JST)
    one_week_ago = now_jst - timedelta(days=7)

    docs = db.collection("activity_data") \
        .document(experiment_id) \
        .collection(data_type) \
        .where("timestamp", ">=", one_week_ago) \
        .stream()

    data = [doc.to_dict() for doc in docs]
    if not data:
        return None, None
    
    # Python 側で `time` フィルタリング（9:00 ~ 21:59 の範囲）
    filtered_data = [d for d in data if "09:00:00" <= d["time"] <= "21:59:59"]

    df = pd.DataFrame(filtered_data)
    return df["value"].mean(), df["value"].std()

# 介入を実行する関数
def should_execute_intervention(experiment_id: str, slack_dm_id: str):
    step_mean_1h = calculate_recent_mean(experiment_id, "steps")
    sedentary_mean_1h = calculate_recent_mean(experiment_id, "minutesSedentary")

    step_mean_week, step_std_week = calculate_weekly_mean_and_std(experiment_id, "steps")
    sedentary_mean_week, sedentary_std_week = calculate_weekly_mean_and_std(experiment_id, "minutesSedentary")

    if step_mean_1h is None or sedentary_mean_1h is None:
        return False

    if (step_mean_week is None or step_std_week is None or
        sedentary_mean_week is None or sedentary_std_week is None):
        return False

    step_threshold_low = step_mean_week - 0.5 * step_std_week
    step_threshold_high = step_mean_week + 0.5 * step_std_week
    sedentary_threshold_high = sedentary_mean_week + 0.5 * sedentary_std_week
    sedentary_threshold_low = sedentary_mean_week - 0.5 * sedentary_std_week


    # 歩数と座位時間の判定
    if step_mean_1h < step_threshold_low:
        step_result = StepResult.BELOW_THRESHOLD
    elif step_mean_1h > step_threshold_high:
        step_result = StepResult.ABOVE_THRESHOLD
    else:
        step_result = StepResult.WITHIN_THRESHOLD

    if sedentary_mean_1h > sedentary_threshold_high:
        sedentary_result = SedentaryResult.ABOVE_THRESHOLD
    elif sedentary_mean_1h < sedentary_threshold_low:
        sedentary_result = SedentaryResult.BELOW_THRESHOLD
    else:
        sedentary_result = SedentaryResult.WITHIN_THRESHOLD

    # メッセージの判定ロジック
    if step_result == StepResult.BELOW_THRESHOLD and sedentary_result == SedentaryResult.ABOVE_THRESHOLD:
        message = InterventionMessage.WALK_MORE.value
    elif step_result == StepResult.ABOVE_THRESHOLD and sedentary_result == SedentaryResult.BELOW_THRESHOLD:
        message = InterventionMessage.TOO_ACTIVE.value
    else:
        message = InterventionMessage.NORMAL.value

    # Slack DMを送信
    send_dm(SLACK_TOKEN, experiment_id, slack_dm_id, message)

    save_intervention_log(experiment_id, step_result, sedentary_result, message)
    
    return True

# 介入ログを保存する関数
def save_intervention_log(experiment_id, step_result, sedentary_result, message):
    db = initialize_firestore()
    now_jst = datetime.now(JST)
    date = now_jst.strftime("%Y-%m-%d")
    
    logs_ref = db.collection("intervention_logs").document(experiment_id).collection(date).document()
    logs_ref.set({
        "experiment_id": experiment_id,
        "step_result": step_result.value,
        "sedentary_result": sedentary_result.value,
        "message": message,
        "time": now_jst.strftime("%H:%M:%S"),
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    print(f"Log saved successfully: {experiment_id} - {step_result.value} / {sedentary_result.value} - {message}")

# Slack DM に送信する関数
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

    return response.json()  # APIのレスポンスを返す
    
# Cloud Functions で定期実行されるエントリーポイント関数
def scheduled_intervention(data, context=None):
    """
    Cloud Functions で定期実行されるエントリーポイント関数。
    1時間に1回（例：毎時00分）実行するように設定する。
    """
    # Firestoreの初期化
    db = initialize_firestore()
    users = db.collection("users").stream()
    
    results = []
    for user_doc in users:
        user_data = user_doc.to_dict()
        experiment_id = user_data.get("experiment_id")
        slack_dm_id = user_data["slack_dm_id"]
        
        if experiment_id and should_intervene():
            triggered = should_execute_intervention(experiment_id, slack_dm_id)
            results.append((experiment_id, triggered))
    
    return f"Checked interventions for all users. Results: {results}", 200

# メイン処理
if __name__ == "__main__":
    scheduled_intervention(None)

import random
from datetime import datetime, timezone, timedelta
from firebase_admin import firestore
from firebase_auth import initialize_firestore  # あなたのプロジェクトに合わせて調整
        
def craete_time_block():
    # Firestore 初期化
    db = initialize_firestore()

    # 日本時間を取得
    JST = timezone(timedelta(hours=9))
    now_jst = datetime.now(JST)
    today_str = now_jst.strftime("%Y-%m-%d")  # 例: "2025-03-26"

    # タイムブロックと候補時間
    time_blocks = {
        "block_1": [9, 10, 11, 12],
        "block_2": [13, 14, 15],
        "block_3": [16, 17, 18, 19],
        "block_4": [20, 21, 22]
    }

    # 各ブロックからランダムに1つずつ選ぶ
    intervene_hours = [random.choice(hours) for hours in time_blocks.values()]
    intervene_hours.sort()  # 昇順で見やすく

    # Firestore に保存
    doc_ref = db.collection("intervene_schedule").document(today_str)
    doc_ref.set({
        "date": today_str,
        "hours": intervene_hours,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

    print(f"{today_str} の介入時刻を Firestore に保存しました: {intervene_hours}")

if __name__ == "__main__":
    craete_time_block()
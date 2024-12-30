import streamlit as st
import pandas as pd
from firebase_admin import firestore
from core.firebase_auth import initialize_firestore

def fetch_data_from_firestore(db, user_id, data_type, date):
    # クエリでデータを取得
    query = db.collection("activity_data").where("user_id", "==", user_id).where("data_type", "==", data_type).where("date", "==", date)
    docs = query.stream()
    results = [doc.to_dict() for doc in docs]

    if not results:
        st.error("指定されたデータが存在しません。")
        return None

    return results

def main():
    st.title("FitbitTracker")

    db = initialize_firestore()

    # ユーザー入力
    user_id = st.text_input("ユーザーIDを入力してください", "test_user")
    data_type = st.selectbox("データタイプを選択してください", ["steps", "heart_rate"])
    date = st.date_input("日付を選択してください")

    if st.button("データを取得"):
        data = fetch_data_from_firestore(db, user_id, data_type, date.strftime("%Y-%m-%d"))
        if data:
            st.title(f"{date} の {data_type} データ")
            # FirestoreのデータをDataFrameに変換
            df = pd.DataFrame(data)
            df["time"] = pd.to_datetime(df["time"], format="%H:%M:%S")
            df = df.sort_values(by="time")  # 時系列順にソート
            df = df.set_index("time")  # timeをインデックスに設定

            # グラフを描画
            st.line_chart(df["value"])
        else:
            st.error("データの取得に失敗しました。")

if __name__ == "__main__":
    main()

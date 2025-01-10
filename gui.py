import sys
import os
import streamlit as st
import requests
import pandas as pd
import webbrowser
from firebase_admin import firestore
sys.path.append(os.path.join(os.path.dirname(__file__), "core"))
from core.firebase_auth import initialize_firestore
from core.fitbit_auth import generate_auth_url, get_access_token


# Firestoreにアカウント情報を登録する
def save_user_data_to_firestore(db, user_id, token_response, experiment_id):
    db.collection("users").document(user_id).set({
        "fitbit_client_id": st.session_state["CLIENT_ID"],
        "fitbit_client_secret": st.session_state["CLIENT_SECRET"],
        "fitbit_access_token": token_response["access_token"],
        "refresh_token": token_response["refresh_token"],
        "token_expiration": token_response["expires_in"],
        "experiment_id": experiment_id,
    })
    st.success("アカウントが保存されました！")


# アカウント作成画面
def account_creation_screen(db):
    st.title("アカウント作成")

    # セッションで値を保持
    if "CLIENT_ID" not in st.session_state:
        st.session_state["CLIENT_ID"] = ""
    if "CLIENT_SECRET" not in st.session_state:
        st.session_state["CLIENT_SECRET"] = ""
    if "redirect_url" not in st.session_state:
        st.session_state["redirect_url"] = ""
    if "auth_code" not in st.session_state:
        st.session_state["auth_code"] = ""
    if "experiment_id" not in st.session_state:
        st.session_state["experiment_id"] = ""

    # ユーザー入力
    user_id = st.text_input("新しいユーザーIDを入力してください")
    st.session_state["CLIENT_ID"] = st.text_input("Fitbit APIのクライアントIDを入力してください", value=st.session_state["CLIENT_ID"])
    st.session_state["CLIENT_SECRET"] = st.text_input("Fitbit APIのクライアントシークレットを入力してください", value=st.session_state["CLIENT_SECRET"])
    REDIRECT_URI = "https://fitbittracker-bczlqhsg8z7tmzyjptxynr.streamlit.app/callback"  # 変更不要
    st.session_state["experiment_id"] = st.text_input("実験IDを入力してください", value=st.session_state["experiment_id"])

    # Fitbit認証URLの生成と表示
    if st.button("Fitbitに接続"):
        if not st.session_state["CLIENT_ID"] or not st.session_state["CLIENT_SECRET"] or not user_id or not st.session_state["experiment_id"]:
            st.error("全ての項目を入力してください")
            return
        auth_url = generate_auth_url(CLIENT_ID=st.session_state["CLIENT_ID"], REDIRECT_URI=REDIRECT_URI)
        st.write("以下のURLを開いてログインしてください：")
        st.write(auth_url)
        webbrowser.open(auth_url)
        st.session_state["redirect_url"] = ""  # リセット

    # リダイレクトURL入力
    st.info("リダイレクトURLをコピーして貼り付けてください")
    st.session_state["redirect_url"] = st.text_input("リダイレクトURLを入力してください", value=st.session_state["redirect_url"])

    # トークン取得処理
    if st.button("トークンを取得"):
        if st.session_state["redirect_url"]:
            try:
                # リダイレクトURLから余計な部分を削除
                clean_url = st.session_state["redirect_url"].split("#")[0]

                # 認証コードを抽出
                st.session_state["auth_code"] = clean_url.split("code=")[1]
                token_response = get_access_token(
                    st.session_state["auth_code"],
                    st.session_state["CLIENT_ID"],
                    st.session_state["CLIENT_SECRET"],
                    REDIRECT_URI
                )
                if token_response:
                    save_user_data_to_firestore(db, user_id, token_response, st.session_state["experiment_id"])
                    st.success("アカウントが作成されました！ログインしてください。")
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = user_id
            except IndexError:
                st.error("リダイレクトURLから認証コードを抽出できませんでした。")
        else:
            st.error("リダイレクトURLを入力してください。")


# ログイン画面
def login_screen(db):
    st.title("ログイン")
    user_id = st.text_input("ユーザーIDを入力してください")
    if st.button("ログイン"):
        user_doc = db.collection("users").document(user_id).get()
        if user_doc.exists:
            st.success("ログイン成功！")
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user_id
        else:
            st.error("アカウントが見つかりません。新しいアカウントを作成してください。")


# メイン画面
def main_screen(db):
    st.title("Fitbit Tracker メイン画面")

    user_id = st.session_state["user_id"]
    data_type = st.selectbox("データタイプを選択してください", ["steps", "heart"])
    date = st.date_input("日付を選択してください")

    if st.button("データを取得"):
        query = db.collection("activity_data").where("user_id", "==", user_id).where("data_type", "==", data_type).where("date", "==", date.strftime("%Y-%m-%d"))
        docs = query.stream()
        data = [doc.to_dict() for doc in docs]

        if data:
            st.write(f"{date} の {data_type} データ")
            df = pd.DataFrame(data)
            df["time"] = pd.to_datetime(df["time"], format="%H:%M:%S")
            df = df.sort_values(by="time").set_index("time")
            st.line_chart(df["value"])
        else:
            st.error("データが見つかりませんでした。")


# メイン関数
def main():
    db = initialize_firestore()

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None

    if not st.session_state["logged_in"]:
        option = st.sidebar.selectbox("選択してください", ["ログイン", "アカウント作成"])
        if option == "ログイン":
            login_screen(db)
        elif option == "アカウント作成":
            account_creation_screen(db)
    else:
        main_screen(db)


if __name__ == "__main__":
    main()

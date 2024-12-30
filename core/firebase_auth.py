import firebase_admin
from firebase_admin import credentials, firestore

# Firebase Admin SDKの初期化
def initialize_firestore():
    # Firebaseアプリが既に初期化されているか確認
    if not firebase_admin._apps:
        # 注意: ここでJSONファイルのパスを直接書かないでください！
        # 環境変数またはStreamlit Secretsを使用してください。
        cred = credentials.Certificate("")  # ローカル環境用
        firebase_admin.initialize_app(cred)

    # Firestoreクライアントを作成して返す
    return firestore.client()

# アクセストークンをFirestoreに保存
def save_user_token(db, user_id, experiment_id, token_data):
    db.collection("users").document(user_id).set({
        "experiment_id": experiment_id,
        "fitbit_access_token": token_data["access_token"],
        "fitbit_refresh_token": token_data["refresh_token"],
        "fitbit_token_expiry": token_data["expires_in"],
        "created_at": firestore.SERVER_TIMESTAMP,
    })
    print(f"ユーザー {user_id} のトークンがFirestoreに保存されました。")

# テスト用: Firestoreにアクセストークンを保存
if __name__ == "__main__":
    # Firestoreを初期化
    db = initialize_firestore()

    # サンプルデータ
    user_id = "test_user"
    experiment_id = "EXP001"
    token_data = {
        "access_token": "取得したアクセストークン",
        "refresh_token": "取得したリフレッシュトークン",
        "expires_in": 3600,
    }

    # Firestoreに保存
    save_user_token(db, user_id, experiment_id, token_data)

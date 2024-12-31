from google.cloud import secretmanager
import firebase_admin
from firebase_admin import credentials, firestore

# Google Secret Managerから秘密情報を取得する関数
def access_secret_version():
    """
    Google Secret Managerから最新のシークレットを取得
    """
    # Secret Managerクライアントを初期化
    client = secretmanager.SecretManagerServiceClient()
    
    # 環境変数からプロジェクトIDとSecret IDを取得
    PROJECT_ID = os.getenv("PROJECT_ID")
    SECRET_ID = os.getenv("SECRET_ID")

    if not project_id or not secret_id:
        raise EnvironmentError("PROJECT_ID または SECRET_ID が設定されていません。")

    # Secretのパスを作成
    name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"

    # Secretを取得
    response = client.access_secret_version(request={"name": name})

    # Secretのペイロード（JSON文字列）を取得してデコード
    secret_payload = response.payload.data.decode("UTF-8")
    return secret_payload

# Firebase Admin SDKの初期化
def initialize_firestore():
    """
    Firebase Admin SDKを初期化し、Firestoreクライアントを返す
    """
    # Firebaseアプリが既に初期化されているか確認
    if not firebase_admin._apps:
        try:
            # Google Secret ManagerからFirebase認証情報を取得
            firebase_credentials_json = access_secret_version()

            # Firebase Admin SDKを初期化
            cred = credentials.Certificate(firebase_credentials_json)
            firebase_admin.initialize_app(cred)

        except Exception as e:
            raise RuntimeError(f"Firebase Admin SDKの初期化中にエラーが発生しました: {e}")

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

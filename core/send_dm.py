import requests

def send_dm(token, channel, text):
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

# 使い方の例
SLACK_TOKEN = ""  # Botのトークン
USER_ID = ""  # 送信先ユーザーのSlack ID
MESSAGE = "うおおおおおおおおおおお"

send_dm(SLACK_TOKEN, USER_ID, MESSAGE)

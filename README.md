# Fitbit Tracker

Fitbit Tracker は、ユーザが自身の身体活動データを可視化し、運動習慣を改善するためのアプリケーションです。  
Fitbit API を使用して、歩数・心拍数・消費カロリー・移動距離・階数などのデータを収集し、  
**過去1週間のデータを基準に異常値を検知し、必要に応じて介入メッセージを送信** する機能を備えています。

---

## 🌟 主な機能

1. **ログイン機能**
   - ユーザの新規登録やログインが可能。
   - Fitbit API の OAuth 認証をアプリ画面上で完結できるように実装。

2. **自動データ取得**
   - GCP（Google Cloud Platform）の Cloud Functions を使用して、Fitbit API から **1時間ごと** にデータを取得。

3. **Fitbit API との連携**
   - Fitbit API を使用し、**歩数・心拍数・消費カロリー・移動距離・階数・アクティブ時間** を取得。
   - Firestore に保存し、履歴データと比較できる仕組みを構築。

4. **介入（通知機能）**
   - **直近1時間のデータが過去1週間の平均値から 0.5標準偏差以上ずれた場合** に介入。
   - 介入メッセージは **Slack の DM** で自動送信（アカウント作成時に DM ID を登録）。
   - 介入が実施されたタイミングは可視化画面にマーキングされる。

5. **データの可視化**
   - **選択した日の 1分ごとのデータ** を表示。
   - **過去1週間の平均値の横線** を表示。
   - **介入が行われたタイミングのマーキング** を表示。

6. **デプロイ**
   - **Streamlit Cloud** にデプロイ済み、Webブラウザからアクセス可能。
   - **実行はこちら** 👉 [Fitbit Tracker アプリ](https://fitbittracker-bczlqhsg8z7tmzyjptxynr.streamlit.app/)

---

## 🎯 使用用途

- **身体活動の可視化**  
  ユーザは自身の運動データをリアルタイムで確認できる（データは 1時間ごとに更新）。
  
- **介入の効果検証**  
  - **「通知あり」グループ** と **「通知＋可視化」グループ** の比較を行い、可視化の効果を分析。
  - ユーザの行動変容にどの程度影響があるのかをデータ分析。

---

## 💻 使用方法

1. アプリにアクセスし、アカウントを作成・ログイン。
2. Fitbitアカウントと連携し、運動データを取得可能にする。
3. 1時間ごとにデータが自動更新され、可視化画面で確認。
4. 異常値検出時に Slack で通知を受け取り、可視化画面で介入履歴を確認。

---

## 🛠️ 技術スタック

- **フロントエンド**: Streamlit
- **バックエンド**: Python, Fitbit API
- **データベース**: Firebase Firestore
- **スケジューリング**: GCP Cloud Functions + Cloud Scheduler
- **通知機能**: Slack API
- **ホスティング**: Streamlit Cloud

---

## 📌 今後の課題

1. **リアルタイム性の向上**  
 - 現在は 1時間ごとのデータ更新、将来的に短縮できるか検討。

2. **データの拡張**  
 - 現在は「歩数・心拍数・消費カロリー・階数・距離・アクティブ時間」のみ取得。
 - 追加データ（睡眠データなど）の導入を検討。

3. **分析機能の強化**  
 - ユーザが自身の活動を比較しやすいようなダッシュボードの強化。
 - 介入の影響を可視化し、行動変容のパターンを分析。

---

## 📂 リポジトリ

詳細な実装については、以下のリポジトリをご覧ください：

🔗 [Fitbit Tracker GitHubリポジトリ](https://github.com/ryun89/fitbit_tracker)

---

## 📝 ライセンス

このプロジェクトのライセンスについては、リポジトリ内の [LICENSE](https://github.com/ryun89/fitbit_tracker/blob/main/LICENSE) をご参照ください。

---

## ✉️ お問い合わせ

このアプリに関する質問やフィードバックがあれば、GitHubの [Issues](https://github.com/ryun89/fitbit_tracker/issues) をご利用ください。

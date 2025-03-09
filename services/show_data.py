import altair as alt
import sys
import os
import streamlit as st
import pandas as pd
sys.path.append(os.path.join(os.path.dirname(__file__), "core"))
from datetime import datetime, timedelta

# データを可視化する関数
def display_data_chart(db, experiment_id, data_type, date):
    formatted_date = date.strftime("%Y-%m-%d")
    print(f"検索クエリ: activity_data/{experiment_id}/{data_type} where date == {formatted_date}") # デバッグ用
    # 指定した日付のデータを取得
    docs = db.collection("activity_data") \
                .document(experiment_id) \
                .collection(data_type) \
                .where("date", "==", formatted_date) \
                .stream()
    data = [doc.to_dict() for doc in docs]
    
    # 介入データを取得
    intervention_docs = db.collection("interventions") \
                            .document(experiment_id) \
                            .collection(formatted_date) \
                            .stream()
    print(f"検索クエリ: interventions/{experiment_id}/{formatted_date}")  # デバッグ用
    intervention_data = [doc.to_dict() for doc in intervention_docs]

    # 過去7日間の平均を計算
    start_date = date - timedelta(days=7)
    docs_avg = db.collection("daily_summary") \
                    .document(experiment_id) \
                    .collection(data_type) \
                    .where("date", ">=", start_date.strftime("%Y-%m-%d")) \
                    .where("date", "<", date.strftime("%Y-%m-%d")) \
                    .stream()
                            
    data_avg = [doc.to_dict() for doc in docs_avg]
    print("取得データ:", data_avg)  # デバッグ用

    if data:
        st.write(f"{formatted_date} の {data_type} データ")
        df = pd.DataFrame(data)
        df["time"] = pd.to_datetime(df["time"], format="%H:%M:%S")
        df = df.sort_values(by="time")
        
        if intervention_data:
            print("介入データ:", intervention_data)  # デバッグ用
            df_intervention = pd.DataFrame(intervention_data)
            df_intervention["time"] = pd.to_datetime(df_intervention["time"], format="%H:%M:%S")
            
            # 介入時間ごとに、一番近い `df` の値を取得
            df_intervention["value"] = df_intervention["time"].apply(
                lambda t: df.loc[(df["time"] - t).abs().idxmin(), "value"]
                if not df.empty else None
            )
            df_intervention.dropna(inplace=True)  # NaN を削除（該当する値がなかった場合）
        else:
            df_intervention = pd.DataFrame(columns=["time", "message"])

        # 過去7日間の平均値を計算
        if data_avg:
            df_avg = pd.DataFrame(data_avg)
            avg_value = df_avg["average_value"].mean()  # 平均値を計算
        else:
            avg_value = None

        # Altairで折れ線グラフを描画
        chart = alt.Chart(df).mark_line(color="red").encode(
            x=alt.X("time:T", title="時間"),
            y=alt.Y("value:Q", title="値")
        ).properties(
            width=700,  # グラフの幅
            height=400  # グラフの高さ
        )
        
        # 介入点をプロットする
        if not df_intervention.empty:
            intervention_marks = alt.Chart(df_intervention).mark_circle(
                color="blue", size=300
            ).encode(
                x="time:T",
                y="value:Q",  # 修正点：介入時の `y` 値を `df` から取得した値にする
                tooltip=["message"]  # ホバーで介入メッセージを表示
            )
            chart = chart + intervention_marks

        # 過去7日間の平均値を横線として追加
        if avg_value is not None:
            avg_line = alt.Chart(pd.DataFrame({"平均値": [avg_value]})).mark_rule(
                color="yellow", strokeDash=[5, 5]
            ).encode(y="平均値:Q")

            chart = chart + avg_line  # グラフに横線を追加

        st.altair_chart(chart, use_container_width=True)
    else:
        st.error("データが見つかりませんでした。")

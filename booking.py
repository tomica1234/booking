import streamlit as st
import streamlit_calendar as st_calendar
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd


# 認証情報の設定
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
service_account_info = st.secrets["google_service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)

# Google Sheetを開く
sheet = client.open("app").worksheet("booking")

# Google SheetをPandas DataFrameに読み込む
def load_data():
    df = pd.DataFrame(sheet.get_all_values(), columns=['id', 'start_date', 'start_time', 'end_date', 'end_time', 'purpose'])
    data = df[1:]  # ヘッダーを除外
    data['id'] = pd.to_numeric(data['id'], errors='coerce')  # IDを数値として扱う
    data.index = data.index + 1
    data.reset_index(drop=True, inplace=True)
    return data

# 新しいIDを生成
def generate_next_id(data):
    if data.empty:
        return 1  # 最初のID
    return data['id'].max() + 1  # 現在の最大ID + 1

# 時間重複を確認する
def is_time_conflict(start_date, start_time, end_date, end_time, data):
    new_start = datetime.datetime.combine(start_date, start_time)
    new_end = datetime.datetime.combine(end_date, end_time)
    for _, row in data.iterrows():
        existing_start = datetime.datetime.strptime(row['start_date'] + " " + row['start_time'], "%Y-%m-%d %H:%M:%S")
        existing_end = datetime.datetime.strptime(row['end_date'] + " " + row['end_time'], "%Y-%m-%d %H:%M:%S")
        if (new_start < existing_end) and (new_end > existing_start):
            return True
    return False

# スプレッドシートのデータをロード
data = load_data()

# 予約システムのタイトル
st.title('予約システム')

# 予約追加フォーム
with st.form("add_data_form"):
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("開始日")
        start_time = st.time_input("開始時間", datetime.time(9, 0))
        end_date = st.date_input("終了日")
        end_time = st.time_input("終了時間", datetime.time(20, 0))
    with col2:
        options = ["橘 駿太", "竹内 琉雄", "林田 航生", "池上 真歩"]
        choice1 = st.multiselect("選択してください", options)
        choice2 = st.text_input("4人以外の同乗者を入力してください")

        # 入力値を判定し、選択された値を代入
        if choice1 and not choice2:
            selected_purpose = choice1
        elif choice2 and not choice1:
            selected_purpose = choice2 + '(ゲスト)'
        elif choice1 and choice2:
            selected_purpose = choice1 + [choice2 + '(ゲスト)']
        else:
            selected_purpose = None  # どちらも入力されていない場合

    submit_add = st.form_submit_button("追加")
    if submit_add:
        has_error = False

        # 必須チェック
        if len(choice1) == 0:
            st.error("エラー: 少なくとも1人を選択してください。")
            has_error = True

        # 時間の妥当性チェック
        if not has_error and datetime.datetime.combine(start_date, start_time) >= datetime.datetime.combine(end_date, end_time):
            st.error("エラー: 開始時間は終了時間よりも前でなければなりません。")
            has_error = True

        # 重複チェック
        if not has_error and is_time_conflict(start_date, start_time, end_date, end_time, data):
            st.error("エラー: この時間にはすでに予約が存在します。")
            has_error = True

        if not has_error:
            # 新しいIDを生成（連番）
            new_id = generate_next_id(data)
            
            # JSONシリアライズ可能な形式に変換
            new_data = [str(new_id), str(start_date), str(start_time), str(end_date), str(end_time), str(selected_purpose)]
            
            # データをスプレッドシートに追加
            sheet.append_row(new_data)
            st.success(f"予約が正常に追加されました！ ID: {new_id}")
            st.experimental_rerun()


# 予約削除フォーム
with st.form("delete_data_form_unique"):
    delete_id = st.number_input("削除する予約のIDを入力してください", min_value=1, step=1)
    submit_delete = st.form_submit_button("削除")

    if submit_delete:
        try:
            if delete_id in data['id'].values:
                # int64をintにキャスト
                row_to_delete = int(data[data['id'] == delete_id].index[0] + 2)  # ヘッダーを考慮して+2
                sheet.delete_rows(row_to_delete)
                st.success(f"ID {delete_id} の予約を削除しました。")
                st.experimental_rerun()
            else:
                st.error(f"ID {delete_id} が見つかりません。")
        except Exception as e:
            st.error(f"エラーが発生しました: {str(e)}")


# カレンダー表示
if 'event_list' not in st.session_state:
    st.session_state.event_list = []

if len(st.session_state.event_list) == 0:
    for _, row in data.iterrows():
        st.session_state.event_list.append({
            'id': row['id'],  # IDをイベントに追加
            'title': f"ID: {row['id']} - {row['purpose']}",  # IDをタイトルに表示
            'start': f"{row['start_date']}T{row['start_time']}",
            'end': f"{row['end_date']}T{row['end_time']}"
        })

# カレンダーオプション
options = {
    'initialView': 'timeGridWeek',
    'eventClick': """
    function(info) {
        alert('Event ID: ' + info.event.extendedProps.id + '\\nTitle: ' + info.event.title);
    }
    """  # イベントクリック時にIDを表示
}

st_calendar.calendar(events=st.session_state.event_list, options=options)

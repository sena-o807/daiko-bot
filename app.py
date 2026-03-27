import json
import re
import os
from datetime import datetime, timedelta
from flask import Flask, request, abort

from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ===== 設定 =====
CHANNEL_ACCESS_TOKEN = "rPe7xqjYineh3NLysFFCUQOttnIcd5x86n4FvIiM/Q32OuYQl6Ou9T139SIZPsy69aIDlOff4v1T9Q/i2xx28vkQhDqr5nn/HldIkktf4MAzXFc2m+FT4hSv1nncE4DRZ9kNgYAndlzVR/5gxTH5+AdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "ab3d2f37e7e7ec96bccefa4eecff76ca"
GROUP_ID = "Cda29bba1aa8811b34ac7b333e4ddc06b"

DATA_FILE = "data.json"

app = Flask(__name__)
handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# ===== データ操作 =====
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ===== 日付抽出 =====
def extract_date(text):
    patterns = [
        r'(\d{1,2})[/-](\d{1,2})',
        r'(\d{1,2})月(\d{1,2})日'
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            month, day = map(int, m.groups())
            year = datetime.now().year
            try:
                return datetime(year, month, day)
            except:
                return None
    return None

# ===== 3ヶ月以内判定 =====
def is_valid_date(date):
    today = datetime.now()
    limit = today + timedelta(days=90)
    return today <= date <= limit

# ===== 削除判定 =====
DELETE_KEYWORDS = ["見つかりました", "決まりました", "埋まりました", "〆", "締め"]

def is_delete_message(text):
    return any(k in text for k in DELETE_KEYWORDS)

# ===== Webhook =====
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# ===== メイン処理 =====
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text
    user_id = event.source.user_id
    message_id = event.message.id
    user_name = get_user_name(user_id)

    data = load_data()
    date = extract_date(text)

    # ===== 一覧コマンド =====
    if text == "代行一覧":
        reply(event, generate_list())
        return

    # ===== 削除処理 =====
    if date and is_delete_message(text):
        new_data = []
        deleted = False

        for item in data:
            item_date = datetime.fromisoformat(item["date"])
            if item_date.date() == date.date() and item["userId"] == user_id:
                deleted = True
                continue
            new_data.append(item)

        save_data(new_data)

        if deleted:
            reply(event, "代行を削除しました")
        return

    # ===== 登録処理（ここ変更）=====
    if date and is_valid_date(date) and "代行" in text:
        data.append({
            "date": date.isoformat(),
            "userId": user_id,
            "userName": user_name,
            "messageId": message_id,
            "createdAt": datetime.now().isoformat()
        })

        save_data(data)

        reply(event, f"{date.month}/{date.day} の代行を登録しました")
        return

# ===== ユーザー名取得 =====
def get_user_name(user_id):
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            profile = line_bot_api.get_profile(user_id)
            return profile.display_name
    except:
        return "不明"

# ===== 返信 =====
def reply(event, text):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text)]
            )
        )

# ===== 一覧生成 =====
def generate_list():
    data = load_data()

    today = datetime.now()
    data = [d for d in data if datetime.fromisoformat(d["date"]) >= today]

    data.sort(key=lambda x: (x["date"], x["createdAt"]))

    save_data(data)

    if not data:
        return "📋現在の代行一覧\nなし"

    text = f"📋現在の代行一覧（{len(data)}件）\n\n"

    for d in data:
        dt = datetime.fromisoformat(d["date"])
        text += f"・{dt.month}/{dt.day}（{d['userName']}）\n"

    return text

# ===== cron =====
@app.route("/cron", methods=['GET'])
def cron():
    message = generate_list()

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.push_message(
            {
                "to": GROUP_ID,
                "messages": [TextMessage(text=message)]
            }
        )

    return "OK"

# ===== 起動 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
import os
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ===== 設定 =====
CHANNEL_ACCESS_TOKEN = "rPe7xqjYineh3NLysFFCUQOttnIcd5x86n4FvIiM/Q32OuYQl6Ou9T139SIZPsy69aIDlOff4v1T9Q/i2xx28vkQhDqr5nn/HldIkktf4MAzXFc2m+FT4hSv1nncE4DRZ9kNgYAndlzVR/5gxTH5+AdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "ab3d2f37e7e7ec96bccefa4eecff76ca"
GROUP_ID = "Cda29bba1aa8811b34ac7b333e4ddc06b"

DATA_FILE = "data.json"
LAST_SENT_FILE = "last_sent.txt"

JST = timezone(timedelta(hours=9))

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

# ===== テキスト正規化 =====
def normalize_text(text):
    text = unicodedata.normalize("NFKC", text)

    # 記号統一
    text = text.replace("〜", "~").replace("～", "~")
    text = text.replace("，", ",").replace("．", ".")
    text = text.replace("・", ",")

    return text

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
            year = datetime.now(JST).year
            try:
                return datetime(year, month, day, tzinfo=JST)
            except:
                return None
    return None

# ===== コマ抽出 =====
def extract_period(text):
    date_match = re.search(r'(\d{1,2}[/-]\d{1,2}|\d{1,2}月\d{1,2}日)', text)
    if not date_match:
        return None

    after_text = text[date_match.end():]

    m = re.search(r'(\d+[^\s]*コマ目)', after_text)
    if m:
        return m.group(1)

    return None

# ===== 曜日生成 =====
def get_weekday(date):
    weekday = ["月","火","水","木","金","土","日"]
    return weekday[date.weekday()]

# ===== 日付チェック =====
def is_valid_date(date):
    today = datetime.now(JST).date()
    limit = today + timedelta(days=90)
    return today <= date.date() <= limit

# ===== 削除判定 =====
DELETE_KEYWORDS = ["見つかりました", "みつかりました", "〆"]

def is_delete_message(text):
    return any(k in text for k in DELETE_KEYWORDS)

# ===== 送信制御 =====
def already_sent_today():
    today = datetime.now(JST).date()
    try:
        with open(LAST_SENT_FILE, "r") as f:
            return f.read() == str(today)
    except:
        return False

def mark_sent_today():
    with open(LAST_SENT_FILE, "w") as f:
        f.write(str(datetime.now(JST).date()))

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
    raw_text = event.message.text
    text = normalize_text(raw_text)

    user_id = event.source.user_id
    message_id = event.message.id

    data = load_data()

    date = extract_date(text)
    period = extract_period(text)

    user_name = get_user_name(user_id)

    # ===== 一覧 =====
    if text == "代行一覧":
        reply(event, generate_list())
        return

    # ===== 削除 =====
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

    # ===== 登録 =====
    if date and is_valid_date(date) and "代行" in text and period:
        data.append({
            "date": date.isoformat(),
            "period": period,
            "userId": user_id,
            "userName": user_name,
            "messageId": message_id,
            "createdAt": datetime.now(JST).isoformat()
        })

        save_data(data)

        reply(event, f"{date.month}/{date.day} を登録しました")
        return

# ===== ユーザー名 =====
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

    today = datetime.now(JST).date()
    data = [d for d in data if datetime.fromisoformat(d["date"]).date() >= today]

    data.sort(key=lambda x: (x["date"], x["createdAt"]))
    save_data(data)

    if not data:
        return "📋現在の代行一覧\nなし"

    text = f"📋現在の代行一覧（{len(data)}件）\n\n"

    for d in data:
        dt = datetime.fromisoformat(d["date"])
        w = get_weekday(dt)

        text += f"・{dt.month}/{dt.day}（{w}） {d['period']}（{d['userName']}）\n"

    return text

# ===== cron =====
@app.route("/cron", methods=['GET'])
def cron():
    now = datetime.now(JST)

    if now.hour != 20:
        return "NOT TIME"

    if already_sent_today():
        return "ALREADY SENT"

    data = load_data()

    today = now.date()
    data = [d for d in data if datetime.fromisoformat(d["date"]).date() >= today]

    if not data:
        return "NO DATA"

    data.sort(key=lambda x: (x["date"], x["createdAt"]))
    save_data(data)

    message = f"📋現在の代行一覧（{len(data)}件）\n\n"

    for d in data:
        dt = datetime.fromisoformat(d["date"])
        w = get_weekday(dt)

        message += f"・{dt.month}/{dt.day}（{w}） {d['period']}（{d['userName']}）\n"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.push_message(
            {
                "to": GROUP_ID,
                "messages": [TextMessage(text=message)]
            }
        )

    mark_sent_today()
    return "OK"

# ===== 起動 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
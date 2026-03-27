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
from linebot.v3.webhooks import Event

# ===== 設定 =====
CHANNEL_ACCESS_TOKEN = "rPe7xqjYineh3NLysFFCUQOttnIcd5x86n4FvIiM/Q32OuYQl6Ou9T139SIZPsy69aIDlOff4v1T9Q/i2xx28vkQhDqr5nn/HldIkktf4MAzXFc2m+FT4hSv1nncE4DRZ9kNgYAndlzVR/5gxTH5+AdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "ab3d2f37e7e7ec96bccefa4eecff76ca"
GROUP_ID = "YOUR_GROUP_ID"

DATA_FILE = "data.json"

app = Flask(__name__)
handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# ===== Webhook =====
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    print("===== CALLBACK RECEIVED =====", flush=True)
    print(body, flush=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("INVALID SIGNATURE", flush=True)
        abort(400)

    return 'OK'

# ===== 全イベントキャッチ =====
@handler.add(Event)
def handle_all(event):
    print("===== EVENT =====", flush=True)
    print(event, flush=True)

# ===== 起動 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
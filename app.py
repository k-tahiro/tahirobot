import os
import re
import sys

from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
import requests

app = Flask(__name__)

# 環境変数からchannel_secret・channel_access_tokenを取得
channel_secret = os.environ['LINE_CHANNEL_SECRET']
channel_access_token = os.environ['LINE_CHANNEL_ACCESS_TOKEN']

if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# TODO: deploy時に確認
controller_host = os.environ['CONTROLLER_HOST']
list_url = 'http://{}/codes/'.format(controller_host)
transmit_url = 'http://{}/codes/transmit/{}'.format(controller_host, '{}')


@app.route("/")
def hello_world():
    return "hello world!"


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    r_text = None

    if '停止' in text:
        code_key = 'stop'
    elif '冷房' in text or '暖房' in text:
        mode = 'c' if '冷房' in text else 'w'
        temps = re.findall(r'[0-9]+(?:\.[0-9]+)?', text)
        if temps:
            code_key = '{}{}'.format(mode, temps[0])
        else:
            r_text = '温度を設定してね(・∀・)'
    else:
        r_text = '冷房なのか暖房なのかはっきりしてね(・∀・)'

    r = requests.get(list_url)
    codes = [
        code['code_key']
        for code in r.json()
    ]
    if code_key in codes:
        r = requests.post(transmit_url.format(code_key))
        rj = r.json()
        if rj['success']:
            r_text = 'エアコン操作したよ(・∀・)'
            is_checked = rj['label'] != -1
            is_right = (code_key == 'stop' and rj['label'] == 0) \
                or (code_key != 'stop' and rj['label'] == 1)
            if is_right:
                r_text += '\n' '操作成功したわ(・∀・)'
            elif not is_checked:
                r_text += '\n' '結果確認できなかったわ(・∀・)'
            else:
                r_text += '\n' 'うまく操作できなかったわ(・∀・)'
        else:
            r_text = 'なんか失敗したわ(・∀・)'
    else:
        r_text = r_text or 'データベースに設定がなかったわ(・∀・)'

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=r_text))


if __name__ == "__main__":
    app.run()

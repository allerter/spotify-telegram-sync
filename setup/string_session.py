from telethon.sessions import StringSession
from telethon import TelegramClient


API_ID = int(input("Enter Telegram API ID here: "))
API_HASH = input("Enter Telegram API hash here: ")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("Check your saved messages on Telegram and copy the STRING_SESSION value.")
    session_string = client.session.save()
    saved_messages_template = f"""
<code>STRING_SESSION</code>: <code>{session_string}</code>
⚠️ <i>Please be carefull when passing this value to third parties</i>"""
    client.send_message("me", saved_messages_template, parse_mode="html")

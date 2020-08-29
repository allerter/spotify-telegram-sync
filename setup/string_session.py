from telethon.sessions import StringSession
from telethon import TelegramClient

print(
    """Please go to my.telegram.org.
Login using your Telegram account.
Click on API Development Tools.
Create a new application by entering the required details.
"""
)
API_ID = int(input("Enter API ID here: "))
API_HASH = input("Enter Api hash here: ")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("Check your saved messages on Telegram and copy the STRING_SESSION value.")
    session_string = client.session.save()
    saved_messages_template = f"""
<code>STRING_SESSION</code>: <code>{session_string}</code>
⚠️ <i>Please be carefull when passing this value to third parties</i>"""
    client.send_message("me", saved_messages_template, parse_mode="html")

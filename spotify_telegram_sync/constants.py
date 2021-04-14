"""Some constants e.g. the spotify token"""
import os

SPOTIFY_CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
SPOTIFY_REFRESH_TOKEN = os.environ["SPOTIFY_REFRESH_TOKEN"]
SPOTIFY_PLAYLIST_ID = os.environ["SPOTIFY_PLAYLIST_ID"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL"]
DATABASE_URL = os.environ["DATABASE_URL"]
TELETHON_API_ID = os.environ["TELETHON_API_ID"]
TELETHON_API_HASH = os.environ["TELETHON_API_HASH"]
TELETHON_SESSION_STRING = os.environ["TELETHON_SESSION_STRING"]
DEEZER_ARL_TOKEN = os.environ["DEEZER_ARL_TOKEN"]
USING_HEROKU = (
    True if os.environ.get("USING_HEROKU", "false").lower() == "true" else False
)
if USING_HEROKU:
    DATABASE_URL = DATABASE_URL.replace("postgres", "postgresql+asyncpg")
UPDATE_BIOS = (
    True if os.environ.get("UPDATE_BIOS", "false").lower() == "true" else False
)
UPDATE_PLAYLIST = (
    True if os.environ.get("UPDATE_PLAYLIST", "false").lower() == "true" else False
)
CHECK_TELEGRAM = (
    True if os.environ.get("CHECK_TELEGRAM", "false").lower() == "true" else False
)
SERVER_PORT = int(os.environ.get("SERVER_PORT", 5000))

# This used to be the photo of the pinned message if the channel has no pic.
DEFAULT_PIC = os.path.join(os.getcwd(), "..", "logo.png")

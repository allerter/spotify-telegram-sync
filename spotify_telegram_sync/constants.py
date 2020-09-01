"""Some constants e.g. the spotify token"""
import os
import tekore as tk
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REFRESH_TOKEN = os.environ.get('SPOTIFY_REFRESH_TOKEN')
SPOTIFY_PLAYLIST_ID = os.environ.get('SPOTIFY_PLAYLIST_ID')
TELEGRAM_CHANNEL = os.environ.get('TELEGRAM_CHANNEL')
DATABASE_URL = os.environ.get('DATABASE_URL')
SERVER_PORT = int(os.environ.get('PORT', 5000))
SERVER_ADDRESS = 'https://' + os.environ.get('APP_NAME') + '.herokuapp.com'
TELETHON_API_ID = os.environ.get('TELETHON_API_ID')
TELETHON_API_HASH = os.environ.get('TELETHON_API_HASH')
TELETHON_SESSION_WEB = os.environ.get('TELETHON_SESSION_WEB')
TELETHON_SESSION_WORKER = os.environ.get('TELETHON_SESSION_WORKER')
DEEZER_ARL_TOKEN = os.environ.get('DEEZER_ARL_TOKEN')
UPDATE_BIOS = True if os.environ.get('UPDAE_BIOS', 'true').lower() == 'true' else False
CHECK_CHANNEL_DELETED = (True if os.environ.get('CHECK_CHANNEL_DELETED', 'true').lower()
                        == 'true' else False)
CHECK_LOCAL_PLAYBACK = (True if os.environ.get('CHECK_LOCAL_PLAYBACK', 'true').lower()
                        == 'true' else False)
USING_WEB_SERVER = (True if os.environ.get('USING_WEB_SERVER', 'true').lower()
                    == 'true' else False)
if USING_WEB_SERVER is False:
    CHECK_LOCAL_PLAYBACK = False

# This used to be the photo of the pinned message if the channel has no pic.
DEFAULT_PIC = 'https://raw.githubusercontent.com/Allerter/spotify-telegram-sync/master/logo.png'

# spotify client
cred = tk.RefreshingCredentials(SPOTIFY_CLIENT_ID,
                                SPOTIFY_CLIENT_SECRET)
token = cred.refresh_user_token(SPOTIFY_REFRESH_TOKEN)
spotify = tk.Spotify(token, sender=tk.RetryingSender())

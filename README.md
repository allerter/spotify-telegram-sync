# spotify-telegram-sync
A bot that syncs your Spotify playlist with your Telegram channels and updates your bio and a pinned message on your channel based on your current playback.

This *README* file covers the following topics:
    - :ref:`Setup`
    - :ref:`How it Works`
    - :ref:`Environment Variables`


Setup
*****
To sync your Spotify playlist with your Telegram channel you will need:
- Spotify: client ID, client secret, refresh token
- Telegram: channel username, API ID, API hash, two string sessions
- Deezer: ARL token
- Database: a table named *playlist* with two columns: *spotify_id*, *telegram_id*


Spotify
=======
Go to the `developer's dashboard <https://developer.spotify.com/dashboard/applications>`_ and create an app by clicking
on *CREATE AN APP*. After creating the app, you'll be redirected to another page. In this page (the app's page),
you will see *Client ID* on the left hand side and *SHOW CLIENT SECRET*. Copy the value of those two and save them somewhere. Now all you need from Spotify is your refresh token.
Now copy the link below and replace *CLIENT_ID* with the one you saved before.
https://accounts.spotify.com/authorize?client_id=CLIENT_ID&response_type=code&redirect_uri=https%3A%2F%2Fexample.com%2Fcallback&scope=user-read-playback-state%20user-read-currently-playing%20playlist-read-collaborative%20playlist-modify-public%20playlist-read-private%20playlist-modify-private

Click on the link now and click *Agree*. After that you'll be redirected to another page. Copy the whole link of that page (it's something like https://example.com/callback?code=...). 


Before continuing to setup, install the packages in the ``requirements.txt`` file. To do this run:
```bash
pip install -r requirements.txt
```

.. Note::
    If you'd like to enable :ref:`Local Playback`, also install the packages of ``requirements.txt`` in the ``local playback`` folder. 

Now run ``spotify_refresh_token.py`` in the ``setup`` folder get your refresh token. You can run it from the command line:
```bash
python spotify_refresh_token.py
```


Telegram
========
Go to `my.telegram.org <https://my.telegram.org/>`_. After logging in, go to *API development tools*, and create an app.
After creating the app, copy *App api_id* and *App api_hash*.
Next up is getting those two Telegram sessions.

Now run ``string_session.py`` in the ``setup`` folder twice to get two string sessions (one for the web process, and one for the worker process). You can run the script from the command line:
```bash
python string_session.py
```


Deezer
======
To get your ARL token, watch `this YouTube video <https://www.youtube.com/watch?v=pWcG9T3WyYQ>`_.


Database
========
This bot uses a *Postgres* database. But the code of ``database.py`` is relatively simple and you can modify it if you're using another DBMS.

You'll need a database with a table named *playlist* that has *spotify_id* and *telegram_id* columns. If you don't use the 
*Deploy to Heroku* below, you will need to create the table yourself by running/modifying ``setup_db.py`` in the ``setup`` folder.

Now you have all the requirements needed for the bot. Let's see how the bot works.


How it Works
************
Let's take it part by part:

Syncing Telegram Channel and Spotify playlist
=============================================
To do this, the bot checks your Spotify playlist every hour. Once it gets the tracks from your playlist, the bot compares them to the tracks in the *playlist* table (initially no tracks). Then it uploads any track that doesn't exist in the database. Finally it saves the *Spotify ID* and *Telegram link* of those tracks in the database. Alternatively, if there are tracks which exist in the database, but not in your Spotify playlist, the bot removes those tracks from Telegram using the *Telegram link* it had saved before.


Telegram Deleted Messages
=========================
The bot checks the channel's deleted messages every 5 minutes, and if it finds any songs, it will search for those songs in the database (using their *Telegram link*) and then removes them from your Spotify playlist, and from the database as well. To enable this feature, set the *CHECK_DELETED_MESSAGES* variable to *TRUE*


Telegram New Messages
=====================
Whenever you upload or forward a new song to your Telegram channel, the bot uses the song's meta data or its filename to find it on Spotify. If the search is successful, then the bot adds that song to your playlist on Spotify and the database.


Updating the Bio
================
The bot can also update your account bio and a pinned message in your Telegram channel to reflect your current playback on Spotify. To do this, the bot checks your Spotify playback every 6 seconds to see if a track is playing or not. If there were one, it updates your bio every 30 seconds and the pinned message every 6 seconds to that song. For example this is how your bio and the pinned message would look like:
- bio: "listening to We Will Rock You by Queen"
- pinned message: "*This User* (replaced with your first name) is listening to We Will Rock You by Queen."
The bot automatically accounts for when the bio message exceeds the 70-character limit.
Now what happens when there's no song playing? In this case, the bot updates the two like this:
- bio: the bot sets the bio to a default value saved in your Saved Messages (more on this below).
- pinned message: "*This User* (replaced with your first name) isn't listening to anything right now." The bot also update the picture of the pinned message to your channel's profile picture.

To revert your bio back to its default value when there is no song playing, the bot looks for a message in your Saved Message. To set this up, go to your saved message and post a message like this:
"default bio: This is my default bio." If you don't set this message or change the bio manually, the bot will just reset your bio to empty. Also, if you don't pin a message in your channel, the bot won't have anything to update and will check again the next time when you're playing something on Spotify.

To enable this feature, set *UPDATE_BIOS* to *TRUE*.

Local Playback
--------------
What if you're listening to music locally on your Windows PC, but want to have the bio updated nonetheless? In this case you can run the ``get_playing_song.py`` locally. This script checks to see which processes are playing audio and then checks the audio files in use by those processes. If it finds any audio files, it will send a request to your web server, informing the bot. Then the bot updates the bios accordingly.

To set this feature up, you'll need to run the web server in ``server.py`` (automatically run in Heroku), set the *USING_WEB_SERVER* and *CHECK_LOCAL_PLAYBACK* variables to *True*. On your PC, run ``handle.exe`` once and click *Agree*. Then replace the *SERVER_ADDRESS* variable in ``get_playing_song.py`` with the address of your server, and run it. The script will check every 2 seconds, and will send a request to the server if it determines that you're playing a song, and logs failures in ``failures.log`` in the same directory of the script.


Environment Variables
*********************
You need to set the following variables in your environment to make the bot work:

- DATABASE_URL (automatically set in Heroku)
    The URL of your database
- SERVER_PORT (automatically set in Heroku)
    The port of your web server if you're using one
- SPOTIFY_CLIENT_ID 
    Your Spotify app's client ID
- SPOTIFY_CLIENT_SECRET
    Your Spotify app's client secret
- SPOTIFY_REFRESHT_TOKEN
    Your Spotify refresh token
- SPOTIFY_PLAYLIST_ID
    The ID of your playlist on Spotify
- TELETHON_API_ID
    The API ID of your Telegram app
- TELETHON_API_HASH
    The API Hash of your Telegram app
- TELETHON_SESSION_WORKER
    The first session string of your Telegram account
- TELETHON_SESSION_WEB
    The second session string of your Telegram account
- TELEGRAM_CHANNEL
    The username of your Telegram channel
- DEEZER_ARL_TOKEN
    Your Deezer ARL token
- USING_WEB_SERVER
    Whether you will be using a web server. *TRUE* for Heroku.
- APP_NAME
    The name of your app on Heroku. If you don't want to deploy the bot on Heroku, manually change the ``SERVER_ADDRESS`` variable in ``constants.py`` to the address of your server.
- UPDATE_BIOS
      Would you like to have your account bio and a pinned message on your channel to be updated to your current playback on Spotify?"
- CHECK_CHANNEL_DELETED
      Would you like the bot to check when you delete songs on your Telegram account, and remove them from your Spotify playlist as well?
- CHECK_LOCAL_PLAYBACK":
      Would you like the bot to check for local playback updates?
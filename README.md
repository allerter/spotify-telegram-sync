Spotify Telegram Sync
=====================

A userbot that syncs your Spotify playlist with your Telegram channel and
updates your bio and a pinned message on your channel based on your
current playback.

[![image](https://www.herokucdn.com/deploy/button.svg)](https://www.heroku.com/deploy?template=https://github.com/Allerter/spotify-telegram-sync/tree/master)

Table of Contents
-----------------

> -   [Setup](#setup)
> -   [How it Works](#how-it-works)
> -   [Starting the bot](#starting-the-bot)
> -   [Deploying to Heroku](#deploying-to-heroku)


Setup
-----

The term *bot* and *userbot* will be used interchangeably in this README
to refer to the script.
To sync your Spotify playlist with your Telegram channel you will need:

-   **Spotify**: client ID, client secret, refresh token
-   **Telegram**: channel username, API ID, API hash and a string session
-   **Deezer**: ARL token
-   **Database**: a table named *playlist* with two columns:
    *spotify\_id*, *telegram\_id*
-   **Environment Variables**: Some env vars that you will need to set
    after setting things up.

### Spotify

Go to the [developer's
dashboard](https://developer.spotify.com/dashboard/applications) and
create an app by clicking on *CREATE AN APP*. After creating the app,
you'll be redirected to another page. In this page (the app's page), you
will see *Client ID* on the left hand side and *SHOW CLIENT SECRET*.
Copy the value of those two and save them somewhere. Now all you need
from Spotify is your refresh token. 

Before continuing, install the packages in the
`requirements.txt` file. To do this run:

    pip install -r requirements.txt

Now run `spotify_refresh_token.py` in the `setup` folder get your
refresh token. The script will ask for your Spotify app ID, app secret, and
then the link of the webpage after you click *Agree* (the link will be
someting like `https://example.com/callback?code=...`) You can run the script
from the command line:

    python spotify_refresh_token.py

### Telegram

Go to [my.telegram.org](https://my.telegram.org/). After logging in, go
to *API development tools*, and create an app. After creating the app,
copy *App api\_id* and *App api\_hash*. Next up is getting a Telegram
account session in string format.

Now run `string_session.py` in the `setup` folder to get the
string session. You can run the script from the command line:

    python string_session.py

### Deezer

To get your ARL token, watch [this YouTube
video](https://www.youtube.com/watch?v=pWcG9T3WyYQ).

### Database

You'll need a database with a table named *playlist* that has
*spotify\_id* and *telegram\_id* columns. The userbot uses SQLAlchemy
to connect to the database and will automatically create the table for
you. All you need to do is provide it with the correct database URL through
the `DATABASE_URL` environment variable. Also make sure to have the database
driver installed. For example if you'll be using Postgres, you should have
`asyncpg` installed. Then your database URL would look something like this:
`postgresql+asyncpg://username:password@host/database_name`


### Environment Variables
-   **DATABASE\_URL** (automatically set in Heroku)  
    The URL of your database used by SQLAlchemy

-   **SPOTIFY\_CLIENT\_ID**
    Your Spotify app's client ID

-   **SPOTIFY\_CLIENT\_SECRET**
    Your Spotify app's client secret

-   **SPOTIFY\_REFRESHT\_TOKEN**
    Your Spotify refresh token

-   **SPOTIFY\_PLAYLIST\_ID**  
    The ID of your playlist on Spotify

-   **TELETHON\_API\_ID**  
    The API ID of your Telegram app

-   **TELETHON\_API\_HASH**  
    The API Hash of your Telegram app

-   **TELEGRAM\_SESSION**  
    The string session you generated using `string_session.py`

-   **TELEGRAM\_CHANNEL**  
    The username of your Telegram channel

-   **DEEZER\_ARL\_TOKEN** 
    Your Deezer ARL token

-   **UPDATE\_BIOS**
    Accepts `false` or `true`. Defaults to `false`.  
    Would you like to have your account bio and a pinned message on your
    channel to be updated to your current playback on Spotify?

-   **UPDATE\_PLAYLIST**
    Accepts `false` or `true`. Defaults to `false`.  
    Should changes to the Spotify playlist be reflected on your Telegram channel?

-   **CHECK\_TELEGRAM**
    Accepts `false` or `true`. Defaults to `false`.  
    Should changes to the Telegram channel be reflected on your Spotify playlist?
    For example if a song is posted on your Telegram channel or removed from it.

Now you have all the requirements needed for the userbot. Let's see how the
it works. You can skip this part and go straight to starting the bot.


How it Works
------------

Let's take it part by part:

### Syncing Telegram Channel and Spotify playlist

To do this, the bot checks your Spotify playlist every hour. Once it
gets the tracks from your playlist, the bot compares them to the tracks
in the *playlist* table (initially no tracks). Then it uploads any track
that doesn't exist in the database. Finally it saves the *Spotify ID*
and *Telegram link* of those tracks in the database. Alternatively, if
there are tracks which exist in the database, but not in your Spotify
playlist, the bot removes those tracks from Telegram using the *Telegram
link* it had saved before.

### Telegram Deleted Messages

The bot checks the admin logs and if it finds any deleted tracks,
it will search for those songs in the database (using
their *Telegram link*) and then removes them from your Spotify playlist,
and from the database as well.

Requires `$CHECK_TELEGRAM=true`

### Telegram New Messages

Whenever you upload or forward a new song to your Telegram channel, the
bot uses the song's meta data or its filename to find it on Spotify. If
the search is successful, then the bot adds that song to your playlist
on Spotify and the database if it isn't there already.

Requires `$CHECK_TELEGRAM=true`

### Updating the Bio

The bot can also update your account bio and a pinned message in your
Telegram channel to reflect your current playback on Spotify. To do
this, the bot checks your Spotify playback every 5 seconds to see if a
track is playing or not. If there is one, it updates your bio every 30
seconds and the pinned message every 5 seconds to reflect that song. For
example this is how your bio and the pinned message would look like:

**Song playing**:

-   **bio**: "listening to We Will Rock You by Queen"
-   **pinned** message: "*This User* (replaced with your first name) is
    listening to [We Will Rock
    You](https://open.spotify.com/track/4pbJqGIASGPr0ZpGpnWkDn) by
    Queen."

The bot automatically accounts for when the bio message exceeds the
70-character limit. Now what happens when there's no song playing? In
that case, the bot updates the two like this:

**No Song playing**:

-   **bio**: the bot sets the bio to a default value saved in your Saved
    Messages (more on this below).
-   **pinned message**: "*This User* (replaced with your first name)
    isn't listening to anything right now." The bot also update the
    picture of the pinned message to your channel's profile picture.

To revert your bio back to its default value when there is no song
playing, the bot looks for a message in your Saved Messages. To set this
up, go to your saved message and post a message like this: 
```
default bio:
This is my default bio.
```
If you don't set this message or change the bio
manually, the bot will just reset your bio to empty. Also, if you don't
pin a message in your channel, the bot won't have anything to update and
will check again the next time when you're playing something on Spotify.

Requires `$UPDATE_PLAYBACK=true`

#### ~~Local Playback~~ (This Feature Has Been Removed)

What if you're listening to music locally on your Windows PC on another media player,
but want to have the bio updated nonetheless? In this case you can run the
`get_playing_song.py` locally. This script checks to see which processes
are playing audio and then checks the audio files in use by those
processes. If it finds any audio files, it will send a request to your
web server, informing the bot. Then the bot updates the bios
accordingly.

To set this feature up, you'll need to run the web server in `server.py`
(automatically run in Heroku), set the *USING\_WEB\_SERVER* and
*CHECK\_LOCAL\_PLAYBACK* variables to *True*. On your PC, run
`handle.exe` once and click *Agree*. Then replace the *SERVER\_ADDRESS*
variable in `get_playing_song.py` with the address of your server, and
run it. The script will check every 2 seconds, and will send a request
to the server if it determines that you're playing a song, and logs
failures in `failures.log` in the same directory of the script.


Deploying to Heroku
-------------------
Using the *Deploy to Heroku* button above is the easiest way to set the bot up. After clicking on the link
you will enter the value of the variables mentioned below, and if all the values are correct the bot will
set itself up. After the deployment succeeds, all you need to to is go to the *Resource* and turn the 
*worker* process on by clicking on its button on the right. After that the bot will be all set up. If you
need to change any of the environment variables, you can do so using the *Config Vars* section in the
*Settings* tab.

Starting the Bot
----------------

You can start the script in two ways:
- `python bot.py`: Usual way to start the bot.
- `python server.py`: Starts a web server that updates the playlist if
  it receives GET requests at `/check_playlist`. This way is useful if
  you'd like to use Cron jobs to check the playlist. Set `$SERVER_PORT`
  to set the port, otherwise port 5000 is used. The web server will be
  available at `http://localhost:5000/` by default.

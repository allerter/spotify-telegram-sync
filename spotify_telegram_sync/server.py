from constants import (SERVER_PORT, TELEGRAM_CHANNEL,
                       SPOTIFY_PLAYLIST_ID, TELETHON_API_ID,
                       TELETHON_API_HASH, TELETHON_SESSION_WEB,
                       USING_WEB_SERVER, spotify)
from get_song_file import download_track
from database import database

from waitress import serve
from telethon import TelegramClient
from telethon.sessions import StringSession
from flask import Flask, request

from threading import Thread
from time import time
import logging

# web server
app = Flask(__name__)

playback = {'artist': '', 'title': '', 'time': time()}

# telegram client
client = TelegramClient(StringSession(TELETHON_SESSION_WEB),
                        TELETHON_API_ID, TELETHON_API_HASH)

# disable hachoir warnings
logging.getLogger("hachoir").setLevel(logging.CRITICAL)


def check_playlist():
    # get id, url and isrc of non-local songs
    spotify_songs = []
    tracks = spotify.playlist_items(SPOTIFY_PLAYLIST_ID)
    for item in tracks.items:
        track = item.track
        if not track.is_local and track.external_ids.get('isrc'):
            spotify_songs.append((track.id,
                                  track.external_urls['spotify'],
                                  track.external_ids['isrc']))

    # get songs from db
    playlist = database('select')
    difference = len(spotify_songs) - len(playlist)
    client.start()
    # songs were added to the playlist
    if difference > 0:
        upload_to_db_songs = []
        playlist = [x[0] for x in playlist]
        # specify new songs
        to_be_added = list(set([x[0] for x in spotify_songs]) - set(playlist))
        to_be_added = [x for x in spotify_songs if x[0] in to_be_added]

        # download each song and send it to the Telegram channel
        for song in to_be_added:
            file = download_track(isrc=song[2], output='file')[0]
            msg = client.loop.run_until_complete(
                client.send_file(TELEGRAM_CHANNEL, file))
            upload_to_db_songs.append((song[0], str(msg.id)))

        # add new songs to database
        database('insert', upload_to_db_songs)
    # songs were removed from the playlist
    elif difference < 0:
        # specify deleted songs
        spotify_ids = list(set([x[0] for x in playlist])
                           - set([x[0] for x in spotify_songs]))

        # get telegram ids of deleted songs and delete them
        # telegram_ids = [x[1] for x in database('select', {'spotify_id': spotify_ids})]
        telegram_ids = [x[1] for x in playlist if x[0] in spotify_ids]
        client.loop.run_until_complete(
            client.delete_messages(TELEGRAM_CHANNEL, telegram_ids))

        # remove deleted songs from database
        database('delete', {'spotify_id': spotify_ids})
    client.disconnect()


@app.route('/check_playlist', methods=['GET'])
def check_playlist_route():
    thread = Thread(target=check_playlist)
    thread.start()
    return "I'll check"


@app.route('/', methods=['GET'])
def home_route():
    return 'OK'


@app.route('/local_playback', methods=['GET', 'POST'])
def local_playback_route():
    if request.method == 'POST':
        artist = request.form.get('artist')
        title = request.form.get('title')
        now_time = time()
        playback.update({'artist': artist,
                         'title': title,
                         'time': now_time})
        return 'Set'
    elif request.method == 'GET':
        return playback


def main():
    serve(app, host="0.0.0.0", port=SERVER_PORT)


if __name__ == '__main__' or USING_WEB_SERVER:
    main()

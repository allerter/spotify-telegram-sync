import constants
from database import database
from get_song_file import download_track

import tekore as tk
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon import errors, events, types, TelegramClient
from telethon.sessions import StringSession
import requests
import asyncio

from string import punctuation
from collections import namedtuple
import logging
import time
import re
# initiate  telegram client
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = TelegramClient(StringSession(constants.TELETHON_SESSION_WORKER),
                        constants.TELETHON_API_ID, constants.TELETHON_API_HASH)
client.start()

spotify = constants.spotify

telegram_channel = client.loop.run_until_complete(
    client.get_input_entity(constants.TELEGRAM_CHANNEL)
)
time.sleep(1)
telegram_me = client.loop.run_until_complete(
    client.get_input_entity('me')
)


def clean_str(s):
    return s.translate(str.maketrans('', '', punctuation)).replace(' ', '').lower()


def send_track(file):
    msg = client.run_until_complete(client.send_file(constants.TELEGRAM_CHANNEL, file))
    return msg.id


def delete_tracks(telegram_ids):
    client.run_until_complete(client.delete_messages(constants.TELEGRAM_CHANNEL,
                                                     telegram_ids))


def search_spotify(artist, title):
    """serarches song on spotify and returns the matches"""
    matches = []
    query = f'{title} artist:{artist}'
    spotify_search = spotify.search(query, types=('track',))
    for res in spotify_search[0].items:
        res_artist = res.artists[0].name
        res_title = res.name
        if (clean_str(res_artist) == clean_str(artist)
                and clean_str(res_title) == clean_str(title)):
            matches.append(res)

    return matches


def search_deezer(artist, title):
    """serarches song on deezer and returns the first match's cover art"""
    match = None
    query = f'?q=artist:{artist} track:{title}'
    deezer_search = requests.get('https://api.deezer.com/search' + query)
    for res in deezer_search['data']:
        res_artist = res['artist']['name']
        res_title = res['title']
        if (clean_str(res_artist) == clean_str(artist)
                and clean_str(res_title) == clean_str(title)):
            match = res['album']['cover_xl']
            break

    return match


@client.on(events.NewMessage(chats=(telegram_channel)))
async def new_message_handler(event):
    """ checks for songs in new messages to telegram channel,
    and adds them to spotify playlist.
    """
    # check if event is a song
    if event.audio and not event.audio.attributes[0].voice:
        # extract song artist and title
        telegram_id = str(event.message.id)
        doc = event.audio.attributes
        if artist := doc[0].performer:
            artist = artist.split(',')[0]
        else:
            artist = ''
        title = doc[0].title
        file_name = doc[1].file_name

        # get artist and title from file name
        # weren't in the attributes
        if not all([artist, title]):
            artist, title = file_name.split('-')
            title = title[:title.rfind('.')]

        # find song on Spotify
        matches = [res.id for res in search_spotify(artist, title)]
        spotify_songs = []

        # get spotify playlist songs
        tracks = spotify.playlist_items(constants.SPOTIFY_PLAYLIST_ID, as_tracks=True)
        for item in tracks['items']:
            if not item['is_local']:
                song = item['track']
                spotify_songs.append(song['id'])
        spotify_songs = set(spotify_songs)

        # add song to playlist and database
        if matches and not set(matches).intersection(spotify_songs):
            spotify.playlist_add(constants.SPOTIFY_PLAYLIST_ID,
                                 [f'spotify:track:{matches[0]}'])
            database('insert', [(matches[0], telegram_id)])


def get_user_about(current_song):
    user_about = f'listening to {current_song.name} by {current_song.artist}'
    if len(user_about) > 70:
        user_about = f'🎧 {current_song.artist} - {current_song.name}'
        if len(user_about) > 70:
            user_about = re.sub(r'.feat.*[\)\[]', '', user_about)
            if len(user_about) > 70:
                user_about = user_about[:67] + '...'
    return user_about


async def update_bios():
    last_song = namedtuple('last_song', ['artist', 'name', 'id'])
    last_song.name = 'No Song Was Playing'
    last_song.artist = 'No Artist'
    last_song.id = None
    pinned_message = await client.get_messages(telegram_channel,
                                               ids=types.InputMessagePinned())
    one_hour_counter = time.time()
    counter = 30

    while True:
        # get user bio and spotify playback
        counter_start = time.time()
        if counter >= 30:
            user_full = await client(GetFullUserRequest(telegram_me))
            user_about = user_full.about
            user_id = user_full.user.id
            user_first_name = user_full.user.first_name

            if counter_start - one_hour_counter >= 3600:
                telegram_channel_pic = \
                    await client.download_profile_photo(telegram_channel, file=bytes)
                one_hour_counter = counter_start
        try:
            playback = spotify.playback_currently_playing(tracks_only=True)
        except tk.ServiceUnavailable:
            logger.log(logging.INFO, 'Spotify Unavilable')
            playback = None
        except tk.TooManyRequests as e:
            # TODO: use tk.RetryingSender with an async sender
            wait = e.response.headers['Retry-After']
            logger.log(logging.WARN, 'Spotify rate limit exceeded')
            await asyncio.sleep(wait + 1)
            counter += wait + 1
            continue

        if ((playback and playback.is_playing and playback.item)
                or constants.CHECK_LOCAL_PLAYBACK is False):
            local_playback = None
        else:
            url = f'{constants.SERVER_ADDRESS}/local_playback'
            local_playback = requests.get(url).json()
            if counter_start - local_playback['time'] > 10:
                local_playback = None

        # check if a track is playing
        if (playback and playback.is_playing and playback.item) or local_playback:

            if local_playback:
                item_artist = local_playback['artist']
                item_name = local_playback['title']
            else:
                item_artist = playback.item.artists[0].name
                item_name = playback.item.name

            current_song = namedtuple('current_song', ['artist', 'name', 'id'])
            current_song.artist = item_artist
            current_song.name = item_name
            current_song.id = playback.item.id if playback and playback.item else None

            # if current track is same as the last track, there's no need to update
            if (
                (playback and current_song.id != last_song.id)
                or
                (local_playback and current_song.name != last_song.name)
            ):

                item_name = item_name if item_name else 'Unknown Title'
                item_artist = item_artist if item_artist else 'Unknown Artist'

                if (local_playback
                    and item_artist != 'Unknown Artist'
                    and item_name != 'Unknown Title'
                    and (matches := search_spotify(item_artist, item_name))
                    and matches[0].external_ids.get('isrc')
                    ):
                    isrc = matches[0].external_ids['isrc']
                    cover_art = requests.get(
                        f'https://api.deezer.com/track/isrc:{isrc}')
                    cover_art = (cover_art.json()['album']['cover_xl']
                                 if cover_art.json().get('album')
                                 else requests.get(matches[0].images[0].url).content
                                 )
                    current_song_url = matches[0].external_urls['spotify']
                    current_song.id = matches[0].id

                elif (playback
                      and not playback.item.is_local):
                    if isrc := playback.item.external_ids.get('isrc'):
                        cover_art = requests.get(
                            f'https://api.deezer.com/track/isrc:{isrc}').json()
                        item_pic = playback.item.album.images[0].url
                        cover_art = (cover_art['album']['cover_xl']
                                     if cover_art.get('album')
                                     else requests.get(item_pic).content
                                     )
                    else:
                        item_pic = playback.item.album.images[0].url
                        cover_art = requests.get(item_pic).content
                    current_song_url = playback.item.external_urls['spotify']
                else:
                    cover_art = telegram_channel_pic
                    current_song_url = '""'

                # setting pinned_message text
                text = (f'[{current_song.name}]({current_song_url}) by '
                        f'{current_song.artist}'
                        )

                msg_text = (f'[{user_first_name}](tg://user?id={user_id})'
                            + ' is listening to '
                            + text
                            )

                # replacing user bio and keeping it shorter than the limit (70)
                if counter >= 30:
                    user_about = get_user_about(current_song)
                    try:
                        counter = 0
                        await client(UpdateProfileRequest(about=user_about))
                    except errors.MessageNotModifiedError:
                        pass
                    except errors.FloodWaitError as e:
                        counter -= e.seconds
                    counter_start = time.time()

                # update pinnes message
                try:
                    if pinned_message:
                        await client.edit_message(telegram_channel,
                                                  pinned_message.id,
                                                  text=msg_text, link_preview=False,
                                                  file=cover_art if cover_art else None)
                except errors.MessageNotModifiedError:
                    pass
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    logger.log(logging.WARN, 'Flood wait for updating pinned message')

                last_song = current_song

            elif counter >= 30 and current_song.name not in user_about:
                user_about = get_user_about(current_song)
                try:
                    counter = 0
                    await client(UpdateProfileRequest(about=user_about))
                except errors.MessageNotModifiedError:
                    pass
                except errors.FloodWaitError as e:
                    counter -= e.seconds
                counter_start = time.time()
        else:
            if counter >= 30:
                # look for the default bio in user's saved messages
                if saved_msg := await client.get_messages(telegram_me, search='default bio'):
                    default_user_about = saved_msg[0].text.replace('default bio: ', '')
                else:
                    default_user_about = ''
                # update user bio to defaul value if it already isn't
                if default_user_about != user_about:
                    await client(UpdateProfileRequest(about=default_user_about))
                    counter = 0
                    counter_start = time.time()

            if last_song.name != 'No Song Was Playing' and pinned_message:
                msg_text = pinned_message.text
                msg_text = (msg_text[:msg_text.find(')') + 1]
                            + " isn't listening to anything right now."
                            )
                try:
                    await client.edit_message(telegram_channel,
                                              pinned_message.id,
                                              text=msg_text, link_preview=False,
                                              file=telegram_channel_pic)
                except errors.MessageNotModifiedError:
                    pass
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    logger.log(logging.WARN, 'Flood wait for updating pinned message')

            last_song.name = 'No Song Was Playing'
            last_song.artist = 'No Artist'
            last_song.id = None

        await asyncio.sleep(6)
        counter_end = time.time()
        counter += counter_end - counter_start


async def check_deleted():
    old_id = 1
    while True:
        deleted = []
        async for event in client.iter_admin_log(telegram_channel,
                                                 min_id=old_id):
            # event should be: deleted, audio, and not a voice audio
            if event.deleted_message:
                try:
                    if not (event.old.media
                            and event.old.media.document
                            and event.old.media.document.mime_type == 'audio/mpeg'
                            and not event.old.media.document.attributes[0].voice):
                        continue
                except AttributeError:
                    continue

                # add message id to be checked against DB records
                deleted.append((str(event.old.id)))
        else:
            old_id = event.old.id

        # delete songs from spotify
        if deleted:
            songs = database('select', {'telegram_id': deleted})
            if songs:
                spotify_ids = [x[0] for x in songs]
                spotify.playlist_remove(constants.SPOTIFY_PLAYLIST_ID, spotify_ids)
                database('delete', {'spotify_id': spotify_ids})

        await asyncio.sleep(300)


async def check_playlist():
    while True:
        # get id, url and isrc of non-local songs
        spotify_songs = []
        tracks = spotify.playlist_items(constants.SPOTIFY_PLAYLIST_ID)
        for item in tracks.items:
            track = item.track
            if not track.is_local and track.external_ids.get('isrc'):
                spotify_songs.append((track.id,
                                      track.external_urls['spotify'],
                                      track.external_ids['isrc']))

        # get songs from db
        playlist = database('select')
        difference = len(spotify_songs) - len(playlist)
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
                msg = await client.send_file(telegram_channel, file)
                upload_to_db_songs.append((song[0], str(msg.id)))

            # add new songs to database
            database('insert', upload_to_db_songs)
        # songs were removed from the playlist
        elif difference < 0:
            # specify deleted songs
            spotify_ids = list(set([x[0] for x in playlist])
                               - set([x[0] for x in spotify_songs]))

            # get telegram ids of deleted songs and delete them
            telegram_ids = [x[1] for x in playlist if x[0] in spotify_ids]
            await client.delete_messages(telegram_channel, telegram_ids)

            # remove deleted songs from database
            database('delete', {'spotify_id': spotify_ids})
        await asyncio.sleep(300)


async def keep_alive():
    """Keep Heroku app from going to sleep
    by sending HTTP requests to web server

    """
    while True:
        requests.get(constants.SERVER_ADDRESS)
        await asyncio.sleep(1740)


loop = asyncio.get_event_loop()

if constants.UPDATE_BIOS:
    loop.create_task(update_bios())

if constants.CHECK_CHANNEL_DELETED:
    loop.create_task(check_deleted())

if constants.USING_WEB_SERVER is False:
    logging.getLogger("hachoir").setLevel(logging.CRITICAL)
    loop.create_task(check_playlist())
else:
    loop.create_task(keep_alive())
# Use the following if you're separating the web server from the bot process
# from within the script
# else:
#    import server
#    import multiprocessing
#    p = multiprocessing.Process(target=server.main())
#    p.start()

client.run_until_disconnected()

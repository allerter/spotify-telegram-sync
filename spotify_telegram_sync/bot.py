import asyncio
import logging
import platform
import re
import signal
import sys
import time
from collections import namedtuple
from string import punctuation
from typing import Dict, List, Optional, Union

import constants
import httpx
import tekore as tk
from database import Database
from get_song_file import DeezLoader
from telethon import TelegramClient, errors, events, tl, types
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

# initiate  telegram client
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("sts")
logger.setLevel(logging.DEBUG)


def clean_str(s: str) -> str:
    return s.translate(str.maketrans("", "", punctuation)).replace(" ", "").lower()


async def get_cover_art(track: tk.model.FullTrack) -> Union[str, bytes]:
    deezer_cover_art = None
    if isrc := track.external_ids.get("isrc"):
        req = await httpx_client.get(f"https://api.deezer.com/track/isrc:{isrc}")
        deezer_track = req.json()
        deezer_cover_art = (
            deezer_track["album"]["cover_xl"] if deezer_track.get("album") else None
        )
    else:
        deezer_cover_art = None

    if deezer_cover_art is not None:
        logger.debug("Found Deezer cover art for track.")
        cover_art = deezer_cover_art
    else:
        logger.debug("Downloading cover art from Spotify.")
        cover_art = (await httpx_client.get(track.album.images[0].url)).content

    return cover_art


async def search_spotify(artist: str, title: str) -> List[tk.model.FullTrack]:
    """serarches track on spotify and returns the matches"""
    matches = []
    query = f"{title} artist:{artist}"
    spotify_search = await spotify.search(query, types=("track",))
    for res in spotify_search[0].items:
        res_artist = res.artists[0].name
        res_title = res.name
        if clean_str(res_artist) == clean_str(artist) and clean_str(
            res_title
        ) == clean_str(title):
            matches.append(res)

    return matches


async def search_deezer(artist: str, title: str) -> Optional[str]:
    """serarches track on deezer and returns the first match's cover art"""
    params = {"q": f"?q=artist:{artist} track:{title}"}
    req = await httpx_client.get("https://api.deezer.com/search", params=params)
    deezer_search = req.json()
    for track in deezer_search["data"]:
        track_artist = track["artist"]["name"]
        track_title = track["title"]
        if clean_str(track_artist) == clean_str(artist) and clean_str(
            track_title
        ) == clean_str(title):
            return track["album"]["cover_xl"]
    return None


async def new_message_handler(event: events.NewMessage) -> None:
    """checks for tracks in new messages to telegram channel,
    and adds them to spotify playlist.
    """
    logger = logging.getLogger("sts.new_message")
    logger.info("New post on Telegram channel.")
    # check if event is a track
    if event.audio and not event.audio.attributes[0].voice:
        # extract track artist and title
        telegram_id = str(event.message.id)
        doc = event.audio.attributes
        if artist := doc[0].performer:
            artist = artist.split(",")[0]
        else:
            artist = ""
        title = doc[0].title
        file_name = doc[1].file_name

        # get artist and title from file name
        # weren't in the attributes
        if not all([artist, title]):
            artist, title = file_name.split("-")
            title = title[: title.rfind(".")]

        # find track on Spotify
        matches = [res.id for res in await search_spotify(artist, title)]
        spotify_tracks = []
        logger.debug(
            "Spotify matches %sfound for the new message.", "" if matches else "not "
        )
        # get spotify playlist tracks
        tracks = await spotify.playlist_items(
            constants.SPOTIFY_PLAYLIST_ID, as_tracks=True
        )
        for item in tracks["items"]:
            if not item["is_local"]:
                track = item["track"]
                spotify_tracks.append(track["id"])
        spotify_tracks = set(spotify_tracks)

        # add track to playlist and database
        already_in_playlist = set(matches).intersection(spotify_tracks)
        if matches and not already_in_playlist:
            await spotify.playlist_add(
                constants.SPOTIFY_PLAYLIST_ID, [f"spotify:track:{matches[0]}"]
            )
            await database.add_tracks([(matches[0], telegram_id)])
            logger.info("Added Telegram track on Spotify.")
        else:
            if already_in_playlist:
                logger.info("Telegram track is already in playlist.")


def format_user_about(current_track: tk.model.FullTrack) -> str:
    user_about = f"listening to {current_track.name} by {current_track.artists[0].name}"
    if len(user_about) > 70:
        user_about = f"🎧 {current_track.artists[0].name} - {current_track.name}"
        if len(user_about) > 70:
            user_about = re.sub(r".feat.*[\)\[]", "", user_about)
            if len(user_about) > 70:
                user_about = user_about[:67] + "..."
    return user_about


async def get_default_pic() -> Union[str, bytes, tl.custom.InputSizedFile]:
    pic = await client.download_profile_photo(telegram_channel, file=bytes)
    if pic is None:
        playlist = await spotify.playlist(constants.SPOTIFY_PLAYLIST_ID)
        if playlist.images:
            default_pic = (await httpx_client.get(playlist.images[0].url)).content
        else:
            default_pic = constants.DEFAULT_PIC
    else:
        default_pic = await client.upload_file(pic)
    return default_pic


async def update_bios() -> None:
    global pinned_message, default_pic

    logger = logging.getLogger("sts.update_bios")
    last_track = namedtuple("last_track", ["artist", "name", "id"])
    last_track.name = "No Song Was Playing"
    last_track.artist = "No Artist"
    last_track.id = None
    pinned_message = await client.get_messages(
        telegram_channel, ids=types.InputMessagePinned()
    )
    await asyncio.sleep(1)
    default_pic = await get_default_pic()

    one_hour_counter = time.time()
    default_sleep_time = 5
    sleep_time = default_sleep_time
    counter = 30
    counter_start = time.time()

    while True:
        # get user bio and spotify playback
        logger.info("Checking playback...")
        logger.debug("Counter: %d - counter_start: %s", counter, counter_start)
        if counter >= 30:
            logger.debug("Getting user about.")
            user_full = await client(GetFullUserRequest(telegram_me))
            user_about = user_full.about
            if user_about is None:
                user_about = ""
            user_id = user_full.user.id
            user_first_name = user_full.user.first_name

            # update channel pic every hour
            if counter_start - one_hour_counter >= 3600:
                logger.debug("Getting default photo and pinned message.")
                default_pic = await get_default_pic()
                await asyncio.sleep(1)
                pinned_message = await client.get_messages(
                    telegram_channel, ids=types.InputMessagePinned()
                )
                one_hour_counter = counter_start
        try:
            playback = await spotify.playback_currently_playing(tracks_only=True)
        except tk.ServiceUnavailable:
            logger.info("Spotify unavilable")
            playback = None
        except tk.TooManyRequests as e:
            wait = e.response.headers["Retry-After"]
            logger.warn("Spotify rate limit exceeded. Waiting %d seconds", wait)
            await asyncio.sleep(wait + 1)
            counter += wait + 1
            playback = None
        except tk.HTTPError as e:
            error = f"HTTPError caught: {str(e)}"
            logger.error(error)
            playback = None
        except Exception as e:
            error = f"Exception caught: {type(e)} - {str(e)}"
            logger.error(error)
            playback = None

        # check if a track is playing
        if playback and playback.is_playing and playback.item:
            logger.info("Playback is playing.")
            # Reset to default since user is playing and might change the track soon
            sleep_time = default_sleep_time
            current_track = playback.item
            # if current track is the same as the last track, there's no need to update
            if playback and current_track.id != last_track.id:
                logger.info("New track: %s", current_track.name)
                if playback and not playback.item.is_local:
                    cover_art = await get_cover_art(playback.item)
                    current_track_url = playback.item.external_urls["spotify"]
                else:
                    cover_art = default_pic
                    current_track_url = '""'

                # don't include secondary artists in artist name
                # if they're already in the title (featured artists)
                artist = " & ".join(
                    artist.name
                    for artist in current_track.artists
                    if artist.name not in current_track.name
                )
                text = f"[{current_track.name}]({current_track_url}) by " f"{artist}"
                msg_text = (
                    f"[{user_first_name}](tg://user?id={user_id}) "
                    + "is listening to "
                    + text
                )
                # replace user bio and keep it shorter than the limit (70 chars)
                if counter >= 30:
                    user_about = format_user_about(current_track)
                    try:
                        counter = 0
                        await client(UpdateProfileRequest(about=user_about))
                    except errors.MessageNotModifiedError:
                        logger.info("User bio is the current track. Skipping update")
                    except errors.FloodWaitError as e:
                        logger.warn(
                            (
                                "Flood wait for updating user bio. "
                                "Penalty: %d seconds"
                            ),
                            e.seconds,
                        )
                        counter -= e.seconds
                    counter_start = time.time()

                # update pinned message
                if pinned_message:
                    try:
                        await client.edit_message(
                            telegram_channel,
                            pinned_message.id,
                            text=msg_text,
                            link_preview=False,
                            file=cover_art if cover_art else None,
                        )
                    except errors.MessageIdInvalidError:
                        logger.info("Pinned message not found. Must have been deleted!")
                        pinned_message = None
                    except errors.MessageNotModifiedError:
                        logger.info(
                            "Pinned message is the current track. Skipping update"
                        )
                    except errors.FloodWaitError as e:
                        logger.warn(
                            (
                                "Flood wait for updating pinned message. "
                                "Waiting %d seconds"
                            ),
                            e.seconds,
                        )
                        await asyncio.sleep(e.seconds)

                last_track = current_track
            elif counter >= 30 and current_track.name not in user_about:
                # for cases where pinned message was updated,
                # but the user bio wasn't because the counter hadn't reached 30
                logger.info("Current track not in user about. Updating...")
                user_about = format_user_about(current_track)
                try:
                    counter = 0
                    await client(UpdateProfileRequest(about=user_about))
                except errors.MessageNotModifiedError:
                    logger.info("User bio is the current track. Skipping update")
                except errors.FloodWaitError as e:
                    logger.warn(
                        ("Flood wait for updating user bio. " "Penalty: %d"), e.seconds
                    )
                    counter -= e.seconds
                counter_start = time.time()
            else:
                if pinned_message:
                    logger.info("Pinned message already displaying track.")
                else:
                    logger.info("No pinned mesage to update (yet).")
        else:
            logger.debug("Playback is paused. Updating...")
            if counter >= 30:
                # look for the default bio in user's saved messages
                if saved_msg := await client.get_messages(
                    telegram_me, search="default bio"
                ):
                    default_user_about = (
                        saved_msg[0].text.replace("default bio:", "").strip()[:70]
                    )
                    logger.info("Default user about found. Using default.")
                else:
                    default_user_about = ""
                    logger.info("Default user about not found. Setting it to empty.")
                # update user bio to defaul value if it already isn't
                if default_user_about != user_about:
                    await client(UpdateProfileRequest(about=default_user_about))
                    counter = 0
                    counter_start = time.time()

            if last_track.name != "No Song Was Playing" and pinned_message:
                logger.info("Updating pinned message.")
                msg_text = pinned_message.text
                msg_text = (
                    msg_text[: msg_text.find(")") + 1]
                    + " isn't listening to anything right now."
                )
                try:
                    await client.edit_message(
                        telegram_channel,
                        pinned_message.id,
                        text=msg_text,
                        link_preview=False,
                        file=default_pic,
                    )
                except errors.MessageIdInvalidError:
                    logger.info("Pinned message not found. Must have been deleted!")
                    pinned_message = None
                except errors.MessageNotModifiedError:
                    logger.info("Pinned message is still the default. Skipping update.")
                except errors.FloodWaitError as e:
                    logger.warn(
                        ("Flood wait for updating pinnes message. Waiting %d seconds."),
                        e.seconds,
                    )
                    await asyncio.sleep(e.seconds)

            last_track.name = "No Song Was Playing"
            last_track.artist = "No Artist"
            last_track.id = None

        logger.debug("Sleeping for %d seconds.", sleep_time)
        await asyncio.sleep(sleep_time)
        # don't sleep more than 3 minutes
        sleep_time += default_sleep_time if sleep_time <= 180 else 0
        counter_end = time.time()
        counter += int(counter_end - counter_start)


async def check_deleted() -> None:
    logger = logging.getLogger("sts.check_deleted")
    old_id = 1
    while True:
        logger.info("Checking Telegram admin log for deleted tracks...")
        deleted = []
        async for event in client.iter_admin_log(telegram_channel, min_id=old_id):
            # event should be: deleted, audio, and not a voice audio
            if event.deleted_message:
                try:
                    if not (
                        event.old.media
                        and event.old.media.document
                        and event.old.media.document.mime_type == "audio/mpeg"
                        and not event.old.media.document.attributes[0].voice
                    ):
                        continue
                except AttributeError:
                    continue
                logger.info("Found deleted track. Message ID: %d", event.old.id)
                # add message id to be checked against DB records
                deleted.append((str(event.old.id)))
        else:
            old_id = event.old.id
            logger.debug("Setting last checked log ID to %d.", old_id)

        # delete tracks from spotify
        if deleted:
            tracks = await database.get_tracks(telegram_ids=deleted)
            if tracks:
                spotify_ids = [x.spotify_id for x in tracks]
                await spotify.playlist_remove(
                    constants.SPOTIFY_PLAYLIST_ID, spotify_ids
                )
                await database.delete_tracks(spotify_ids=spotify_ids)
                logger.info(
                    "Deleted following tracks from Spotify playlist: %s", tracks
                )
            else:
                logger.info("Tracks were already deleted from Spotify.")

        await asyncio.sleep(3600)  # checks every hour


async def update_playlist(
    spotify: tk.Spotify, telegram: TelegramClient, database: Database
) -> None:
    logger = logging.getLogger("sts.update_playlist")
    logger.info("Checking playlist...")
    # get id, url and isrc of non-local tracks

    spotify_tracks = []
    tracks = await spotify.playlist_items(constants.SPOTIFY_PLAYLIST_ID)
    for item in tracks.items:
        track = item.track
        if track and not track.is_local and track.external_ids.get("isrc"):
            spotify_tracks.append(
                (
                    track.id,
                    track.external_urls["spotify"],
                    track.external_ids["isrc"],
                )
            )

    # get tracks from db
    playlist = await database.get_all_tracks()
    difference = len(spotify_tracks) - len(playlist)
    # tracks were added to the playlist
    if difference > 0:
        logger.info(
            "%d tracks were added on Spotify. Downloading tracks...", difference
        )
        upload_to_db_tracks = []
        playlist = [x.spotify_id for x in playlist]
        # specify new tracks
        to_be_added = list(set([x[0] for x in spotify_tracks]) - set(playlist))
        to_be_added = [x for x in spotify_tracks if x[0] in to_be_added]

        # download each track and send it to the Telegram channel
        deezer = DeezLoader(constants.DEEZER_ARL_TOKEN)
        for track in to_be_added:
            logger.debug("Downloading %s", track[0])
            file = None
            try:
                file = await deezer.from_spotify(isrc=track[2])
            except Exception as e:
                logger.error(
                    "Couldn't download track %s. Reason: %s",
                    track[0],
                    f"{type(e)} - {str(e)}",
                )
            if file:
                logger.debug("Uploading %s", track[0])
                uploaded_file = await telegram.upload_file(
                    file, file_name=file.name, part_size_kb=512
                )
                msg = await telegram.send_file(telegram_channel, uploaded_file)
                msg_id = str(msg.id)
                logger.info("Added track %s on Telegram.", track[0])
            else:
                msg_id = None
            upload_to_db_tracks.append((track[0], msg_id))

        # add new tracks to database
        await database.add_tracks(upload_to_db_tracks)
        logger.debug("Added tracks to database.")
        logger.info("Playlist updated.")
    # tracks were removed from the playlist
    elif difference < 0:
        # specify deleted tracks
        logger.info("%d Tracks were removed on Spotify. Deleting...", abs(difference))
        playlist = [(x.spotify_id, x.telegram_id) for x in playlist]
        spotify_ids = list(
            set([x[0] for x in playlist]) - set([x[0] for x in spotify_tracks])
        )
        # get telegram ids of deleted tracks and delete them
        telegram_ids = [x[1] for x in playlist if x[0] in spotify_ids]
        try:
            await telegram.delete_messages(telegram_channel, telegram_ids)
        except Exception as e:
            logger.error("Couldn't delete tracks on Telegram. Reason: %s", e)

        # remove deleted tracks from database
        await database.delete_tracks(spotify_ids=spotify_ids)
        logger.debug("Deleted tracks from database.")
        logger.info("Playlist updated. Deleted tracks: %s", spotify_ids)
    else:
        logger.info("Playlist is already up to date.")


async def update_playlist_loop() -> None:
    while True:
        await update_playlist(database=database, telegram=client, spotify=spotify)
        await asyncio.sleep(300)


async def prepare_clients(
    queue: asyncio.Queue,
    use_database: bool = True,
    use_telegram: bool = True,
    use_httpx: bool = True,
    use_spotify: bool = True,
) -> None:
    ClientTypes = Union[tk.Spotify, TelegramClient, Database, httpx.AsyncClient]
    clients: Dict[str, ClientTypes] = {}
    # database
    if use_database:
        database = Database()
        await database.init(constants.DATABASE_URL)
        clients["database"] = database
        logger.debug("Database is ready.")

    # telegram
    if use_telegram:
        telegram = TelegramClient(
            StringSession(constants.TELETHON_SESSION_STRING),
            constants.TELETHON_API_ID,
            constants.TELETHON_API_HASH,
        )
        await telegram.start()
        clients["telegram"] = telegram
        logger.debug("Telegram is ready.")

    # httpx
    if use_httpx:
        httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=20.0),
            http2=True,
        )
        clients["httpx"] = httpx_client
        logger.debug("httpx is ready.")

    # spotify
    if use_spotify:
        cred = tk.RefreshingCredentials(
            constants.SPOTIFY_CLIENT_ID, constants.SPOTIFY_CLIENT_SECRET
        )
        token = cred.refresh_user_token(constants.SPOTIFY_REFRESH_TOKEN)
        spotify = tk.Spotify(token, asynchronous=True)
        clients["spotify"] = spotify
        logger.debug("Spotify is ready.")

    await queue.put(clients)


async def clean_up() -> None:
    if constants.UPDATE_BIOS:
        try:
            await client(UpdateProfileRequest(about=""))
        except errors.MessageNotModifiedError:
            pass
        except Exception as e:
            logger.error("Telegram error while cleaning up: %s", e)
        try:
            if pinned_message is not None:
                msg_text = pinned_message.text
                msg_text = (
                    msg_text[: msg_text.find(")") + 1]
                    + " isn't listening to anything right now."
                )
                await client.edit_message(
                    telegram_channel,
                    pinned_message.id,
                    text=msg_text,
                    link_preview=False,
                )
        except errors.MessageNotModifiedError:
            pass
        except Exception as e:
            logger.error("Telegram error while cleaning up: %s", e)
    await client.disconnect()
    await httpx_client.aclose()
    await spotify.close()


async def signal_handler(
    signal: signal.Signals, loop: asyncio.AbstractEventLoop
) -> None:
    logger.info(f"Received exit signal {signal.name}...")
    raise OSError(f"Signal: {signal.name}")


async def exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    logger.error("Exception raised: %s", context["message"])
    await clean_up()


if __name__ == "__main__":
    logger.info("Starting up...")
    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    queue = asyncio.Queue()
    loop.run_until_complete(prepare_clients(queue))
    clients = loop.run_until_complete(queue.get())
    database = clients["database"]
    httpx_client = clients["httpx"]
    client = clients["telegram"]
    spotify = clients["spotify"]
    pinned_message = None
    default_pic = None
    telegram_channel = client.loop.run_until_complete(
        client.get_input_entity(constants.TELEGRAM_CHANNEL)
    )
    time.sleep(1)
    telegram_me = client.loop.run_until_complete(client.get_input_entity("me"))

    tasks = []
    if constants.UPDATE_BIOS and constants.UPDATE_PLAYLIST:
        logger.info("Update playlist: ✔️ | Update bio: ✔️")
        tasks.append(loop.create_task(update_bios()))
        tasks.append(loop.create_task(update_playlist_loop()))
    elif constants.UPDATE_BIOS:
        logger.info("Update playlist: ❌ | Update bio: ✔️")
        tasks.append(loop.create_task(update_bios()))
    else:
        logger.info("Update playlist: ✔️ | Update bio: ❌")
        tasks.append(loop.create_task(update_playlist_loop()))
    if constants.CHECK_TELEGRAM:
        logger.info("Check Telegram: ✔️")
        tasks.append(loop.create_task(check_deleted()))
        client.on(events.NewMessage(chats=(telegram_channel)))(new_message_handler)
    else:
        logger.info("Check Telegram: ❌")

    # handle signals
    if platform.system() != "Linux":
        loop.set_exception_handler(exception_handler)
    else:
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT, signal.SIGQUIT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(signal_handler(s, loop))
            )

    # loop.set_exception_handler(handle_exception)

    while True:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received.")
            exit(0)
        except Exception as e:
            if isinstance(e, OSError) and e.args[0].startswith("Signal"):
                exit(0)
            else:
                tb = sys.exc_info()[2]
                logger.error("Exception: %s, ", e.with_traceback(tb))
                exit(1)
        finally:
            logger.info("Cleaning up before exiting...")
            loop.run_until_complete(clean_up())
        logger.info("Telegram client disconnected. Restarting...")
        client.start()

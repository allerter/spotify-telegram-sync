from pycaw import AudioUtilities

import mutagen
import requests

from time import sleep
import subprocess
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='failures.log'
                    )
logger = logging.getLogger(__name__)

extensions = ['.mp3', '.flac', '.ogg']

SERVER_ADDRESS = 'https://spotify-telegram-sync.herokuapp.com'  # IMPORTANT: No trailing "/".


def get_playing_song():
    pids = [sess.ProcessId
            for sess in AudioUtilities.GetAllSessions()
            if sess.State and sess.Process]

    for pid in pids:
        files_in_use = subprocess.check_output(f"handle.exe -p {pid}", shell=True)
        path = None
        for line in files_in_use.decode().split('\n'):
            for extension in extensions:
                if extension in line:
                    path =  \
                    line[line.find(":\\") - 1: line.rfind(extension) + len(extension)]
                    break
            if path is not None:
                break

        if path:
            song = mutagen.File(path, easy=True)
            artist = song['artist'][0].split('/')[0] if song.get('artist') else None
            title = (song['title'][0].replace(' (48 kHz)', '')
                     if song.get('title')
                     else None)
            return artist, title
    return None, None


def main():
    while True:
        artist, title = get_playing_song()
        if artist and title:
            print(artist, title)
            try:
                requests.post(f'{SERVER_ADDRESS}/local_playback',
                              data={'artist': artist, 'title': title})
            except requests.exceptions.RequestException as e:
                logger.log(logging.ERROR, e)
        sleep(2)


if __name__ == '__main__':
    main()

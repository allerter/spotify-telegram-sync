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


def get_playing_song():
    pids = [sess.processId
            for sess in AudioUtilities.GetAllSessions()
            if sess.State and sess.Process]

    for pid in pids:
        files_in_use = subprocess.check_output(f"handle.exe -p {pid}", shell=True)
        path = [line[line.find(":\\") - 1: line.rfind('.mp3') + 4]
                for line in files_in_use.decode().split('\n')
                if '.mp3' in line]

        if path:
            song = mutagen.File(path[0], easy=True)
            artist = song.get('artist')[0] if song.get('artist') else None
            title = (song.get('title')[0].replace(' (48 kHz)', '')
                     if song.get('title')
                     else None)
            return artist, title
    return None, None


def main():
    while True:
        artist, title = get_playing_song()
        if artist and title:
            try:
                requests.post(f'{SERVER_ADDRESS}/local_playback',
                              data={'artist': artist, 'title': title})
            except requests.exceptions.RequestException as e:
                logger.log(logging.ERROR, e)
        sleep(2)


if __name__ == '__main__':
    main()

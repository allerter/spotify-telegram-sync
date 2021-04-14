"""Script refactored from
https://github.com/Utonia/deezloader
"""
import asyncio
import logging
from binascii import a2b_hex, b2a_hex
from collections import OrderedDict
from hashlib import md5
from io import BytesIO
from typing import Any, Dict, Iterator, Optional, Union

import httpx
from Crypto.Cipher import AES, Blowfish
from mutagen import File
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, TYER

qualities = {
    "FLAC": {"n_quality": "9", "f_format": ".flac", "s_quality": "FLAC"},
    "MP3_320": {"n_quality": "3", "f_format": ".mp3", "s_quality": "320"},
    "MP3_256": {"n_quality": "5", "f_format": ".mp3", "s_quality": "256"},
    "MP3_128": {"n_quality": "1", "f_format": ".mp3", "s_quality": "128"},
}
valid_id3_tags = list(EasyID3.valid_keys.keys())


class Sender:
    """Sends requests to the GeniusT Recommender."""

    API_ROOT = "https://api.deezer.com/"
    PRIVATE_API_ROOT = "https://www.deezer.com/ajax/gw-light.php"
    CDN_ROOT = "https://e-cdns-proxy-{song_md5}.dzcdn.net/mobile/1/{song_hash}"

    def __init__(self, timeout: float = 10.0, retries: int = 0, sleep_time: int = 2):
        self._session = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=timeout * 1.5),
            http2=True,
        )
        self.sleep_time = sleep_time
        self.timeout = timeout
        self.retries = retries
        self.logger = logging.getLogger("Sender")

    async def close(self) -> None:
        await self._session.aclose()

    async def request(
        self,
        path: str = "",
        method: str = "GET",
        json_response: bool = True,
        root: str = "api",
        **kwargs,
    ) -> Union[dict, httpx.Response]:
        """Makes a request to Genius."""
        if root == "api":
            uri = self.API_ROOT
        elif root == "private_api":
            uri = self.PRIVATE_API_ROOT
        else:
            uri = ""
        uri += path

        # Make the request
        response = None
        tries = 0
        while response is None and tries <= self.retries:
            tries += 1
            try:
                response = await self._session.request(method, uri, **kwargs)
                response.raise_for_status()
            except httpx.TransportError as e:  # pragma: no cover
                error = "Request timed out:\n{e}".format(e=e)
                self.logger.warn(error)
                if tries > self.retries:
                    raise e
            except httpx.HTTPStatusError as e:  # pragma: no cover
                if e.response.status_code == 429:
                    self.logger.warn(
                        "Too many requests. Waiting %d seconds.", self.sleep_time
                    )
                    await asyncio.sleep(self.sleep_time)
                    tries -= 1
                elif e.response.status_code < 500 or tries > self.retries:
                    raise e
        return response.json() if json_response else response


def md5hex(data: bytes) -> bytes:
    hashed = md5(data).hexdigest().encode()
    return hashed


def genurl(md5: str, quality: str, ids: str, media: str) -> str:
    data = b"\xa4".join(a.encode() for a in [md5, quality, ids, media])

    data = b"\xa4".join([md5hex(data), data]) + b"\xa4"

    if len(data) % 16:
        data += b"\x00" * (16 - len(data) % 16)

    c = AES.new("jo6aey6haid2Teih".encode(), AES.MODE_ECB)

    media_url = b2a_hex(c.encrypt(data)).decode()

    return media_url


def decryptfile(content: Iterator[bytes], key: str, file: BytesIO) -> None:
    seg = 0
    file.seek(0)
    for data in content:
        if not data:
            break

        if seg % 3 == 0 and len(data) == 2048:
            data = Blowfish.new(
                key.encode(), Blowfish.MODE_CBC, a2b_hex("0001020304050607")
            ).decrypt(data)
        file.write(data)
        seg += 1


def calcbfkey(songid: str) -> str:
    h = md5(b"%d" % int(songid)).hexdigest().encode()
    key = b"g4el58wc0zvf9na1"
    return "".join(chr(h[i] ^ h[i + 16] ^ key[i]) for i in range(16))


class DeezLoader:
    def __init__(self, arl_token: str) -> None:
        self.arl_token = arl_token
        self._arl_cookie = {"arl": arl_token}
        self._sender = Sender(retries=3)

    def _sort_artists(self, artists: list) -> str:
        if len(artists) > 1:
            for a in artists:
                for b in artists:
                    if a in b and a != b:
                        artists.remove(b)
        return ", ".join(OrderedDict.fromkeys(artists))

    async def _get_track(self, isrc: str) -> Dict[str, str]:
        datas: Dict[str, Any] = {}
        json_track = await self._sender.request(
            f"track/isrc:{isrc}", headers={"Accept-Language": "en-US,en;q=0.5"}
        )

        album_id = json_track["album"]["id"]
        json_album = await self._sender.request(
            f"album/{album_id}", headers={"Accept-Language": "en-US,en;q=0.5"}
        )
        datas["genre"] = []

        try:
            for a in json_album["genres"]["data"]:
                datas["genre"].append(a["name"])
        except KeyError:
            pass

        datas["genre"] = " & ".join(datas["genre"])
        datas["album_artist"]: list = []

        for a in json_album["contributors"]:
            if a["role"] == "Main":
                datas["album_artist"].append(a["name"])

        datas["album_artist"] = " & ".join(datas["album_artist"])
        datas["album"] = json_album["title"]
        datas["label"] = json_album["label"]
        datas["upc"] = json_album["upc"]

        datas["title"] = json_track["title"]
        array = []

        for a in json_track["contributors"]:
            if a["name"] != "":
                array.append(a["name"])

        array.append(json_track["artist"]["name"])

        datas["artist"] = self._sort_artists(array)
        datas["tracknumber"] = str(json_track["track_position"])
        datas["discnumber"] = str(json_track["disk_number"])
        datas["date"] = json_track["release_date"]
        datas["bpm"] = str(json_track["bpm"])
        datas["duration"] = str(json_track["duration"])
        datas["isrc"] = json_track["isrc"]
        datas["link"] = json_track["link"]
        datas["cover"] = json_track["album"]["cover_xl"]
        return datas

    async def close(self) -> None:
        await self._sender.close()

    async def _send_private_request(
        self,
        method: str,
        access_token: str = "null",
        json: Optional[dict] = None,
    ) -> dict:
        params = {
            "api_version": "1.0",
            "api_token": access_token,
            "input": "3",
            "method": method,
        }
        res = await self._sender.request(
            method="POST",
            params=params,
            json=json,
            cookies=self._arl_cookie,
            root="private_api",
        )
        return res["results"]

    async def _download(self, quality: str, data: Dict[str, str]) -> BytesIO:
        token = (await self._send_private_request("deezer.getUserData"))["checkForm"]
        ids = data["link"].split("?utm")[0].split("/")[-1]
        output = BytesIO()
        infos = await self._send_private_request("song.getData", token, {"sng_id": ids})
        ids = infos["SNG_ID"]
        num_quality = qualities[quality]["n_quality"]
        file_format = qualities[quality]["f_format"]

        try:
            song_md5 = infos["FALLBACK"]["MD5_ORIGIN"]
            version = infos["FALLBACK"]["MEDIA_VERSION"]
        except KeyError:
            song_md5 = infos["MD5_ORIGIN"]
            version = infos["MEDIA_VERSION"]
        song_hash = genurl(song_md5, num_quality, ids, version)
        try:
            crypted_audio = await self._sender.request(
                self._sender.CDN_ROOT.format(song_md5=song_md5[0], song_hash=song_hash),
                headers={"Accept-Language": "en-US,en;q=0.5"},
                root="cdn",
                json_response=False,
            )
        except (IndexError, Exception):
            exception = None
            crypted_audio = None
            for available_quality in qualities:
                if quality == available_quality:
                    continue

                num_quality = qualities[available_quality]["n_quality"]
                file_format = qualities[available_quality]["f_format"]
                song_hash = genurl(song_md5, num_quality, ids, infos["MEDIA_VERSION"])

                try:
                    crypted_audio = await self._sender.request(
                        self._sender.CDN_ROOT.format(
                            song_md5=song_md5[0], song_hash=song_hash
                        ),
                        hedaers={"Accept-Language": "en-US,en;q=0.5"},
                        root="cdn",
                        json_response=False,
                    )
                except Exception as e:
                    exception = e
                if crypted_audio is None and exception:
                    raise exception

        artist = [x for x in data["artist"].split(", ") if x not in data["title"]]
        artist = " & ".join(artist)
        data["improved_artist"] = artist
        name = f'{artist} - {data["title"]}{file_format}'
        output.name = name
        decryptfile(crypted_audio.iter_bytes(2048), calcbfkey(ids), output)
        output.seek(0)
        await self._write_tags(output, data)
        output.seek(0)
        return output

    async def from_spotify(self, isrc: str, quality: str = "MP3_320") -> BytesIO:
        track_data = await self._get_track(isrc)
        return await self._download(quality, track_data)

    async def _write_tags(self, file: BytesIO, data: dict) -> None:
        audio = File(file, easy=True)
        for key, value in data.items():
            if key == "artist":
                audio["artist"] = data["improved_artist"]
            elif key in valid_id3_tags:
                audio[key] = value
        audio.save(file, v2_version=3)
        audio = File(file)
        albumart = (
            await self._sender.request(data["cover"], root="none", json_response=False)
        ).content
        audio["APIC"] = APIC(
            encoding=3,
            mime="image/jpeg",
            type=3,
            desc="Cover",
            data=albumart,
        )
        audio["TYER"] = TYER(text=data["date"])
        # audio['TPUB'] = TPUB(text=data['label'])
        # audio['TPE2'] = TPE2(text=data['album_artist'])
        audio.save(file, v2_version=3)

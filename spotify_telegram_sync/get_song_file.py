from constants import DEEZER_ARL_TOKEN

from requests import Session, get
from hashlib import md5
from binascii import a2b_hex, b2a_hex
from Crypto.Cipher import AES, Blowfish
from mutagen.easyid3 import EasyID3
from mutagen.id3 import TYER, APIC
from mutagen import File

from io import BytesIO
from collections import OrderedDict

qualities = {
    "FLAC": {
        "n_quality": "9",
        "f_format": ".flac",
        "s_quality": "FLAC"
    },

    "MP3_320": {
        "n_quality": "3",
        "f_format": ".mp3",
        "s_quality": "320"
    },

    "MP3_256": {
        "n_quality": "5",
        "f_format": ".mp3",
        "s_quality": "256"
    },

    "MP3_128": {
        "n_quality": "1",
        "f_format": ".mp3",
        "s_quality": "128"
    }
}
valid_id3_tags = list(EasyID3.valid_keys.keys())
req = Session()
req.cookies['arl'] = DEEZER_ARL_TOKEN


def md5hex(data):
    hashed = md5(data).hexdigest().encode()
    return hashed


def genurl(md5, quality, ids, media):
    data = b"\xa4".join(a.encode()for a in [md5, quality, ids, media])

    data = b"\xa4".join([md5hex(data), data]) + b"\xa4"

    if len(data) % 16:
        data += b"\x00" * (16 - len(data) % 16)

    c = AES.new("jo6aey6haid2Teih".encode(), AES.MODE_ECB)

    media_url = b2a_hex(c.encrypt(data)).decode()

    return media_url


def get_api(method, api_token="null", json_data=None):
    params = {
        "api_version": "1.0",
        "api_token": api_token,
        "input": "3",
        "method": method
    }

    private_api_link = "https://www.deezer.com/ajax/gw-light.php"
    try:
        return req.post(private_api_link,
                        params=params,
                        json=json_data).json()['results']
    except Exception:
        return req.post(private_api_link,
                        params=params,
                        json=json_data).json()['results']


def request(url, control=False):
    try:
        thing = get(url, headers={"Accept-Language": "en-US,en;q=0.5"})
    except Exception:
        thing = get(url, headers={"Accept-Language": "en-US,en;q=0.5"})
    if control:
        res = thing.json()
        if res.get('error'):
            print(res['error']['message'])
            raise

    return thing


def artist_sort(array):
    if len(array) > 1:
        for a in array:
            for b in array:
                if a in b and a != b:
                    array.remove(b)

    artists = ", ".join(OrderedDict.fromkeys(array))

    return artists


def tracking(URL, album=None):
    datas = {}
    json_track = request(URL, True).json()

    if not album:
        album_id = json_track['album']['id']
        json_album = request(f'https://api.deezer.com/album/{album_id}', True).json()

        datas['genre'] = []

        try:
            for a in json_album['genres']['data']:
                datas['genre'].append(a['name'])
        except KeyError:
            pass

        datas['genre'] = " & ".join(datas['genre'])
        datas['album_artist'] = []

        for a in json_album['contributors']:
            if a['role'] == "Main":
                datas['album_artist'].append(a['name'])

        datas['album_artist'] = " & ".join(datas['album_artist'])
        datas['album'] = json_album['title']
        datas['label'] = json_album['label']
        datas['upc'] = json_album['upc']

    datas['title'] = json_track['title']
    array = []

    for a in json_track['contributors']:
        if a['name'] != "":
            array.append(a['name'])

    array.append(json_track['artist']['name'])

    datas['artist'] = artist_sort(array)
    datas['tracknumber'] = str(json_track['track_position'])
    datas['discnumber'] = str(json_track['disk_number'])
    datas['date'] = json_track['release_date']
    datas['bpm'] = str(json_track['bpm'])
    datas['duration'] = str(json_track['duration'])
    datas['isrc'] = json_track['isrc']
    datas['link'] = json_track['link']
    datas['cover'] = json_track['album']['cover_xl']
    return datas


def decryptfile(content, key, file):
    seg = 0
    file.seek(0)
    for data in content:
        if not data:
            break

        if seg % 3 == 0 and len(data) == 2048:
            data = Blowfish.new(key.encode(), Blowfish.MODE_CBC,
                                a2b_hex("0001020304050607")).decrypt(data)
        file.write(data)
        seg += 1


def calcbfkey(songid):
    h = md5(b"%d" % int(songid)).hexdigest().encode()
    key = b"g4el58wc0zvf9na1"
    return "".join(chr(h[i] ^ h[i + 16] ^ key[i]) for i in range(16))


def write_tags(file, data):
    audio = File(file, easy=True)
    for key, value in data.items():
        if key in valid_id3_tags:
            audio[key] = value
    audio.save(file, v2_version=3)
    audio = File(file)
    albumart = get(data['cover']).content
    audio['APIC'] = APIC(encoding=3, mime='image/jpeg',
                         type=3, desc=u'Cover',
                         data=albumart)
    audio['TYER'] = TYER(text=data['date'])
    # audio['TPUB'] = TPUB(text=data['label'])
    # audio['TPE2'] = TPE2(text=data['album_artist'])
    audio.save(file, v2_version=3)


def download(link, details, recursive_quality=None,
             recursive_download=None,
             not_interface=None,
             zips=False,
             include_tags=True):

    token = get_api('deezer.getUserData')['checkForm']
    ids = link.split("?utm")[0].split("/")[-1]
    datas = details['datas']
    quality = details['quality']
    output = details['output']
    infos = get_api('song.getData', token, {"sng_id": ids})
    ids = infos['SNG_ID']
    num_quality = qualities[quality]['n_quality']
    file_format = qualities[quality]['f_format']
    # song_quality = qualities[quality]['s_quality']

    try:
        song_md5 = infos['FALLBACK']['MD5_ORIGIN']
        version = infos['FALLBACK']['MEDIA_VERSION']
    except KeyError:
        song_md5 = infos['MD5_ORIGIN']
        version = infos['MEDIA_VERSION']
    song_hash = genurl(song_md5, num_quality, ids, version)
    try:
        crypted_audio = request(
            f'https://e-cdns-proxy-{song_md5[0]}.dzcdn.net/mobile/1/{song_hash}')
    except (IndexError, Exception):
        if not recursive_quality:
            raise "The quality chosen can't be downloaded"

        for a in qualities:
            if details['quality'] == a:
                continue

            num_quality = qualities[a]['n_quality']
            file_format = qualities[a]['f_format']
            song_hash = genurl(song_md5, num_quality, ids, infos['MEDIA_VERSION'])

            try:
                crypted_audio = request(
                    f'https://e-cdns-proxy-{song_md5[0]}.dzcdn.net/mobile/1/{song_hash}'
                )
            except Exception:
                raise "Error with this song"

    artist = [x for x in datas['artist'].split(', ') if x not in datas['title']]
    artist = ' & '.join(artist)
    name = f'{artist} - {datas["title"]}{file_format}'
    if isinstance(output, BytesIO):
        output.name = name
    else:
        output = open(name, 'wb')
    decryptfile(crypted_audio.iter_content(2048),
                calcbfkey(ids), output)
    if isinstance(output, BytesIO):
        output.seek(0)
    if include_tags:
        write_tags(output if isinstance(output, BytesIO) else name, datas)
    if isinstance(output, BytesIO):
        output.seek(0)
        return output
    else:
        return name


def download_track(isrc, output, quality='MP3_320',
                   recursive_quality=True,
                   recursive_download=False,
                   not_interface=False,
                   include_tags=True):

    # Get Deezer ID of song
    url = f'https://api.deezer.com/track/isrc:{isrc}'
    datas = tracking(url)

    details = {"datas": datas, "quality": quality, "output": output}

    file = download(datas['link'], details, recursive_quality,
                    recursive_download, not_interface, include_tags=include_tags)
    return file, datas


# bio = download_track(isrc='USWB12000270', output='')
# with open(bio.name, "wb") as f:
#    f.write(bio.getbuffer())

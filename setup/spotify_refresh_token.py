import requests

client_id = input('Enter your Spotify client ID: ')
client_secret = input('Enter your Spotify client secret: ')
link = input('Enter the link you copied: ')

initial_token = link.split("code=")[1]
body = {"client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "redirect_uri": "https://example.com/callback",
        "code": initial_token
    }
r = requests.post("https://accounts.spotify.com/api/token", data=body)
if r.status_code == 200:
    print("Here's your Spotify refresh token:")
    print(r.json()['refresh_token'])
else:
    print('Something went wrong.')
    print(r.text)

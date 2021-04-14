import tekore as tk

client_id = input("Enter your Spotify app ID: ")
client_secret = input("Enter your Spotify app secret: ")
redirect_uri = "https://example.com/callback"
token = tk.prompt_for_user_token(
    client_id, client_secret, redirect_uri, scope=tk.scope.every
)
print(token.refresh_token)

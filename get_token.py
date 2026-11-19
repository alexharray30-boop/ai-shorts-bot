"""
Run this ONCE on your own computer to connect your YouTube channel.

  1. Put the OAuth file you downloaded from Google Cloud next to this script
     and name it  client_secret.json
  2. pip install google-auth-oauthlib
  3. python get_token.py
  4. A browser opens -> choose the AlexHarray channel -> Allow
  5. Copy the 3 values printed below into GitHub -> Settings -> Secrets -> Actions

Never share these values or commit client_secret.json to GitHub.
"""
import json
import pathlib

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

secret = pathlib.Path(__file__).with_name("client_secret.json")
flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
info = json.loads(secret.read_text())
info = info.get("installed") or info.get("web")

print("\n=== Add these as GitHub Actions secrets ===\n")
print("YT_CLIENT_ID     =", info["client_id"])
print("YT_CLIENT_SECRET =", info["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
print("\nDone. Keep these private.")

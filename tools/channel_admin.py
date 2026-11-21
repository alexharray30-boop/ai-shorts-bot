"""List a channel's videos with their status, or delete one video by id.
  python tools/channel_admin.py list
  python tools/channel_admin.py delete VIDEO_ID
Uses CHANNEL / YT_* or YT2_* secrets exactly like the bot."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "bot"))
import main  # noqa: E402

yt = main.yt_client()
cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

if cmd == "list":
    ch = yt.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()["items"][0]
    print("CHANNEL:", ch["snippet"]["title"], "| videos:", ch["statistics"].get("videoCount"))
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = [i["snippet"]["resourceId"]["videoId"]
           for i in yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50).execute()["items"]]
    for v in yt.videos().list(part="snippet,status,statistics,contentDetails", id=",".join(ids)).execute()["items"]:
        s = v["status"]
        rr = v["contentDetails"].get("regionRestriction", {})
        print(f"VIDEO {v['id']} | {v['snippet']['publishedAt'][:16]} | {v['snippet']['title'][:70]}")
        print(f"      views={v['statistics'].get('viewCount')} privacy={s.get('privacyStatus')} "
              f"upload={s.get('uploadStatus')} rejection={s.get('rejectionReason', '-')} "
              f"licensedContent={v['contentDetails'].get('licensedContent')} "
              f"blockedIn={len(rr.get('blocked', []))} countries")
elif cmd == "delete":
    vid = sys.argv[2]
    v = yt.videos().list(part="snippet", id=vid).execute().get("items", [])
    if not v:
        sys.exit(f"video {vid} not found on this channel")
    yt.videos().delete(id=vid).execute()
    print("DELETED:", vid, "|", v[0]["snippet"]["title"])

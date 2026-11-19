"""
AI Shorts Bot
-------------
Trending (US/UK) topic -> AI script -> AI images -> animated 10s vertical video
-> AI voiceover + captions -> upload to YouTube as a Short.

Everything uses free services:
  * YouTube Data API (trending + upload)      - free quota
  * Pollinations.ai (AI images + AI text)     - free, no key
  * Google Gemini (optional, better scripts)  - free API key
  * edge-tts (AI voice)                       - free
  * FFmpeg (editing)                          - free

Usage:
  python bot/main.py                # upload only if >= MIN_HOURS since last upload
  python bot/main.py --force        # make + upload now
  python bot/main.py --dry-run      # make the video only, no upload
  python bot/main.py --check-only   # print due=true/false (for GitHub Actions)
"""

import argparse
import asyncio
import datetime as dt
import json
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
STATE_FILE = ROOT / "state" / "history.json"
MUSIC_DIR = ROOT / "music"

W, H, FPS = 1080, 1920, 30
DURATION = float(os.getenv("VIDEO_SECONDS", "10"))
NUM_SCENES = 3
XFADE = 0.5
MIN_HOURS = float(os.getenv("MIN_HOURS_BETWEEN_UPLOADS", "10"))
PRIVACY = os.getenv("PRIVACY_STATUS", "public")  # public | unlisted | private
VOICE = os.getenv("TTS_VOICE", "en-US-AndrewMultilingualNeural")
REGIONS = ["US", "GB"]
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
UA = {"User-Agent": "ai-shorts-bot/1.0"}


def _find_ffmpeg():
    if os.getenv("FFMPEG"):
        return os.environ["FFMPEG"]
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


FFMPEG = _find_ffmpeg()


def log(*a):
    print("[bot]", *a, flush=True)


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
def load_history():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_history(hist):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(hist[-200:], indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- #
# YouTube
# --------------------------------------------------------------------------- #
def have_yt_creds():
    return all(os.getenv(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def yt_client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def hours_since_last_upload(yt, history):
    """Uses the channel's real uploads list, falls back to local history."""
    latest = None
    try:
        ch = yt.channels().list(part="contentDetails", mine=True).execute()
        uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        items = yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=5).execute().get("items", [])
        for it in items:
            t = dt.datetime.fromisoformat(it["snippet"]["publishedAt"].replace("Z", "+00:00"))
            latest = t if latest is None or t > latest else latest
    except Exception as e:
        log("could not read channel uploads, using local history:", e)
    for h in history:
        try:
            t = dt.datetime.fromisoformat(h["time"])
            latest = t if latest is None or t > latest else latest
        except Exception:
            pass
    if latest is None:
        return float("inf")
    return (dt.datetime.now(dt.timezone.utc) - latest).total_seconds() / 3600


def trending_signals(yt):
    """Titles + tags of what is trending right now in the US and UK."""
    signals = []
    if yt is None:
        return signals
    for region in REGIONS:
        for cat in (None, "28", "24", "1"):  # all, Science&Tech, Entertainment, Film&Animation
            try:
                kw = {"videoCategoryId": cat} if cat else {}
                res = yt.videos().list(part="snippet", chart="mostPopular", regionCode=region,
                                       maxResults=15, **kw).execute()
                for v in res.get("items", []):
                    sn = v["snippet"]
                    signals.append(sn["title"])
                    signals.extend(sn.get("tags", [])[:5])
            except Exception as e:
                log(f"trending {region}/{cat} skipped:", str(e)[:120])
    # de-duplicate, keep order
    seen, out = set(), []
    for s in signals:
        k = s.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(s.strip())
    return out[:120]


def upload(yt, path, meta):
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    title = clean_title(meta["title"])
    tags = fit_tags(meta.get("tags", []))
    hashtags = " ".join("#" + re.sub(r"[^A-Za-z0-9]", "", h) for h in meta.get("hashtags", []) if h)
    desc = f"{meta.get('description', '').strip()}\n\n{hashtags} #Shorts #AI #AIart\n\n" \
           "Made with AI (images + voice). All visuals are AI-generated and original."
    body = {
        "snippet": {
            "title": title,
            "description": desc[:4900],
            "tags": tags,
            "categoryId": os.getenv("YT_CATEGORY_ID", "24"),
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": PRIVACY,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # YouTube's AI-content disclosure
        },
    }

    def _do(b):
        media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True, chunksize=-1)
        req = yt.videos().insert(part="snippet,status", body=b, media_body=media)
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        return resp

    try:
        resp = _do(body)
    except HttpError as e:
        if e.resp.status == 400 and "containsSyntheticMedia" in str(e):
            body["status"].pop("containsSyntheticMedia")
            resp = _do(body)
        else:
            raise
    log("uploaded:", f"https://youtube.com/shorts/{resp['id']}")
    return resp["id"]


def clean_title(t):
    t = re.sub(r"[<>]", "", t).strip()
    if "#shorts" not in t.lower() and len(t) <= 90:
        t += " #Shorts"
    return t[:100]


def fit_tags(tags):
    out, total = [], 0
    for t in tags:
        t = re.sub(r"[<>,\"]", "", str(t)).strip()[:30]
        if not t:
            continue
        cost = len(t) + (2 if " " in t else 0) + 1
        if total + cost > 480:
            break
        out.append(t)
        total += cost
    return out


# --------------------------------------------------------------------------- #
# Script writing (AI)
# --------------------------------------------------------------------------- #
SCRIPT_PROMPT = """You are a viral YouTube Shorts producer for an "AI videos" channel.
Audience: USA and UK. Video length: exactly {secs} seconds, vertical, {n} AI-generated scenes.

Trending on YouTube right now (US/UK titles & tags):
{trending}

Recent videos on this channel (do NOT repeat these ideas):
{recent}

Pick ONE idea that rides a current trend or evergreen high-search topic, in a format like:
"AI imagines ...", "What if ... (AI)", "AI shows ... in the year 3000", "AI turns ... into ...".

STRICT RULES (copyright & safety):
- NO real people, celebrities, politicians, brand names, logos, or copyrighted characters/franchises.
- Use generic, descriptive concepts only (e.g. "a futuristic London", not a specific film).
- Family-friendly, no tragedies, no misinformation.
- Scenes must show places, landscapes, cities, vehicles, animals, creatures, robots or objects.
  NEVER people, human bodies or human-like figures.
- Keep it simple and visual: each scene clearly shows the idea at a glance (scroll-stopping, bright, epic).
- Captions: plain simple English words (no hyphens or fancy words).

Return ONLY valid JSON with these keys:
{{
 "idea": "short internal description",
 "title": "catchy title, max 70 chars, high-search keywords first",
 "description": "2-3 sentences with natural search keywords",
 "tags": ["15-20 search keywords people in the US/UK actually type"],
 "hashtags": ["5 hashtags without #"],
 "narration": "spoken voiceover, 18-24 words, strong hook in first 3 words, ends with a question or 'follow for more'",
 "captions": ["{n} short on-screen captions, max 5 words each, one per scene"],
 "scenes": ["{n} very detailed cinematic image prompts, vertical 9:16, photorealistic or stylized, dramatic lighting, one per scene"]
}}"""

FALLBACK_IDEAS = [
    ("AI imagines cities in the year 3000", ["a futuristic New York style megacity in the year 3000, flying cars, neon skyline, cinematic",
      "a futuristic London style city in 3000, glass towers over a river, golden hour, ultra detailed",
      "a floating sky city above clouds in the year 3000, sunrise, epic scale, photorealistic"]),
    ("AI turns the seasons into creatures", ["a majestic spring spirit creature made of blossoms, forest, soft light, fantasy art",
      "a summer fire phoenix creature over a golden desert, dramatic sunset, cinematic",
      "a winter ice dragon creature in a frozen mountain storm, blue light, epic"]),
    ("What if planets were giant pets", ["a cute fluffy creature version of planet Mars sitting in space, pixar style, glowing",
      "a playful ocean creature version of planet Earth hugging the moon, stylized 3D, stars",
      "a sleepy giant gas creature version of Jupiter curled up in space, soft light, 3D render"]),
    ("AI shows the ocean's deepest secrets", ["a glowing bioluminescent deep sea city, mysterious, cinematic underwater lighting",
      "a colossal ancient sea creature in the dark ocean abyss, rays of light, ultra detailed",
      "a hidden crystal cave under the ocean, glowing jellyfish, magical, photorealistic"]),
    ("AI imagines dinosaurs living today", ["a friendly dinosaur walking through a modern city park, people-free, cinematic photo",
      "a dinosaur drinking from a mountain lake at sunrise, national geographic style",
      "a herd of dinosaurs crossing a highway bridge at golden hour, epic wide shot"]),
    ("AI turns food into tiny worlds", ["a miniature village built inside a giant donut, tilt shift, cozy lights",
      "a tiny city skyline on top of a pizza, macro photography, warm light",
      "a small waterfall world inside a cup of coffee, fantasy macro, cinematic"]),
]


def recent_titles(history):
    return [h.get("title", "") for h in history[-25:]]


def ask_gemini(prompt):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0}},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def ask_pollinations(prompt):
    r = requests.post(
        "https://text.pollinations.ai/openai",
        headers={**UA, "Content-Type": "application/json"},
        json={"model": "openai", "messages": [{"role": "user", "content": prompt}],
              "seed": random.randint(1, 10**6)},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def parse_json(text):
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def valid_meta(m):
    try:
        return (m["title"] and m["narration"] and len(m["scenes"]) >= NUM_SCENES
                and len(m["captions"]) >= NUM_SCENES)
    except Exception:
        return False


def write_script(trending, history):
    prompt = SCRIPT_PROMPT.format(
        secs=int(DURATION), n=NUM_SCENES,
        trending="\n".join("- " + t for t in trending[:60]) or "- (not available, use evergreen viral AI topics)",
        recent="\n".join("- " + t for t in recent_titles(history)) or "- (none yet)",
    )
    for name, fn in (("gemini", ask_gemini), ("pollinations", ask_pollinations), ("pollinations", ask_pollinations)):
        try:
            raw = fn(prompt)
            if not raw:
                continue
            meta = parse_json(raw)
            if valid_meta(meta):
                meta["scenes"] = meta["scenes"][:NUM_SCENES]
                meta["captions"] = meta["captions"][:NUM_SCENES]
                meta["writer"] = name
                log(f"script by {name}:", meta["title"])
                return meta
        except Exception as e:
            log(f"{name} failed:", str(e)[:150])

    used = set(recent_titles(history))
    choices = [i for i in FALLBACK_IDEAS if i[0] not in used] or FALLBACK_IDEAS
    title, scenes = random.choice(choices)
    log("using built-in fallback idea:", title)
    return {
        "idea": title, "title": title, "writer": "fallback",
        "description": f"{title}. Watch what artificial intelligence created! New AI videos every day.",
        "tags": ["ai", "ai art", "ai video", "ai generated", "artificial intelligence", "ai imagines",
                 "what if", "midjourney style", "ai shorts", "future", "viral shorts", "satisfying"],
        "hashtags": ["ai", "aiart", "aivideo", "shorts", "viral"],
        "narration": f"{title}. Number three will blow your mind. Which one is your favorite? Follow for more!",
        "captions": ["Watch this...", "Wait for it...", "Which one wins?"],
        "scenes": scenes,
    }


# --------------------------------------------------------------------------- #
# Media generation
# --------------------------------------------------------------------------- #
SAFE_SUFFIX = (", vertical composition, epic cinematic scene, highly detailed, vivid colors, "
               "no people, no humans, no person, no text, no watermark, safe for work")
BANNED = re.compile(r"\b(woman|women|girl|man|men|boy|person|people|human|humanoid|avatar|body|nude|"
                    r"naked|sexy|lady|figure|model|bikini|skin)\b", re.I)


def safe_prompt(prompt):
    """Strip anything that tends to produce people/bodies (YouTube safety + likeness)."""
    p = BANNED.sub("", prompt)
    p = re.sub(r"\b9:16\b|vertical cinematic shot:?", "", p, flags=re.I)
    return re.sub(r"\s{2,}", " ", p).strip(" ,.") + SAFE_SUFFIX


def gen_image(prompt, path, seed):
    full = safe_prompt(prompt)
    for attempt in range(6):
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(full) +
               f"?width={W}&height={H}&nologo=true&safe=true&seed={seed + attempt}&model=flux")
        try:
            r = requests.get(url, headers=UA, timeout=180)
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                path.write_bytes(r.content)
                img = Image.open(path).convert("RGB")
                # free tier stamps a small logo in the bottom-right corner: crop it off
                img = img.crop((0, 0, img.width, int(img.height * 0.955)))
                img = cover(img, W, H).filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=2))
                img.save(path, quality=95)
                return True
            log(f"image attempt {attempt + 1}: HTTP {r.status_code}")
        except Exception as e:
            log(f"image attempt {attempt + 1} failed:", str(e)[:120])
        time.sleep(15 * (attempt + 1))  # free tier is rate-limited
    return False


def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * s + 0.5), int(img.height * s + 0.5)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def fallback_image(path, seed):
    rnd = random.Random(seed)
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    c1 = [rnd.randint(0, 120) for _ in range(3)]
    c2 = [rnd.randint(100, 255) for _ in range(3)]
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    for _ in range(40):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(20, 220)
        d.ellipse([x - r, y - r, x + r, y + r], outline=tuple(rnd.randint(150, 255) for _ in range(3)), width=4)
    img.filter(ImageFilter.GaussianBlur(3)).save(path, quality=95)


def find_font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def caption_png(text, path):
    """Big bold Shorts-style caption with thick outline, transparent background."""
    text = re.sub(r"[^\x20-\x7E]", "", re.sub("[  -​ ]", " ", re.sub("[‐-―]", "-", text))).upper().strip()
    font = find_font(92)
    img = Image.new("RGBA", (W, 520), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    words, lines, cur = text.split(), [], ""
    for wd in words:
        test = (cur + " " + wd).strip()
        if d.textlength(test, font=font) > W - 140 and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = test
    lines.append(cur)
    lines = lines[:3]
    y = (520 - len(lines) * 112) // 2
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=font)
        x = (W - tw) / 2
        fill = (255, 230, 0, 255) if i == 0 else (255, 255, 255, 255)
        d.text((x + 5, y + 7), ln, font=font, fill=(0, 0, 0, 150), stroke_width=6, stroke_fill=(0, 0, 0, 150))
        d.text((x, y), ln, font=font, fill=fill, stroke_width=6, stroke_fill=(0, 0, 0, 255))
        y += 112
    img.save(path)


async def _tts(text, path, rate):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate=rate).save(str(path))


def make_voice(text, path):
    for rate in ("+8%", "+20%", "+32%"):
        try:
            asyncio.run(_tts(text, path, rate))
        except Exception as e:
            log("tts failed:", e)
            return False
        if probe_duration(path) <= DURATION - 0.6:
            return True
    return True  # will be trimmed by -t


def probe_duration(path):
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", out.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def run(cmd):
    log("ffmpeg:", " ".join(cmd[:6]), "...")
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        log(p.stderr[-2500:])
        raise RuntimeError("ffmpeg failed")


MOTIONS = [
    # zoom in to centre
    "z='min(zoom+{s},1.22)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
    # zoom out from centre
    "z='if(eq(on,0),1.22,max(zoom-{s},1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
    # slow pan up while zoomed
    "z='1.18':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{f})'",
    # zoom in towards top
    "z='min(zoom+{s},1.22)':x='iw/2-(iw/zoom/2)':y='0'",
]
TRANSITIONS = ["fade", "slideup", "circleopen", "smoothup", "radial", "dissolve", "zoomin", "wipeleft"]


def render(meta, workdir, final_path):
    seg = (DURATION + (NUM_SCENES - 1) * XFADE) / NUM_SCENES
    frames = int(round(seg * FPS))
    base_seed = random.randint(1, 10**7)

    images = []
    for i, prompt in enumerate(meta["scenes"]):
        img = workdir / f"scene{i}.jpg"
        if i:
            time.sleep(6)
        ok = gen_image(prompt, img, base_seed + i * 101)
        log(f"scene {i + 1}: {'AI image' if ok else 'FAILED'}")
        images.append(img if ok else None)
    good = [p for p in images if p]
    if not good:
        raise RuntimeError("No AI images could be generated - skipping this run, will retry next hour.")
    # if one scene failed, reuse a good one mirrored (different motion) instead of a placeholder
    for i, p in enumerate(images):
        if p is None:
            src = good[i % len(good)]
            dst = workdir / f"scene{i}.jpg"
            Image.open(src).transpose(Image.FLIP_LEFT_RIGHT).save(dst, quality=95)
            images[i] = dst

    clips = []
    motions = random.sample(MOTIONS, k=min(NUM_SCENES, len(MOTIONS)))
    for i, img in enumerate(images):
        motion = motions[i % len(motions)].format(s=f"{0.22 / frames:.5f}", f=frames)
        clip = workdir / f"clip{i}.mp4"
        run([FFMPEG, "-y", "-i", str(img), "-vf",
             f"scale={W * 2}:{H * 2},zoompan={motion}:d={frames}:s={W}x{H}:fps={FPS},"
             f"eq=contrast=1.06:saturation=1.15,format=yuv420p",
             "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(clip)])
        clips.append(clip)

    caps = []
    for i, c in enumerate(meta["captions"]):
        p = workdir / f"cap{i}.png"
        caption_png(c, p)
        caps.append(p)

    voice = workdir / "voice.mp3"
    has_voice = make_voice(meta["narration"], voice)
    music = sorted([p for p in MUSIC_DIR.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a")]) \
        if MUSIC_DIR.exists() else []
    track = random.choice(music) if music else None

    cmd = [FFMPEG, "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    for c in caps:
        cmd += ["-i", str(c)]
    if has_voice:
        cmd += ["-i", str(voice)]
    if track:
        cmd += ["-stream_loop", "-1", "-i", str(track)]

    n = NUM_SCENES
    fc, prev = [], "[0:v]"
    for i in range(1, n):
        off = i * (seg - XFADE)
        tr = random.choice(TRANSITIONS)
        fc.append(f"{prev}[{i}:v]xfade=transition={tr}:duration={XFADE}:offset={off:.3f}[x{i}]")
        prev = f"[x{i}]"
    for i in range(n):
        start = 0.15 + i * (seg - XFADE)
        end = start + seg - XFADE + (XFADE if i == n - 1 else 0)
        fc.append(f"{prev}[{n + i}:v]overlay=0:{int(H * 0.60)}:enable='between(t,{start:.2f},{end:.2f})'[o{i}]")
        prev = f"[o{i}]"
    fc.append(f"{prev}format=yuv420p[vout]")

    ai = 2 * n
    audio = []
    if has_voice:
        fc.append(f"[{ai}:a]aresample=44100,adelay=delays=250:all=1,volume=1.6,apad[va]")
        audio.append("[va]")
        ai += 1
    if track:
        fc.append(f"[{ai}:a]volume=0.12,afade=t=out:st={DURATION - 1.2}:d=1.2[ma]")
        audio.append("[ma]")
    if len(audio) == 2:
        fc.append("[va][ma]amix=inputs=2:duration=first:normalize=0[aout]")
    elif len(audio) == 1:
        fc.append(f"{audio[0]}anull[aout]")
    else:
        fc.append(f"anullsrc=r=44100:cl=stereo[aout]")

    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
            "-t", f"{DURATION}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart", str(final_path)]
    run(cmd)
    log("video ready:", final_path, f"({probe_duration(final_path):.1f}s)")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def gh_output(key, value):
    path = os.getenv("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    history = load_history()
    yt = yt_client() if have_yt_creds() else None
    if yt is None and not args.dry_run:
        sys.exit("Missing YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN (use --dry-run to test).")

    if not args.force and not args.dry_run:
        hrs = hours_since_last_upload(yt, history)
        due = hrs >= MIN_HOURS
        log(f"hours since last upload: {hrs:.1f} (need {MIN_HOURS}) -> due={due}")
        if args.check_only:
            gh_output("due", str(due).lower())
            return
        if not due:
            return
    elif args.check_only:
        gh_output("due", "true")
        return

    if not FFMPEG:
        sys.exit("ffmpeg is not installed.")

    trending = trending_signals(yt)
    log(f"trending signals: {len(trending)}")
    meta = write_script(trending, history)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    workdir = OUT / stamp
    workdir.mkdir(parents=True, exist_ok=True)
    final = OUT / f"short-{stamp}.mp4"
    (workdir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    render(meta, workdir, final)

    if args.dry_run:
        log("dry run - not uploading.")
        return

    vid = upload(yt, final, meta)
    history.append({"time": dt.datetime.now(dt.timezone.utc).isoformat(), "title": meta["title"],
                    "video_id": vid, "writer": meta.get("writer")})
    save_history(history)


if __name__ == "__main__":
    main()

"""
Riddle Shorts Bot (4K)
----------------------
Makes a 10-second 4K (2160x3840) riddle Short and uploads it to YouTube.

  hook banner -> riddle card pops in (AI voice reads it) -> 3-2-1 countdown ring
  -> answer reveal (ding + voice) -> "comment if you got it" call-to-action

Everything is drawn by code (no stock / no downloaded images), so there is
no copyright risk and the picture is always sharp 4K.

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
import math
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from riddles import RIDDLES  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
FONTS = ROOT / "fonts"
STATE_FILE = ROOT / "state" / "history.json"
MUSIC_DIR = ROOT / "music"

SCALE = float(os.getenv("RENDER_SCALE", "1"))  # 1 = 4K, 0.5 = 1080p (fast tests)
W, H = int(2160 * SCALE), int(3840 * SCALE)
FPS = 30
D = float(os.getenv("VIDEO_SECONDS", "10"))
MIN_HOURS = float(os.getenv("MIN_HOURS_BETWEEN_UPLOADS", "10"))
KIDS_SHARE = float(os.getenv("KIDS_SHARE", "1.0"))  # 100% kids videos (riddles only as backup)
PRIVACY = os.getenv("PRIVACY_STATUS", "public")
VOICE = os.getenv("TTS_VOICE", "en-US-AndrewMultilingualNeural")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
UA = {"User-Agent": "riddle-shorts-bot/2.0"}


def S(v):
    """scale a 4K pixel value"""
    return int(v * SCALE)


def log(*a):
    print("[bot]", *a, flush=True)


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
    STATE_FILE.write_text(json.dumps(hist[-500:], indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- #
# YouTube
# --------------------------------------------------------------------------- #
def have_yt_creds():
    return all(os.getenv(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def yt_secrets():
    """Paste-proof: finds the client id / secret / refresh token by their shape, wherever they
    were pasted (extra spaces, new lines, labels, or swapped between the 3 secrets)."""
    blob = " ".join(os.getenv(k, "") for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    cid = re.search(r"[0-9]+-[0-9a-z]+\.apps\.googleusercontent\.com", blob)
    sec = re.search(r"GOCSPX-[A-Za-z0-9_\-]+", blob)
    tok = re.search(r"1//[A-Za-z0-9_\-]+", blob)
    found = {"client id": bool(cid), "client secret": bool(sec), "refresh token": bool(tok)}
    log("secrets found:", ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in found.items()))
    return (cid.group(0) if cid else os.getenv("YT_CLIENT_ID", "").strip(),
            sec.group(0) if sec else os.getenv("YT_CLIENT_SECRET", "").strip(),
            tok.group(0) if tok else os.getenv("YT_REFRESH_TOKEN", "").strip())


def yt_client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    cid, sec, tok = yt_secrets()
    creds = Credentials(
        None,
        refresh_token=tok,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cid,
        client_secret=sec,
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def hours_since_last_upload(yt, history):
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


def upload(yt, path, meta):
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    if meta.get("made_for_kids") and os.getenv("SEO", "1") == "1":
        import seo
        meta = seo.enhance(meta, log)  # live US/UK search phrases

    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description"][:4900],
            "tags": fit_tags(meta["tags"]),
            "categoryId": "27" if meta.get("made_for_kids") else "24",  # Education for kids learning
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": bool(meta.get("made_for_kids")),
                   "containsSyntheticMedia": False},
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


def fit_tags(tags):
    out, total = [], 0
    for t in tags:
        t = re.sub(r"[<>,\"]", "", str(t)).strip()[:30]
        if not t or t in out:
            continue
        cost = len(t) + (2 if " " in t else 0) + 1
        if total + cost > 480:
            break
        out.append(t)
        total += cost
    return out


# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #
HOOKS = ["ONLY 1% CAN SOLVE THIS", "99% GET THIS WRONG", "CAN YOU SOLVE THIS?",
         "GENIUS TEST", "3 SECONDS TO ANSWER", "BET YOU CAN'T GET THIS"]
TITLES = [
    "Only 1% Can Solve This Riddle 🧠 #shorts",
    "99% Get This Riddle Wrong! 🤯 #shorts",
    "Can You Solve This Riddle in 3 Seconds? ⏱️ #shorts",
    "Riddle Only Geniuses Can Answer 🧠 #riddles",
    "Bet You Can't Solve This Riddle 😏 #shorts",
    "Tricky Riddle That Fools Everyone 🤔 #shorts",
    "IQ Test: Can You Answer This Riddle? 🧠 #shorts",
    "Quick Brain Teaser – Can You Get It? ⚡ #shorts",
]
BASE_TAGS = ["riddles", "riddles with answers", "brain teasers", "riddle challenge", "tricky riddles",
             "can you solve this", "only geniuses can solve", "iq test", "brain test", "riddles for adults",
             "hard riddles", "funny riddles", "logic puzzles", "puzzle", "quiz", "trivia", "brain games",
             "riddle shorts", "shorts", "viral shorts", "riddles in english", "mind games", "test your brain"]

PALETTES = [  # top, bottom, accent
    ((88, 28, 135), (15, 23, 42), (250, 204, 21)),
    ((14, 116, 144), (8, 20, 45), (251, 146, 60)),
    ((190, 18, 60), (40, 10, 40), (253, 224, 71)),
    ((22, 101, 52), (5, 30, 25), (250, 204, 21)),
    ((30, 64, 175), (10, 10, 35), (52, 211, 153)),
    ((147, 51, 234), (30, 10, 60), (34, 211, 238)),
    ((234, 88, 12), (60, 15, 10), (255, 255, 255)),
]

AI_PROMPT = """Write ONE new riddle for a YouTube Shorts riddle channel (US/UK adults).
Rules:
- The question must be at most 16 words, clear, and have ONE widely accepted answer.
- The answer must be 1-3 words.
- It must be genuinely correct (double-check the logic). Clever wordplay or logic is best.
- Family-friendly. No real people or brands.
- Do NOT use any of these (already posted): {used}
Return ONLY JSON: {{"question": "...", "answer": "..."}}"""


def ask_ai(prompt):
    key = os.getenv("GEMINI_API_KEY")
    if key:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}:generateContent",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"responseMimeType": "application/json"}},
                timeout=90)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            log("gemini failed:", str(e)[:150])
    r = requests.post("https://text.pollinations.ai/openai", headers={**UA, "Content-Type": "application/json"},
                      json={"model": "openai", "messages": [{"role": "user", "content": prompt}],
                            "seed": random.randint(1, 10**6)}, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def pick_riddle(history):
    used = {h.get("question", "").lower() for h in history}
    fresh = [r for r in RIDDLES if r[0].lower() not in used]
    if fresh:
        q, a = random.choice(fresh)
        return q, a, "bank"
    for _ in range(3):
        try:
            raw = ask_ai(AI_PROMPT.format(used="; ".join(list(used)[-40:])))
            m = re.search(r"\{.*\}", raw, re.S)
            d = json.loads(m.group(0))
            q, a = d["question"].strip(), d["answer"].strip()
            if 3 <= len(q.split()) <= 18 and 1 <= len(a.split()) <= 4 and q.lower() not in used:
                return q, a, "ai"
        except Exception as e:
            log("ai riddle failed:", str(e)[:150])
    q, a = random.choice(RIDDLES)  # everything used: recycle
    return q, a, "recycled"


def build_meta(q, a, hook):
    title = random.choice(TITLES)
    desc = (f"🧠 {q}\n\nThink you know the answer? Watch till the end and comment below! 👇\n"
            "New riddle every day – follow so you don't miss one.\n\n"
            "#riddles #brainteaser #riddlechallenge #iqtest #shorts")
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", q)][:4]
    tags = BASE_TAGS + [f"{w} riddle" for w in words]
    return {"question": q, "answer": a, "hook": hook, "title": title, "description": desc, "tags": tags}


# --------------------------------------------------------------------------- #
# Drawing helpers
# --------------------------------------------------------------------------- #
def font(size, weight="ExtraBold"):
    p = FONTS / f"Poppins-{weight}.ttf"
    if p.exists():
        return ImageFont.truetype(str(p), size)
    for alt in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if os.path.exists(alt):
            return ImageFont.truetype(alt, size)
    return ImageFont.load_default(size=size)


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for wd in text.split():
        test = (cur + " " + wd).strip()
        if draw.textlength(test, font=fnt) > max_w and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = test
    lines.append(cur)
    return lines


def fit_text(text, max_w, max_h, start, weight="ExtraBold", min_size=60, spacing=1.18):
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    size = start
    while size > min_size:
        f = font(size, weight)
        lines = wrap(d, text, f, max_w)
        if len(lines) * size * spacing <= max_h:
            return f, lines, size
        size -= 6
    f = font(min_size, weight)
    return f, wrap(d, text, f, max_w), min_size


def rounded_card(w, h, radius, fill, shadow=True, border=None):
    pad = S(60)
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([pad, pad + S(24), pad + w, pad + h + S(24)], radius,
                                             fill=(0, 0, 0, 140))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(S(28))))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([pad, pad, pad + w, pad + h], radius, fill=fill,
                        outline=border[0] if border else None, width=border[1] if border else 0)
    return img, pad


def draw_center_lines(img, lines, fnt, size, top, color, stroke=0, stroke_fill=None, spacing=1.18):
    d = ImageDraw.Draw(img)
    y = top
    for ln in lines:
        tw = d.textlength(ln, font=fnt)
        d.text(((img.width - tw) / 2, y), ln, font=fnt, fill=color, stroke_width=stroke, stroke_fill=stroke_fill)
        y += int(size * spacing)


def ease_out_back(t):
    t = max(0.0, min(1.0, t))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def make_background(pal, seed):
    """Tall gradient with soft glowing blobs; we pan through it for motion."""
    rnd = random.Random(seed)
    top, bot, acc = pal
    bh = H + S(900)
    grad = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        grad.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    bg = grad.resize((W, bh), Image.BICUBIC)
    glow = Image.new("RGBA", (W, bh), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for _ in range(9):
        r = rnd.randint(S(250), S(700))
        x, y = rnd.randint(0, W), rnd.randint(0, bh)
        c = acc if rnd.random() < 0.4 else (255, 255, 255)
        gd.ellipse([x - r, y - r, x + r, y + r], fill=c + (rnd.randint(18, 40),))
    glow = glow.filter(ImageFilter.GaussianBlur(S(160)))
    bg = Image.alpha_composite(bg.convert("RGBA"), glow).convert("RGB")
    # subtle diagonal pattern
    pat = Image.new("RGBA", (W, bh), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pat)
    step = S(140)
    for k in range(-bh, W + bh, step):
        pd.line([(k, 0), (k + bh, bh)], fill=(255, 255, 255, 10), width=S(18))
    return Image.alpha_composite(bg.convert("RGBA"), pat).convert("RGB")


# --------------------------------------------------------------------------- #
# Audio
# --------------------------------------------------------------------------- #
async def _tts(text, path, rate):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate=rate).save(str(path))


async def edge_tts_save(text, path, rate, voice):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(path))


def probe_duration(path):
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", out.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def tts(text, path, max_len):
    global VOICE
    for rate in ("+5%", "+15%", "+25%", "+35%"):
        for attempt, voice in enumerate([VOICE, VOICE, "en-US-GuyNeural", "en-US-ChristopherNeural"]):
            try:
                asyncio.run(_tts(text, path, rate)) if voice == VOICE else \
                    asyncio.run(edge_tts_save(text, path, rate, voice))
                break
            except Exception as e:
                log(f"tts attempt {attempt + 1} failed:", e)
        else:
            return 0.0
        dur = probe_duration(path)
        if dur <= max_len:
            return dur
    return probe_duration(path)


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        log(p.stderr[-2500:])
        raise RuntimeError("ffmpeg failed")


def sfx(workdir):
    """Original sound effects synthesised with ffmpeg (no copyright)."""
    fx = {
        "whoosh": "anoisesrc=d=0.45:c=pink:a=0.5,highpass=f=300,lowpass=f=5000,"
                  "afade=t=in:d=0.15,afade=t=out:st=0.2:d=0.25",
        "pop": "aevalsrc='0.6*sin(2*PI*(500+900*t)*t)*exp(-14*t)':d=0.25",
        "tick": "aevalsrc='0.55*sin(2*PI*1350*t)*exp(-60*t)':d=0.12",
        "ding": "aevalsrc='0.45*(sin(2*PI*1046*t)+0.6*sin(2*PI*1568*t)+0.3*sin(2*PI*2093*t))*exp(-3.5*t)':d=1.4",
        "pad": f"aevalsrc='0.05*(sin(2*PI*220*t)+sin(2*PI*261.6*t)+sin(2*PI*329.6*t))"
               f"*(0.7+0.3*sin(2*PI*0.25*t))':d={D}",
        # cheerful rising arpeggio
        "yay": "aevalsrc='0.35*sin(2*PI*if(lt(t,0.1),523,if(lt(t,0.2),659,if(lt(t,0.3),784,1046)))*t)"
               "*exp(-5*mod(t,0.1))*if(lt(t,0.3),1,exp(-4*(t-0.3)))':d=1.0",
        # happy bouncy kids music loop (C - Am - F - G), original
        "music": "aevalsrc='0.06*sin(2*PI*if(lt(mod(t,8),2),if(eq(mod(trunc(t*4),4),0),523,if(eq(mod(trunc(t*4),4),1),659,"
                 "if(eq(mod(trunc(t*4),4),2),784,659))),if(lt(mod(t,8),4),if(eq(mod(trunc(t*4),4),0),440,"
                 "if(eq(mod(trunc(t*4),4),1),523,if(eq(mod(trunc(t*4),4),2),659,523))),if(lt(mod(t,8),6),"
                 "if(eq(mod(trunc(t*4),4),0),349,if(eq(mod(trunc(t*4),4),1),440,if(eq(mod(trunc(t*4),4),2),523,440))),"
                 "if(eq(mod(trunc(t*4),4),0),392,if(eq(mod(trunc(t*4),4),1),494,if(eq(mod(trunc(t*4),4),2),587,494))))))*t)"
                 "*exp(-7*mod(t,0.25))"
                 "+0.07*sin(2*PI*if(lt(mod(t,8),2),131,if(lt(mod(t,8),4),110,if(lt(mod(t,8),6),87,98)))*t)"
                 f"*exp(-4*mod(t,0.5))':d={D}",
    }
    out = {}
    for name, expr in fx.items():
        p = workdir / f"{name}.wav"
        run([FFMPEG, "-y", "-f", "lavfi", "-i", expr, "-ar", "44100", "-ac", "2", str(p)])
        out[name] = p
    return out


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render(meta, workdir, final_path):
    pal = random.choice(PALETTES)
    top, bot, acc = pal
    seed = random.randint(1, 10**7)
    rnd = random.Random(seed)

    # ---- audio first (timeline depends on voice length) ----
    qv, av = workdir / "q.mp3", workdir / "a.mp3"
    q_start = 0.55
    q_len = tts(meta["question"], qv, max_len=min(4.2, D - 6.0))
    a_text = f"It's {meta['answer']}!" if not meta["answer"][0].isdigit() else f"The answer is {meta['answer']}!"
    a_len = tts(a_text, av, max_len=1.8)
    cd_start = max(q_start + q_len + 0.15, 3.2)
    cd_start = min(cd_start, D - 5.2)
    reveal = cd_start + 3.0
    cta_t = min(reveal + 1.3, D - 1.2)
    log(f"timeline: voice {q_len:.1f}s, countdown {cd_start:.1f}s, reveal {reveal:.1f}s")

    # ---- static layers ----
    bg = make_background(pal, seed)

    hook_f = font(S(132), "Black")
    d0 = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    hook_w = int(d0.textlength(meta["hook"], font=hook_f)) + S(160)
    hook_img, hp = rounded_card(hook_w, S(230), S(115), acc + (255,))
    draw_center_lines(hook_img, [meta["hook"]], hook_f, S(132), hp + S(30), (20, 20, 30))

    tag_f = font(S(80), "SemiBold")
    tag_img = Image.new("RGBA", (W, S(140)), (0, 0, 0, 0))
    draw_center_lines(tag_img, ["🧠  RIDDLE  •  ANSWER IN 3 SECONDS".replace("🧠  ", "")], tag_f, S(80), 0,
                      (255, 255, 255, 220))

    cw, ch = S(1860), S(1250)
    q_f, q_lines, q_size = fit_text(meta["question"], cw - S(220), ch - S(240), S(170))
    card, cp = rounded_card(cw, ch, S(90), (255, 255, 255, 255))
    text_h = int(len(q_lines) * q_size * 1.18)
    draw_center_lines(card, q_lines, q_f, q_size, cp + (ch - text_h) // 2 - S(10), (17, 24, 39))
    # little "?" badge
    bd = ImageDraw.Draw(card)
    br = S(95)
    bx, by = cp + cw - S(60), cp + S(40)
    bd.ellipse([bx - br, by - br, bx + br, by + br], fill=acc + (255,), outline=(255, 255, 255), width=S(14))
    qf = font(S(130), "Black")
    bd.text((bx - bd.textlength("?", font=qf) / 2, by - S(98)), "?", font=qf, fill=(20, 20, 30))

    aw, ah = S(1700), S(560)
    a_f, a_lines, a_size = fit_text(meta["answer"].upper(), aw - S(160), ah - S(250), S(190), "Black")
    ans, ap = rounded_card(aw, ah, S(80), (34, 197, 94, 255), border=((255, 255, 255, 255), S(14)))
    lab_f = font(S(70), "SemiBold")
    draw_center_lines(ans, ["ANSWER"], lab_f, S(70), ap + S(45), (220, 252, 231))
    a_text_h = int(len(a_lines) * a_size * 1.1)
    draw_center_lines(ans, a_lines, a_f, a_size, ap + S(140) + (ah - S(160) - a_text_h) // 2 - S(20),
                      (255, 255, 255), stroke=S(6), stroke_fill=(21, 128, 61), spacing=1.1)

    cta_f = font(S(96), "ExtraBold")
    cta_img = Image.new("RGBA", (W, S(360)), (0, 0, 0, 0))
    draw_center_lines(cta_img, ["Did you get it right?", "Comment below 👇".replace(" 👇", "!")],
                      cta_f, S(96), S(20), (255, 255, 255), stroke=S(8), stroke_fill=(0, 0, 0))

    num_f = font(S(300), "Black")
    particles = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(S(6), S(22)), rnd.uniform(S(40), S(160)))
                 for _ in range(45)]

    card_y = S(1000)
    ring_cy = card_y + ch + S(470)
    ans_y = card_y + ch + S(110)

    def paste_scaled(frame, layer, cx, cy, scale, alpha=1.0):
        if scale <= 0.01 or alpha <= 0.01:
            return
        L = layer
        if abs(scale - 1) > 0.005:
            L = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))),
                             Image.BILINEAR)
        if alpha < 0.999:
            a = L.getchannel("A").point(lambda v: int(v * alpha))
            L = L.copy()
            L.putalpha(a)
        frame.paste(L, (int(cx - L.width / 2), int(cy - L.height / 2)), L)

    # ---- frames -> ffmpeg ----
    silent = workdir / "video.mp4"
    enc = subprocess.Popen(
        [FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", os.getenv("X264_PRESET", "fast"), "-crf", "18",
         "-threads", "4", "-x264-params", "rc-lookahead=10", "-pix_fmt", "yuv420p", str(silent)],
        stdin=subprocess.PIPE, stderr=open(workdir / "encode.log", "w"))

    total = int(D * FPS)
    for fi in range(total):
        t = fi / FPS
        off = int((math.sin(t * 0.6) * 0.5 + 0.5) * S(900))
        frame = bg.crop((0, off, W, off + H))
        fd = ImageDraw.Draw(frame)

        for (px, py, pr, sp) in particles:
            y = (py - sp * t * 2) % H
            fd.ellipse([px - pr, y - pr, px + pr, y + pr], fill=tuple(min(255, c + 60) for c in top))

        # hook banner slides down + gentle pulse
        hk = ease_out_back(t / 0.5)
        pulse = 1 + 0.025 * math.sin(t * 6) if t > 0.6 else 1
        paste_scaled(frame, hook_img, W / 2, -S(200) + (S(420) + S(200)) * hk, pulse)
        if t > 0.5:
            paste_scaled(frame, tag_img, W / 2, S(700), 1, ease_out((t - 0.5) / 0.4))

        # question card pops in, shrinks slightly at reveal
        cs = ease_out_back((t - 0.35) / 0.45)
        if t >= reveal:
            cs *= 1 - 0.06 * ease_out((t - reveal) / 0.4)
        paste_scaled(frame, card, W / 2, card_y + ch / 2, cs)

        # countdown ring
        if cd_start <= t < reveal:
            lt = t - cd_start
            n = 3 - int(lt)
            frac = 1 - (lt % 1.0)
            R = S(260)
            box = [W / 2 - R, ring_cy - R, W / 2 + R, ring_cy + R]
            fd.ellipse([box[0] - S(30), box[1] - S(30), box[2] + S(30), box[3] + S(30)], fill=(0, 0, 0))
            fd.arc(box, 0, 360, fill=(70, 70, 90), width=S(44))
            fd.arc(box, -90, -90 + 360 * frac, fill=acc, width=S(44))
            pop = 1 + 0.25 * (1 - ease_out((lt % 1.0) / 0.25))
            nf = font(int(S(300) * pop), "Black")
            s = str(n)
            tw = fd.textlength(s, font=nf)
            fd.text((W / 2 - tw / 2, ring_cy - nf.size * 0.62), s, font=nf, fill=(255, 255, 255))
            think_f = font(S(80), "SemiBold")
            msg = "THINK FAST..."
            fd.text((W / 2 - fd.textlength(msg, font=think_f) / 2, ring_cy + R + S(70)), msg,
                    font=think_f, fill=(255, 255, 255))

        # answer reveal
        if t >= reveal:
            rt = t - reveal
            if rt < 0.12:  # flash
                frame = Image.blend(frame, Image.new("RGB", frame.size, (255, 255, 255)), 0.55 * (1 - rt / 0.12))
            paste_scaled(frame, ans, W / 2, ans_y + ah / 2 + S(40), ease_out_back(rt / 0.4))
        if t >= cta_t:
            paste_scaled(frame, cta_img, W / 2, ans_y + ah + S(330), 1, ease_out((t - cta_t) / 0.4))

        # progress bar
        fd = ImageDraw.Draw(frame)
        fd.rectangle([0, H - S(26), int(W * t / D), H], fill=acc)

        enc.stdin.write(frame.tobytes())
    enc.stdin.close()
    enc.wait()
    if enc.returncode != 0:
        raise RuntimeError("video encode failed")

    # ---- audio mix ----
    fx = sfx(workdir)
    music = sorted(p for p in MUSIC_DIR.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a")) \
        if MUSIC_DIR.exists() else []
    bed = random.choice(music) if music else fx["pad"]
    events = [(fx["whoosh"], 0.0, 0.9), (fx["pop"], 0.4, 0.8)]
    if q_len:
        events.append((qv, q_start, 1.7))
    events += [(fx["tick"], cd_start + k, 1.0) for k in range(3)]
    events.append((fx["ding"], reveal, 0.9))
    if a_len:
        events.append((av, reveal + 0.15, 1.8))
    events.append((fx["pop"], cta_t, 0.5))

    cmd = [FFMPEG, "-y", "-i", str(silent)]
    fc, labels = [], []
    for i, (src, at, vol) in enumerate(events):
        cmd += ["-i", str(src)]
        ms = int(at * 1000)
        fc.append(f"[{i + 1}:a]aresample=44100,aformat=channel_layouts=stereo,"
                  f"adelay={ms}|{ms},volume={vol}[e{i}]")
        labels.append(f"[e{i}]")
    cmd += ["-stream_loop", "-1", "-i", str(bed)]
    bi = len(events) + 1
    fc.append(f"[{bi}:a]aresample=44100,aformat=channel_layouts=stereo,volume={0.18 if music else 1.0},"
              f"afade=t=out:st={D - 1}:d=1[bed]")
    labels.append("[bed]")
    fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
              f"alimiter=limit=0.95,atrim=0:{D}[aout]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[aout]", "-t", str(D),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final_path)]
    run(cmd)
    log("video ready:", final_path, f"{W}x{H}, {probe_duration(final_path):.1f}s")


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
    ap.add_argument("--format", choices=["kids", "riddle", "guess_animal", "count", "colors", "odd_one_out",
                                         "abc", "shapes"])
    ap.add_argument("--bank", type=int, help="make this many videos for the video bank (no upload)")
    ap.add_argument("--bank-dir", default=str(ROOT / "bank"))
    ap.add_argument("--bank-formats", help="comma list, e.g. guess_animal,count")
    ap.add_argument("--bank-prefix", default="", help="suffix that keeps parallel batches apart, e.g. -a")
    ap.add_argument("--bank-batch", default="", help="batch number so new files never overwrite old ones")
    ap.add_argument("--bank-used", help="folder of .json files of videos already in the bank (to avoid repeats)")
    ap.add_argument("--video", help="upload this ready-made mp4 (needs --meta)")
    ap.add_argument("--meta")
    args = ap.parse_args()
    if args.bank:
        args.dry_run = True  # making videos only

    history = load_history()
    yt = yt_client() if have_yt_creds() else None
    if yt is None and not args.dry_run:
        sys.exit("Missing YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN (use --dry-run to test).")
    if yt is not None and not args.dry_run:
        # fail fast (before a 10-minute render) if the YouTube connection is broken
        try:
            ch = yt.channels().list(part="snippet", mine=True).execute()
            log("YouTube connected:", ch["items"][0]["snippet"]["title"])
        except Exception as e:
            sys.exit(f"YOUTUBE LOGIN FAILED - check the 3 GitHub secrets or re-run CONNECT.bat. Details: {e}")

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

    # ---- upload a ready-made video (from the video bank) ----
    if args.video:
        meta = json.loads(pathlib.Path(args.meta).read_text(encoding="utf-8"))
        vid = upload(yt, pathlib.Path(args.video), meta)
        record_upload(history, meta, vid)
        return

    if not FFMPEG:
        sys.exit("ffmpeg is not installed.")

    # ---- make a batch of videos for the video bank ----
    if args.bank:
        bank_dir = pathlib.Path(args.bank_dir)
        bank_dir.mkdir(parents=True, exist_ok=True)
        formats = (args.bank_formats or "kids").split(",")
        work_hist = list(history)
        if args.bank_used and pathlib.Path(args.bank_used).exists():  # videos already waiting in the bank
            for jf in pathlib.Path(args.bank_used).glob("*.json"):
                try:
                    m = json.loads(jf.read_text(encoding="utf-8"))
                    work_hist.append({"format": m.get("format"), "key": m.get("key", ""), "keys": m.get("keys", [])})
                except Exception:
                    pass
            log(f"bank: skipping items from {len(work_hist) - len(history)} videos already in the bank")
        made = 0
        for i in range(args.bank):
            fmt_i = formats[i % len(formats)]
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
            wd = OUT / f"bank-{stamp}-{i}"
            wd.mkdir(parents=True, exist_ok=True)
            name = (f"bank-{int(args.bank_batch):03d}-{i:02d}{args.bank_prefix}" if args.bank_batch
                    else f"bank-{i:02d}{args.bank_prefix}")
            final = bank_dir / f"{name}.mp4"
            meta = make_kids(wd, final, work_hist, fmt_i)
            if meta is None:
                log(f"bank video {i + 1} failed, skipping")
                continue
            (bank_dir / f"{name}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            work_hist.append({"format": meta["format"], "key": meta["key"], "keys": meta.get("keys", [])})
            made += 1
            log(f"bank video {i + 1}/{args.bank} ready: {final.name}")
        if not made:
            sys.exit("no bank videos could be made")
        return

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    workdir = OUT / stamp
    workdir.mkdir(parents=True, exist_ok=True)
    final = OUT / f"short-{stamp}.mp4"

    fmt = args.format
    if fmt is None:
        fmt = "kids" if random.random() < KIDS_SHARE else "riddle"

    meta = None
    if fmt != "riddle":
        meta = make_kids(workdir, final, history, fmt)
        if meta is None and fmt != "kids":
            sys.exit("kids video could not be made")
    if meta is None:
        q, a, src = pick_riddle(history)
        meta = build_meta(q, a, random.choice(HOOKS))
        meta.update(source=src, format="riddle", key=f"riddle:{q.lower()}", made_for_kids=False)
        log(f"riddle ({src}): {q} -> {a}")
        render(meta, workdir, final)
    (workdir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.dry_run:
        log("dry run - not uploading.")
        return

    vid = upload(yt, final, meta)
    record_upload(history, meta, vid)


def record_upload(history, meta, vid):
    history.append({"time": dt.datetime.now(dt.timezone.utc).isoformat(), "title": meta["title"],
                    "format": meta.get("format", ""), "key": meta.get("key", ""), "keys": meta.get("keys", []),
                    "question": meta.get("question", ""), "video_id": vid})
    save_history(history)


def make_kids(workdir, final, history, fmt):
    """Kids video at 4K, falling back to 1080p if 4K fails. Returns meta or None."""
    global SCALE, W, H
    import traceback
    import kids
    base = SCALE
    scales = [base] + ([0.5] if base > 0.5 else [])
    try:
        for attempt, sc in enumerate(scales):
            SCALE, W, H = sc, int(2160 * sc), int(3840 * sc)
            wd = workdir if attempt == 0 else workdir / f"retry{attempt}"
            wd.mkdir(parents=True, exist_ok=True)
            try:
                pick = kids.make(sys.modules[__name__])
                meta = pick(wd, final, history, None if fmt == "kids" else fmt)
                log(f"kids video ({meta['format']}, {W}x{H}): {meta['title']}")
                return meta
            except Exception as e:
                log(f"kids video failed at {W}x{H}:", repr(e))
                traceback.print_exc()
        return None
    finally:
        SCALE, W, H = base, int(2160 * base), int(3840 * base)


if __name__ == "__main__":
    main()

"""
AI drama story Shorts (Urdu voice, Roman Urdu captions) for the "Daily videos" channel.
Hook title card -> 6 cinematic AI scenes with slow zoom, captions, narrator voice, dramatic music.
Stories are original (story_content.py); images come from Pollinations (free).
"""
import random
import time
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageFilter

from story_content import STORIES

M = None
W, H, FPS = 1080, 1920, 30
NARRATOR = "ur-PK-AsadNeural"
LOOK = ("cinematic 3D animated movie still, Pixar style, dramatic lighting, emotional, detailed, vertical "
        "composition, fully clothed, modest, family friendly, no text, no watermark")
XF = 0.4


def make(main_module):
    global M
    M = main_module
    return pick


def fetch_image(prompt, path, seed):
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(f"{prompt}, {LOOK}") +
           f"?width={W}&height={H}&nologo=true&safe=true&seed={seed}&model=flux")
    for attempt in range(6):
        try:
            r = requests.get(url, timeout=180, headers={"User-Agent": "story-bot/1.0"})
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                path.write_bytes(r.content)
                img = Image.open(path).convert("RGB")
                img = img.crop((0, 0, img.width, int(img.height * 0.955)))  # remove free-tier logo
                s = max(W / img.width, H / img.height)
                img = img.resize((int(img.width * s + 0.5), int(img.height * s + 0.5)), Image.LANCZOS)
                l, t = (img.width - W) // 2, (img.height - H) // 2
                img = img.crop((l, t, l + W, t + H)).filter(ImageFilter.UnsharpMask(2, 80, 2))
                img.save(path, quality=95)
                return True
            M.log(f"image attempt {attempt + 1}: HTTP {r.status_code}")
        except Exception as e:
            M.log(f"image attempt {attempt + 1} failed:", str(e)[:100])
        time.sleep(12 * (attempt + 1))
    return False


def caption_png(text, path, size=78):
    f = M.font(size, "Black")
    img = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lines = M.wrap(d, text, f, W - 140)[:3]
    y = (420 - len(lines) * int(size * 1.25)) // 2
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        d.text(((W - tw) / 2, y), ln, font=f, fill=(255, 226, 60) if i == 0 else (255, 255, 255),
               stroke_width=8, stroke_fill=(0, 0, 0))
        y += int(size * 1.25)
    img.save(path)


def hook_png(lines, path):
    """Big gold/red title like drama thumbnails, shown over the first scene."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill=(0, 0, 0, 90))
    y = 620
    for i, ln in enumerate(lines):
        f, wl, size = M.fit_text(ln, W - 100, 300, 170, "Black")
        for w in wl:
            tw = d.textlength(w, font=f)
            col = (255, 214, 64) if i == 0 else (239, 45, 45)
            d.text(((W - tw) / 2 + 8, y + 10), w, font=f, fill=(0, 0, 0, 160), stroke_width=12,
                   stroke_fill=(0, 0, 0, 160))
            d.text(((W - tw) / 2, y), w, font=f, fill=col, stroke_width=12, stroke_fill=(20, 10, 0))
            y += int(size * 1.1)
        y += 40
    img.save(path)


def pick(workdir, final, history, force_format=None):
    used = {h.get("key") for h in history}
    choices = [i for i in range(len(STORIES)) if f"story:{i}" not in used] or list(range(len(STORIES)))
    idx = random.choice(choices)
    st = STORIES[idx]
    seed = random.randint(1, 10**6)

    old_voice = M.VOICE
    M.VOICE = NARRATOR
    durs, imgs, caps, voices = [], [], [], []
    try:
        for i, (urdu, cap, prompt) in enumerate(st["scenes"]):
            img = workdir / f"s{i}.jpg"
            if not fetch_image(prompt.format(s=st["style"]), img, seed + i):
                if i == 0:
                    raise RuntimeError("first image failed")
                Image.open(imgs[-1]).transpose(Image.FLIP_LEFT_RIGHT).save(img)
            imgs.append(img)
            v = workdir / f"v{i}.mp3"
            dur = M.tts(urdu, v, max_len=7.5)
            voices.append(v if dur else None)
            durs.append(max(dur + 0.7, 4.0) + (1.6 if i == 0 else 0))  # first scene also carries the hook
            cp = workdir / f"c{i}.png"
            caption_png(cap, cp)
            caps.append(cp)
            time.sleep(4)
    finally:
        M.VOICE = old_voice
    hook = workdir / "hook.png"
    hook_png(st["thumb"], hook)

    # scene clips with slow zoom
    clips = []
    for i, (img, d) in enumerate(zip(imgs, durs)):
        frames = int((d + XF) * FPS)
        z = "min(zoom+0.0009,1.15)" if i % 2 == 0 else "if(eq(on,0),1.15,max(zoom-0.0009,1.0))"
        clip = workdir / f"k{i}.mp4"
        M.run([M.FFMPEG, "-y", "-i", str(img), "-vf",
               f"scale={W * 2}:{H * 2},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}"
               f":s={W}x{H}:fps={FPS},eq=contrast=1.05:saturation=1.12,format=yuv420p",
               "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(clip)])
        clips.append(clip)

    starts, t = [], 0.0
    for d in durs:
        starts.append(t)
        t += d
    total = t + XF

    cmd = [M.FFMPEG, "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    for c in caps:
        cmd += ["-i", str(c)]
    cmd += ["-i", str(hook)]
    n = len(clips)
    fc, prev = [], "[0:v]"
    for i in range(1, n):
        fc.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XF}:offset={starts[i]:.3f}[x{i}]")
        prev = f"[x{i}]"
    for i in range(n):
        s0 = starts[i] + (1.6 if i == 0 else 0.2)
        e0 = starts[i] + durs[i]
        fc.append(f"{prev}[{n + i}:v]overlay=0:{int(H * 0.66)}:enable='between(t,{s0:.2f},{e0:.2f})'[o{i}]")
        prev = f"[o{i}]"
    fc.append(f"{prev}[{2 * n}:v]overlay=0:0:enable='between(t,0,1.6)'[hk]")
    fc.append("[hk]format=yuv420p[vout]")

    fx = M.sfx(workdir)
    ai = 2 * n + 1
    labels = []
    events = [(fx["whoosh"], 0.0, 1.0), (fx["ding"], 1.5, 0.5)]
    for i, v in enumerate(voices):
        if v:
            events.append((v, starts[i] + (1.7 if i == 0 else 0.25), 1.8))
        if i:
            events.append((fx["whoosh"], starts[i] - 0.2, 0.5))
    for k, (src, at, vol) in enumerate(events):
        cmd += ["-i", str(src)]
        ms = int(at * 1000)
        fc.append(f"[{ai + k}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms},volume={vol}[e{k}]")
        labels.append(f"[e{k}]")
    music = workdir / "drama.wav"
    M.run([M.FFMPEG, "-y", "-f", "lavfi", "-i",
           f"aevalsrc='0.05*(sin(2*PI*110*t)+0.7*sin(2*PI*130.8*t)+0.6*sin(2*PI*164.8*t))"
           f"*(0.6+0.4*sin(2*PI*0.12*t))+0.03*sin(2*PI*55*t)':d={total + 1}", "-ar", "44100", "-ac", "2",
           str(music)])
    cmd += ["-i", str(music)]
    fc.append(f"[{ai + len(events)}:a]volume=0.9,afade=t=out:st={total - 1.5}:d=1.5[bed]")
    labels.append("[bed]")
    fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,alimiter=limit=0.95,"
              f"atrim=0:{total}[aout]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)]
    M.run(cmd)

    lesson = st["scenes"][-1][1]
    return {
        "format": "story", "key": f"story:{idx}", "made_for_kids": False, "channel": "story",
        "title": st["title"] + " #shorts",
        "description": (f"{st['title']}\n\n{lesson}\n\nEk nayi dil chhoo lene wali kahani! Poori video dekhein aur "
                        "comment mein batayein aap ko kaisi lagi. 👇\n\nRoz nayi kahani ke liye subscribe karein 🔔\n\n"
                        "#shorts #kahani #urdustory #aistory #moralstory"),
        "tags": ["urdu kahani", "hindi kahani", "moral stories", "ai story", "garib se ameer", "emotional story",
                 "urdu story", "hindi story", "sabaq amoz kahani", "kahaniyan", "ai drama", "story in urdu",
                 "billionaire story", "motivational story", "shorts"],
    }

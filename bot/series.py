"""Kismat Kahaniyan suspense series: 10 stories x 10 parts (~1 minute each, realistic AI images, Urdu voice)
plus one long "Poori Kahani" video per story (all 10 parts joined, 16:9, with chapters).

Every part ends on a cliffhanger and tells viewers what to search for to find the next part.
Images come from Cloudflare (story.fetch_image). When the free daily allowance is used up a QuotaError
stops the run; the bank job simply continues the next day from where it stopped.
"""
import json
import random

from PIL import Image, ImageDraw, ImageFilter

import story as ST
from series_content import SERIES

M = None
W, H, FPS = 1080, 1920, 30
HOOK = 2.2   # title card "NAME / PART x/10" over the first scene
END = 5.0    # end card "search ... Part x+1"
XF = 0.4


def setup(main_module):
    global M
    M = main_module
    ST.M = main_module


def end_png(lines, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill=(0, 0, 0, 150))
    y = 560
    for i, (ln, size, col) in enumerate(lines):
        f, wl, sz = M.fit_text(ln, W - 120, 420, size, "Black")
        for w in wl:
            tw = d.textlength(w, font=f)
            d.text(((W - tw) / 2, y), w, font=f, fill=col, stroke_width=10, stroke_fill=(10, 5, 0))
            y += int(sz * 1.15)
        y += 50
    img.save(path)


def part_meta(si, p):
    s = SERIES[si]
    n = len(s["parts"])
    part = s["parts"][p - 1]
    nxt = (f"👉 Agla part dekhne ke liye YouTube par search karein: \"{s['search']} Part {p + 1}\""
           if p < n else "✅ Kahani khatam! Poori kahani ek hi video mein hamare channel par dekhein.")
    plist = "\n".join(f"Part {k}: search \"{s['search']} Part {k}\"" for k in range(1, n + 1))
    return {
        "format": "series", "key": f"{s['id']}p{p:02d}", "made_for_kids": False, "channel": "story",
        "series": s["id"], "part": p,
        "title": f"{s['name']} | Part {p}/{n} 😱 Urdu Suspense Kahani #shorts"[:100],
        "description": (f"{s['name']} - Part {p}/{n}\n\n{part['title']}\n\n{nxt}\n\n{s['summary']}\n\n"
                        f"Saare parts:\n{plist}\n\nRoz nayi suspense kahani ke liye channel subscribe karein 🔔\n\n"
                        f"#shorts #kahani #urdustory #suspense #{s['tag']}"),
        "tags": [s["search"].lower(), f"{s['search'].lower()} part {p}", "urdu kahani", "suspense story urdu",
                 "urdu story", "kahaniyan", "suspense kahani", "mystery story urdu", "pakistani drama story",
                 "ai story", "hindi kahani", "kismat kahaniyan", "shorts"],
    }


def render_part(workdir, final, si, p):
    """Render part p (1-based) of series si. Returns meta (with timings for the long video)."""
    s = SERIES[si]
    n = len(s["parts"])
    part = s["parts"][p - 1]
    seed = sum(ord(c) * 131 for c in s["id"]) * 100 + p * 7  # stable between runs
    old_voice = M.VOICE
    M.VOICE = ST.NARRATOR
    imgs, durs, caps, voices = [], [], [], []
    try:
        for i, (urdu, cap, prompt) in enumerate(part["scenes"]):
            img = workdir / f"s{i}.jpg"
            full = prompt.format(**s["cast"]) + f", {s['look']}"
            ok = ST.fetch_image(full, img, seed + i)  # raises ST.QuotaError when the free day is used up
            if not ok:
                if i == 0:
                    raise RuntimeError("first image failed")
                Image.open(imgs[-1]).transpose(Image.FLIP_LEFT_RIGHT).save(img)
            imgs.append(img)
            v = workdir / f"v{i}.mp3"
            dur = M.tts(urdu, v, max_len=9.0)
            voices.append(v if dur else None)
            durs.append(max(dur + 1.3, 7.6) + (HOOK if i == 0 else 0))  # ~1 minute per part
            cp = workdir / f"c{i}.png"
            ST.caption_png(cap, cp)
            caps.append(cp)
        # end card scene: last picture, blurred and dark, with the "search next part" card
        endimg = workdir / "end.jpg"
        Image.open(imgs[-1]).convert("RGB").filter(ImageFilter.GaussianBlur(18)).save(endimg, quality=92)
        if p < n:
            lines = [("AAGE KYA HUA?", 150, (255, 214, 64)), ("YouTube par search karein:", 80, (255, 255, 255)),
                     (f"{s['search']} Part {p + 1}", 120, (255, 80, 80)), ("Channel subscribe karein", 70, (255, 255, 255))]
            end_voice = f"آگے کیا ہوا؟ اگلا حصہ دیکھنے کے لیے یوٹیوب پر سرچ کریں: {s['search_ur']}، پارٹ {p + 1}۔"
        else:
            lines = [("KAHANI KHATAM", 150, (255, 214, 64)), ("Poori kahani ek video mein", 85, (255, 255, 255)),
                     ("hamare channel par dekhein", 85, (255, 255, 255)), ("Subscribe karein", 80, (255, 80, 80))]
            end_voice = "کہانی ختم۔ پوری کہانی ایک ہی ویڈیو میں ہمارے چینل پر دیکھیں، اور چینل سبسکرائب کریں۔"
        endcard = workdir / "endcard.png"
        end_png(lines, endcard)
        ev = workdir / "vend.mp3"
        edur = M.tts(end_voice, ev, max_len=END - 0.3)
    finally:
        M.VOICE = old_voice
    hook = workdir / "hook.png"
    ST.hook_png([s["name"].upper(), f"PART {p}/{n}"], hook)

    all_imgs = imgs + [endimg]
    all_durs = durs + [END]
    clips = []
    for i, (img, d) in enumerate(zip(all_imgs, all_durs)):
        frames = int((d + XF) * FPS)
        z = "min(zoom+0.0009,1.15)" if i % 2 == 0 else "if(eq(on,0),1.15,max(zoom-0.0009,1.0))"
        clip = workdir / f"k{i}.mp4"
        M.run([M.FFMPEG, "-y", "-i", str(img), "-vf",
               f"scale={W * 2}:{H * 2},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}"
               f":s={W}x{H}:fps={FPS},eq=contrast=1.05:saturation=1.1,format=yuv420p",
               "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(clip)])
        clips.append(clip)
    starts, t = [], 0.0
    for d in all_durs:
        starts.append(t)
        t += d
    total = t + XF
    ns = len(imgs)  # story scenes (end card is clip index ns)

    cmd = [M.FFMPEG, "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    for c in caps:
        cmd += ["-i", str(c)]
    cmd += ["-i", str(hook), "-i", str(endcard)]
    nc = len(clips)
    fc, prev = [], "[0:v]"
    for i in range(1, nc):
        fc.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XF}:offset={starts[i]:.3f}[x{i}]")
        prev = f"[x{i}]"
    for i in range(ns):
        s0 = starts[i] + (HOOK if i == 0 else 0.2)
        e0 = starts[i] + all_durs[i]
        fc.append(f"{prev}[{nc + i}:v]overlay=0:{int(H * 0.66)}:enable='between(t,{s0:.2f},{e0:.2f})'[o{i}]")
        prev = f"[o{i}]"
    fc.append(f"{prev}[{nc + ns}:v]overlay=0:0:enable='between(t,0,{HOOK})'[hk]")
    fc.append(f"[hk][{nc + ns + 1}:v]overlay=0:0:enable='gte(t,{starts[ns] + 0.1:.2f})'[ed]")
    fc.append("[ed]format=yuv420p[vout]")

    fx = M.sfx(workdir)
    ai = nc + ns + 2
    labels = []
    events = [(fx["whoosh"], 0.0, 1.0), (fx["ding"], HOOK - 0.6, 0.5)]
    for i, v in enumerate(voices):
        if v:
            events.append((v, starts[i] + (HOOK + 0.1 if i == 0 else 0.25), 1.8))
        if i:
            events.append((fx["whoosh"], starts[i] - 0.2, 0.45))
    events.append((fx["ding"], starts[ns], 0.6))
    if edur:
        events.append((ev, starts[ns] + 0.3, 1.8))
    for k, (src, at, vol) in enumerate(events):
        cmd += ["-i", str(src)]
        ms = int(at * 1000)
        fc.append(f"[{ai + k}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms},volume={vol}[e{k}]")
        labels.append(f"[e{k}]")
    music = workdir / "suspense.wav"
    M.run([M.FFMPEG, "-y", "-f", "lavfi", "-i",
           f"aevalsrc='0.045*(sin(2*PI*73.4*t)+0.6*sin(2*PI*87.3*t)+0.5*sin(2*PI*110*t))"
           f"*(0.55+0.45*sin(2*PI*0.09*t))+0.02*sin(2*PI*36.7*t)':d={total + 1}", "-ar", "44100", "-ac", "2",
           str(music)])
    cmd += ["-i", str(music)]
    fc.append(f"[{ai + len(events)}:a]volume=0.9,afade=t=out:st={total - 1.5}:d=1.5[bed]")
    labels.append("[bed]")
    fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,alimiter=limit=0.95,"
              f"atrim=0:{total}[aout]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", str(final)]
    M.run(cmd)
    meta = part_meta(si, p)
    meta.update(hook_len=HOOK, end_start=round(starts[ns], 3), total=round(total, 3))
    return meta


def build_long(workdir, final, si, parts):
    """parts: list of (mp4_path, meta) for parts 1..n in order. Joins them into one 16:9 video:
    title card, then each part without its title card and (except the last) without its end card."""
    s = SERIES[si]
    LW, LH = 1920, 1080
    segs = []
    title = workdir / "title.png"
    ST.hook_png([s["name"].upper(), "POORI KAHANI"], title)
    first_img = workdir / "title_bg.jpg"
    M.run([M.FFMPEG, "-y", "-ss", "3", "-i", str(parts[0][0]), "-frames:v", "1", str(first_img)])
    tclip = workdir / "seg_title.mp4"
    M.run([M.FFMPEG, "-y", "-loop", "1", "-t", "4", "-i", str(first_img), "-loop", "1", "-t", "4", "-i", str(title),
           "-f", "lavfi", "-t", "4", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex",
           "[0:v]scale=1080:1920,setsar=1[a];[a][1:v]overlay=0:0,format=yuv420p,fps=30[v]",
           "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
           "-c:a", "aac", "-b:a", "192k", "-ar", "44100", str(tclip)])
    segs.append(tclip)
    chapters, t = ["0:00 Shuruaat"], 4.0
    for k, (mp4, meta) in enumerate(parts):
        a = meta["hook_len"]
        b = meta["total"] if k == len(parts) - 1 else meta["end_start"]
        seg = workdir / f"seg{k + 1:02d}.mp4"
        M.run([M.FFMPEG, "-y", "-ss", f"{a:.2f}", "-to", f"{b:.2f}", "-i", str(mp4), "-vf", "fps=30,format=yuv420p",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
               str(seg)])
        chapters.append(f"{int(t // 60)}:{int(t % 60):02d} Part {k + 1}: {s['parts'][k]['title']}")
        t += b - a
    lst = workdir / "segs.txt"
    lst.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in segs +
                           [workdir / f"seg{k + 1:02d}.mp4" for k in range(len(parts))]), encoding="utf-8")
    vertical = workdir / "long_vertical.mp4"
    M.run([M.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(vertical)])
    fc = (f"[0:v]split[a][b];[a]scale={LW // 4}:{LH // 4}:force_original_aspect_ratio=increase,"
          f"crop={LW // 4}:{LH // 4},boxblur=12:3,scale={LW}:{LH},eq=brightness=-0.08[bg];"
          f"[b]scale=-2:{LH}[fg];[bg][fg]overlay=(W-w)/2:0,format=yuv420p[v]")
    M.run([M.FFMPEG, "-y", "-i", str(vertical), "-filter_complex", fc, "-map", "[v]", "-map", "0:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", str(final)])
    mins = int(t // 60)
    return {
        "format": "series_long", "key": f"{s['id']}long", "made_for_kids": False, "channel": "story",
        "series": s["id"],
        "title": f"{s['name']} | Poori Kahani (Part 1-{len(parts)}) 😱 Urdu Suspense Story"[:100],
        "description": (f"{s['name']} - poori kahani ek hi video mein ({mins} minute).\n\n{s['summary']}\n\n"
                        + "\n".join(chapters) +
                        "\n\nAisi aur suspense kahaniyon ke liye channel subscribe karein 🔔\n\n"
                        f"#kahani #urdustory #suspense #{s['tag']} #fullstory"),
        "tags": [s["search"].lower(), f"{s['search'].lower()} full story", f"{s['search'].lower()} poori kahani",
                 "urdu kahani", "suspense story urdu", "urdu story full", "kahaniyan", "mystery story urdu",
                 "pakistani story", "hindi kahani", "kismat kahaniyan", "full story"],
    }

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
END = 8.0    # end card: subscribe + share to see the next part, and what to search
XF = 0.4
# the user's rule: every part must end by telling viewers to SUBSCRIBE and SHARE to watch the next part
CTA_LINES = [("AAGE KYA HUA?", 140, (255, 214, 64)),
             ("Agla part dekhne ke liye", 80, (255, 255, 255)),
             ("Channel SUBSCRIBE zaroor karein", 98, (255, 60, 60)),
             ("aur video SHARE karein!", 98, (255, 214, 64))]
CTA_VOICE = "اگلا پارٹ دیکھنے کے لیے چینل کو سبسکرائب ضرور کریں اور ویڈیو کو شیئر کریں۔"


def setup(main_module):
    global M
    M = main_module
    ST.M = main_module


SAFE_TOP, SAFE_BOTTOM, SAFE_SIDE = 300, 1340, 120  # Shorts UI covers the bottom ~30% and the right edge


def end_png(lines, path):
    """End card text kept inside the Shorts safe zone (y 300-1340, 120 px side margins); shrinks to fit."""
    scale = 1.0
    while True:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, 150))
        y = SAFE_TOP
        for ln, size, col in lines:
            f, wl, sz = M.fit_text(ln, W - 2 * SAFE_SIDE, 400, int(size * scale), "Black")
            for w in wl:
                tw = d.textlength(w, font=f)
                d.text(((W - tw) / 2, y), w, font=f, fill=col, stroke_width=max(5, sz // 12), stroke_fill=(10, 5, 0))
                y += int(sz * 1.08)
            y += int(28 * scale)
        if y <= SAFE_BOTTOM or scale < 0.5:
            break
        scale *= 0.92
    img.save(path)


def thumb_card(lines, path, w=W, h=H, top=None):
    """Thumbnail-style title: dark vignette, red frame, huge gold / red / white words (used as the first frame
    of every Short, which YouTube shows as its cover, and for the long video thumbnail)."""
    # smooth dark vignette: light in the middle, darker towards the edges
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse([-w // 4, -h // 6, w + w // 4, h + h // 6], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(min(w, h) // 6))
    alpha = m.point(lambda v: int(205 - v * 0.55))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.putalpha(alpha)
    d = ImageDraw.Draw(img)
    bw = max(8, w // 70)
    d.rectangle([bw, bw, w - bw, h - bw], outline=(220, 30, 30, 255), width=bw)
    y = top if top is not None else int(h * 0.30)
    for ln, size, col in lines:
        f, wl, sz = M.fit_text(ln, w - 2 * w // 12, int(h * 0.3), size, "Black")
        for word in wl:
            tw = d.textlength(word, font=f)
            d.text(((w - tw) / 2 + sz // 14, y + sz // 12), word, font=f, fill=(0, 0, 0, 200),
                   stroke_width=max(6, sz // 11), stroke_fill=(0, 0, 0, 200))
            d.text(((w - tw) / 2, y), word, font=f, fill=col, stroke_width=max(6, sz // 11), stroke_fill=(15, 5, 0))
            y += int(sz * 1.08)
        y += int(h * 0.02)
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
            lines = CTA_LINES + [(f"Search: {s['search']} Part {p + 1}", 62, (255, 255, 255))]
            end_voice = (f"آگے کیا ہوا؟ {CTA_VOICE} اگلا حصہ دیکھنے کے لیے سرچ کریں: {s['search_ur']}، پارٹ {p + 1}۔")
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
    thumb_card([(s["name"].upper(), 165, (255, 214, 64)), (f"PART {p}/{n}", 175, (255, 45, 45)),
                (part["title"].upper() + "?" if p < n else "AAKHRI PART!", 100, (255, 255, 255))], hook)

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
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-threads", "2", "-x264-params", "rc-lookahead=10", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", str(final)]
    M.run(cmd)
    meta = part_meta(si, p)
    meta.update(hook_len=HOOK, end_start=round(starts[ns], 3), total=round(total, 3), cta=True)
    return meta


def append_cta(src, out, workdir):
    """For parts rendered before the subscribe/share rule: add a short end card (blurred last frame, big
    SUBSCRIBE + SHARE text, Urdu voice) after the video. Uses no Cloudflare images."""
    import pathlib
    workdir = pathlib.Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    last = workdir / "last.jpg"
    M.run([M.FFMPEG, "-y", "-sseof", "-0.3", "-i", str(src), "-frames:v", "1", "-update", "1", str(last)])
    Image.open(last).convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(18)).save(last, quality=92)
    card = workdir / "cta.png"
    end_png(CTA_LINES, card)
    old_voice = M.VOICE
    M.VOICE = ST.NARRATOR
    try:
        v = workdir / "cta.mp3"
        vd = M.tts(CTA_VOICE, v, max_len=5.5)
    finally:
        M.VOICE = old_voice
    dur = max(vd + 1.2, 5.0)
    fx = M.sfx(workdir)
    clip = workdir / "cta.mp4"
    cmd = [M.FFMPEG, "-y", "-loop", "1", "-t", f"{dur:.2f}", "-i", str(last), "-i", str(card), "-i", str(fx["ding"])]
    if vd:
        cmd += ["-i", str(v)]
    fc = (f"[0:v]scale={W}:{H},fps={FPS}[b];[b][1:v]overlay=0:0,format=yuv420p[v];"
          "[2:a]aresample=44100,aformat=channel_layouts=stereo,volume=0.6[d]")
    if vd:
        fc += ";[3:a]aresample=44100,aformat=channel_layouts=stereo,adelay=300|300,volume=1.8[n];" \
              "[d][n]amix=inputs=2:duration=longest:normalize=0[a]"
    else:
        fc += ";[d]anull[a]"
    M.run(cmd + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS),
                 "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", str(clip)])
    # join (re-encode so both pieces match exactly)
    M.run([M.FFMPEG, "-y", "-i", str(src), "-i", str(clip), "-filter_complex",
           f"[0:v]scale={W}:{H},fps={FPS},format=yuv420p,setsar=1[v0];[1:v]setsar=1[v1];"
           "[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];[1:a]aresample=44100[a1];"
           "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    return out


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
    # thumbnail for the long video: a dramatic frame from part 1 + big suspense words
    frame = workdir / "thumb_frame.jpg"
    M.run([M.FFMPEG, "-y", "-ss", f"{parts[0][1]['hook_len'] + 9:.1f}", "-i", str(parts[0][0]), "-frames:v", "1",
           str(frame)])
    bg = Image.open(frame).convert("RGB")
    bg = bg.crop((0, (bg.height - bg.width * 9 // 16) // 2, bg.width, (bg.height + bg.width * 9 // 16) // 2))
    bg = bg.resize((1280, 720), Image.LANCZOS)
    card = workdir / "thumb_card.png"
    thumb_card([(s["name"].upper(), 120, (255, 214, 64)), ("POORI KAHANI", 105, (255, 45, 45)),
                (f"PART 1-{len(parts)}", 70, (255, 255, 255))], card, 1280, 720, top=150)
    bg.paste(Image.open(card), (0, 0), Image.open(card))
    bg.save(final.with_suffix(".jpg"), quality=92)
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

"""~8 minute landscape videos for the Islamic channel (2 a week).

Word-for-word safety: these videos use ONLY content that the Shorts already use and that is checked:
  - Allah ke 99 Naam: Arabic from deen_content.NAMES, each one checked against the standard list in bot/deen_verified.json
  - Masnoon Duaen: Arabic ONLY from bot/deen_verified.json (Quran text / Hisn al-Muslim)
Nothing new is written here: the voice only says the Urdu title / meaning already in deen_content,
plus fixed intro / outro lines that contain no Quran or hadith text. No music, no pictures of people.
"""
import json
import pathlib
import random

from PIL import Image

import deen
from deen_content import DUAS, NAMES

TARGET = 480.0  # seconds (8 minutes)
GAP = 0.55

# upload order, then it starts again
PARTS = [
    ("naam", 0, 33), ("dua", "daily"), ("naam", 33, 66), ("dua", "quran"), ("naam", 66, 99),
]
DUA_GROUPS = {
    "daily": ("Roz Ki 18 Masnoon Duaen", "روز کی اٹھارہ مسنون دعائیں",
              [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 20, 28, 29, 30, 31, 35, 32]),
    "quran": ("Qurani Duaen aur Azkaar (18)", "قرآنی دعائیں اور اذکار",
              [10, 11, 12, 13, 14, 15, 17, 18, 22, 23, 24, 25, 26, 19, 21, 27, 33, 34]),
}


def _check_verified(kind, ids):
    """Refuse to make the video if any item is not in the verified list."""
    v = deen.VERIFIED
    for i in ids:
        if kind == "naam":
            ok = v["names"].get(str(i), {})
            # must match the standard list (Tirmidhi) letter by letter, or be spelled exactly as in the Quran
            if not (ok.get("letters_match_list") or ok.get("found_in_quran")):
                raise RuntimeError(f"naam {i + 1} is not verified - refusing to make the video")
        else:
            if str(i) not in v["duas"]:
                raise RuntimeError(f"dua {i} is not verified - refusing to make the video")


def _items(part):
    """Each item: dict with everything render() needs + the voice lines."""
    out = []
    if part[0] == "naam":
        _, a, b = part
        ids = list(range(a, b))
        _check_verified("naam", ids)
        for i in ids:
            ar, roman, mean_r, mean_u = NAMES[i]
            p = deen.plain(ar)
            out.append(dict(
                head="ALLAH KE 99 NAAM", icon="2728", sub=f"Naam number {i + 1} / 99", arabic=ar, ar_size=420,
                translit=roman, label="MATLAB", meaning=mean_r, source="",
                voice=[f"نام نمبر {i + 1}: {p}", f"اس کا مطلب ہے: {mean_u}", f"{p}، یعنی {mean_u}"], mean_idx=1,
                chapter=f"{i + 1}. {roman} - {mean_r}"))
    else:
        title_r, title_u, ids = DUA_GROUPS[part[1]]
        _check_verified("dua", ids)
        for i in ids:
            t_r, t_u, _typed, tr, mean_r, mean_u, src = DUAS[i]
            out.append(dict(
                head="MASNOON DUA", icon="1f932", sub=t_r, arabic=deen.VERIFIED["duas"][str(i)]["arabic"],
                ar_size=230, translit=tr, label="TARJUMA", meaning=mean_r, source=f"Hawala: {src}",
                voice=[t_u, f"اس کا ترجمہ ہے: {mean_u}"], mean_idx=1, chapter=f"{t_r} ({src})"))
    return out


def _intro_outro(part, items):
    if part[0] == "naam":
        _, a, b = part
        intro = f"آئیے اللہ تعالیٰ کے خوبصورت نام سیکھتے ہیں، نام نمبر {a + 1} سے {b} تک، اردو مطلب کے ساتھ۔"
    else:
        intro = f"آئیے سیکھتے ہیں: {DUA_GROUPS[part[1]][1]}، اردو ترجمہ اور حوالے کے ساتھ۔"
    outro = "یہ ویڈیو اپنے گھر والوں کے ساتھ شیئر کریں اور چینل سبسکرائب کریں۔"
    items[0]["voice"] = [intro] + items[0]["voice"]
    items[0]["mean_idx"] += 1
    items[-1]["voice"] = items[-1]["voice"] + [outro]
    items[-1]["cta"] = True


def next_part(history):
    done = [h for h in history if h.get("format") == "deen_long"]
    return PARTS[len(done) % len(PARTS)]


def make_long(M, workdir, final, history):
    deen.make(M)
    part = next_part(history)
    items = _items(part)
    _intro_outro(part, items)

    # 1) measure the voice so the whole video comes out ~8 minutes:
    #    the left-over time is spread as calm pauses after each item (time to read along)
    durs = []
    for k, it in enumerate(items):
        d = 0.6
        for j, line in enumerate(it["voice"]):
            d += (M.tts(line, workdir / f"m{k}_{j}.mp3", 30.0) or 1.5) + GAP
        durs.append(d)
    spare = TARGET - sum(durs)
    tail = max(2.6, min(18.0, spare / len(items)))
    M.log(f"deen long: {len(items)} items, voice {sum(durs):.0f}s, pause {tail:.1f}s each")

    # 2) one clip per item (same colours all through), joined, then made 16:9
    pal = random.choice(deen.PALETTES)
    clips, chapters, t = [], [], 0.0
    for k, it in enumerate(items):
        cw = workdir / f"c{k:03d}"
        cw.mkdir(parents=True, exist_ok=True)
        clip = workdir / f"c{k:03d}.mp4"
        deen.render(cw, clip, it["head"], it["icon"], it["sub"], it["arabic"], M.S(it["ar_size"]), it["translit"],
                    it["label"], it["meaning"], it["source"], it["voice"], cta=it.get("cta", False),
                    mean_idx=it["mean_idx"], pal=pal, tail=tail + (2.6 if it.get("cta") else 0))
        chapters.append(f"{int(t // 60)}:{int(t % 60):02d} {it['chapter']}")
        t += M.probe_duration(clip)
        clips.append(clip)
    lst = workdir / "list.txt"
    lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    vertical = workdir / "vertical.mp4"
    M.run([M.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(vertical)])
    LW, LH = M.S(3840), M.S(2160)
    fc = (f"[0:v]split[a][b];[a]scale={LW // 4}:{LH // 4}:force_original_aspect_ratio=increase,"
          f"crop={LW // 4}:{LH // 4},boxblur=12:3,scale={LW}:{LH},eq=brightness=-0.08[bg];"
          f"[b]scale=-2:{LH}[fg];[bg][fg]overlay=(W-w)/2:0,format=yuv420p[v]")
    M.run([M.FFMPEG, "-y", "-i", str(vertical), "-filter_complex", fc, "-map", "[v]", "-map", "0:a",
           "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-threads", "4", "-c:a", "copy",
           "-movflags", "+faststart", str(final)])

    thumbnail(M, part, items, pal, final.with_suffix(".jpg"), workdir)
    return meta(part, items, chapters, t)


# ------------------------------------------------------------------ thumbnail
def thumbnail(M, part, items, pal, path, workdir):
    """1280x720: dark green/gold, big Arabic of the first item, 3 big words people click on."""
    w, h = 1280, 720
    top, bot, gold = pal
    img = Image.new("RGB", (w, h), bot)
    px = img.load()
    for y in range(h):  # vertical gradient
        k = y / h
        c = tuple(int(top[i] * (1 - k) + bot[i] * k) for i in range(3))
        for x in range(w):
            px[x, y] = c
    img = img.convert("RGBA")
    d = deen.ImageDraw.Draw(img)
    d.rectangle([10, 10, w - 10, h - 10], outline=gold + (255,), width=10)
    # soft gold glow behind the Arabic on the right
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    deen.ImageDraw.Draw(glow).ellipse([w - 600, h // 2 - 280, w - 40, h // 2 + 280], fill=gold + (70,))
    from PIL import ImageFilter
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(40)))
    d = deen.ImageDraw.Draw(img)
    try:
        # Arabic of the first name / dua, verified text only
        ar = deen.arabic_block(items[0]["arabic"], 560, 420, 200 if part[0] == "naam" else 90, (255, 250, 236))
        img.paste(ar, (w - 40 - ar.width, (h - ar.height) // 2), ar)
    except Exception as e:  # never stop the upload for the thumbnail
        M.log("thumbnail arabic skipped:", e)
    if part[0] == "naam":
        _, a, b = part
        lines = [("ALLAH KE", 92, (255, 255, 255)), ("99 NAAM", 120, gold), (f"NAAM {a + 1}-{b}", 64, (255, 255, 255)),
                 ("Urdu Matlab", 54, gold)]
    else:
        name = DUA_GROUPS[part[1]][0]
        lines = [("MASNOON", 96, (255, 255, 255)), ("DUAEN", 120, gold), ({"daily": "ROZ KI 18 DUAEN", "quran": "QURANI DUAEN"}[part[1]], 60, (255, 255, 255)),
                 ("Tarjuma + Hawala", 50, gold)]
    fitted = [(M.fit_text(text, 640, 200, size, "Black"), col) for text, size, col in lines]
    total = sum(len(wl) * int(sz * 1.1) + 12 for (f, wl, sz), col in fitted)
    y = (h - total) // 2
    for (f, wl, sz), col in fitted:
        for word in wl:
            d.text((60, y), word, font=f, fill=col, stroke_width=max(4, sz // 12), stroke_fill=(0, 0, 0))
            y += int(sz * 1.1)
        y += 12
    img.convert("RGB").save(path, quality=92)
    M.log("thumbnail ready:", path.name)


def meta(part, items, chapters, t):
    mins = round(t / 60)
    chap = "\n".join(chapters)
    if part[0] == "naam":
        _, a, b = part
        k = a // 33 + 1
        title = f"Allah Ke 99 Naam (Part {k}/3) | Naam {a + 1}-{b} Urdu Matlab Ke Saath 🤍 Asma ul Husna"
        desc = (f"Allah Ta'ala ke 99 khoobsurat naam - naam number {a + 1} se {b} tak, har naam ka Urdu matlab "
                f"({mins} minute).\n\nHar naam ke Arabic alfaaz Asma-ul-Husna ki standard fehrist (Tirmidhi) se harf-ba-harf mila kar check kiye gaye hain.\n\n{chap}\n\n"
                "Ye video apne ghar walon ko share karein aur channel subscribe karein 🤍\n\n"
                "#allah #asmaulhusna #99namesofallah #islam #urdu")
        tags = ["allah ke 99 naam", "asma ul husna", "99 names of allah", "allah ke 99 naam urdu tarjuma ke sath",
                "allah names with meaning in urdu", "asma ul husna with urdu translation", "allah ke naam",
                "islamic video urdu", f"allah ke 99 naam part {k}"]
    else:
        name, _u, ids = DUA_GROUPS[part[1]]
        title = f"{name} 🤲 Arabic, Urdu Tarjuma aur Hawala Ke Saath"
        desc = (f"{name} - har dua Arabic mein, Urdu tarjume aur hawale ke saath ({mins} minute).\n\n"
                f"Arabic alfaaz Quran-e-Pak aur Hisn al-Muslim se mila kar check kiye gaye hain.\n\n{chap}\n\n"
                "Ye duaen yaad karein aur apne ghar walon ko share karein 🤲\n\n#dua #masnoondua #islam #urdu")
        tags = ["masnoon duain", "masnoon dua", "dua in urdu", "daily duas in urdu", "roz ki duain",
                "qurani duain", "dua with urdu translation", "islamic video urdu", "hisnul muslim urdu"]
    key = f"long:{part[0]}:{part[1]}"
    return {"format": "deen_long", "key": key, "keys": [], "title": title[:100], "description": desc,
            "tags": tags, "made_for_kids": False, "channel": "deen", "long": True}

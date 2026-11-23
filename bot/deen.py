"""Islamic Urdu Shorts (Khurram Shahzad channel): Allah ke 99 Naam and Masnoon Duaen.

Rules: Arabic is drawn with a real text-shaping engine (raqm) or the video is NOT made; the voice reads
only Urdu (no synthetic recitation of Arabic); no music; no pictures of people.
"""
import glob
import os
import random
import re

from PIL import Image, ImageDraw, ImageFont, features

import kids
from deen_content import DUAS, NAMES

M = None
VOICE = "ur-PK-AsadNeural"
PALETTES = [  # top, bottom, accent (gold)
    ((6, 78, 59), (2, 24, 18), (234, 196, 88)),
    ((15, 40, 71), (3, 9, 26), (234, 196, 88)),
    ((40, 30, 80), (10, 8, 30), (234, 196, 88)),
    ((19, 78, 74), (3, 26, 28), (234, 196, 88)),
]
HARAKAT = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")
AR_FONTS = [os.getenv("ARABIC_FONT", "")] + sorted(glob.glob("/usr/share/fonts/**/Amiri-Regular.ttf", recursive=True)) \
    + sorted(glob.glob("/usr/share/fonts/**/NotoNaskhArabic-Regular.ttf", recursive=True)) \
    + ["C:/Windows/Fonts/trado.ttf", "C:/Windows/Fonts/arial.ttf"]


def make(main_module):
    global M
    M = main_module
    kids.M = main_module
    kids.STYLE.update(voice=VOICE)
    return pick


# ------------------------------------------------------------------ text helpers
def _ar_font(size):
    path = next((p for p in AR_FONTS if p and os.path.exists(p)), None)
    if not path:
        raise RuntimeError("no Arabic font found")
    if features.check("raqm"):
        return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM), True
    if os.getenv("DEEN_ALLOW_NO_RAQM") == "1":  # local layout preview only, Arabic will look wrong
        return ImageFont.truetype(path, size), False
    raise RuntimeError("Arabic text shaping (raqm) is not available - refusing to render broken Arabic")


def arabic_block(text, w, h, start, color):
    """Transparent layer with centred, correctly shaped right-to-left Arabic, wrapped to fit."""
    size = start
    while True:
        f, raqm = _ar_font(size)
        kw = {"direction": "rtl", "language": "ar"} if raqm else {}
        lines, cur = [], ""
        for word in text.split():
            test = (cur + " " + word).strip()
            if cur and f.getlength(test, **kw) > w:
                lines.append(cur)
                cur = word
            else:
                cur = test
        lines.append(cur)
        lh = int(size * 1.75)
        if len(lines) * lh <= h or size <= M.S(70):
            break
        size = int(size * 0.92)
    img = Image.new("RGBA", (w, max(lh * len(lines), lh)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for k, ln in enumerate(lines):
        d.text((w / 2, k * lh + lh / 2), ln, font=f, fill=color, anchor="mm", **kw)
    return img


def latin_block(text, w, h, start, color, weight="ExtraBold", stroke=0):
    f, lines, size = M.fit_text(text, w, h, start, weight=weight)
    img = Image.new("RGBA", (w, int(len(lines) * size * 1.18) + M.S(20)), (0, 0, 0, 0))
    M.draw_center_lines(img, lines, f, size, 0, color, stroke=stroke, stroke_fill=(0, 0, 0))
    return img


def card(layer, w, fill, pad_y):
    c, pad = M.rounded_card(w, layer.height + pad_y * 2, M.S(70), fill)
    c.paste(layer, (pad + (w - layer.width) // 2, pad + pad_y), layer)
    return c


def header(text, icon_code, workdir):
    ban = kids.text_banner(text, M.S(120), (255, 255, 255), (20, 40, 30))
    icon = kids.emoji(icon_code, M.S(200), workdir)
    out = Image.new("RGBA", (ban.width + icon.width + M.S(20), max(ban.height, icon.height)), (0, 0, 0, 0))
    out.paste(icon, (0, (out.height - icon.height) // 2), icon)
    out.paste(ban, (icon.width + M.S(20), (out.height - ban.height) // 2), ban)
    return out


def plain(ar):
    return HARAKAT.sub("", ar).replace("ٱ", "ا")


# ------------------------------------------------------------------ video
class Quiet(kids.Scene):
    """No music bed and no sound effects: only the Urdu voice."""

    def mix(self, silent, final_path):
        cmd = [M.FFMPEG, "-y", "-i", str(silent)]
        fc, labels = [], []
        for i, (src, at, vol) in enumerate(self.events):
            cmd += ["-i", str(src)]
            ms = int(at * 1000)
            fc.append(f"[{i + 1}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms},volume={vol}[e{i}]")
            labels.append(f"[e{i}]")
        cmd += ["-f", "lavfi", "-t", str(M.D), "-i", "anullsrc=r=44100:cl=stereo"]
        labels.append(f"[{len(self.events) + 1}:a]")
        fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
                  f"alimiter=limit=0.95,atrim=0:{M.D}[aout]")
        cmd += ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[aout]", "-t", str(M.D),
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final_path)]
        M.run(cmd)


def render(workdir, final, head_text, icon, sub, arabic, ar_size, translit, label, meaning, source, voice_lines):
    pal = random.choice(PALETTES)
    gold = pal[2]
    M.D = 30.0  # temporary; set from the voice below
    sc = Quiet(workdir, pal)
    t, starts = 0.6, []
    for k, line in enumerate(voice_lines):
        starts.append(t)
        dur = sc.say(line, t, f"v{k}", max_len=14.0, vol=1.9) or 1.5
        t += dur + 0.55
    M.D = round(max(t + 2.6, 12.0), 2)
    cta_t = M.D - 2.6

    W = M.W - M.S(240)
    head = header(head_text, icon, workdir)
    subl = latin_block(sub, W, M.S(330), M.S(120), (255, 255, 255), weight="Black", stroke=M.S(6))
    ar = card(arabic_block(arabic, W - M.S(160), M.S(1050), ar_size, (18, 52, 38)), W, (255, 250, 236, 255), M.S(70))
    tr = latin_block(translit, W - M.S(40), M.S(380), M.S(92), gold, weight="SemiBold")
    lab = latin_block(label, W, M.S(140), M.S(90), gold, weight="Black")
    mean = card(latin_block(meaning, W - M.S(160), M.S(820), M.S(118), (255, 255, 255)), W, (0, 0, 0, 120), M.S(60))
    src = latin_block(source, W, M.S(120), M.S(72), (230, 230, 230), weight="SemiBold") if source else None
    cta = kids.text_banner("Share karein  •  Subscribe karein", M.S(84), (255, 255, 255), (20, 40, 30))

    # vertical layout from the real heights
    y = M.S(330)
    pos = {}
    for name, layer, gap in (("head", head, 60), ("sub", subl, 70), ("ar", ar, 30), ("tr", tr, 70),
                             ("lab", lab, 10), ("mean", mean, 40), ("src", src, 0)):
        if layer is None:
            continue
        pos[name] = y + layer.height / 2
        y += layer.height + M.S(gap)
    bottom = M.H - M.S(420)
    if y > bottom:  # squeeze everything a bit if it is too tall
        k = (bottom - M.S(330)) / (y - M.S(330))
        pos = {n: M.S(330) + (v - M.S(330)) * k for n, v in pos.items()}
    else:  # keep the header on top and centre the rest in the free space
        shift = (bottom - y) / 2
        pos = {n: v + (shift if n != "head" else 0) for n, v in pos.items()}
    t_mean = starts[-2] if len(starts) >= 2 else 2.0

    def draw(t):
        f, d = sc.base_frame(t)
        sc.paste(f, head, M.W / 2, pos["head"], M.ease_out_back(t / 0.5))
        sc.paste(f, subl, M.W / 2, pos["sub"], alpha=M.ease_out((t - 0.3) / 0.5))
        sc.paste(f, ar, M.W / 2, pos["ar"], 0.9 + 0.1 * M.ease_out_back((t - 0.6) / 0.6), alpha=M.ease_out((t - 0.6) / 0.5))
        sc.paste(f, tr, M.W / 2, pos["tr"], alpha=M.ease_out((t - 1.2) / 0.6))
        sc.paste(f, lab, M.W / 2, pos["lab"], alpha=M.ease_out((t - t_mean + 0.3) / 0.4))
        sc.paste(f, mean, M.W / 2, pos["mean"], M.ease_out_back((t - t_mean + 0.2) / 0.5),
                 alpha=M.ease_out((t - t_mean + 0.2) / 0.4))
        if src is not None:
            sc.paste(f, src, M.W / 2, pos["src"], alpha=M.ease_out((t - t_mean) / 0.6))
        if t >= cta_t:
            sc.paste(f, cta, M.W / 2, M.H - M.S(260), M.ease_out_back((t - cta_t) / 0.4))
        return f

    sc.encode(draw, final)


def make_name(workdir, final, used):
    fresh = [i for i in range(len(NAMES)) if f"naam:{i}" not in used]
    i = fresh[0] if fresh else random.randrange(len(NAMES))  # in order: 1, 2, 3 ... 99
    ar, roman, mean_r, mean_u = NAMES[i]
    voice = [f"اللہ تعالیٰ کا ایک خوبصورت نام: {plain(ar)}", f"اس کا مطلب ہے: {mean_u}",
             "یہ نام یاد کریں اور آگے شیئر کریں۔"]
    render(workdir, final, "ALLAH KE 99 NAAM", "2728", f"Naam number {i + 1} / 99", ar, M.S(420),
           roman, "MATLAB", mean_r, "", voice)
    title = random.choice([f"Allah Ka Naam {roman} 🤍 Matlab Kya Hai? #shorts",
                           f"{roman} Ka Matlab 🤍 Allah Ke 99 Naam ({i + 1}/99) #shorts",
                           f"Allah Ke 99 Naam: {roman} 🤍 Urdu Matlab #shorts"])
    desc = (f"{ar}\n{roman}: {mean_r}\n\nAllah Ta'ala ke 99 khoobsurat naamon mein se naam number {i + 1}. "
            "Roz ek naam yaad karein aur apne ghar walon ko bhi share karein 🤍\n\n"
            "#allah #asmaulhusna #99namesofallah #islam #islamicshorts #urdu #shorts")
    tags = ["allah ke 99 naam", "asma ul husna", "99 names of allah", "allah names with meaning in urdu",
            roman.lower(), "allah ke naam", "islamic shorts", "islam", "urdu islamic", "names of allah"]
    return {"format": "naam", "key": f"naam:{i}", "title": title, "description": desc, "tags": tags}


def make_dua(workdir, final, used):
    fresh = [i for i in range(len(DUAS)) if f"dua:{i}" not in used]
    i = random.choice(fresh or list(range(len(DUAS))))
    t_r, t_u, ar, tr, mean_r, mean_u, src = DUAS[i]
    voice = [t_u, f"اس کا ترجمہ ہے: {mean_u}", "یہ دعا یاد کریں اور آگے شیئر کریں۔"]
    render(workdir, final, "MASNOON DUA", "1f932", t_r, ar, M.S(230), tr, "TARJUMA", mean_r, f"Hawala: {src}", voice)
    title = f"{t_r} 🤲 Masnoon Dua #shorts"
    if len(title) > 95:
        title = f"{t_r[:80]} 🤲 #shorts"
    desc = (f"{t_r}\n\n{ar}\n\n{tr}\n\nTarjuma: {mean_r}\n\nHawala: {src}\n\n"
            "Ye dua yaad karein aur apne ghar walon ko bhi share karein 🤲\n\n"
            "#dua #masnoondua #islam #islamicshorts #urdu #shorts")
    tags = ["masnoon dua", "dua in urdu", "masnoon duain", t_r.lower()[:60], "daily duas", "islamic dua",
            "islamic shorts", "islam", "urdu islamic", "dua with urdu translation"]
    return {"format": "dua", "key": f"dua:{i}", "title": title, "description": desc, "tags": tags}


FORMATS = {"naam": make_name, "dua": make_dua}


def pick(workdir, final, history, force_format=None):
    used = set()
    for h in history:
        used.add(h.get("key", ""))
        used.update(h.get("keys", []))
    if force_format in FORMATS:
        fn = FORMATS[force_format]
    else:
        last = history[-1].get("format") if history else "dua"
        fn = make_dua if last == "naam" else make_name  # take turns
    meta = fn(workdir, final, used)
    meta["made_for_kids"] = False
    meta["channel"] = "deen"
    return meta

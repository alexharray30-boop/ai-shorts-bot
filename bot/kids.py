"""
Kids Shorts formats (4K, Made for Kids)
---------------------------------------
  guess_animal : silhouette -> 3-2-1 -> colourful reveal + confetti
  count        : objects pop in one by one with a big counter
  colors       : 4 colours, each with a matching cartoon object
  odd_one_out  : grid of the same item with one different, then circled

Art: Google Noto Emoji (Apache License 2.0), fetched from fonts.gstatic.com.
Voice: edge-tts child-friendly voice. Sounds: synthesised (no copyright).
"""
import math
import random
import subprocess

import requests
from PIL import Image, ImageDraw, ImageFilter

M = None  # main module (set by make())
FORCE_PAL = None  # keeps one colour theme across all rounds of a long video

KID_VOICE = "en-US-AnaNeural"
EMOJI_URL = "https://fonts.gstatic.com/s/e/notoemoji/latest/{code}/512.png"

ANIMALS = [
    ("lion", "1f981"), ("elephant", "1f418"), ("giraffe", "1f992"), ("zebra", "1f993"),
    ("monkey", "1f412"), ("penguin", "1f427"), ("dolphin", "1f42c"), ("whale", "1f40b"),
    ("octopus", "1f419"), ("turtle", "1f422"), ("rabbit", "1f407"), ("dog", "1f415"),
    ("cat", "1f408"), ("horse", "1f40e"), ("cow", "1f404"), ("pig", "1f416"), ("sheep", "1f411"),
    ("rooster", "1f413"), ("duck", "1f986"), ("owl", "1f989"), ("crocodile", "1f40a"),
    ("snake", "1f40d"), ("butterfly", "1f98b"), ("bee", "1f41d"), ("snail", "1f40c"),
    ("kangaroo", "1f998"), ("camel", "1f42b"), ("rhino", "1f98f"), ("hippo", "1f99b"),
    ("flamingo", "1f9a9"), ("parrot", "1f99c"), ("peacock", "1f99a"), ("dinosaur", "1f996"),
    ("shark", "1f988"), ("crab", "1f980"), ("koala", "1f428"), ("panda", "1f43c"), ("fox", "1f98a"),
    ("squirrel", "1f43f"), ("hedgehog", "1f994"), ("bat", "1f987"), ("eagle", "1f985"),
    ("swan", "1f9a2"), ("sloth", "1f9a5"), ("otter", "1f9a6"), ("gorilla", "1f98d"),
    ("deer", "1f98c"), ("mouse", "1f401"), ("lobster", "1f99e"), ("seal", "1f9ad"),
]
COUNT_ITEMS = [
    ("apples", "1f34e"), ("bananas", "1f34c"), ("strawberries", "1f353"), ("oranges", "1f34a"),
    ("balloons", "1f388"), ("stars", "2b50"), ("cars", "1f697"), ("ducks", "1f986"),
    ("cupcakes", "1f9c1"), ("watermelons", "1f349"), ("rockets", "1f680"), ("fish", "1f41f"),
    ("teddy bears", "1f9f8"), ("ice creams", "1f366"), ("donuts", "1f369"), ("butterflies", "1f98b"),
]
COLORS = [
    ("RED", (239, 68, 68), [("apple", "1f34e"), ("strawberry", "1f353"), ("fire truck", "1f692")]),
    ("YELLOW", (250, 204, 21), [("banana", "1f34c"), ("lemon", "1f34b"), ("chick", "1f424")]),
    ("GREEN", (34, 197, 94), [("frog", "1f438"), ("broccoli", "1f966"), ("turtle", "1f422")]),
    ("BLUE", (59, 130, 246), [("whale", "1f433"), ("blue heart", "1f499"), ("butterfly", "1f98b")]),
    ("ORANGE", (249, 115, 22), [("orange", "1f34a"), ("carrot", "1f955"), ("pumpkin", "1f383")]),
    ("PURPLE", (168, 85, 247), [("grapes", "1f347"), ("eggplant", "1f346"), ("purple heart", "1f49c")]),
    ("PINK", (236, 72, 153), [("flamingo", "1f9a9"), ("pig", "1f437"), ("peach", "1f351")]),
    ("BROWN", (146, 92, 54), [("bear", "1f43b"), ("chestnut", "1f330"), ("cookie", "1f36a")]),
]
ODD_PAIRS = [
    ("1f34e", "1f345", "tomato"), ("1f42d", "1f439", "hamster"), ("1f697", "1f695", "taxi"),
    ("1f353", "1f352", "cherries"), ("1f431", "1f42f", "tiger"), ("1f34b", "1f34c", "banana"),
    ("1f436", "1f43a", "wolf"), ("1f414", "1f424", "chick"), ("1f41f", "1f420", "tropical fish"),
    ("1f34a", "1f3c0", "basketball"), ("1f438", "1f422", "turtle"), ("1f34f", "1f350", "pear"),
]
KID_PALETTES = [  # top, bottom, accent
    ((56, 189, 248), (37, 99, 235), (250, 204, 21)),
    ((244, 114, 182), (168, 85, 247), (253, 224, 71)),
    ((74, 222, 128), (13, 148, 136), (255, 255, 255)),
    ((251, 191, 36), (249, 115, 22), (255, 255, 255)),
    ((129, 140, 248), (79, 70, 229), (253, 224, 71)),
]
CONFETTI = [(239, 68, 68), (250, 204, 21), (34, 197, 94), (59, 130, 246), (236, 72, 153), (255, 255, 255)]


# --------------------------------------------------------------------------- #
def make(main_module):
    global M
    M = main_module
    return pick


_cache = {}


def emoji(code, size, workdir):
    key = (code, size)
    if key in _cache:
        return _cache[key]
    p = workdir.parent / "emoji_cache" / f"{code}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        r = requests.get(EMOJI_URL.format(code=code), timeout=60)
        r.raise_for_status()
        p.write_bytes(r.content)
    img = Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS)
    _cache[key] = img
    return img


def silhouette(img, color=(20, 24, 48)):
    s = Image.new("RGBA", img.size, color + (255,))
    s.putalpha(img.getchannel("A"))
    return s


def shadowed(img, blur=30, offset=24):
    pad = blur * 2
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 110))
    sh.putalpha(img.getchannel("A").point(lambda v: int(v * 0.45)))
    out.paste(sh, (pad, pad + offset), sh)
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.paste(img, (pad, pad), img)
    return out


def text_banner(text, size, fill, color, weight="Black", stroke=0):
    f = M.font(size, weight)
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    w = int(d.textlength(text, font=f)) + M.S(170)
    img, pad = M.rounded_card(w, int(size * 1.7), int(size * 0.85), fill + (255,))
    M.draw_center_lines(img, [text], f, size, pad + int(size * 0.22), color, stroke=stroke,
                        stroke_fill=(0, 0, 0) if stroke else None)
    return img


def big_text(text, size, color=(255, 255, 255), stroke=14, weight="Black"):
    f = M.font(size, weight)
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    w = int(d.textlength(text, font=f)) + M.S(80)
    img = Image.new("RGBA", (w, int(size * 1.5)), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    dd.text((M.S(40) + M.S(10), M.S(14)), text, font=f, fill=(0, 0, 0, 120), stroke_width=stroke,
            stroke_fill=(0, 0, 0, 120))
    dd.text((M.S(40), 0), text, font=f, fill=color, stroke_width=stroke, stroke_fill=(30, 30, 60))
    return img


class Confetti:
    def __init__(self, cx, cy, t0, n=140, seed=1):
        r = random.Random(seed)
        self.t0, self.cx, self.cy = t0, cx, cy
        self.p = [(r.uniform(0, 2 * math.pi), r.uniform(M.S(900), M.S(2600)), r.choice(CONFETTI),
                   r.uniform(M.S(14), M.S(32)), r.uniform(0, 6)) for _ in range(n)]

    def draw(self, d, t):
        dt = t - self.t0
        if dt < 0 or dt > 2.5:
            return
        g = M.S(2200)
        for ang, sp, c, sz, rot in self.p:
            x = self.cx + math.cos(ang) * sp * dt
            y = self.cy + math.sin(ang) * sp * dt * 0.8 + 0.5 * g * dt * dt
            w = sz * (0.6 + 0.4 * abs(math.sin(rot + dt * 8)))
            d.rectangle([x - w, y - sz * 0.5, x + w, y + sz * 0.5], fill=c)


class Scene:
    """Shared video/audio plumbing for all kids formats."""

    def __init__(self, workdir, pal):
        self.workdir, self.pal = workdir, pal
        self.bg = M.make_background(pal, random.randint(1, 10**6))
        self.events = []  # (wav/mp3, start, volume)
        self.fx = M.sfx(workdir)
        self.bubbles = [(random.uniform(0, M.W), random.uniform(0, M.H), random.uniform(M.S(20), M.S(70)),
                         random.uniform(M.S(60), M.S(200))) for _ in range(28)]

    def say(self, text, at, name, max_len=3.0, vol=1.8):
        p = self.workdir / f"{name}.mp3"
        old = M.VOICE
        M.VOICE = KID_VOICE
        try:
            dur = M.tts(text, p, max_len)
        finally:
            M.VOICE = old
        if dur:
            self.events.append((p, at, vol))
        return dur

    def fx_at(self, name, at, vol=1.0):
        self.events.append((self.fx[name], at, vol))

    def base_frame(self, t):
        off = int((math.sin(t * 0.7) * 0.5 + 0.5) * M.S(900))
        f = self.bg.crop((0, off, M.W, off + M.H))
        d = ImageDraw.Draw(f, "RGBA")
        for (x, y, r, sp) in self.bubbles:
            yy = (y - sp * t * 2) % (M.H + 2 * r) - r
            d.ellipse([x - r, yy - r, x + r, yy + r], outline=(255, 255, 255, 90), width=M.S(8))
        return f, d

    def paste(self, frame, layer, cx, cy, scale=1.0, alpha=1.0, angle=0):
        if scale <= 0.01 or alpha <= 0.01:
            return
        L = layer
        if abs(scale - 1) > 0.005:
            L = L.resize((max(1, int(L.width * scale)), max(1, int(L.height * scale))), Image.BILINEAR)
        if angle:
            L = L.rotate(angle, resample=Image.BILINEAR, expand=True)
        if alpha < 0.999:
            L = L.copy()
            L.putalpha(L.getchannel("A").point(lambda v: int(v * alpha)))
        frame.paste(L, (int(cx - L.width / 2), int(cy - L.height / 2)), L)

    def encode(self, draw_fn, final_path):
        silent = self.workdir / "video.mp4"
        enc = subprocess.Popen(
            [M.FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{M.W}x{M.H}", "-r", str(M.FPS),
             "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "4",
             "-x264-params", "rc-lookahead=10", "-pix_fmt", "yuv420p", str(silent)],
            stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        for fi in range(int(M.D * M.FPS)):
            t = fi / M.FPS
            frame = draw_fn(t)
            M.ImageDraw.Draw(frame).rectangle([0, M.H - M.S(26), int(M.W * t / M.D), M.H], fill=self.pal[2])
            enc.stdin.write(frame.tobytes())
        enc.stdin.close()
        enc.wait()
        if enc.returncode:
            raise RuntimeError("video encode failed")
        self.mix(silent, final_path)

    def mix(self, silent, final_path):
        cmd = [M.FFMPEG, "-y", "-i", str(silent)]
        fc, labels = [], []
        for i, (src, at, vol) in enumerate(self.events):
            cmd += ["-i", str(src)]
            ms = int(at * 1000)
            fc.append(f"[{i + 1}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms},"
                      f"volume={vol}[e{i}]")
            labels.append(f"[e{i}]")
        cmd += ["-i", str(self.fx["music"])]
        bi = len(self.events) + 1
        fc.append(f"[{bi}:a]aresample=44100,aformat=channel_layouts=stereo,volume=0.9,"
                  f"afade=t=out:st={M.D - 1}:d=1[bed]")
        labels.append("[bed]")
        fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
                  f"alimiter=limit=0.95,atrim=0:{M.D}[aout]")
        cmd += ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[aout]", "-t", str(M.D),
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final_path)]
        M.run(cmd)


def countdown(frame, d, t, start, cx, cy, acc):
    if not (start <= t < start + 3):
        return
    lt = t - start
    n = 3 - int(lt)
    frac = 1 - (lt % 1.0)
    R = M.S(200)
    d.ellipse([cx - R - M.S(26), cy - R - M.S(26), cx + R + M.S(26), cy + R + M.S(26)], fill=(255, 255, 255))
    d.arc([cx - R, cy - R, cx + R, cy + R], 0, 360, fill=(220, 220, 235), width=M.S(36))
    d.arc([cx - R, cy - R, cx + R, cy + R], -90, -90 + 360 * frac, fill=acc, width=M.S(36))
    f = M.font(int(M.S(240) * (1 + 0.25 * (1 - M.ease_out((lt % 1) / 0.25)))), "Black")
    s = str(n)
    d.text((cx - d.textlength(s, font=f) / 2, cy - f.size * 0.62), s, font=f, fill=(30, 30, 60))


# --------------------------------------------------------------------------- #
# Formats
# --------------------------------------------------------------------------- #
def guess_animal(workdir, final, used):
    pool = ANIMALS
    sl = __import__("os").getenv("ANIMAL_SLICE")  # e.g. "0/2": parallel batches use different animals
    if sl:
        k, m = (int(x) for x in sl.split("/"))
        pool = [a for i, a in enumerate(ANIMALS) if i % m == k]
    choices = [a for a in pool if f"animal:{a[0]}" not in used] or pool
    name, code = random.choice(choices)
    pal = FORCE_PAL or random.choice(KID_PALETTES)
    sc = Scene(workdir, pal)
    acc = pal[2] if pal[2] != (255, 255, 255) else (250, 204, 21)

    art = shadowed(emoji(code, M.S(1500), workdir), blur=M.S(30), offset=M.S(30))
    sil = shadowed(silhouette(emoji(code, M.S(1500), workdir)), blur=M.S(30), offset=M.S(30))
    title = text_banner("WHO AM I?", M.S(170), (255, 255, 255), (30, 30, 60))
    sub = big_text("Guess the animal!", M.S(110), stroke=M.S(10))
    label = big_text(name.upper() + "!", M.S(260), color=acc, stroke=M.S(16))
    qmark = big_text("?", M.S(520), color=(255, 255, 255), stroke=M.S(18))

    sc.fx_at("whoosh", 0.0, 0.8)
    sc.fx_at("pop", 0.45)
    ql = sc.say("Can you guess this animal?", 0.5, "q", max_len=2.4)
    cd = max(0.5 + ql + 0.2, 3.0)
    reveal = cd + 3
    for k in range(3):
        sc.fx_at("tick", cd + k)
    sc.fx_at("ding", reveal, 0.9)
    sc.fx_at("yay", reveal, 0.7)
    sc.say(f"It's a {name}!" if name[0] not in "aeiou" else f"It's an {name}!", reveal + 0.15, "a", 2.0)
    sc.say("Did you get it right?", min(reveal + 1.8, M.D - 1.6), "c", 1.5, vol=1.4)
    conf = Confetti(M.W / 2, M.S(1750), reveal, seed=code.__hash__() % 999)
    cy = M.S(1750)

    def draw(t):
        f, d = sc.base_frame(t)
        sc.paste(f, title, M.W / 2, M.S(-200) + M.S(620) * M.ease_out_back(t / 0.5))
        sc.paste(f, sub, M.W / 2, M.S(780), alpha=M.ease_out((t - 0.4) / 0.4))
        wob = math.sin(t * 5) * 3
        if t < reveal:
            sc.paste(f, sil, M.W / 2, cy, M.ease_out_back((t - 0.4) / 0.5) * (1 + 0.03 * math.sin(t * 6)), angle=wob)
            if t > 1.0:
                sc.paste(f, qmark, M.W / 2 + M.S(560), cy - M.S(560), 0.6 + 0.08 * math.sin(t * 7), angle=-12)
        else:
            rt = t - reveal
            if rt < 0.15:
                f = Image.blend(f, Image.new("RGB", f.size, (255, 255, 255)), 0.6 * (1 - rt / 0.15))
            sc.paste(f, art, M.W / 2, cy, M.ease_out_back(rt / 0.45) * (1 + 0.03 * math.sin(t * 6)), angle=wob)
            sc.paste(f, label, M.W / 2, M.S(2900), M.ease_out_back((rt - 0.15) / 0.4))
        d = ImageDraw.Draw(f)
        countdown(f, d, t, cd, M.W / 2, M.S(3050), acc)
        conf.draw(d, t)
        return f

    sc.encode(draw, final)
    em = {"lion": "🦁", "elephant": "🐘", "penguin": "🐧", "dog": "🐶", "cat": "🐱"}.get(name, "🐾")
    return {
        "format": "guess_animal", "key": f"animal:{name}",
        "title": random.choice([f"Guess the Animal! {em} Fun Quiz for Kids",
                                f"Who Am I? 🤔 Guess the Animal Shadow {em}",
                                f"Can You Guess This Animal? {em} Kids Quiz",
                                f"Animal Shadow Quiz for Kids {em} Guess Who!"]) + " #shorts",
        "description": "Can you guess the animal from its shadow? 🐾 A fun learning quiz for kids and toddlers!\n"
                       "Learn animal names in English with bright cartoons.\n\n#kids #animals #learning #quiz #shorts",
        "tags": ["guess the animal", "animal quiz for kids", "animals for kids", "learn animals", "kids quiz",
                 "shadow quiz", "toddler learning", "preschool learning", "kids learning videos",
                 "animal names", f"{name} for kids", "educational videos for kids", "fun quiz", "shorts"],
    }


def count(workdir, final, used):
    fresh = [i for i in COUNT_ITEMS if not any(k.startswith(f"count:{i[0]}:") for k in used)]
    item, code = random.choice(fresh or COUNT_ITEMS)
    n = random.randint(5, 9)
    pal = FORCE_PAL or random.choice(KID_PALETTES)
    sc = Scene(workdir, pal)
    acc = pal[2] if pal[2] != (255, 255, 255) else (250, 204, 21)
    size = M.S(520)
    art = shadowed(emoji(code, size, workdir), blur=M.S(16), offset=M.S(16))
    title = text_banner(f"COUNT THE {item.upper()}!", M.S(120), (255, 255, 255), (30, 30, 60))
    cols = 3
    xs = [M.W / 2 + (c - 1) * M.S(620) for c in range(cols)]
    rows = math.ceil(n / cols)
    y0 = M.S(1350) + (3 - rows) * M.S(300)
    pos = [(xs[i % cols], y0 + (i // cols) * M.S(620)) for i in range(n)]
    start, step = 1.6, min(0.75, (M.D - 4.2) / n)
    total_t = start + n * step + 0.2
    numbers = [big_text(str(k), M.S(300), color=acc, stroke=M.S(16)) for k in range(1, n + 1)]
    words = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

    sc.fx_at("whoosh", 0, 0.8)
    sc.say(f"Let's count the {item}!", 0.3, "q", 1.5)
    for k in range(n):
        sc.fx_at("pop", start + k * step, 0.9)
    sc.say(", ".join(words[:n]) + "!", start - 0.05, "nums", max_len=n * step + 0.3, vol=1.6)
    sc.fx_at("ding", total_t, 0.9)
    sc.fx_at("yay", total_t, 0.7)
    sc.say(f"{words[n - 1].capitalize()} {item}! Great job!", total_t + 0.15, "a", 2.2)
    conf = Confetti(M.W / 2, M.S(1800), total_t, seed=n * 7)
    final_lbl = big_text(f"{n} {item.upper()}!", M.S(200), color=(255, 255, 255), stroke=M.S(14))

    def draw(t):
        f, d = sc.base_frame(t)
        sc.paste(f, title, M.W / 2, M.S(-200) + M.S(620) * M.ease_out_back(t / 0.5))
        shown = 0
        for i, (x, y) in enumerate(pos):
            ti = start + i * step
            if t >= ti:
                shown = i + 1
                bounce = 1 + 0.05 * math.sin((t - ti) * 8) if t < total_t else 1 + 0.04 * math.sin(t * 6 + i)
                sc.paste(f, art, x, y, M.ease_out_back((t - ti) / 0.3) * bounce)
        if 0 < shown and t < total_t:
            lt = t - (start + (shown - 1) * step)
            sc.paste(f, numbers[shown - 1], M.W / 2, M.S(3250), 1 + 0.3 * (1 - M.ease_out(lt / 0.25)))
        if t >= total_t:
            sc.paste(f, final_lbl, M.W / 2, M.S(3250), M.ease_out_back((t - total_t) / 0.4))
        conf.draw(ImageDraw.Draw(f), t)
        return f

    sc.encode(draw, final)
    return {
        "format": "count", "key": f"count:{item}:{n}",
        "title": random.choice([f"Let's Count the {item.title()}! 🔢 Numbers for Kids",
                                f"How Many {item.title()}? Count With Me! 🎈",
                                f"Counting {item.title()} 1 to {n} 🔢 Learn Numbers"]) + " #shorts",
        "description": f"Count the {item} with us! 🔢 Fun number learning for toddlers and preschool kids.\n\n"
                       "#counting #numbers #kidslearning #toddler #shorts",
        "tags": ["counting for kids", "learn numbers", "count with me", "numbers for kids", "123 for kids",
                 "toddler learning", "preschool", "kids learning videos", "math for kids", "counting 1 to 10",
                 "educational videos", f"{item} for kids", "shorts"],
    }


def colors(workdir, final, used):
    picks = random.sample(COLORS, 4)
    pal = FORCE_PAL or random.choice(KID_PALETTES)
    sc = Scene(workdir, pal)
    seg = (M.D - 1.4) / 4
    title = text_banner("LEARN COLORS!", M.S(150), (255, 255, 255), (30, 30, 60))
    items = []
    for k, (cname, rgb, objs) in enumerate(picks):
        oname, code = random.choice(objs)
        t0 = 1.0 + k * seg
        art = shadowed(emoji(code, M.S(1250), workdir), blur=M.S(28), offset=M.S(28))
        lbl = big_text(cname, M.S(300), color=rgb, stroke=M.S(18))
        obj = big_text(oname.title(), M.S(130), stroke=M.S(10))
        items.append((t0, rgb, art, lbl, obj))
        sc.fx_at("pop", t0)
        sc.say(f"{cname.title()}! {oname.title()}!", t0 + 0.1, f"c{k}", max_len=seg - 0.3)
    sc.fx_at("whoosh", 0, 0.8)
    sc.say("Let's learn colors!", 0.15, "q", 0.9)
    sc.fx_at("yay", M.D - 0.8, 0.5)

    def draw(t):
        f, d = sc.base_frame(t)
        cur = None
        for it in items:
            if t >= it[0]:
                cur = it
        if cur:
            t0, rgb, art, lbl, obj = cur
            lt = t - t0
            circ = Image.new("RGBA", (M.S(1700), M.S(1700)), (0, 0, 0, 0))
            ImageDraw.Draw(circ).ellipse([0, 0, M.S(1700), M.S(1700)], fill=rgb + (255,),
                                         outline=(255, 255, 255), width=M.S(30))
            sc.paste(f, circ, M.W / 2, M.S(1800), M.ease_out_back(lt / 0.35))
            sc.paste(f, art, M.W / 2, M.S(1800), M.ease_out_back((lt - 0.08) / 0.4) * (1 + 0.03 * math.sin(t * 6)),
                     angle=math.sin(t * 4) * 4)
            sc.paste(f, lbl, M.W / 2, M.S(3000), M.ease_out_back((lt - 0.1) / 0.35))
            sc.paste(f, obj, M.W / 2, M.S(3330), alpha=M.ease_out((lt - 0.3) / 0.3))
        sc.paste(f, title, M.W / 2, M.S(-200) + M.S(620) * M.ease_out_back(t / 0.5))
        return f

    sc.encode(draw, final)
    names = ", ".join(p[0].title() for p in picks)
    return {
        "format": "colors", "key": "colors:" + "-".join(p[0] for p in picks),
        "title": random.choice(["Learn Colors for Kids 🌈 Fun & Easy!", "Colors for Toddlers 🎨 Learn with Fun!",
                                f"Learn {picks[0][0].title()}, {picks[1][0].title()} & More Colors 🌈"]) + " #shorts",
        "description": f"Let's learn colors: {names}! 🌈 Bright, fun color learning for toddlers and preschoolers.\n\n"
                       "#colors #learncolors #toddler #kidslearning #shorts",
        "tags": ["learn colors", "colors for kids", "colors for toddlers", "colours for kids", "learning colors",
                 "toddler learning", "preschool learning", "kids learning videos", "rainbow colors",
                 "educational videos for kids", "baby learning", "shorts"],
    }


def odd_one_out(workdir, final, used):
    fresh = [p for p in ODD_PAIRS if f"odd:{p[0]}:{p[1]}" not in used]
    a, b, bname = random.choice(fresh or ODD_PAIRS)
    pal = FORCE_PAL or random.choice(KID_PALETTES)
    sc = Scene(workdir, pal)
    acc = pal[2] if pal[2] != (255, 255, 255) else (250, 204, 21)
    cols, rows = 4, 5
    size = M.S(400)
    A = emoji(a, size, workdir)
    B = emoji(b, size, workdir)
    odd = random.randrange(cols * rows)
    gx = [M.W / 2 + (c - 1.5) * M.S(480) for c in range(cols)]
    gy = [M.S(1150) + r * M.S(470) for r in range(rows)]
    title = text_banner("FIND THE ODD ONE!", M.S(130), (255, 255, 255), (30, 30, 60))
    panel, pp = M.rounded_card(M.S(2000), M.S(2420), M.S(80), (255, 255, 255, 235))
    sc.fx_at("whoosh", 0, 0.8)
    ql = sc.say("Can you find the odd one out?", 0.4, "q", 2.4)
    cd = max(0.4 + ql + 1.2, 3.6)
    reveal = cd + 3
    for k in range(3):
        sc.fx_at("tick", cd + k)
    sc.fx_at("ding", reveal, 0.9)
    sc.fx_at("yay", reveal, 0.7)
    sc.say(f"There it is! The {bname}!", reveal + 0.15, "a", 2.2)
    ox, oy = gx[odd % cols], gy[odd // cols]
    conf = Confetti(ox, oy, reveal, n=90, seed=odd)
    found = big_text(f"THE {bname.upper()}!", M.S(180), color=acc, stroke=M.S(14))

    def draw(t):
        f, d = sc.base_frame(t)
        sc.paste(f, title, M.W / 2, M.S(-200) + M.S(620) * M.ease_out_back(t / 0.5))
        sc.paste(f, panel, M.W / 2, M.S(2090), M.ease_out_back((t - 0.2) / 0.4))
        for i in range(cols * rows):
            ti = 0.45 + i * 0.03
            x, y = gx[i % cols], gy[i // cols]
            s = M.ease_out_back((t - ti) / 0.3)
            if i == odd and t >= reveal:
                s *= 1.25 + 0.08 * math.sin(t * 8)
            sc.paste(f, B if i == odd else A, x, y, s)
        d = ImageDraw.Draw(f)
        if t >= reveal:
            r = M.S(270) * M.ease_out_back((t - reveal) / 0.35)
            d.ellipse([ox - r, oy - r, ox + r, oy + r], outline=(239, 68, 68), width=M.S(30))
            sc.paste(f, found, M.W / 2, M.S(3480), M.ease_out_back((t - reveal - 0.2) / 0.4))
        else:
            countdown(f, d, t, cd, M.W / 2, M.S(3530), acc)
        conf.draw(d, t)
        return f

    sc.encode(draw, final)
    return {
        "format": "odd_one_out", "key": f"odd:{a}:{b}",
        "title": random.choice(["Find the Odd One Out! 👀 Kids Puzzle", "Can You Spot the Different One? 🔍",
                                "Odd One Out Challenge for Kids 🧩"]) + " #shorts",
        "description": "Can you find the odd one out? 👀 A fun brain puzzle for kids!\n\n"
                       "#oddoneout #kidspuzzle #brainteaser #kids #shorts",
        "tags": ["odd one out", "find the odd one out", "kids puzzle", "spot the difference", "brain games for kids",
                 "puzzle for kids", "kids quiz", "emoji puzzle", "find the different", "kids learning videos",
                 "educational videos for kids", "shorts"],
    }


FORMATS = [(guess_animal, 3), (count, 2), (colors, 2), (odd_one_out, 2)]


# --------------------------------------------------------------------------- #
# Long (about 1 minute) videos: intro + 5 rounds of one format
# --------------------------------------------------------------------------- #
ROUNDS = int(__import__("os").getenv("KIDS_ROUNDS", "5"))
ROUND_SECONDS = 11.0
LONG_INFO = {
    "guess_animal": (["GUESS ALL", "{n} ANIMALS!"], "Can you guess all {n} animals? Let's go!",
                     ["Guess {n} Animals! 🐾 Fun Shadow Quiz for Kids", "Can You Guess All {n} Animals? 🦁 Kids Quiz",
                      "Animal Shadow Quiz 🐘 Guess {n} Animals with Me!"]),
    "count": (["LET'S", "COUNT!"], "Let's count together! Ready?",
              ["Count With Me! 🔢 {n} Fun Counting Games for Kids", "Let's Count Together! 🍎 Numbers for Kids",
               "Counting Fun for Toddlers 🔢 Learn Numbers 1 to 9"]),
    "colors": (["LET'S LEARN", "COLORS!"], "Let's learn colors together!",
               ["Learn Colors with Fun Objects 🌈 Kids Learning", "Colors for Toddlers 🎨 Learn {n} Rounds of Colors!",
                "Rainbow Colors for Kids 🌈 Learn & Play"]),
    "odd_one_out": (["FIND THE", "ODD ONE!"], "Can you find the odd one out? {n} puzzles!",
                    ["Find the Odd One Out! 👀 {n} Puzzles for Kids", "Spot the Different One! 🔍 {n} Kids Puzzles",
                     "Odd One Out Challenge 🧩 {n} Fun Puzzles for Kids"]),
}


def intro(workdir, final, lines, voice):
    pal = FORCE_PAL
    sc = Scene(workdir, pal)
    acc = pal[2] if pal[2] != (255, 255, 255) else (250, 204, 21)
    l1 = big_text(lines[0], M.S(230), stroke=M.S(16))
    l2 = big_text(lines[1], M.S(300), color=acc, stroke=M.S(18))
    play = text_banner("LET'S PLAY!", M.S(140), (255, 255, 255), (30, 30, 60))
    sc.fx_at("whoosh", 0, 0.9)
    sc.fx_at("yay", 0.5, 0.6)
    sc.say(voice, 0.3, "intro", max_len=M.D - 0.5)
    conf = Confetti(M.W / 2, M.S(1700), 0.5, n=120, seed=3)

    def draw(t):
        f, d = sc.base_frame(t)
        sc.paste(f, l1, M.W / 2, M.S(1450), M.ease_out_back(t / 0.4))
        sc.paste(f, l2, M.W / 2, M.S(1850), M.ease_out_back((t - 0.2) / 0.45) * (1 + 0.04 * math.sin(t * 7)))
        sc.paste(f, play, M.W / 2, M.S(2500), M.ease_out_back((t - 0.6) / 0.4))
        conf.draw(ImageDraw.Draw(f), t)
        return f

    sc.encode(draw, final)


def badge(text, path):
    img = text_banner(text, M.S(90), (255, 255, 255), (30, 30, 60))
    img.save(path)
    return img


def pick_long(workdir, final, history, fn):
    global FORCE_PAL
    used = set()
    for h in history:
        used.add(h.get("key", ""))
        used.update(h.get("keys", []))
    FORCE_PAL = random.choice(KID_PALETTES)
    name = fn.__name__
    lines, voice, titles = LONG_INFO[name]
    n = ROUNDS
    old_d = M.D
    clips, badges, metas = [], [], []
    try:
        M.D = 3.0
        iw = workdir / "intro"
        iw.mkdir(exist_ok=True)
        intro(iw, iw / "intro.mp4", [lines[0].format(n=n), lines[1].format(n=n)], voice.format(n=n))
        clips.append(iw / "intro.mp4")
        M.D = ROUND_SECONDS
        for r in range(n):
            rw = workdir / f"round{r + 1}"
            rw.mkdir(exist_ok=True)
            m = fn(rw, rw / "round.mp4", used)
            used.add(m["key"])
            metas.append(m)
            clips.append(rw / "round.mp4")
            badges.append(badge(f"{r + 1} / {n}", rw / "badge.png") and rw / "badge.png")
            M.log(f"round {r + 1}/{n} done: {m['key']}")
    finally:
        M.D = old_d
        FORCE_PAL = None

    # join: intro + rounds (with "x / n" badge in the top-left corner)
    cmd = [M.FFMPEG, "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    for b in badges:
        cmd += ["-i", str(b)]
    fc, parts = [], ["[0:v][0:a]"]
    for r in range(n):
        vi, bi = r + 1, len(clips) + r
        fc.append(f"[{vi}:v][{bi}:v]overlay={M.S(30)}:{M.S(40)}[v{r}]")
        parts.append(f"[v{r}][{vi}:a]")
    fc.append(f"{''.join(parts)}concat=n={len(clips)}:v=1:a=1[v][a]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-threads", "4", "-x264-params", "rc-lookahead=10",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)]
    M.run(cmd)

    items = [m["key"].split(":", 1)[1].split(":")[0] for m in metas]
    tags = []
    for m in metas:
        tags += [t for t in m["tags"] if t not in tags]
    desc = metas[0]["description"].split("\n\n")[0]
    if name == "guess_animal":
        desc += "\n\nAnimals in this video: " + ", ".join(i.title() for i in items) + " 🐾"
    desc += "\n\nNew fun learning videos for kids every day! 🎉\n\n#kids #kidslearning #toddler #preschool #shorts"
    return {
        "format": name + "_long", "key": metas[0]["key"], "keys": [m["key"] for m in metas],
        "title": random.choice(titles).format(n=n) + " #shorts", "description": desc, "tags": tags,
    }


def pick(workdir, final, history, force_format=None):
    used = {h.get("key", "") for h in history}
    if force_format:
        fn = dict((f.__name__, f) for f, _ in FORMATS)[force_format]
    else:
        recent = [h.get("format", "").replace("_long", "") for h in history[-2:]]
        opts = [(f, w) for f, w in FORMATS if f.__name__ not in recent] or FORMATS
        fn = random.choices([f for f, _ in opts], weights=[w for _, w in opts])[0]
    if ROUNDS > 1:
        meta = pick_long(workdir, final, history, fn)
    else:
        meta = fn(workdir, final, used)
    meta["made_for_kids"] = True
    return meta

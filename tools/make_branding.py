"""Makes the Pakistan channel's profile picture (800x800) and banner (2560x1440)."""
import pathlib
import sys

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "branding"
NAME = sys.argv[2] if len(sys.argv) > 2 else "DIMAGH LAGAO"
OUT.mkdir(parents=True, exist_ok=True)


def font(size, weight="Black"):
    return ImageFont.truetype(str(ROOT / "fonts" / f"Poppins-{weight}.ttf"), size)


def emoji(code, size):
    p = OUT / f"_{code}.png"
    if not p.exists():
        p.write_bytes(requests.get(f"https://fonts.gstatic.com/s/e/notoemoji/latest/{code}/512.png", timeout=60).content)
    return Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS)


def gradient(w, h, top, bot):
    g = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return g.resize((w, h), Image.BICUBIC)


def glow(img, spots):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for x, y, r, c in spots:
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    return Image.alpha_composite(img.convert("RGBA"), lay.filter(ImageFilter.GaussianBlur(120)))


def outlined(d, xy, text, f, fill, stroke=10, anchor="mm"):
    d.text((xy[0] + 8, xy[1] + 12), text, font=f, fill=(0, 0, 0, 120), anchor=anchor, stroke_width=stroke,
           stroke_fill=(0, 0, 0, 120))
    d.text(xy, text, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=(10, 30, 20))


GREEN_T, GREEN_B, GOLD = (6, 140, 70), (2, 40, 22), (250, 204, 21)

# ---- profile picture ----
S = 800
pp = gradient(S, S, GREEN_T, GREEN_B)
pp = glow(pp, [(250, 220, 260, GOLD + (60,)), (600, 640, 240, (255, 255, 255, 40))])
d = ImageDraw.Draw(pp)
d.ellipse([30, 30, S - 30, S - 30], outline=GOLD, width=22)
brain = emoji("1f9e0", 430)
pp.paste(brain, ((S - 430) // 2, 90), brain)
q = emoji("2753", 150)
pp.paste(q, (560, 70), q)
outlined(d, (S // 2, 610), NAME.split()[0], font(118), (255, 255, 255), stroke=8)
outlined(d, (S // 2, 705), " ".join(NAME.split()[1:]) or "", font(82), GOLD, stroke=7)
pp.convert("RGB").save(OUT / "profile_800x800.png")

# ---- banner (safe area for all devices: 1546x423 in the centre) ----
W, H = 2560, 1440
bn = gradient(W, H, GREEN_T, GREEN_B)
bn = glow(bn, [(700, 600, 420, GOLD + (55,)), (1900, 820, 460, (255, 255, 255, 35)), (1280, 720, 300, GOLD + (30,))])
stripes = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(stripes)
for x in range(-H, W, 120):
    sd.line([(x, 0), (x + H, H)], fill=(255, 255, 255, 14), width=18)
bn = Image.alpha_composite(bn, stripes)
d = ImageDraw.Draw(bn)
icons = [("1f9e0", 330, 640), ("1f3cf", 2230, 640), ("2753", 470, 880), ("1f4a1", 2090, 880)]
for code, x, y in icons:
    im = emoji(code, 230)
    bn.paste(im, (x - 115, y - 115), im)
outlined(d, (W // 2, 640), NAME, font(190), (255, 255, 255), stroke=12)
outlined(d, (W // 2, 790), "GK Quiz  •  Paheliyan  •  Cricket  •  Facts", font(70, "ExtraBold"), GOLD, stroke=6)
pill_w, pill_h = 760, 110
d.rounded_rectangle([W // 2 - pill_w // 2, 860, W // 2 + pill_w // 2, 860 + pill_h], radius=55, fill=(255, 255, 255))
d.text((W // 2, 860 + pill_h // 2), "ROZ NAYI VIDEO  🔔".replace("  🔔", ""), font=font(64), fill=(10, 60, 30),
       anchor="mm")
bn.convert("RGB").save(OUT / "banner_2560x1440.png", quality=95)
for p in OUT.glob("_*.png"):
    p.unlink()
print("saved:", OUT)

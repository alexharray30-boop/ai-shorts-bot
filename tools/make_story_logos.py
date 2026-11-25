"""Three profile-picture options (800x800) for Kismat Kahaniyan."""
import pathlib
import sys

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "branding"
OUT.mkdir(parents=True, exist_ok=True)
S = 800
GOLD, RED, DARK = (250, 204, 21), (190, 20, 40), (28, 4, 10)


def font(size, w="Black"):
    return ImageFont.truetype(str(ROOT / "fonts" / f"Poppins-{w}.ttf"), size)


def emoji(code, size):
    p = OUT / f"_{code}.png"
    if not p.exists():
        p.write_bytes(requests.get(f"https://fonts.gstatic.com/s/e/notoemoji/latest/{code}/512.png", timeout=60).content)
    return Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS)


def radial(c_in, c_out):
    img = Image.new("RGB", (S, S), c_out)
    d = ImageDraw.Draw(img)
    for r in range(S // 2 + 200, 0, -4):
        t = r / (S // 2 + 200)
        col = tuple(int(c_in[i] * (1 - t) + c_out[i] * t) for i in range(3))
        d.ellipse([S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r], fill=col)
    return img.convert("RGBA")


def text(d, xy, s, f, fill, stroke=8, sf=(30, 5, 10)):
    d.text((xy[0] + 6, xy[1] + 8), s, font=f, fill=(0, 0, 0, 140), anchor="mm", stroke_width=stroke,
           stroke_fill=(0, 0, 0, 140))
    d.text(xy, s, font=f, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=sf)


def sparkle(img, pts):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for x, y, r in pts:
        d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD + (200,))
    return Image.alpha_composite(img, lay.filter(ImageFilter.GaussianBlur(3)))


# 1) Royal crown on deep red, name below (bold and simple)
a = radial((150, 20, 40), DARK)
a = sparkle(a, [(140, 160, 6), (660, 140, 5), (700, 420, 4), (110, 470, 5)])
d = ImageDraw.Draw(a)
d.ellipse([28, 28, S - 28, S - 28], outline=GOLD, width=20)
cr = emoji("1f451", 400)
a.paste(cr, ((S - 400) // 2, 90), cr)
text(d, (S // 2, 575), "KISMAT", font(104), (255, 255, 255))
text(d, (S // 2, 665), "KAHANIYAN", font(62), GOLD, stroke=7)
a.convert("RGB").save(OUT / "logo_1_crown.png")

# 2) "KK" monogram in a gold medallion with a crown on top (looks premium when small)
b = radial((60, 10, 20), (10, 2, 5))
d = ImageDraw.Draw(b)
for r, col in [(330, GOLD), (300, (120, 15, 30)), (285, GOLD), (270, (90, 10, 22))]:
    d.ellipse([S / 2 - r, S / 2 - r + 40, S / 2 + r, S / 2 + r + 40], fill=col)
text(d, (S // 2, S // 2 + 50), "KK", font(300), GOLD, stroke=10, sf=(60, 8, 15))
cr = emoji("1f451", 230)
b.paste(cr, ((S - 230) // 2, 20), cr)
text(d, (S // 2, 640), "KISMAT KAHANIYAN", font(38, "ExtraBold"), (255, 255, 255), stroke=5)
b.convert("RGB").save(OUT / "logo_2_monogram.png")

# 3) Open story book with sparkles and a crown (story channel feel)
c = radial((120, 30, 90), (20, 5, 25))
c = sparkle(c, [(170, 200, 7), (630, 180, 6), (600, 330, 4), (200, 360, 5), (400, 120, 5)])
d = ImageDraw.Draw(c)
d.ellipse([28, 28, S - 28, S - 28], outline=GOLD, width=18)
bk = emoji("1f4d6", 380)
c.paste(bk, ((S - 380) // 2, 170), bk)
cr = emoji("1f451", 170)
c.paste(cr, ((S - 170) // 2, 70), cr)
st = emoji("2728", 120)
c.paste(st, (585, 140), st)
text(d, (S // 2, 610), "KISMAT", font(110), GOLD)
text(d, (S // 2, 700), "KAHANIYAN", font(70), (255, 255, 255), stroke=7)
c.convert("RGB").save(OUT / "logo_3_storybook.png")

# preview of all three side by side
prev = Image.new("RGB", (S * 3 + 80, S + 40), (245, 245, 245))
for i, n in enumerate(["logo_1_crown.png", "logo_2_monogram.png", "logo_3_storybook.png"]):
    im = Image.open(OUT / n)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, S, S], fill=255)  # how YouTube shows it (round)
    prev.paste(im, (20 + i * (S + 20), 20), mask)
prev.save(OUT / "_preview.png")
for p in OUT.glob("_1*.png"):
    p.unlink()
for p in OUT.glob("_2*.png"):
    p.unlink()
print("saved", OUT)

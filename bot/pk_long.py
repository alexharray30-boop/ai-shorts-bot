"""Dimagh Lagao: ~8 minute landscape Islamic Quiz (35 questions), 2 a week, with a thumbnail.

Islamic Quiz is the format that gets the most views on this channel; long videos add the watch hours
YouTube needs for monetization. Uses the same question bank as the Shorts (pk_islami.ISLAMI).
"""
import random

from PIL import Image, ImageDraw, ImageFilter

import kids
import pk

ROUNDS = 35  # 35 x 13 s + intro = about 8 minutes


def make_long(M, workdir, final, history):
    pk.make(M)
    kids.STYLE["palettes"] = pk.PALETTES
    vertical = workdir / "vertical.mp4"
    meta = kids.pick_long(workdir, vertical, history, pk.islami, rounds=ROUNDS)
    kids.to_landscape(vertical, final)
    n = sum(1 for h in history if h.get("format") == "islami_long8") + 1
    thumbnail(M, final.with_suffix(".jpg"))
    questions = meta["description"].split("\n\n", 1)[1] if "\n\n" in meta["description"] else ""
    meta.update(
        format="islami_long8", long=True, made_for_kids=False, channel="pk",
        title=random.choice([
            f"Islamic Quiz in Urdu 🕌 {ROUNDS} Sawal - Kitne Sahi Kar Sakte Hain? (Part {n})",
            f"Islamic Quiz Urdu 🕌 {ROUNDS} Sawal Jawab - Aap Ke Kitne Sahi Honge? (Part {n})",
            f"Islami Sawal Jawab 🕌 {ROUNDS} Islamic Quiz Urdu Mein - Apna Ilm Check Karein (Part {n})",
        ])[:100],
        description=(f"{ROUNDS} Islamic sawal Urdu mein - har sawal ke 4 jawab, 3 second sochiye, phir sahi jawab! 🕌\n\n"
                     "Comment mein batayein aap ke kitne jawab sahi the 👇\n\n" + questions[:3500] +
                     "\n\nDimagh Lagao (@DimaghLagaoQuiz) - roz naye quiz ke liye subscribe karein 🔔\n\n"
                     "#islamicquiz #islamicquizurdu #urduquiz #islam #dimaghlagao"),
        tags=["islamic quiz", "islamic quiz in urdu", "islamic sawal jawab", "islami quiz", "islamic questions",
              "urdu quiz", "islamic gk", "islamic general knowledge", "dimagh lagao", "islamic quiz urdu"],
    )
    return meta


def thumbnail(M, path):
    w, h = 1280, 720
    top, bot = (6, 78, 59), (2, 24, 18)
    gold = (250, 204, 21)
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        k = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - k) + bot[i] * k) for i in range(3)))
    img = img.convert("RGBA")
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([w - 560, h // 2 - 260, w - 40, h // 2 + 260], fill=gold + (80,))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(40)))
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, w - 10, h - 10], outline=gold + (255,), width=10)
    # big mosque emoji on the right + a "?" badge
    try:
        tmp = path.parent / "thumb_emoji"
        tmp.mkdir(exist_ok=True)
        em = kids.emoji("1f54c", 380, tmp)
        img.paste(em, (w - 300 - em.width // 2, (h - em.height) // 2), em)
    except Exception as e:
        M.log("thumbnail emoji skipped:", e)
    lines = [("ISLAMIC", 110, (255, 255, 255)), ("QUIZ", 150, gold), (f"{ROUNDS} SAWAL", 80, (255, 255, 255)),
             ("Kitne Sahi? 🤔".replace(" 🤔", ""), 66, gold)]
    fitted = [(M.fit_text(t, 680, 220, s, "Black"), c) for t, s, c in lines]
    total = sum(len(wl) * int(sz * 1.08) + 10 for (f, wl, sz), c in fitted)
    y = (h - total) // 2
    for (f, wl, sz), col in fitted:
        for word in wl:
            d.text((60, y), word, font=f, fill=col, stroke_width=max(4, sz // 12), stroke_fill=(0, 0, 0))
            y += int(sz * 1.08)
        y += 10
    img.convert("RGB").save(path, quality=92)
    M.log("thumbnail ready:", path.name)

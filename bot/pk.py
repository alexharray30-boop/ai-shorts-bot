"""
Pakistan channel formats (4K, Urdu voice, Roman Urdu on screen)
---------------------------------------------------------------
  gk       : general knowledge MCQ (4 options, countdown, answer)
  cricket  : cricket MCQ
  paheli   : Urdu riddle with countdown and answer
  fact     : "Kya aap jante hain?" amazing fact

Reuses the drawing / audio engine from kids.py.
"""
import math
import random

from PIL import Image, ImageDraw

import kids
from pk_content import CRICKET, FACTS, GK, GTA, PAHELIYAN

M = None
VOICE = "ur-PK-UzmaNeural"  # clear Pakistani female voice; Gul and Asad are backups
PALETTES = [  # top, bottom, accent
    ((4, 120, 60), (2, 44, 24), (250, 204, 21)),      # Pakistan green
    ((30, 64, 175), (8, 15, 45), (250, 204, 21)),
    ((126, 34, 206), (30, 10, 60), (52, 211, 153)),
    ((159, 18, 57), (40, 8, 20), (253, 224, 71)),
    ((15, 118, 110), (4, 30, 35), (251, 146, 60)),
]
LONG_INFO = {
    "gk": (["GK QUIZ", "{n} SAWAL!"], "کیا آپ ان سوالوں کے جواب دے سکتے ہیں؟ چلیں شروع کرتے ہیں!",
           ["GK Quiz in Urdu 🧠 Kya Aap {n} Sawal Ka Jawab De Sakte Hain?", "Urdu General Knowledge Quiz 🇵🇰 {n} Sawal",
            "Sirf Genius Hi Jawab De Sakta Hai 🧠 GK Quiz Urdu"]),
    "cricket": (["CRICKET", "QUIZ!"], "کرکٹ کے سوال! کیا آپ اصلی فین ہیں؟",
                ["Cricket Quiz in Urdu 🏏 Sirf Asli Fan Jawab Dega", "Pakistan Cricket Quiz 🇵🇰🏏 {n} Sawal",
                 "Cricket GK Urdu 🏏 Kitne Sahi Kar Sakte Ho?"]),
    "paheli": (["URDU", "PAHELIYAN!"], "کیا آپ یہ پہیلیاں بوجھ سکتے ہیں؟",
               ["Urdu Paheliyan 🤔 Bujho To Jaanein!", "{n} Mazedaar Paheliyan 🧩 Dimagh Lagao",
                "Paheliyan with Answers in Urdu 🤔 Kitni Bujh Sakte Ho?"]),
    "gta": (["GTA 6", "QUIZ!"], "جی ٹی اے سکس کوئز! کیا آپ اصلی گیمر ہیں؟",
            ["GTA 6 Quiz in Urdu 🎮 Sirf Asli Gamer Jawab Dega", "GTA 6 Ke {n} Sawal 🎮 Kitne Sahi Kar Sakte Ho?",
             "GTA 6 Quiz 🌴🚗 Vice City Wapas! Urdu Mein"]),
    "fact": (["KYA AAP", "JANTE HAIN?"], "کیا آپ جانتے ہیں؟ یہ حیرت انگیز باتیں!",
             ["Kya Aap Jante Hain? 🤯 Amazing Facts in Urdu", "{n} Hairat Angez Facts 😱 Urdu Mein",
              "Amazing Facts in Urdu 🤯 Dimagh Hila Dene Wale"]),
}
FOOTER = ("\n\nRoz naye GK Quiz, Cricket Quiz, Paheliyan aur Amazing Facts! Channel subscribe karein 🔔\n\n"
          "#urdu #gkquiz #pakistan #paheliyan #shorts")
TAGS = ["gk quiz in urdu", "general knowledge urdu", "urdu quiz", "pakistan quiz", "gk questions", "paheliyan",
        "urdu paheliyan", "cricket quiz", "amazing facts in urdu", "kya aap jante hain", "dimagh lagao",
        "urdu shorts", "pakistan", "quiz", "shorts"]


def make(main_module):
    global M
    M = main_module
    kids.M = main_module
    kids.STYLE.update(voice=VOICE, palettes=PALETTES, long_info=LONG_INFO, play="SHURU KAREIN!",
                      footer=FOOTER, round_lines=True)
    kids.ROUND_SECONDS = 13.0  # Urdu needs time to be spoken at a natural speed
    return pick


def _acc(pal):
    return pal[2] if pal[2] != (255, 255, 255) else (250, 204, 21)


def header(text, icon_code, workdir):
    ban = kids.text_banner(text, M.S(130), (255, 255, 255), (30, 30, 60))
    icon = kids.emoji(icon_code, M.S(220), workdir)
    out = Image.new("RGBA", (ban.width + icon.width + M.S(20), max(ban.height, icon.height)), (0, 0, 0, 0))
    out.paste(icon, (0, (out.height - icon.height) // 2), icon)
    out.paste(ban, (icon.width + M.S(20), (out.height - ban.height) // 2), ban)
    return out


def text_card(text, w, h, start, fill=(255, 255, 255), color=(17, 24, 39), weight="ExtraBold"):
    f, lines, size = M.fit_text(text, w - M.S(200), h - M.S(160), start, weight=weight)
    card, pad = M.rounded_card(w, h, M.S(80), fill + (255,))
    th = int(len(lines) * size * 1.18)
    M.draw_center_lines(card, lines, f, size, pad + (h - th) // 2 - M.S(10), color)
    return card


def option_pill(letter, text, state, acc):
    w, h = M.S(1800), M.S(230)
    fill = {"normal": (255, 255, 255), "right": (34, 197, 94), "dim": (226, 232, 240)}[state]
    tcol = {"normal": (17, 24, 39), "right": (255, 255, 255), "dim": (148, 163, 184)}[state]
    card, pad = M.rounded_card(w, h, M.S(115), fill + (255,), shadow=state != "dim")
    d = ImageDraw.Draw(card)
    r = M.S(80)
    cx, cy = pad + M.S(130), pad + h // 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 30, 60) if state != "right" else (255, 255, 255))
    lf = M.font(M.S(100), "Black")
    d.text((cx - d.textlength(letter, font=lf) / 2, cy - M.S(72)), letter, font=lf,
           fill=(255, 255, 255) if state != "right" else (21, 128, 61))
    f, lines, size = M.fit_text(text, w - M.S(380), h - M.S(40), M.S(105), weight="ExtraBold")
    ty = pad + (h - int(len(lines) * size * 1.12)) // 2 - M.S(8)
    for ln in lines:
        d.text((pad + M.S(260), ty), ln, font=f, fill=tcol)
        ty += int(size * 1.12)
    if state == "right":
        cf = M.font(M.S(130), "Black")
        d.text((pad + w - M.S(170), cy - M.S(95)), "✓" if False else "", font=cf, fill=(255, 255, 255))
    return card


def _pick_index(prefix, items, used):
    fresh = [i for i in range(len(items)) if f"{prefix}:{i}" not in used]
    return random.choice(fresh or list(range(len(items))))


def _quiz(workdir, final, used, prefix, bank, title, icon):
    i = _pick_index(prefix, bank, used)
    q_r, q_u, opts, correct, ans_u = bank[i]
    pal = kids.FORCE_PAL or random.choice(PALETTES)
    acc = _acc(pal)
    sc = kids.Scene(workdir, pal)
    head = header(title, icon, workdir)
    card = text_card(q_r, M.S(1900), M.S(900), M.S(150))
    letters = "ABCD"
    pills = [(option_pill(letters[k], o, "normal", acc), option_pill(letters[k], o, "right" if k == correct else "dim", acc))
             for k, o in enumerate(opts)]
    sc.fx_at("whoosh", 0, 0.7)
    sc.fx_at("pop", 0.35)
    ql = sc.say(q_u, 0.45, "q", max_len=5.4)
    cd = min(max(0.45 + ql + 0.3, 3.4), M.D - 4.4)
    reveal = cd + 3
    for k in range(3):
        sc.fx_at("tick", cd + k)
    sc.fx_at("ding", reveal, 0.9)
    sc.say(f"صحیح جواب: {ans_u}", reveal + 0.15, "a", max_len=M.D - reveal - 0.4)
    ys = [M.S(2050) + k * M.S(300) for k in range(4)]
    conf = kids.Confetti(M.W / 2, ys[correct], reveal, n=90, seed=i)

    def draw(t):
        f, d = sc.base_frame(t)
        sc.paste(f, head, M.W / 2, M.S(-200) + M.S(560) * M.ease_out_back(t / 0.5))
        sc.paste(f, card, M.W / 2, M.S(1250), M.ease_out_back((t - 0.3) / 0.45))
        for k, (normal, after) in enumerate(pills):
            tk = 0.7 + k * 0.12
            layer = after if t >= reveal else normal
            s = M.ease_out_back((t - tk) / 0.35)
            if t >= reveal and k == correct:
                s *= 1.04 + 0.03 * math.sin(t * 8)
            sc.paste(f, layer, M.W / 2, ys[k], s)
        d = ImageDraw.Draw(f)
        kids.countdown(f, d, t, cd, M.W / 2, M.S(3330), acc)
        conf.draw(d, t)
        return f

    sc.encode(draw, final)
    return {"format": prefix, "key": f"{prefix}:{i}", "line": f"❓ {q_r}  ✅ {opts[correct]}",
            "title": "", "description": f"{title} 🇵🇰 Kya aap jawab de sakte hain? Comment mein batayein! 👇",
            "tags": TAGS}


def gk(workdir, final, used):
    return _quiz(workdir, final, used, "gk", GK, "GK QUIZ", "1f9e0")


def cricket(workdir, final, used):
    return _quiz(workdir, final, used, "cricket", CRICKET, "CRICKET QUIZ", "1f3cf")


def paheli(workdir, final, used):
    i = _pick_index("paheli", PAHELIYAN, used)
    r_r, r_u, a_r, a_u = PAHELIYAN[i]
    pal = kids.FORCE_PAL or random.choice(PALETTES)
    acc = _acc(pal)
    sc = kids.Scene(workdir, pal)
    head = header("PAHELI BUJHO!", "2753", workdir)
    card = text_card(r_r, M.S(1900), M.S(1150), M.S(165))
    ans = text_card(a_r.upper(), M.S(1700), M.S(420), M.S(170), fill=(34, 197, 94), color=(255, 255, 255),
                    weight="Black")
    think = kids.big_text("SOCHIYE...", M.S(120), stroke=M.S(10))
    sc.fx_at("whoosh", 0, 0.7)
    sc.fx_at("pop", 0.35)
    ql = sc.say(r_u, 0.45, "q", max_len=5.6)
    cd = min(max(0.45 + ql + 0.3, 3.4), M.D - 4.2)
    reveal = cd + 3
    for k in range(3):
        sc.fx_at("tick", cd + k)
    sc.fx_at("ding", reveal, 0.9)
    sc.fx_at("yay", reveal, 0.5)
    sc.say(f"جواب ہے: {a_u}", reveal + 0.15, "a", max_len=M.D - reveal - 0.4)
    conf = kids.Confetti(M.W / 2, M.S(2650), reveal, n=110, seed=i)

    def draw(t):
        f, d = sc.base_frame(t)
        sc.paste(f, head, M.W / 2, M.S(-200) + M.S(560) * M.ease_out_back(t / 0.5))
        sc.paste(f, card, M.W / 2, M.S(1450), M.ease_out_back((t - 0.3) / 0.45))
        d = ImageDraw.Draw(f)
        if t < reveal:
            if t > 1.0:
                sc.paste(f, think, M.W / 2, M.S(2450), alpha=0.6 + 0.4 * math.sin(t * 4) ** 2)
            kids.countdown(f, d, t, cd, M.W / 2, M.S(2950), acc)
        else:
            rt = t - reveal
            if rt < 0.12:
                f = Image.blend(f, Image.new("RGB", f.size, (255, 255, 255)), 0.5 * (1 - rt / 0.12))
            sc.paste(f, ans, M.W / 2, M.S(2650), M.ease_out_back(rt / 0.4))
        conf.draw(ImageDraw.Draw(f), t)
        return f

    sc.encode(draw, final)
    return {"format": "paheli", "key": f"paheli:{i}", "line": f"🤔 {r_r}  ✅ {a_r}", "title": "",
            "description": "Urdu Paheliyan 🤔 Kya aap ne sahi bujha? Comment mein batayein! 👇", "tags": TAGS}


def fact(workdir, final, used):
    i = _pick_index("fact", FACTS, used)
    f_r, f_u, code = FACTS[i]
    pal = kids.FORCE_PAL or random.choice(PALETTES)
    sc = kids.Scene(workdir, pal)
    head = header("KYA AAP JANTE HAIN?", "1f4a1", workdir)
    art = kids.shadowed(kids.emoji(code, M.S(1100), workdir), blur=M.S(26), offset=M.S(26))
    card = text_card(f_r, M.S(1900), M.S(900), M.S(150))
    wow = kids.big_text("WOW! 🤯".replace(" 🤯", ""), M.S(260), color=_acc(pal), stroke=M.S(16))
    sc.fx_at("whoosh", 0, 0.7)
    sc.fx_at("pop", 0.4)
    fl = sc.say(f_u, 0.6, "f", max_len=6.5)
    wow_t = min(max(0.6 + fl + 0.3, 5.0), M.D - 2.0)
    sc.fx_at("ding", wow_t, 0.8)
    sc.say("کمال ہے نا؟", wow_t + 0.2, "w", max_len=1.6)

    def draw(t):
        f, d = sc.base_frame(t)
        sc.paste(f, head, M.W / 2, M.S(-200) + M.S(560) * M.ease_out_back(t / 0.5))
        sc.paste(f, art, M.W / 2, M.S(1300), M.ease_out_back((t - 0.3) / 0.5) * (1 + 0.03 * math.sin(t * 5)),
                 angle=math.sin(t * 3) * 4)
        sc.paste(f, card, M.W / 2, M.S(2550), M.ease_out_back((t - 0.5) / 0.45))
        if t >= wow_t:
            sc.paste(f, wow, M.W / 2, M.S(3400), M.ease_out_back((t - wow_t) / 0.35), angle=-6)
        return f

    sc.encode(draw, final)
    return {"format": "fact", "key": f"fact:{i}", "line": f"💡 {f_r}", "title": "",
            "description": "Kya Aap Jante Hain? 🤯 Hairat angez facts Urdu mein!", "tags": TAGS}


def gta(workdir, final, used):
    return _quiz(workdir, final, used, "gta", GTA, "GTA 6 QUIZ", "1f3ae")


NEON = [((236, 72, 153), (49, 10, 101), (34, 211, 238)), ((168, 85, 247), (20, 8, 60), (250, 204, 21)),
        ((249, 115, 22), (88, 12, 80), (34, 211, 238))]
FORMATS = [(gk, 3), (cricket, 2), (paheli, 3), (fact, 2)]  # gta only on request


def pick(workdir, final, history, force_format=None):
    if force_format:
        fn = dict((f.__name__, f) for f, _ in FORMATS + [(gta, 0)])[force_format]
    else:
        recent = [h.get("format", "").replace("_long", "") for h in history[-2:]]
        opts = [(f, w) for f, w in FORMATS if f.__name__ not in recent] or FORMATS
        fn = random.choices([f for f, _ in opts], weights=[w for _, w in opts])[0]
    if fn is gta:
        kids.STYLE["palettes"] = NEON
    try:
        meta = kids.pick_long(workdir, final, history, fn)
    finally:
        kids.STYLE["palettes"] = PALETTES
    meta["made_for_kids"] = False
    meta["channel"] = "pk"
    return meta

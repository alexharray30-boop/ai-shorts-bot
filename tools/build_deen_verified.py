"""Builds bot/deen_verified.json: the Arabic shown on the Islamic channel, copied EXACTLY from authoritative
sources instead of being typed by hand.

* Quranic duas   -> the exact words from the Quran text on quran.com (Imlaei script) for the given Surah:Ayat.
                    Only change: a shadda on the very first letter that exists only because of the word
                    before it in the ayat (e.g. "وَقُل رَّبِّ" -> "رَبِّ") is removed, as every dua book does.
* Hadith duas    -> the exact words from Hisn al-Muslim (hisnmuslim.com, Arabic edition).
* Allah ke Naam  -> letters checked against the standard list (api.aladhan.com) and searched in the Quran.

Any dua that cannot be found word-for-word in its source is left out (never shown).
python tools/build_deen_verified.py
"""
import json
import pathlib
import re
import sys
import time
import unicodedata

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))
from deen_content import DUAS, NAMES  # noqa: E402

# Hisn al-Muslim chapter to take each hadith dua from (part of the Arabic chapter title)
HINTS = {"Khana shuru karne ki dua": "الطعام", "Khane se pehle Bismillah bhool jayein to": "الطعام",
         "Khana khane ke baad ki dua": "الفراغ من الطعام", "Sone ki dua": "النوم",
         "Neend se jaagne ki dua": "الاستيقاظ", "Ghar se nikalne ki dua": "الخروج من المنزل",
         "Bathroom mein jaane se pehle ki dua": "دخول الخلاء", "Bathroom se nikalne ki dua": "الخروج من الخلاء",
         "Masjid mein dakhil hone ki dua": "دخول المسجد", "Masjid se nikalne ki dua": "الخروج من المسجد",
         "Istighfar (roz parhne wala)": "الاستغفار", "Naya kapra pehnne ki dua": "الثوب",
         "Gham aur pareshani se panah ki dua": "الهم", "Ghussa aaye to kya parhein": "الغضب",
         "Bimar ki ayadat ki dua": "المريض", "Shadi ki mubarakbad ki dua": "للمتزوج",
         "Roza iftar karne ke baad ki dua": "إفطار", "Baarish hone par dua": "المطر",
         "Subah shaam hifazat ki dua (3 baar)": "الصباح والمساء", "Do halke magar wazni kalimaat": "التسبيح",
         "Jannat ka khazana": "", "Chheenk aane par": "العطاس"}
MARK = re.compile(r"[ً-ْٰـۖ-ۭٓ-ٟ]")


def skel_map(text):
    """Letters-only skeleton of text plus, for every skeleton char, its index in the original text."""
    text = unicodedata.normalize("NFC", text)
    sk, idx = [], []
    for i, ch in enumerate(text):
        if MARK.match(ch):
            continue
        if ch in "أإآٱ":
            ch = "ا"
        elif ch == "ى":
            ch = "ي"
        elif ch == "ة":
            ch = "ه"
        elif not ("ء" <= ch <= "ي"):
            ch = " "
        if ch == " " and sk and sk[-1] == " ":
            continue
        sk.append(ch)
        idx.append(i)
    return "".join(sk), idx, text


def extract(source, wanted):
    """Exact substring of `source` whose letters equal the letters of `wanted` (whole words only)."""
    s_sk, s_idx, s_txt = skel_map(" " + source + " ")
    w_sk = " " + skel_map(wanted)[0].strip() + " "
    pos = s_sk.find(w_sk)
    if pos < 0:
        return None
    a = s_idx[pos + 1]
    b = s_idx[pos + len(w_sk) - 2] + 1
    while b < len(s_txt) and MARK.match(s_txt[b]):  # keep the marks of the last letter
        b += 1
    out = s_txt[a:b]
    out = re.sub(r"[()\[\]{}﴿﴾«»\"*.]", "", out)
    return re.sub(r"\s+", " ", out).strip(" ،,")


HARAKAT = set("ًٌٍَُِّْٰ")


def letters(t):
    """[(letter, {marks})] with old spellings normalised: a fatha/tanween or shadda written on the alif
    after a letter (لاَ , إِلاَّ , صَيِّباً) belongs to the letter before it."""
    out = []
    for ch in unicodedata.normalize("NFC", t):
        if ch in HARAKAT:
            if out:
                out[-1][1].add(ch)
        elif "ء" <= ch <= "ي":
            out.append([ch, set()])
    for k in range(1, len(out)):
        if out[k][0] == "ا":
            mv = out[k][1] & {"َ", "ً", "ّ"}
            out[k - 1][1] |= mv
            out[k][1] -= mv
    return out


def consistent(source, mine):
    """True when both have the same letters and every mark the source has is also in mine."""
    S, M = letters(source), letters(mine)
    if [a for a, _ in S] != [a for a, _ in M]:
        return False
    return all(s <= m for (_, s), (_, m) in zip(S, M))


def get(url):
    for _ in range(4):
        try:
            r = requests.get(url, timeout=40)
            r.encoding = "utf-8"
            return json.loads(r.text.lstrip("﻿"))
        except Exception:
            time.sleep(3)
    raise RuntimeError(f"could not load {url}")


def verse(key):
    return get(f"https://api.quran.com/api/v4/quran/verses/imlaei?verse_key={key}")["verses"][0]["text_imlaei"]


def hisn_texts():
    idx = get("https://www.hisnmuslim.com/api/ar/husn_ar.json")
    out = []
    for ch in list(idx.values())[0]:
        d = get(ch["TEXT"].replace("http://", "https://"))
        for items in d.values():
            out += [(ch["TITLE"], it.get("ARABIC_TEXT", "")) for it in items]
    return out


def main():
    hisn = hisn_texts()
    result = {"duas": {}, "dropped": {}, "names": {}}
    for i, d in enumerate(DUAS):
        m = re.search(r"(\d+):(\d+)(?:-(\d+))?", d[6])
        if m:
            s, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3) or m.group(2))
            keys = [f"{s}:{v}" for v in range(a, b + 1)]
            src = " ".join(verse(k) for k in keys)
            ar = extract(src, d[2])
            if ar:
                full_sk = skel_map(src)[0].strip()
                if not full_sk.startswith(skel_map(ar)[0].strip()) and len(ar) > 1 and ar[1:2] in ("ّ",) or \
                        (not full_sk.startswith(skel_map(ar)[0].strip()) and "ّ" in ar[1:3] and ar[0] in "رل"):
                    ar = ar[0] + ar[1:3].replace("ّ", "") + ar[3:]
                result["duas"][i] = {"arabic": ar, "from": f"Quran {'+'.join(keys)} (quran.com)"}
            else:
                result["dropped"][i] = f"not found in Quran {keys}"
        else:
            hit = None
            hint = HINTS.get(d[0], "")
            for title, t in sorted(hisn, key=lambda x: hint not in x[0]):  # the right chapter first
                ar = extract(t, d[2])
                if ar:
                    hit = (title, ar)
                    break
            if hit and consistent(hit[1], d[2]):
                # same letters, and every zer/zabar/pesh printed in Hisn al-Muslim is identical in ours;
                # ours only adds the marks the website left out
                result["duas"][i] = {"arabic": d[2], "from": f"Hisn al-Muslim: {hit[0]}", "source_text": hit[1]}
            elif hit:
                result["dropped"][i] = f"harakat differ from Hisn al-Muslim: {hit[1]}"
            else:
                result["dropped"][i] = "not found word-for-word in Hisn al-Muslim"

    names = get("https://api.aladhan.com/v1/asmaAlHusna")["data"]
    quran = get("https://api.quran.com/api/v4/quran/verses/imlaei")["verses"]
    q_words = set()
    for v in quran:
        for w in skel_map(v["text_imlaei"])[0].split():
            q_words.add(w)
    for i, (ar, roman, *_r) in enumerate(NAMES):
        mine, ref = skel_map(ar)[0].strip(), skel_map(names[i]["name"])[0].strip()
        in_quran = all(w in q_words or ("ال" + w) in q_words or (w.startswith("ال") and w[2:] in q_words)
                       for w in mine.split())
        result["names"][i] = {"letters_match_list": mine.replace(" ", "") == ref.replace(" ", ""),
                              "found_in_quran": in_quran}
    (ROOT / "bot" / "deen_verified.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    bad_names = [i + 1 for i, r in result["names"].items() if not r["letters_match_list"]]
    print(f"duas verified: {len(result['duas'])}, dropped: {result['dropped']}")
    print(f"names whose letters differ from the list: {bad_names}")
    print(f"names found in the Quran: {sum(r['found_in_quran'] for r in result['names'].values())}/99")


if __name__ == "__main__":
    main()

"""Checks the Islamic channel's Arabic against authoritative sources - nothing typed by hand is trusted.

* Quranic duas: compared letter-by-letter AND harakat-by-harakat with the Quran text from quran.com
  (Imlaei script, the same text printed in normal Mushafs), using the Surah:Ayat in the dua's source.
* Allah ke 99 Naam: compared with the standard list from api.aladhan.com.

python tools/verify_deen.py            -> report only, exit 1 on any difference
"""
import json
import pathlib
import re
import sys
import time
import unicodedata

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "bot"))
from deen_content import DUAS, NAMES  # noqa: E402

QURAN = "https://api.quran.com/api/v4/quran/verses/imlaei?verse_key={}"
MARKS = re.compile(r"[ً-ْٰ]")      # harakat, shadda, sukun, dagger alif
DECOR = re.compile(r"[ـۖ-ۭٓ-ٟ]")  # tatweel and Quran annotation signs


def norm(s, keep_harakat=True):
    s = unicodedata.normalize("NFC", s).replace("ٱ", "ا")
    s = DECOR.sub("", s)
    if not keep_harakat:
        s = MARKS.sub("", s)
    # put the marks on every letter in one fixed order (shadda first), so equal text compares equal
    out, cur = [], ""
    for ch in s:
        if MARKS.match(ch):
            cur += ch
        else:
            if cur:
                out.append("".join(sorted(cur)))
                cur = ""
            out.append(ch)
    out.append("".join(sorted(cur)))
    return re.sub(r"\s+", " ", "".join(out)).strip()


def verse_text(key):
    for _ in range(3):
        try:
            return requests.get(QURAN.format(key), timeout=30).json()["verses"][0]["text_imlaei"]
        except Exception:
            time.sleep(2)
    raise RuntimeError(f"could not load {key}")


def quran_ref(src):
    m = re.search(r"(\d+):(\d+)(?:-(\d+))?", src)
    if not m:
        return None
    s, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3) or m.group(2))
    return [f"{s}:{v}" for v in range(a, b + 1)]


problems, report = [], {}
for i, d in enumerate(DUAS):
    keys = quran_ref(d[6])
    if not keys:
        report[i] = "hadith (not in Quran)"
        continue
    src = " ".join(verse_text(k) for k in keys)
    mine, ref = norm(d[2]), norm(src)
    if mine in ref:
        report[i] = f"OK exact match with Quran {'+'.join(keys)}"
    elif norm(d[2], False) in norm(src, False):
        problems.append(f"DUA {i} ({d[0]}): letters OK but harakat differ from Quran {keys}\n   mine : {d[2]}\n   quran: {src}")
    else:
        problems.append(f"DUA {i} ({d[0]}): NOT found in Quran {keys}\n   mine : {d[2]}\n   quran: {src}")

names = requests.get("https://api.aladhan.com/v1/asmaAlHusna", timeout=30).json()["data"]
for i, (ar, roman, *_rest) in enumerate(NAMES):
    ref = names[i]["name"]
    if norm(ar, False) != norm(ref, False):
        problems.append(f"NAAM {i + 1} ({roman}): letters differ\n   mine : {ar}\n   list : {ref}")
    elif norm(ar) != norm(ref):
        problems.append(f"NAAM {i + 1} ({roman}): harakat differ\n   mine : {ar}\n   list : {ref}")

for i, r in report.items():
    print(f"dua {i:2d}: {r}  - {DUAS[i][0]}")
print(f"\n{len(problems)} difference(s)")
for p in problems:
    print(p)
if "--json" in sys.argv:
    print(json.dumps(problems, ensure_ascii=False))
sys.exit(1 if problems else 0)

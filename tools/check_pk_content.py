"""Checks all Dimagh Lagao content before rendering: shape, duplicates, answers, Urdu text, emoji images.
Usage: python tools/check_pk_content.py [--no-net]
"""
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "bot"))
import pk_content as c  # noqa: E402

URDU = re.compile(r"[؀-ۿ]")
errors = []


def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())


seen = {}
for name in ["GK", "CRICKET", "ISLAMI", "GTA", "GAME"]:
    for i, it in enumerate(getattr(c, name)):
        where = f"{name}[{i}]"
        if len(it) != 5:
            errors.append(f"{where}: needs 5 fields"); continue
        q, qu, opts, k, au = it
        if len(opts) != 4 or len({o.strip().lower() for o in opts}) != 4:
            errors.append(f"{where}: needs 4 different options: {opts}")
        if not (isinstance(k, int) and 0 <= k < len(opts)):
            errors.append(f"{where}: bad answer index {k}")
        if not URDU.search(qu) or not URDU.search(au):
            errors.append(f"{where}: Urdu text missing")
        if not q.strip().endswith("?"):
            errors.append(f"{where}: question should end with ?")
        key = norm(q)
        if key in seen:
            errors.append(f"{where}: duplicate of {seen[key]}: {q}")
        seen[key] = where

for i, it in enumerate(c.PAHELIYAN):
    where = f"PAHELIYAN[{i}]"
    if len(it) != 4 or not URDU.search(it[1]) or not URDU.search(it[3]):
        errors.append(f"{where}: bad shape / Urdu missing")
    key = norm(it[0])
    if key in seen:
        errors.append(f"{where}: duplicate of {seen[key]}")
    seen[key] = where

codes = set()
for i, it in enumerate(c.FACTS):
    where = f"FACTS[{i}]"
    if len(it) != 3 or not URDU.search(it[1]):
        errors.append(f"{where}: bad shape / Urdu missing")
    key = norm(it[0])
    if key in seen:
        errors.append(f"{where}: duplicate of {seen[key]}")
    seen[key] = where
    codes.add(it[2])

if "--no-net" not in sys.argv:
    import requests
    from kids import EMOJI_URL
    for code in sorted(codes | {"1f54c", "1f3ae", "1f9e0", "1f3cf", "2753", "1f4a1"}):
        r = requests.get(EMOJI_URL.format(code=code), timeout=30)
        if r.status_code != 200:
            errors.append(f"emoji {code}: HTTP {r.status_code}")

print({n: len(getattr(c, n)) for n in ["GK", "ISLAMI", "CRICKET", "PAHELIYAN", "FACTS", "GTA", "GAME"]})
if errors:
    print("\n".join(errors))
    sys.exit(f"{len(errors)} problem(s)")
print("all content OK")

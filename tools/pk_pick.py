"""Pick the next Dimagh Lagao video from the bank (prints its .mp4 name).

Islamic Quiz gets by far the most views, so out of every 3 uploads 2 are
Islamic Quiz (when the bank has any). The third slot goes to the other
formats in order of how well they do; Facts (lowest views) only go when
nothing else is left.

usage: python tools/pk_pick.py <folder with the bank .json files> [history.json]
"""
import json
import pathlib
import sys

ISLAMI = "islami_long"
# best -> worst by views so far; anything unknown goes just before facts
OTHERS = ["gta_long", "gk_long", "paheli_long", "cricket_long", "game_long"]
LAST = ["fact_long"]


def rank(fmt):
    if fmt in OTHERS:
        return OTHERS.index(fmt)
    if fmt in LAST:
        return 100 + LAST.index(fmt)
    return 50


def main():
    folder = pathlib.Path(sys.argv[1])
    hist_path = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "state/pk_history.json")
    hist = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else []
    recent = [h.get("format") for h in hist[-2:]]

    items = []
    for jf in sorted(folder.glob("*.json")):
        try:
            fmt = json.loads(jf.read_text(encoding="utf-8")).get("format", "")
        except Exception:
            continue
        items.append((jf.stem + ".mp4", fmt))
    if not items:
        return

    islami = [n for n, f in items if f == ISLAMI]
    others = sorted((x for x in items if x[1] != ISLAMI), key=lambda x: (rank(x[1]), x[0]))
    # recent formats among the other slot: don't repeat the same one back to back
    last_other = next((h.get("format") for h in reversed(hist) if h.get("format") != ISLAMI), None)

    want_islami = islami and not (recent == [ISLAMI, ISLAMI] and others)
    if want_islami:
        print(islami[0])
        return
    if others:
        best = others[0][1]
        pick = others[0]
        if best == last_other:
            alt = [x for x in others if x[1] != last_other and rank(x[1]) < 100]
            if alt:
                pick = alt[0]
        print(pick[0])
        return
    print(islami[0])


if __name__ == "__main__":
    main()

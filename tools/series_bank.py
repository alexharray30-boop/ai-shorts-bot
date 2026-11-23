"""Renders the next Kismat Kahaniyan series parts, in story order, until --max parts are made or Cloudflare's
free daily image allowance runs out. When a story's last part is made, its long "Poori Kahani" video is built.

python tools/series_bank.py --done done.txt --max 40 --out bank --long-out longbank
  done.txt : names already in the "series-archive" release (one per line), e.g. s01p03.mp4
  Parts 1..n-1 needed for a long video are downloaded from "series-archive" with the gh CLI.
"""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))
import main as M  # noqa: E402
import series  # noqa: E402
import story  # noqa: E402
from series_content import SERIES  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--done", default="done.txt")
ap.add_argument("--max", type=int, default=40)
ap.add_argument("--out", default="bank")
ap.add_argument("--long-out", default="longbank")
ap.add_argument("--only", help="render just this part, e.g. s01p01 (test)")
a = ap.parse_args()

series.setup(M)
out, lout = pathlib.Path(a.out), pathlib.Path(a.long_out)
out.mkdir(parents=True, exist_ok=True)
lout.mkdir(parents=True, exist_ok=True)
done_file = pathlib.Path(a.done)
done = set(done_file.read_text().split()) if done_file.exists() else set()
work = ROOT / "out" / "series"


def fetch_archived(name, dest):
    p = dest / name
    if not p.exists():
        subprocess.run(["gh", "release", "download", "series-archive", "-p", name, "-D", str(dest), "--clobber"],
                       check=True)
    return p


made = 0
for si, s in enumerate(SERIES):
    for p in range(1, len(s["parts"]) + 1):
        key = f"{s['id']}p{p:02d}"
        if a.only and key != a.only:
            continue
        if f"{key}.mp4" in done:
            continue
        if made >= a.max:
            break
        wd = work / key
        wd.mkdir(parents=True, exist_ok=True)
        try:
            meta = series.render_part(wd, out / f"{key}.mp4", si, p)
        except story.QuotaError as e:
            M.log(f"Cloudflare free daily limit reached after {made} parts - continuing tomorrow ({e})")
            sys.exit(0)
        (out / f"{key}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        done.add(f"{key}.mp4")
        made += 1
        M.log(f"made {key} ({meta['total']:.0f}s): {meta['title']}")
        if p == len(s["parts"]) and not a.only:
            parts = []
            for k in range(1, p + 1):
                kk = f"{s['id']}p{k:02d}"
                mp4 = out / f"{kk}.mp4" if (out / f"{kk}.mp4").exists() else fetch_archived(f"{kk}.mp4", wd)
                js = out / f"{kk}.json" if (out / f"{kk}.json").exists() else fetch_archived(f"{kk}.json", wd)
                parts.append((mp4, json.loads(pathlib.Path(js).read_text(encoding="utf-8"))))
            lmeta = series.build_long(wd, lout / f"{s['id']}long.mp4", si, parts)
            (lout / f"{s['id']}long.json").write_text(json.dumps(lmeta, ensure_ascii=False, indent=1), encoding="utf-8")
            M.log(f"long video ready: {lmeta['title']}")
M.log(f"done: {made} new parts")

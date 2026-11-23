"""Plans a big Dimagh Lagao bank run: gives every parallel job its own questions so no question is
repeated in any video, and none that was already uploaded or is already waiting in the bank.

python tools/pk_plan.py "islami:20,gk:20,cricket:15,paheli:15,fact:15,game:10,gta:5" --per-job 5 --used used
Prints  matrix=<json>  (for $GITHUB_OUTPUT) and a summary on stderr.
"""
import argparse
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))
import pk_content as c  # noqa: E402

POOLS = {"gk": c.GK, "islami": c.ISLAMI, "cricket": c.CRICKET, "paheli": c.PAHELIYAN, "fact": c.FACTS,
         "gta": c.GTA, "game": c.GAME}

ap = argparse.ArgumentParser()
ap.add_argument("plan")
ap.add_argument("--per-job", type=int, default=5)
ap.add_argument("--rounds", type=int, default=5)
ap.add_argument("--used", default="used", help="folder with .json files of videos already in the bank")
ap.add_argument("--seed", type=int, default=None)
a = ap.parse_args()
rnd = random.Random(a.seed)

used = set()
hist = ROOT / "state" / "pk_history.json"
entries = json.loads(hist.read_text(encoding="utf-8")) if hist.exists() else []
for jf in pathlib.Path(a.used).glob("*.json") if pathlib.Path(a.used).exists() else []:
    try:
        entries.append(json.loads(jf.read_text(encoding="utf-8")))
    except Exception:
        pass
for e in entries:
    used.add(e.get("key", ""))
    used.update(e.get("keys", []))

jobs, problems = [], []
for part in a.plan.split(","):
    fmt, videos = part.split(":")
    videos = int(videos)
    keys = [f"{fmt}:{i}" for i in range(len(POOLS[fmt]))]
    fresh = [k for k in keys if k not in used]
    rnd.shuffle(fresh)
    need = videos * a.rounds
    if len(fresh) < need:
        problems.append(f"{fmt}: needs {need} new items, only {len(fresh)} are new (some will repeat)")
        old = [k for k in keys if k in used]
        rnd.shuffle(old)
        fresh += old
    take = fresh[:need]
    for start in range(0, videos, a.per_job):
        n = min(a.per_job, videos - start)
        allow = take[start * a.rounds:(start + n) * a.rounds]
        jobs.append({"formats": fmt, "n": n, "allow": ",".join(allow)})

for i, j in enumerate(jobs):
    j["part"] = f"p{i + 1:02d}"

print(f"already used: {len(used)} items; jobs: {len(jobs)}; videos: {sum(j['n'] for j in jobs)}", file=sys.stderr)
for p in problems:
    print("WARNING:", p, file=sys.stderr)
print("matrix=" + json.dumps({"include": jobs}, ensure_ascii=False))

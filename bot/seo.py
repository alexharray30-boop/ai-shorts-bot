"""
Live US/UK YouTube SEO
----------------------
Right before each upload, asks YouTube's own search suggestions (what people in
the US and UK are typing right now) for every topic of the video, ranks the
phrases, and uses the best ones for the title, description, tags and hashtags.

Brand / other-channel names are filtered out (using them would be misleading
metadata, which YouTube penalises).
"""
import re
import time

import requests

SUGGEST = "https://suggestqueries.google.com/complete/search"
REGIONS = ["US", "GB"]

SEEDS = {
    "guess_animal": ["guess the animal", "animals for kids", "animal quiz for kids", "animal names for kids",
                     "guess the animal for kids"],
    "count": ["counting for kids", "learn numbers for kids", "count with me", "numbers for toddlers",
              "counting 1 to 10"],
    "colors": ["learn colors", "colors for kids", "colors for toddlers", "colours for kids", "learning colors"],
    "odd_one_out": ["find the odd one out", "odd one out", "spot the difference for kids", "brain games for kids",
                    "puzzles for kids"],
    "abc": ["abc for toddlers", "learn abc", "phonics for kids", "alphabet for kids", "learn letters for kids"],
    "shapes": ["shapes for kids", "learn shapes", "shapes for toddlers", "shapes for preschool"],
    "_all": ["learning videos for toddlers", "educational videos for kids", "preschool learning", "kids learning"],
}
MAIN = {  # the phrase each title should lead with
    "guess_animal": "Guess the Animal", "count": "Counting for Kids", "colors": "Learn Colors",
    "odd_one_out": "Find the Odd One Out", "abc": "ABC for Toddlers", "shapes": "Learn Shapes",
}
HASHTAG = {
    "guess_animal": "#guesstheanimal", "count": "#counting", "colors": "#learncolors",
    "odd_one_out": "#oddoneout", "abc": "#abc", "shapes": "#shapes",
}
# brands, shows, people and off-topic words we must never put in our metadata
BLOCK = re.compile(
    r"\b(vhs|dvd|logo|promo|concert|live|intro|trailer|cocomelon|blippi|pinkfong|baby ?shark|super simple|"
    r"ms ?rachel|rachel|kevin|langue|little baby bum|sesame|peppa|bluey|disney|nick|pbs|cartoon network|"
    r"chuchu|lingokids|bounce patrol|dave and ava|jack hartmann|kids tv|hey bear|numberblocks|alphablocks|"
    r"roblox|minecraft|fortnite|tiktok|meme|prank|scary|horror|showtime|favourites|hits|video hits|"
    r"song|songs|sound|sounds|noise|noises|rhyme|rhymes|asmr|movie|full episode|episode|season|in hindi|in urdu|in spanish|"
    r"espanol|español|tamil|telugu|arabic|bangla|nepali|sinhala|\d{4})\b", re.I)


def suggestions(q, region):
    try:
        r = requests.get(SUGGEST, params={"client": "firefox", "ds": "yt", "hl": "en", "gl": region, "q": q},
                         timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return [s for s in r.json()[1] if isinstance(s, str)]
    except Exception:
        return []


def live_keywords(fmt, limit=30):
    """Ranked list of phrases US/UK viewers are searching for this topic."""
    score = {}
    seeds = SEEDS.get(fmt, []) + SEEDS["_all"]
    for seed in seeds:
        for region in REGIONS:
            for pos, s in enumerate(suggestions(seed, region)):
                s = re.sub(r"\s+", " ", s.lower()).strip()
                if len(s) < 4 or len(s) > 40 or BLOCK.search(s):
                    continue
                score[s] = score.get(s, 0) + (10 - pos) + (3 if region == "US" else 2)
            time.sleep(0.15)
    for seed in seeds:  # our own seed phrases always count
        score[seed] = score.get(seed, 0) + 5
    return [k for k, _ in sorted(score.items(), key=lambda kv: -kv[1])][:limit]


def enhance(meta, log=print):
    """Rewrite title / description / tags with live US+UK search phrases. Safe: on any error the
    original metadata is kept."""
    fmt = meta.get("format", "").replace("_long", "").replace("_compilation", "")
    long_video = bool(meta.get("long"))
    if fmt not in SEEDS:
        return meta
    try:
        kws = live_keywords(fmt)
    except Exception as e:
        log("seo: keyword lookup failed, keeping original metadata:", e)
        return meta
    if len(kws) < 5:
        log("seo: too few live keywords, keeping original metadata")
        return meta
    m = dict(meta)

    # title: lead with the main searched phrase, keep the fun hook, end with #shorts
    title = re.sub(r"\s*#shorts\s*$", "", meta.get("title", ""), flags=re.I).strip()
    main = MAIN[fmt]
    if main.lower() not in title.lower() and not long_video:
        title = f"{main} | {title}"
    limit = 100 if long_video else 90
    if len(title) > limit:
        title = title[:limit].rsplit(" ", 1)[0]
    m["title"] = title if long_video else title + " #shorts"

    # description: keyword-rich first lines (what search + Shorts shelf read), then the original text
    top = [k for k in kws if k.lower() != main.lower()][:6]
    parts = meta.get("description", "").split("\n\n")
    first = parts[0]
    middle = ("\n\n".join(p for p in parts[1:] if not p.startswith("#")) + "\n\n") if long_video else ""
    m["description"] = (
        f"{first}\n\n{middle}"
        f"Perfect for toddlers and preschool kids in the USA and UK: {', '.join(top)}.\n"
        "New fun learning videos for kids every day - subscribe so you never miss one! 🎉\n\n"
        + ("" if long_video else "#shorts ") + f"#kidslearning {HASHTAG[fmt]} #toddlerlearning #preschool"
    )

    # tags: live phrases first, then our own
    tags = []
    for t in kws + meta.get("tags", []):
        if t not in tags:
            tags.append(t)
    m["tags"] = tags
    m["seo_keywords"] = kws[:15]
    log("seo: title ->", m["title"])
    log("seo: top US/UK searches ->", ", ".join(kws[:8]))
    return m


# --------------------------------------------------------------------------- #
# Pakistan channel (Dimagh Lagao)
# --------------------------------------------------------------------------- #
SEEDS_PK = {
    "gk": ["gk quiz in urdu", "general knowledge questions in urdu", "general knowledge questions and answers pakistan",
           "gk questions about pakistan", "urdu quiz", "pakistan gk"],
    "cricket": ["cricket quiz", "cricket quiz pakistan", "pakistan cricket", "cricket gk", "cricket quiz urdu"],
    "paheli": ["paheliyan in urdu", "paheliyan in urdu with answer", "urdu paheliyan", "paheliyan mushkil",
               "riddles in urdu"],
    "fact": ["amazing facts urdu", "amazing facts in urdu", "kya aap jante hain", "interesting facts in urdu",
             "amazing facts shorts"],
    "gta": ["gta 6", "gta 6 quiz", "gta vi", "gta 6 facts", "gta vice city"],
    "islami": ["islamic quiz in urdu", "islamic questions in urdu", "islami sawal jawab", "islamic gk",
               "islamic quiz"],
    "game": ["gaming quiz", "free fire quiz", "pubg quiz", "minecraft quiz", "gamer quiz urdu"],
    "_all": ["urdu quiz", "quiz in urdu", "dimagh lagao"],
}
MAIN_PK = {"gk": "GK Quiz in Urdu", "cricket": "Cricket Quiz Pakistan", "paheli": "Urdu Paheliyan",
           "fact": "Amazing Facts in Urdu", "gta": "GTA 6 Quiz", "islami": "Islamic Quiz in Urdu",
           "game": "Gaming Quiz"}
HASHTAG_PK = {"gk": "#gkquiz", "cricket": "#cricketquiz", "paheli": "#paheliyan", "fact": "#amazingfacts",
              "gta": "#gta6", "islami": "#islamicquiz", "game": "#gamingquiz"}
BLOCK_PK = re.compile(
    r"\b(hub|world|point|master|channel|ducky|techno|gamerz|bhai|hindi|english|tamil|bangla|bengali|"
    r"kaise|banaye|song|songs|live|stream|trailer|gameplay|ending|leak|leaks|download|apk|mod|"
    r"bhejo|funny|vlog|prank|\d{4})\b", re.I)


def live_keywords_pk(fmt, limit=30):
    score = {}
    seeds = SEEDS_PK.get(fmt, []) + SEEDS_PK["_all"]
    for seed in seeds:
        for pos, s in enumerate(suggestions(seed, "PK")):
            s = re.sub(r"\s+", " ", s.lower()).strip()
            if len(s) < 4 or len(s) > 45 or BLOCK.search(s) or BLOCK_PK.search(s):
                continue
            score[s] = score.get(s, 0) + (10 - pos)
        time.sleep(0.15)
    for seed in seeds:
        score[seed] = score.get(seed, 0) + 5
    return [k for k, _ in sorted(score.items(), key=lambda kv: -kv[1])][:limit]


def enhance_pk(meta, log=print):
    fmt = meta.get("format", "").replace("_long", "")
    if fmt not in SEEDS_PK:
        return meta
    try:
        kws = live_keywords_pk(fmt)
    except Exception as e:
        log("seo-pk: lookup failed, keeping metadata:", e)
        return meta
    if len(kws) < 5:
        return meta
    m = dict(meta)
    title = re.sub(r"\s*#shorts\s*$", "", meta.get("title", ""), flags=re.I).strip()
    main = MAIN_PK[fmt]
    if main.lower() not in title.lower():
        title = f"{main} | {title}"
    if len(title) > 90:
        title = title[:90].rsplit(" ", 1)[0]
    m["title"] = title + " #shorts"
    top = [k for k in kws if k.lower() != main.lower()][:6]
    body = meta.get("description", "")
    m["description"] = (
        f"{body.split(chr(10) + chr(10))[0]}\n\n"
        f"Is video mein: {', '.join(top)}.\n\n"
        + "\n\n".join(body.split("\n\n")[1:2]) +
        "\n\nRoz naye Urdu quiz, paheliyan aur facts! Channel subscribe karein 🔔\n\n"
        f"#shorts #urdu {HASHTAG_PK[fmt]} #pakistan #dimaghlagao"
    )
    tags = []
    for t in kws + meta.get("tags", []):
        if t not in tags:
            tags.append(t)
    m["tags"] = tags
    m["seo_keywords"] = kws[:15]
    log("seo-pk: title ->", m["title"])
    log("seo-pk: top Pakistan searches ->", ", ".join(kws[:8]))
    return m


SEEDS_SERIES = ["suspense story urdu", "urdu kahani", "mystery story urdu", "urdu story", "sachi kahani",
                "suspense kahani", "urdu thriller story", "pakistani story", "jasoosi kahani", "emotional story urdu"]


def enhance_series(meta, log=print):
    """Suspense series: keep the exact searchable title ("<Name> | Part n/10"), add the phrases people in
    Pakistan are searching right now to the tags and description."""
    try:
        score = {}
        name = meta.get("tags", [""])[0]
        for seed in [name] + SEEDS_SERIES:
            for pos, sug in enumerate(suggestions(seed, "PK")):
                sug = re.sub(r"\s+", " ", sug.lower()).strip()
                if len(sug) < 4 or len(sug) > 45 or BLOCK.search(sug) or BLOCK_PK.search(sug):
                    continue
                score[sug] = score.get(sug, 0) + (10 - pos)
            time.sleep(0.15)
        kws = [k for k, _ in sorted(score.items(), key=lambda kv: -kv[1])][:20]
    except Exception as e:
        log("seo-series: lookup failed, keeping metadata:", e)
        return meta
    if len(kws) < 3:
        return meta
    m = dict(meta)
    tags = []
    for t in meta.get("tags", [])[:4] + kws + meta.get("tags", [])[4:]:
        if t not in tags:
            tags.append(t)
    m["tags"] = tags
    body = meta.get("description", "")
    m["description"] = body + "\n\nSearch: " + ", ".join(kws[:10])
    m["seo_keywords"] = kws
    log("seo-series: top keywords ->", ", ".join(kws[:8]))
    return m

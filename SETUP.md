# AI Shorts Bot: Setup Guide (Roman Urdu)

Ye bot har 10 ghante baad khud ek **10 second ki AI video (YouTube Short)** banata hai aur aapke channel par upload karta hai. Ye GitHub ke cloud par chalta hai, isliye **aapka computer band ho tab bhi** kaam karta rahega. Saare tools free hain.

**Har video kaise banti hai:**
1. US aur UK ki trending YouTube videos ke titles aur tags padhe jaate hain.
2. AI ek naya idea chunta hai ("AI imagines…", "What if…"), aur us ke liye title, description, tags aur hashtags likhta hai.
3. 3 AI images banti hain (Pollinations.ai, free).
4. Editing hoti hai: zoom aur pan motion, transitions, color boost, bade yellow/white captions, aur AI voiceover (edge-tts).
5. Video YouTube par #Shorts ke saath upload hoti hai, aur "AI-generated" disclosure khud on ho jata hai.

---

## Step 1: Code GitHub par daalein
1. github.com par jayein → **New repository** → naam `ai-shorts-bot` → **Private** chunein → Create.
2. Is folder ki saari files upload karein ("uploading an existing file"). `.github/workflows/shorts.yml` bhi zaroor upload honi chahiye.

## Step 2: Google Cloud mein YouTube API on karein (sirf ek baar)
1. https://console.cloud.google.com par jayein → naya project banayein (`ai-shorts-bot`).
2. **APIs & Services → Library** → "YouTube Data API v3" search karein → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External**
   - App name: kuch bhi rakh lein, aur apni email daal dein
   - **Audience / Test users** mein apni Gmail add karein
   - ⚠️ Phir **"Publish app" (In production)** zaroor dabayein. Agar app "Testing" mode mein rahi to har 7 din baad connection toot jayega.
4. **Credentials → Create credentials → OAuth client ID** → type **Desktop app** → JSON download karein.
5. Download ki hui file ka naam badal kar `client_secret.json` rakhein aur use `get_token.py` wale folder mein rakh dein.

## Step 3: Channel connect karein (apne computer par, sirf ek baar)
Python install karein (python.org se), phir:
```
pip install google-auth-oauthlib
python get_token.py
```
Browser khulega. **AlexHarray** channel chunein → "Google hasn't verified this app" aaye to **Advanced → Continue** dabayein → **Allow**.
Screen par 3 values aayengi: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

## Step 4: GitHub Secrets daalein
Repository → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `YT_CLIENT_ID` | Step 3 se |
| `YT_CLIENT_SECRET` | Step 3 se |
| `YT_REFRESH_TOKEN` | Step 3 se |
| `GEMINI_API_KEY` | *(optional, behtar scripts ke liye)* aistudio.google.com → "Get API key" (free) |

## Step 5: Pehle test karein
**Actions** tab → "AI Shorts Bot" → **Run workflow** → mode **test** → Run.
5 se 8 minute baad run kholein → neeche **Artifacts** se video download karke dekhein.
Pasand aaye to mode **upload** chala kar pehli video upload karein. Uske baad bot khud har 10 ghante upload karega.

---

## ⚠️ Bahut zaroori: YouTube API Audit
YouTube ka rule hai ke kisi naye (unverified) Google Cloud project se API ke zariye upload hone wali videos **"Private (locked)"** ho jati hain. Isliye:
1. Ye form bharein: **YouTube API Services – Audit and Quota Extension Form**
   (Google mein search karein: "YouTube API audit form"). Ye free hai.
2. Form mein likhein ke ye aapka personal tool hai jo sirf aapke apne channel par aapki apni original AI content upload karta hai.
3. Approval aane tak videos private rahengi. Approval ke baad public upload hongi.
   Tab tak GitHub mein **Settings → Variables → `PRIVACY_STATUS` = `private`** set kar dein.

## Views ke liye tips
- Bot titles aur tags trending US/UK topics se banata hai, lekin **views ki koi guarantee nahi**.
- Har kuch din baad videos dekhein. Jo video zyada chale, us jaise ideas `bot/main.py` ke `FALLBACK_IDEAS` mein daal dein.
- YouTube mass-produced/repetitive content pasand nahi karta. Isliye har video ka idea alag hota hai, phir bhi kabhi kabhi apni khud ki videos bhi daalte rahein.
- Background music chahiye to YouTube Studio → **Audio Library** se free tracks download karke repo mein `music/` folder bana kar daal dein. Bot khud halki awaz mein mix karega.

## Settings badalna
`.github/workflows/shorts.yml` mein:
- `MIN_HOURS_BETWEEN_UPLOADS: "10"`: kitne ghante baad upload ho
- `VIDEO_SECONDS: "10"`: video ki lambai
- `TTS_VOICE` env add karke awaz badal sakte hain (jaise `en-GB-RyanNeural` UK accent ke liye)

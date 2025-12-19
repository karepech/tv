import requests
import json
import re
import os
from datetime import datetime, timedelta, timezone

# =====================================================
# API-FOOTBALL (RapidAPI)
# =====================================================
API_BASE = "https://v3.football.api-sports.io"
API_KEY = os.getenv("RAPIDAPI_KEY")

HEADERS = {
    "x-rapidapi-host": "v3.football.api-sports.io",
    "x-rapidapi-key": API_KEY
}

# =====================================================
# WAKTU
# =====================================================
TIMEZONE_WIB = timezone(timedelta(hours=7))
NOW = datetime.now(TIMEZONE_WIB)
HORIZON = NOW + timedelta(days=1)

# =====================================================
# OUTPUT
# =====================================================
OUTPUT_DIR = "output"
OUTPUT_M3U = os.path.join(OUTPUT_DIR, "event_combined.m3u")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "schedule.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =====================================================
# LOAD FILE
# =====================================================
with open("playlist_sources.txt", encoding="utf-8") as f:
    PLAYLIST_URLS = [x.strip() for x in f if x.strip()]

with open("providers.json", encoding="utf-8") as f:
    PROVIDERS = json.load(f)

# =====================================================
# UTIL
# =====================================================
def clean(txt: str) -> str:
    return re.sub(r"[^A-Z0-9 ]+", " ", txt.upper()).strip()

def api_get(endpoint, params=None):
    try:
        r = requests.get(API_BASE + endpoint, headers=HEADERS, params=params, timeout=30)
        if r.status_code != 200:
            return []
        return r.json().get("response", [])
    except:
        return []

# =====================================================
# LOAD IPTV CHANNEL (EVENT ONLY)
# =====================================================
def load_channels():
    channels = []

    for src in PLAYLIST_URLS:
        try:
            lines = requests.get(src, timeout=60).text.splitlines()
        except:
            continue

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if line.startswith("#EXTINF") and i + 1 < len(lines):
                url = lines[i + 1].strip()

                if (
                    not url
                    or url.startswith("#")
                    or not url.lower().startswith("http")
                ):
                    i += 1
                    continue

                raw = line.split(",", 1)[-1].strip()
                name = raw.upper()

                # HANYA EVENT MATCH
                is_match = (
                    re.search(r"\sVS\s", name)
                    or re.search(r"\sV\s", name)
                    or re.search(r"\s-\s", name)
                    or "WIB" in name
                )

                if is_match:
                    channels.append({
                        "raw": raw,
                        "clean": clean(raw),
                        "url": url
                    })

                i += 2
            else:
                i += 1

    return channels

# =====================================================
# API DATA
# =====================================================
def get_live_matches():
    return api_get("/fixtures", {"live": "all"})

def get_schedule_matches():
    data = []
    for d in [NOW.date(), (NOW + timedelta(days=1)).date()]:
        data += api_get("/fixtures", {"date": d.isoformat()})
    return data

# =====================================================
# GENERATE EVENT PLAYLIST
# =====================================================
def generate():
    channels = load_channels()
    api_live = get_live_matches()
    api_schedule = get_schedule_matches()

    now_str = NOW.strftime("%Y-%m-%d %H:%M:%S WIB")

    m3u = [
        "#EXTM3U",
        f"# UPDATED: {now_str}",
        "# MODE: EVENT MATCH ONLY (DUPLICATE ALLOWED)",
        "# SOURCE: IPTV + API-FOOTBALL"
    ]

    schedule = []

    # =================================================
    # 1️⃣ EVENT DARI IPTV (PRIORITAS)
    # =================================================
    for ch in channels:
        m3u.append(
            f'#EXTINF:-1 group-title="LIVE | EVENT",{ch["raw"]}'
        )
        m3u.append(ch["url"])

    # =================================================
    # 2️⃣ LIVE EVENT DARI API (MULTI PROVIDER)
    # =================================================
    for m in api_live:
        league = clean(m["league"]["name"])
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]
        title = f"{home} vs {away}"

        schedule.append({
            "league": league,
            "match": title,
            "status": "LIVE"
        })

        for key, providers in PROVIDERS.items():
            if key in league:
                for p in providers:
                    p_clean = clean(p)
                    for ch in channels:
                        if p_clean in ch["clean"]:
                            m3u.append(
                                f'#EXTINF:-1 group-title="LIVE | EVENT",{title} ({p})'
                            )
                            m3u.append(ch["url"])

    # =================================================
    # 3️⃣ PRE-LIVE (H+1)
    # =================================================
    for m in api_schedule:
        kickoff = datetime.fromisoformat(
            m["fixture"]["date"].replace("Z", "+00:00")
        ).astimezone(TIMEZONE_WIB)

        if kickoff <= HORIZON:
            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]
            title = f"{home} vs {away}"
            time_str = kickoff.strftime("%d %b %H:%M WIB")

            schedule.append({
                "match": title,
                "status": "PRE-LIVE",
                "kickoff": time_str
            })

            m3u.append(
                f'#EXTINF:-1 group-title="PRE-LIVE | EVENT",{title} (Kick-off {time_str})'
            )
            m3u.append("http://prelive.placeholder/stream")

    # =================================================
    # FALLBACK
    # =================================================
    if len(m3u) <= 4:
        m3u.append(
            '#EXTINF:-1 group-title="INFO",Tidak ada event pertandingan'
        )
        m3u.append("http://info.placeholder/stream")

    # =================================================
    # SAVE
    # =================================================
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)

    print("[OK] EVENT MATCH ONLY playlist updated")

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    generate()

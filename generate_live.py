import requests
import json
import re
import os
from datetime import datetime, timedelta, timezone

# =====================================================
# API-FOOTBALL
# =====================================================
API_BASE = "https://v3.football.api-sports.io"
API_KEY = os.getenv("RAPIDAPI_KEY")

HEADERS = {
    "x-rapidapi-host": "v3.football.api-sports.io",
    "x-rapidapi-key": API_KEY
}

# =====================================================
# TIME
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
# LOAD SOURCE FILES
# =====================================================
with open("playlist_sources.txt", encoding="utf-8") as f:
    PLAYLIST_URLS = [x.strip() for x in f if x.strip()]

with open("providers.json", encoding="utf-8") as f:
    PROVIDERS = json.load(f)

# =====================================================
# SPORT DEFINITIONS (KETAT)
# =====================================================
SPORT_LIGAS = [
    "BUNDESLIGA", "PREMIER", "LALIGA", "LA LIGA",
    "SERIE A", "LIGUE", "UEFA", "UCL", "UEL",
    "CHAMPIONS", "EUROPA",
    "MOTOGP", "FORMULA", "F1",
    "NBA", "NFL"
]

SPORT_PROVIDERS = [
    "BEIN", "SSC", "DAZN", "SKY",
    "ESPN", "SPOTV", "FOX SPORTS"
]

# =====================================================
# UTIL
# =====================================================
def clean(text: str) -> str:
    return re.sub(r"[^A-Z0-9 ]+", " ", text.upper()).strip()

def is_sport_event(name: str) -> bool:
    name = name.upper()

    # 1️⃣ PERTANDINGAN (PALING KUAT)
    if re.search(r"\sVS\s|\sV\s", name):
        return True

    # 2️⃣ LIGA SPORT
    if any(lg in name for lg in SPORT_LIGAS):
        return True

    # 3️⃣ PROVIDER SPORT
    if any(p in name for p in SPORT_PROVIDERS):
        return True

    return False

def api_get(endpoint, params=None):
    try:
        r = requests.get(API_BASE + endpoint, headers=HEADERS, params=params, timeout=30)
        if r.status_code != 200:
            return []
        return r.json().get("response", [])
    except:
        return []

# =====================================================
# LOAD IPTV EVENT CHANNEL (ANTI MOVIE)
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

                if not is_sport_event(raw):
                    i += 2
                    continue

                channels.append({
                    "raw": raw,
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
# GENERATE FINAL PLAYLIST
# =====================================================
def generate():
    iptv_events = load_channels()
    api_live = get_live_matches()
    api_schedule = get_schedule_matches()

    now_str = NOW.strftime("%Y-%m-%d %H:%M:%S WIB")

    m3u = [
        "#EXTM3U",
        f"# UPDATED: {now_str}",
        "# MODE: SPORT EVENT ONLY (NO MOVIE)",
        "# SOURCE: IPTV + API-FOOTBALL"
    ]

    schedule = []

    # =================================================
    # 1️⃣ IPTV EVENTS (PRIORITAS)
    # =================================================
    for ch in iptv_events:
        m3u.append(f'#EXTINF:-1 group-title="LIVE | EVENT",{ch["raw"]}')
        m3u.append(ch["url"])

    # =================================================
    # 2️⃣ API LIVE EVENTS
    # =================================================
    for m in api_live:
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]
        title = f"{home} vs {away}"

        schedule.append({
            "match": title,
            "status": "LIVE"
        })

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

            m3u.append(
                f'#EXTINF:-1 group-title="PRE-LIVE | EVENT",{title} (Kick-off {time_str})'
            )
            m3u.append("http://prelive.placeholder/stream")

            schedule.append({
                "match": title,
                "status": "PRE-LIVE",
                "kickoff": time_str
            })

    if len(m3u) <= 4:
        m3u.append('#EXTINF:-1 group-title="INFO",Tidak ada event sport')
        m3u.append("http://info.placeholder/stream")

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)

    print("[OK] SPORT EVENT ONLY playlist generated")

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    generate()

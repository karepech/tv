import requests
import json
import re
import os
from datetime import datetime, timedelta, timezone

# =====================================================
# API-FOOTBALL (RapidAPI) CONFIG
# =====================================================

API_BASE = "https://v3.football.api-sports.io"
API_KEY = os.getenv("RAPIDAPI_KEY")  # dari GitHub Secrets

HEADERS = {
    "x-rapidapi-host": "v3.football.api-sports.io",
    "x-rapidapi-key": API_KEY
}

# =====================================================
# WAKTU
# =====================================================

TIMEZONE_WIB = timezone(timedelta(hours=7))
NOW = datetime.now(TIMEZONE_WIB)
HORIZON = NOW + timedelta(days=1)  # 1 hari ke depan

# =====================================================
# OUTPUT
# =====================================================

OUTPUT_DIR = "output"
OUTPUT_M3U = os.path.join(OUTPUT_DIR, "event_combined.m3u")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "schedule.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# =====================================================
# LOAD FILE LOKAL
# =====================================================

with open("providers.json", encoding="utf-8") as f:
    PROVIDERS = json.load(f)

with open("playlist_sources.txt", encoding="utf-8") as f:
    PLAYLIST_URLS = [x.strip() for x in f if x.strip()]

# =====================================================
# UTIL
# =====================================================

def clean(text):
    return re.sub(r"[^A-Z0-9 ]+", " ", text.upper()).strip()

def api_get(endpoint, params=None):
    try:
        r = requests.get(
            API_BASE + endpoint,
            headers=HEADERS,
            params=params,
            timeout=30
        )
        if r.status_code != 200:
            return []
        return r.json().get("response", [])
    except:
        return []

# =====================================================
# LOAD IPTV CHANNEL
# =====================================================

def load_channels():
    channels = []
    for url in PLAYLIST_URLS:
        try:
            lines = requests.get(url, timeout=60).text.splitlines()
        except:
            continue

        i = 0
        while i < len(lines):
            if lines[i].startswith("#EXTINF") and i + 1 < len(lines):
                name = clean(lines[i].split(",")[-1])
                stream = lines[i + 1].strip()
                channels.append((name, stream))
                i += 2
            else:
                i += 1

    return channels

# =====================================================
# LIVE MATCHES
# =====================================================

def get_live_matches():
    return api_get("/fixtures", {"live": "all"})

# =====================================================
# SCHEDULE (HARI INI + BESOK)
# =====================================================

def get_schedule_matches():
    matches = []
    for d in [NOW.date(), (NOW + timedelta(days=1)).date()]:
        matches += api_get("/fixtures", {"date": d.isoformat()})
    return matches

# =====================================================
# GENERATE PLAYLIST
# =====================================================

def generate():
    if not API_KEY:
        raise RuntimeError("RAPIDAPI_KEY belum tersedia (cek GitHub Secrets)")

    channels = load_channels()
    live_matches = get_live_matches()
    schedule_matches = get_schedule_matches()

    now_str = NOW.strftime("%Y-%m-%d %H:%M WIB")

    m3u = [
        "#EXTM3U",
        f"# UPDATED: {now_str}",
        "# SOURCE: API-FOOTBALL (RapidAPI)",
        "# MODE: PRE-LIVE -> LIVE AUTO"
    ]

    schedule = []

    # ================= LIVE =================
    for m in live_matches:
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
                    for ch_name, ch_url in channels:
                        if p_clean in ch_name:
                            m3u.append(
                                f'#EXTINF:-1 group-title="LIVE | {key}",{title} ({p})'
                            )
                            m3u.append(ch_url)

    # ================= PRE-LIVE =================
    for m in schedule_matches:
        kickoff = datetime.fromisoformat(
            m["fixture"]["date"].replace("Z", "+00:00")
        ).astimezone(TIMEZONE_WIB)

        if NOW <= kickoff <= HORIZON:
            league = clean(m["league"]["name"])
            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]
            title = f"{home} vs {away}"
            time_str = kickoff.strftime("%d %b %H:%M WIB")

            schedule.append({
                "league": league,
                "match": title,
                "status": "PRE-LIVE",
                "kickoff": time_str
            })

            m3u.append(
                f'#EXTINF:-1 group-title="PRE-LIVE | {league}",{title} (Kick-off {time_str})'
            )
            m3u.append("http://prelive.placeholder/stream")

    # ================= INFO JIKA KOSONG =================
    if len(m3u) <= 4:
        m3u.append(
            '#EXTINF:-1 group-title="INFO",Tidak ada pertandingan live / jadwal 24 jam ke depan'
        )
        m3u.append("http://info.placeholder/stream")

    # SIMPAN FILE
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)

    print("[OK] event_combined.m3u & schedule.json updated")

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    generate()

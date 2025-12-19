import requests
import json
import re
import os
from datetime import datetime, timedelta, timezone

# =====================================================
# KONFIGURASI
# =====================================================

API_KEY = "1"
LIVE_API = "https://www.thesportsdb.com/api/v1/json/1/livescore.php?s=Soccer"
NEXT_API = "https://www.thesportsdb.com/api/v1/json/1/eventsnextleague.php?id="

LEAGUE_IDS = {
    "PREMIER LEAGUE": "4328",
    "LA LIGA": "4335",
    "SERIE A": "4332",
    "BUNDESLIGA": "4331",
    "LIGUE 1": "4334",
    "SAUDI": "4646"
}

TIMEZONE_WIB = timezone(timedelta(hours=7))
NOW_WIB = datetime.now(TIMEZONE_WIB)
HORIZON = NOW_WIB + timedelta(days=1)  # ⬅️ 1 HARI KE DEPAN

OUTPUT_DIR = "output"
OUTPUT_M3U = os.path.join(OUTPUT_DIR, "event_combined.m3u")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "schedule.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# =====================================================
# LOAD FILE EKSTERNAL
# =====================================================

with open("providers.json", encoding="utf-8") as f:
    PROVIDERS = json.load(f)

with open("playlist_sources.txt", encoding="utf-8") as f:
    PLAYLIST_URLS = [x.strip() for x in f if x.strip()]

# =====================================================
# UTIL
# =====================================================

def clean(txt):
    return re.sub(r"[^A-Z0-9 ]+", " ", txt.upper()).strip()

def safe_get(url):
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        if "application/json" not in r.headers.get("Content-Type", ""):
            return None
        return r.json()
    except:
        return None

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
# LIVE EVENT (REAL STATUS)
# =====================================================

def get_live_events():
    data = safe_get(LIVE_API)
    if not data:
        return []

    events = data.get("events") or []
    return [
        e for e in events
        if e.get("strStatus") in ("Live", "In Progress")
    ]

# =====================================================
# PRE-LIVE (JADWAL 1 HARI KE DEPAN)
# =====================================================

def get_pre_live_events():
    upcoming = []

    for league, lid in LEAGUE_IDS.items():
        data = safe_get(NEXT_API + lid)
        if not data:
            continue

        for e in data.get("events", []):
            if not e.get("dateEvent") or not e.get("strTime"):
                continue

            try:
                kickoff_utc = datetime.strptime(
                    f"{e['dateEvent']} {e['strTime']}",
                    "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=timezone.utc)

                kickoff_wib = kickoff_utc.astimezone(TIMEZONE_WIB)

                # ⬇️ FILTER 1 HARI KE DEPAN
                if NOW_WIB <= kickoff_wib <= HORIZON:
                    upcoming.append((league, e, kickoff_wib))
            except:
                continue

    return upcoming

# =====================================================
# GENERATE MODE A (PRE-LIVE → LIVE)
# =====================================================

def generate():
    channels = load_channels()
    live_events = get_live_events()
    pre_live_events = get_pre_live_events()

    m3u = ["#EXTM3U"]
    schedule = []

    # ---------- LIVE ----------

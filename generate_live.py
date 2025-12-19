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

# League ID (penting untuk PRE-LIVE)
LEAGUE_IDS = {
    "PREMIER LEAGUE": "4328",
    "LA LIGA": "4335",
    "SERIE A": "4332",
    "BUNDESLIGA": "4331",
    "LIGUE 1": "4334",
    "SAUDI": "4646"
}

TIMEZONE_WIB = timezone(timedelta(hours=7))

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
        print(f"[IPTV] {url}")
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

    print(f"[OK] IPTV channel loaded: {len(channels)}")
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
# PRE-LIVE EVENT (JADWAL)
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

                # tampilkan max H-6 jam
                if datetime.now(TIMEZONE_WIB) <= kickoff_wib <= datetime.now(TIMEZONE_WIB) + timedelta(hours=6):
                    upcoming.append((league, e, kickoff_wib))
            except:
                continue

    return upcoming

# =====================================================
# GENERATE MODE A
# =====================================================

def generate():
    channels = load_channels()
    live_events = get_live_events()
    pre_live_events = get_pre_live_events()

    m3u = ["#EXTM3U"]
    schedule = []

    # ---------------- LIVE ----------------
    for e in live_events:
        league = clean(e.get("strLeague", ""))
        home = e.get("strHomeTeam", "")
        away = e.get("strAwayTeam", "")
        title = f"{home} vs {away}"

        schedule.append({"league": league, "match": title, "status": "LIVE"})

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

    # ---------------- PRE-LIVE ----------------
    for league, e, kickoff in pre_live_events:
        home = e.get("strHomeTeam", "")
        away = e.get("strAwayTeam", "")
        title = f"{home} vs {away}"
        time_str = kickoff.strftime("%H:%M WIB")

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

    # SIMPAN
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)

    print("[DONE] MODE A generated")

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    generate()

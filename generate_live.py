import requests
import json
import re
from datetime import datetime, timezone

API_KEY = "1"
LIVE_API = "https://www.thesportsdb.com/api/v1/json/1/livescore.php?s=Soccer"

OUTPUT_M3U = "output/event_combined.m3u"
OUTPUT_JSON = "output/schedule.json"

# =====================================================
# LOAD FILES
# =====================================================

with open("providers.json", encoding="utf-8") as f:
    PROVIDERS = json.load(f)

with open("playlist_sources.txt", encoding="utf-8") as f:
    PLAYLIST_URLS = [x.strip() for x in f if x.strip()]

# =====================================================
# LOAD IPTV CHANNELS
# =====================================================

def load_all_channels():
    channels = []
    for url in PLAYLIST_URLS:
        try:
            print(f"Load IPTV: {url}")
            lines = requests.get(url, timeout=60).text.splitlines()
        except:
            continue

        i = 0
        while i < len(lines):
            if lines[i].startswith("#EXTINF") and i + 1 < len(lines):
                name = lines[i].split(",")[-1].upper()
                stream = lines[i + 1].strip()
                channels.append((name, stream))
                i += 2
            else:
                i += 1
    return channels

# =====================================================
# LOAD LIVE EVENTS (REAL STATUS)
# =====================================================

def get_live_events():
    data = requests.get(LIVE_API, timeout=30).json()
    return [
        e for e in data.get("events", [])
        if e.get("strStatus") in ("Live", "In Progress")
    ]

# =====================================================
# GENERATE LIVE M3U + JSON
# =====================================================

def generate():
    all_channels = load_all_channels()
    events = get_live_events()

    m3u = ["#EXTM3U"]
    schedule = []

    for e in events:
        league = (e.get("strLeague") or "").upper()
        home = e.get("strHomeTeam", "")
        away = e.get("strAwayTeam", "")
        title = f"{home} vs {away}"

        schedule.append({
            "league": league,
            "match": title,
            "status": e.get("strStatus")
        })

        for league_key, provider_list in PROVIDERS.items():
            if league_key in league:
                for provider in provider_list:
                    for ch_name, ch_url in all_channels:
                        if provider in ch_name:
                            m3u.append(
                                f'#EXTINF:-1 group-title="LIVE | {league_key}",{title} ({provider})'
                            )
                            m3u.append(ch_url)

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)

    print("✔ event_combined.m3u updated")
    print("✔ schedule.json updated")

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    generate()

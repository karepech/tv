import requests
import json
import re
import os
from datetime import datetime, timezone

# =====================================================
# KONFIGURASI
# =====================================================

API_KEY = "1"
LIVE_API = "https://www.thesportsdb.com/api/v1/json/1/livescore.php?s=Soccer"

OUTPUT_DIR = "output"
OUTPUT_M3U = os.path.join(OUTPUT_DIR, "event_combined.m3u")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "schedule.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# =====================================================
# LOAD PROVIDER MAPPING
# =====================================================

with open("providers.json", encoding="utf-8") as f:
    PROVIDERS = json.load(f)

# =====================================================
# LOAD PLAYLIST SOURCES
# =====================================================

with open("playlist_sources.txt", encoding="utf-8") as f:
    PLAYLIST_URLS = [x.strip() for x in f if x.strip()]

# =====================================================
# UTIL
# =====================================================

def clean_text(txt):
    return re.sub(r"[^A-Z0-9 ]+", " ", txt.upper()).strip()

# =====================================================
# LOAD IPTV CHANNELS (AMAN)
# =====================================================

def load_all_channels():
    channels = []

    for url in PLAYLIST_URLS:
        print(f"[IPTV] Load: {url}")
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                print(f"[WARN] IPTV HTTP {r.status_code}")
                continue
            lines = r.text.splitlines()
        except Exception as e:
            print(f"[WARN] IPTV gagal: {e}")
            continue

        i = 0
        while i < len(lines):
            if lines[i].startswith("#EXTINF") and i + 1 < len(lines):
                name = clean_text(lines[i].split(",")[-1])
                stream = lines[i + 1].strip()
                channels.append((name, stream))
                i += 2
            else:
                i += 1

    print(f"[OK] Total channel IPTV: {len(channels)}")
    return channels

# =====================================================
# AMBIL LIVE EVENT (REAL STATUS, ANTI ERROR)
# =====================================================

def get_live_events():
    try:
        r = requests.get(
            LIVE_API,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        if r.status_code != 200:
            print(f"[WARN] Live API HTTP {r.status_code}")
            return []

        if "application/json" not in r.headers.get("Content-Type", ""):
            print("[WARN] Live API bukan JSON")
            return []

        data = r.json()
        events = data.get("events")

        if not events:
            print("[INFO] Tidak ada event live")
            return []

        live = [
            e for e in events
            if e.get("strStatus") in ("Live", "In Progress")
        ]

        print(f"[OK] Live event: {len(live)}")
        return live

    except Exception as e:
        print(f"[ERROR] Live API error: {e}")
        return []

# =====================================================
# GENERATE LIVE PLAYLIST + JSON
# =====================================================

def generate():
    all_channels = load_all_channels()
    events = get_live_events()

    m3u = ["#EXTM3U"]
    schedule = []

    for e in events:
        league = clean_text(e.get("strLeague", "UNKNOWN"))
        home = e.get("strHomeTeam", "")
        away = e.get("strAwayTeam", "")
        title = f"{home} vs {away}"

        schedule.append({
            "league": league,
            "match": title,
            "status": e.get("strStatus")
        })

        for league_key, providers in PROVIDERS.items():
            if league_key in league:
                for provider in providers:
                    provider_clean = clean_text(provider)
                    for ch_name, ch_url in all_channels:
                        if provider_clean in ch_name:
                            m3u.append(
                                f'#EXTINF:-1 group-title="LIVE | {league_key}",{title} ({provider})'
                            )
                            m3u.append(ch_url)

    # SIMPAN FILE
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)

    print("[DONE] event_combined.m3u & schedule.json dibuat")

# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    generate()

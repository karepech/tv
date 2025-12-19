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
# FILE LOKAL
# =====================================================

with open("providers.json", encoding="utf-8") as f:
    PROVIDERS = json.load(f)

with open("playlist_sources.txt", encoding="utf-8") as f:
    PLAYLIST_URLS = [x.strip() for x in f if x.strip()]

# =====================================================
# KEYWORD SPORT (FILTER UTAMA)
# =====================================================

SPORT_KEYWORDS = [
    "SPORT", "SPORTS", "LIVE",
    "FOOTBALL", "SOCCER", "FUTSAL",
    "BUNDESLIGA", "PREMIER", "LALIGA",
    "SERIE A", "LIGUE", "UCL", "UEL",
    "VS", "MATCH",
    "BEIN", "SSC", "DAZN", "SKY",
    "ESPN", "SPOTV"
]

# =====================================================
# UTIL
# =====================================================

def clean(text):
    return re.sub(r"[^A-Z0-9 ]+", " ", text.upper()).strip()

def is_sport(name):
    return any(k in name for k in SPORT_KEYWORDS)

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
# LOAD IPTV CHANNEL (SPORT ONLY + VALID URL)
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
            line = lines[i].strip()

            if line.startswith("#EXTINF") and i + 1 < len(lines):
                stream = lines[i + 1].strip()

                # ---- FILTER URL VALID ----
                if (
                    not stream
                    or stream.startswith("#")
                    or len(stream) < 10
                    or not stream.lower().startswith("http")
                ):
                    i += 1
                    continue

                name = clean(line.split(",")[-1])

                # ---- FILTER SPORT ONLY ----
                if not is_sport(name):
                    i += 2
                    continue

                channels.append((name, stream))
                i += 2
            else:
                i += 1

    return channels

# =====================================================
# DETEKSI LIVE DARI IPTV (SPORT ONLY)
# =====================================================

def detect_live_from_iptv(channels):
    live = []
    for name, url in channels:
        if "LIVE" in name or "VS" in name:
            live.append((name, url))
    return live

# =====================================================
# API-FOOTBALL
# =====================================================

def get_live_matches():
    return api_get("/fixtures", {"live": "all"})

def get_schedule_matches():
    matches = []
    for d in [NOW.date(), (NOW + timedelta(days=1)).date()]:
        matches += api_get("/fixtures", {"date": d.isoformat()})
    return matches

# =====================================================
# GENERATE M3U (SPORT ONLY)
# =====================================================

def generate():
    if not API_KEY:
        raise RuntimeError("RAPIDAPI_KEY belum tersedia")

    channels = load_channels()
    iptv_live = detect_live_from_iptv(channels)
    api_live = get_live_matches()
    api_schedule = get_schedule_matches()

    now_str = NOW.strftime("%Y-%m-%d %H:%M:%S WIB")

    m3u = [
        "#EXTM3U",
        f"# UPDATED: {now_str}",
        "# MODE: SPORT ONLY | IPTV LIVE PRIORITY"
    ]

    schedule = []

    # ================= LIVE IPTV =================
    for name, url in iptv_live:
        m3u.append(
            f'#EXTINF:-1 group-title="LIVE | SPORT",{name}'
        )
        m3u.append(url)

    # ================= LIVE API =================
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
                    for ch_name, ch_url in channels:
                        if p_clean in ch_name:
                            m3u.append(
                                f'#EXTINF:-1 group-title="LIVE | SPORT",{title} ({p})'
                            )
                            m3u.append(ch_url)

    # ================= PRE-LIVE =================
    for m in api_schedule:
        kickoff = datetime.fromisoformat(
            m["fixture"]["date"].replace("Z", "+00:00")
        ).astimezone(TIMEZONE_WIB)

        if kickoff <= HORIZON:
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
                f'#EXTINF:-1 group-title="PRE-LIVE | SPORT",{title} (Kick-off {time_str})'
            )
            m3u.append("http://prelive.placeholder/stream")

    # ================= FALLBACK =================
    if len(m3u) <= 3:
        m3u.append(
            '#EXTINF:-1 group-title="INFO",Tidak ada live sport / jadwal 24 jam ke depan'
        )
        m3u.append("http://info.placeholder/stream")

    # SIMPAN
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)

    print("[OK] SPORT ONLY playlist updated")

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    generate()

“””
MiLB Prospect Scanner
Sweeps all minor league levels daily for:

HITTERS:

- Age <= 21
- OPS >= .850
- BB/K >= 0.75
- 50+ PA

PITCHERS (Breakout Profile):

- Age <= 24
- K/9 >= 10.0
- BB/9 <= 3.5
- ERA <= 4.00
- 15+ IP

Posts results ranked by OPS (hitters) and K-BB% (pitchers) to Discord.
“””

import time, requests, os, sys
from datetime import date

CURRENT_YEAR = 2026
EMBED_COLOR_HIT  = 0x2ECC71   # Green — hitters
EMBED_COLOR_PITCH = 0x3498DB  # Blue — pitchers

SPORT_IDS = [11, 12, 13, 14, 15, 16, 17]
SPORT_NAMES = {
11: “AAA”, 12: “AA”, 13: “High-A”, 14: “Single-A”,
15: “Rookie+”, 16: “Rookie”, 17: “DSL/VSL”
}

# Hitter filters

MIN_PA      = 50
MIN_OPS     = 0.850
MIN_BB_K    = 0.75
MAX_AGE_HIT = 21

# Pitcher filters

MIN_IP      = 15.0
MAX_ERA     = 4.00
MIN_K9      = 10.0
MAX_BB9     = 3.5
MAX_AGE_PIT = 24

def get(url, retries=3):
for attempt in range(retries):
try:
r = requests.get(url, timeout=20)
if r.status_code == 200:
return r.json()
if r.status_code == 429:
print(”  Rate limited, waiting 30s…”)
time.sleep(30)
else:
time.sleep(2)
except Exception as e:
print(”  Request error: “ + str(e))
time.sleep(2)
return None

def get_teams_for_sport(sport_id):
data = get(
“https://statsapi.mlb.com/api/v1/teams?sportId=” + str(sport_id) +
“&season=” + str(CURRENT_YEAR)
)
if not data:
return []
return [t[“id”] for t in data.get(“teams”, [])]

def get_team_roster(team_id):
data = get(
“https://statsapi.mlb.com/api/v1/teams/” + str(team_id) +
“/roster?rosterType=active&season=” + str(CURRENT_YEAR) +
“&hydrate=person(birthDate)”
)
if not data:
return []
return data.get(“roster”, [])

def get_stats(player_id, sport_id, group):
data = get(
“https://statsapi.mlb.com/api/v1/people/” + str(player_id) +
“/stats?stats=season&season=” + str(CURRENT_YEAR) +
“&group=” + group + “&sportId=” + str(sport_id)
)
if not data:
return None
for grp in data.get(“stats”, []):
splits = grp.get(“splits”, [])
if splits:
return splits[0].get(“stat”, {})
return None

def calc_age(birth_date_str):
try:
parts = birth_date_str.split(”-”)
bday = date(int(parts[0]), int(parts[1]), int(parts[2]))
today = date.today()
return today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))
except Exception:
return 99

def fmt(val, decimals=3):
if val is None or val == “”:
return “—”
try:
f = float(val)
if decimals == 3:
return “{:.3f}”.format(f).lstrip(“0”) or “.000”
return “{:.2f}”.format(f)
except:
return str(val)

def parse_ip(ip_str):
“”“Convert innings pitched string (e.g. ‘23.1’) to float outs.”””
try:
parts = str(ip_str).split(”.”)
full = int(parts[0])
partial = int(parts[1]) if len(parts) > 1 else 0
return full + partial / 3.0
except:
return 0.0

def scan_level(sport_id):
level_name = SPORT_NAMES.get(sport_id, str(sport_id))
print(“Scanning “ + level_name + “…”)

```
hitters  = []
pitchers = []
seen     = set()

teams = get_teams_for_sport(sport_id)
print("  " + str(len(teams)) + " teams")

for team_id in teams:
    roster = get_team_roster(team_id)
    time.sleep(0.2)

    for entry in roster:
        person    = entry.get("person", {})
        player_id = person.get("id")
        name      = person.get("fullName", "Unknown")
        birth     = person.get("birthDate", "")

        if not player_id or player_id in seen:
            continue
        seen.add(player_id)

        age = calc_age(birth)

        # ── HITTER CHECK ──────────────────────────────
        if age <= MAX_AGE_HIT:
            stat = get_stats(player_id, sport_id, "hitting")
            time.sleep(0.15)
            if stat:
                pa = int(stat.get("plateAppearances", 0) or 0)
                if pa >= MIN_PA:
                    try:
                        ops = float(stat.get("ops", 0) or 0)
                    except:
                        ops = 0
                    bb = int(stat.get("baseOnBalls", 0) or 0)
                    so = int(stat.get("strikeOuts", 1) or 1)
                    bb_k = bb / so if so > 0 else 0
                    if ops >= MIN_OPS and bb_k >= MIN_BB_K:
                        hitters.append({
                            "name":  name,
                            "age":   age,
                            "level": level_name,
                            "team":  "",
                            "pa":    pa,
                            "ops":   ops,
                            "bb_k":  bb_k,
                            "slash": fmt(stat.get("avg")) + "/" + fmt(stat.get("obp")) + "/" + fmt(stat.get("slg")),
                            "OPS":   fmt(stat.get("ops")),
                            "G":     str(stat.get("gamesPlayed", "—")),
                            "H":     str(stat.get("hits", "—")),
                            "2B":    str(stat.get("doubles", "—")),
                            "3B":    str(stat.get("triples", "—")),
                            "HR":    str(stat.get("homeRuns", "—")),
                            "RBI":   str(stat.get("rbi", "—")),
                            "BB":    str(bb),
                            "SO":    str(so),
                            "SB":    str(stat.get("stolenBases", "—")),
                        })

        # ── PITCHER CHECK ─────────────────────────────
        if age <= MAX_AGE_PIT:
            stat = get_stats(player_id, sport_id, "pitching")
            time.sleep(0.15)
            if stat:
                ip = parse_ip(stat.get("inningsPitched", 0))
                if ip >= MIN_IP:
                    try:
                        era  = float(stat.get("era",  99) or 99)
                        k9   = float(stat.get("strikeoutsPer9Inn", 0) or 0)
                        bb9  = float(stat.get("walksPer9Inn", 99) or 99)
                    except:
                        continue

                    # Compute K-BB% approximation from raw counts
                    so_total = int(stat.get("strikeOuts", 0) or 0)
                    bb_total = int(stat.get("baseOnBalls", 0) or 0)
                    bf_total = int(stat.get("battersFaced", 1) or 1)
                    k_bb_pct = (so_total - bb_total) / bf_total if bf_total > 0 else 0

                    if era <= MAX_ERA and k9 >= MIN_K9 and bb9 <= MAX_BB9:
                        pitchers.append({
                            "name":     name,
                            "age":      age,
                            "level":    level_name,
                            "ip":       ip,
                            "k_bb_pct": k_bb_pct,
                            "ERA":      fmt(stat.get("era"), 2),
                            "WHIP":     fmt(stat.get("whip"), 2),
                            "IP":       str(stat.get("inningsPitched", "—")),
                            "K9":       fmt(stat.get("strikeoutsPer9Inn"), 2),
                            "BB9":      fmt(stat.get("walksPer9Inn"), 2),
                            "SO":       str(so_total),
                            "BB":       str(bb_total),
                            "HR":       str(stat.get("homeRuns", "—")),
                            "W":        str(stat.get("wins", "—")),
                            "L":        str(stat.get("losses", "—")),
                            "G":        str(stat.get("gamesPlayed", "—")),
                            "GS":       str(stat.get("gamesStarted", "—")),
                            "SV":       str(stat.get("saves", "—")),
                            "k_bb_pct_str": "{:.1f}".format(k_bb_pct * 100) + "%",
                        })

    time.sleep(0.3)

print("  Hitters: " + str(len(hitters)) + " | Pitchers: " + str(len(pitchers)))
return hitters, pitchers
```

def build_hitter_field(p):
return {
“name”: “🟢 “ + p[“name”] + “ (” + str(p[“age”]) + “) · “ + p[“level”],
“value”: “\n”.join([
“**” + p[“slash”] + “** | OPS: **” + p[“OPS”] + “** | BB/K: **” + “{:.2f}”.format(p[“bb_k”]) + “**”,
p.get(“team”, “—”),
“G:” + p[“G”] + “  PA:” + str(p[“pa”]) + “  H:” + p[“H”] +
“  2B:” + p[“2B”] + “  3B:” + p[“3B”] + “  HR:” + p[“HR”],
“RBI:” + p[“RBI”] + “  BB:” + p[“BB”] + “  K:” + p[“SO”] + “  SB:” + p[“SB”],
]),
“inline”: False
}

def build_pitcher_field(p):
return {
“name”: “🔵 “ + p[“name”] + “ (” + str(p[“age”]) + “) · “ + p[“level”],
“value”: “\n”.join([
“ERA: **” + p[“ERA”] + “** | WHIP: **” + p[“WHIP”] + “** | K-BB%: **” + p[“k_bb_pct_str”] + “**”,
“K/9: **” + p[“K9”] + “** | BB/9: **” + p[“BB9”] + “**”,
“W:” + p[“W”] + “  L:” + p[“L”] + “  SV:” + p[“SV”] +
“  G:” + p[“G”] + “  GS:” + p[“GS”] + “  IP:” + p[“IP”],
“K:” + p[“SO”] + “  BB:” + p[“BB”] + “  HR:” + p[“HR”],
]),
“inline”: False
}

def post_section(webhook_url, title, description, fields, color):
“”“Post a titled section + player fields to Discord.”””
header = {
“embeds”: [{
“title”: title,
“description”: description,
“color”: color,
}]
}
r = requests.post(webhook_url, json=header, timeout=15)
if r.status_code not in (200, 204):
print(“Header post failed: “ + str(r.status_code))
time.sleep(1)

```
chunks = [fields[i:i+25] for i in range(0, len(fields), 25)]
for chunk in chunks:
    payload = {"embeds": [{"color": color, "fields": chunk}]}
    r = requests.post(webhook_url, json=payload, timeout=15)
    if r.status_code not in (200, 204):
        raise Exception("Discord post failed: " + str(r.status_code) + " — " + r.text)
    time.sleep(1)
```

def post_to_discord(webhook_url, all_hitters, all_pitchers):
today = date.today().strftime(”%A, %B %-d, %Y”)

```
# ── HITTERS ──────────────────────────────────────
all_hitters.sort(key=lambda x: x["ops"], reverse=True)
if all_hitters:
    fields = [build_hitter_field(p) for p in all_hitters]
    post_section(
        webhook_url,
        "🟢 MiLB Breakout Hitters — " + today,
        "**" + str(len(all_hitters)) + " players** · Age ≤21 · OPS ≥.850 · BB/K ≥0.75 · 50+ PA · Ranked by OPS",
        fields,
        EMBED_COLOR_HIT,
    )
else:
    requests.post(webhook_url, json={"embeds": [{"title": "🟢 MiLB Breakout Hitters — " + today,
        "description": "No qualifiers today.", "color": EMBED_COLOR_HIT}]}, timeout=15)
    time.sleep(1)

# ── PITCHERS ─────────────────────────────────────
all_pitchers.sort(key=lambda x: x["k_bb_pct"], reverse=True)
if all_pitchers:
    fields = [build_pitcher_field(p) for p in all_pitchers]
    post_section(
        webhook_url,
        "🔵 MiLB Breakout Pitchers — " + today,
        "**" + str(len(all_pitchers)) + " players** · Age ≤24 · K/9 ≥10.0 · BB/9 ≤3.5 · ERA ≤4.00 · 15+ IP · Ranked by K-BB%",
        fields,
        EMBED_COLOR_PITCH,
    )
else:
    requests.post(webhook_url, json={"embeds": [{"title": "🔵 MiLB Breakout Pitchers — " + today,
        "description": "No qualifiers today.", "color": EMBED_COLOR_PITCH}]}, timeout=15)
    time.sleep(1)
```

def main():
webhook_url = os.environ.get(“DISCORD_WEBHOOK_URL”, “”)
if not webhook_url:
print(“ERROR: DISCORD_WEBHOOK_URL not set”)
sys.exit(1)

```
print("Starting MiLB scanner for " + str(CURRENT_YEAR) + "...")

all_hitters  = []
all_pitchers = []

for sport_id in SPORT_IDS:
    h, p = scan_level(sport_id)
    all_hitters.extend(h)
    all_pitchers.extend(p)
    time.sleep(1)

print("\nTotal hitters: " + str(len(all_hitters)))
print("Total pitchers: " + str(len(all_pitchers)))

post_to_discord(webhook_url, all_hitters, all_pitchers)
print("Done!")
```

if **name** == “**main**”:
main()

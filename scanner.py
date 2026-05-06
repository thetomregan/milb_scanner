"""
MiLB Prospect Scanner
Sweeps all minor league levels daily for hitters who meet:
  - Age <= 21
  - OPS >= .850
  - BB/K >= 0.75
  - 50+ PA
Posts results ranked by OPS to Discord.
"""

import json, time, requests, os, sys
from datetime import date
from pathlib import Path

CURRENT_YEAR = 2026
EMBED_COLOR = 0x2ECC71  # Green — distinct from the prospect report

# MLB Stats API sport IDs
# 11=AAA, 12=AA, 13=High-A, 14=Single-A, 15=Rookie Adv, 16=Rookie, 17=DSL
SPORT_IDS = [11, 12, 13, 14, 15, 16, 17]
SPORT_NAMES = {
    11: "AAA", 12: "AA", 13: "High-A", 14: "Single-A",
    15: "Rookie+", 16: "Rookie", 17: "DSL/VSL"
}

# Filter thresholds
MIN_PA       = 50
MIN_OPS      = 0.850
MIN_BB_K     = 0.75
MAX_AGE      = 21


def get(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                print("  Rate limited, waiting 30s...")
                time.sleep(30)
            else:
                time.sleep(2)
        except Exception as e:
            print("  Request error: " + str(e))
            time.sleep(2)
    return None


def get_teams_for_sport(sport_id):
    """Get all teams playing at a given sport/level."""
    data = get(
        "https://statsapi.mlb.com/api/v1/teams?sportId=" + str(sport_id) +
        "&season=" + str(CURRENT_YEAR)
    )
    if not data:
        return []
    return [t["id"] for t in data.get("teams", [])]


def get_team_roster(team_id):
    """Get active roster for a team."""
    data = get(
        "https://statsapi.mlb.com/api/v1/teams/" + str(team_id) +
        "/roster?rosterType=active&season=" + str(CURRENT_YEAR) +
        "&hydrate=person(birthDate)"
    )
    if not data:
        return []
    return data.get("roster", [])


def get_player_hitting_stats(player_id, sport_id):
    """Get season hitting stats for a player at a specific sport level."""
    data = get(
        "https://statsapi.mlb.com/api/v1/people/" + str(player_id) +
        "/stats?stats=season&season=" + str(CURRENT_YEAR) +
        "&group=hitting&sportId=" + str(sport_id)
    )
    if not data:
        return None
    for group in data.get("stats", []):
        splits = group.get("splits", [])
        if splits:
            return splits[0].get("stat", {})
    return None


def calc_age(birth_date_str):
    """Calculate age from birth date string (YYYY-MM-DD)."""
    try:
        parts = birth_date_str.split("-")
        bday = date(int(parts[0]), int(parts[1]), int(parts[2]))
        today = date.today()
        age = today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))
        return age
    except Exception:
        return 99


def fmt(val, decimals=3):
    if val is None or val == "":
        return "—"
    try:
        f = float(val)
        if decimals == 3:
            return "{:.3f}".format(f).lstrip("0") or ".000"
        return "{:.2f}".format(f)
    except:
        return str(val)


def scan_level(sport_id):
    """Scan all teams at a given level, return qualifying players."""
    level_name = SPORT_NAMES.get(sport_id, str(sport_id))
    print("Scanning " + level_name + "...")
    qualifying = []

    teams = get_teams_for_sport(sport_id)
    print("  " + str(len(teams)) + " teams found")

    seen_players = set()

    for team_id in teams:
        roster = get_team_roster(team_id)
        time.sleep(0.2)

        for entry in roster:
            person = entry.get("person", {})
            player_id = person.get("id")
            name = person.get("fullName", "Unknown")
            birth_date = person.get("birthDate", "")

            if not player_id or player_id in seen_players:
                continue
            seen_players.add(player_id)

            age = calc_age(birth_date)
            if age > MAX_AGE:
                continue

            stat = get_player_hitting_stats(player_id, sport_id)
            time.sleep(0.15)

            if not stat:
                continue

            pa = int(stat.get("plateAppearances", 0) or 0)
            if pa < MIN_PA:
                continue

            try:
                ops = float(stat.get("ops", 0) or 0)
            except:
                continue
            if ops < MIN_OPS:
                continue

            bb  = int(stat.get("baseOnBalls", 0) or 0)
            so  = int(stat.get("strikeOuts", 1) or 1)
            bb_k = bb / so if so > 0 else 0
            if bb_k < MIN_BB_K:
                continue

            qualifying.append({
                "name":    name,
                "age":     age,
                "level":   level_name,
                "team":    entry.get("team", {}).get("name", "—") if "team" in entry else "—",
                "pa":      pa,
                "ops":     ops,
                "bb_k":    bb_k,
                "slash":   fmt(stat.get("avg")) + "/" + fmt(stat.get("obp")) + "/" + fmt(stat.get("slg")),
                "OPS":     fmt(stat.get("ops")),
                "G":       str(stat.get("gamesPlayed", "—")),
                "H":       str(stat.get("hits", "—")),
                "2B":      str(stat.get("doubles", "—")),
                "3B":      str(stat.get("triples", "—")),
                "HR":      str(stat.get("homeRuns", "—")),
                "RBI":     str(stat.get("rbi", "—")),
                "BB":      str(bb),
                "SO":      str(so),
                "SB":      str(stat.get("stolenBases", "—")),
            })

        time.sleep(0.3)

    print("  " + str(len(qualifying)) + " qualifying players at " + level_name)
    return qualifying


def build_player_field(p):
    bb_k_str = "{:.2f}".format(p["bb_k"])
    return {
        "name": "🌟 " + p["name"] + " (" + str(p["age"]) + ") · " + p["level"],
        "value": "\n".join([
            "**" + p["slash"] + "** | OPS: **" + p["OPS"] + "** | BB/K: **" + bb_k_str + "**",
            p.get("team", "—"),
            "G:" + p["G"] + "  PA:" + str(p["pa"]) + "  H:" + p["H"] +
            "  2B:" + p["2B"] + "  3B:" + p["3B"] + "  HR:" + p["HR"],
            "RBI:" + p["RBI"] + "  BB:" + p["BB"] + "  K:" + p["SO"] + "  SB:" + p["SB"],
        ]),
        "inline": False
    }


def post_to_discord(webhook_url, all_qualifying):
    today = date.today().strftime("%A, %B %-d, %Y")

    if not all_qualifying:
        payload = {
            "embeds": [{
                "title": "🔍 MiLB Watchlist Scanner — " + today,
                "description": "No players currently meeting all criteria.\n(Age ≤21 · OPS ≥.850 · BB/K ≥0.75 · 50+ PA)",
                "color": EMBED_COLOR,
            }]
        }
        requests.post(webhook_url, json=payload, timeout=15)
        return

    # Sort by OPS descending
    all_qualifying.sort(key=lambda x: x["ops"], reverse=True)

    fields = [build_player_field(p) for p in all_qualifying]

    # Header embed
    header = {
        "embeds": [{
            "title": "🔍 MiLB Watchlist Scanner — " + today,
            "description": (
                "**" + str(len(all_qualifying)) + " players** meeting all criteria across all levels\n" +
                "Filters: Age ≤21 · OPS ≥.850 · BB/K ≥0.75 · 50+ PA · Ranked by OPS"
            ),
            "color": EMBED_COLOR,
        }]
    }
    requests.post(webhook_url, json=header, timeout=15)
    time.sleep(1)

    # Post players in chunks of 25
    chunks = [fields[i:i+25] for i in range(0, len(fields), 25)]
    for chunk in chunks:
        payload = {"embeds": [{"color": EMBED_COLOR, "fields": chunk}]}
        r = requests.post(webhook_url, json=payload, timeout=15)
        if r.status_code not in (200, 204):
            raise Exception("Discord post failed: " + str(r.status_code) + " — " + r.text)
        time.sleep(1)


def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        print("ERROR: DISCORD_WEBHOOK_URL not set")
        sys.exit(1)

    print("Starting MiLB scanner for " + str(CURRENT_YEAR) + "...")
    print("Filters: Age <=" + str(MAX_AGE) + ", OPS >=" + str(MIN_OPS) +
          ", BB/K >=" + str(MIN_BB_K) + ", PA >=" + str(MIN_PA))

    all_qualifying = []
    for sport_id in SPORT_IDS:
        results = scan_level(sport_id)
        all_qualifying.extend(results)
        time.sleep(1)

    print("\nTotal qualifying: " + str(len(all_qualifying)))
    post_to_discord(webhook_url, all_qualifying)
    print("Done!")


if __name__ == "__main__":
    main()

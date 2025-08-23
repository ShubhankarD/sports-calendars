# src/usopen_calendar.py
import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Union, Optional, List

import requests
from ics import Calendar, Event
from ics.contentline import ContentLine

# ---------- Config ----------
ET = ZoneInfo("America/New_York")
BASE_URL = "https://www.usopen.org/en_US/scores/feeds/2025/schedule/scheduleDays.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 20  # seconds
DEFAULT_EVENT_HOURS = 2


# ---------- Helpers: JSON fetch ----------
def fetch_json(url: str):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


# ---------- Helpers: Extras (VCALENDAR/VEVENT content lines) ----------
def add_vcalendar_extras(cal: Calendar, extras: Dict[str, Union[str, tuple]]):
    """
    Add VCALENDAR-level extra properties.
    'extras' values:
      - "string" -> value with no params
      - ("value", {"PARAM": ["VAL"]}) -> value with params
    """
    for name, val in extras.items():
        if isinstance(val, tuple):
            value, params = val
            cal.extra.append(ContentLine(name=name, params=params, value=value))
        else:
            cal.extra.append(ContentLine(name=name, params={}, value=val))


def add_vevent_extras(event: Event, extras: Dict[str, Union[str, tuple]]):
    from ics.grammar.parse import ContentLine
    for name, val in extras.items():
        if isinstance(val, tuple):
            value, params = val
            event.extra.append(ContentLine(name=name, params=params, value=value))
        else:
            event.extra.append(ContentLine(name=name, params={}, value=val))


# ---------- Core parsing: names ----------
def _join_names(team: Optional[list]) -> str:
    """Join A/B display names for a team if present."""
    team = team or [{}]
    t = team[0] if team else {}
    names = [t.get("displayNameA"), t.get("displayNameB")]
    joined = " & ".join([n for n in names if n])
    return joined


# ---------- NEW: nation → flag helpers ----------
# 3-letter IOC/NOC → ISO-3166 alpha-2 (extend as needed)
IOC_TO_ISO2 = {
    # Americas
    "USA": "US", "CAN": "CA", "MEX": "MX",
    "ARG": "AR", "BRA": "BR", "CHI": "CL", "COL": "CO", "PER": "PE",
    "URU": "UY", "PAR": "PY", "BOL": "BO", "ECU": "EC", "VEN": "VE",
    "CRC": "CR", "PAN": "PA", "GUA": "GT", "HON": "HN", "ESA": "SV", "NCA": "NI", "BIZ": "BZ",
    "CUB": "CU", "DOM": "DO", "HAI": "HT", "JAM": "JM", "TTO": "TT",
    "BAH": "BS", "BAR": "BB", "BER": "BM", "GUY": "GY", "SUR": "SR",
    "PUR": "PR", "ANT": "AG", "DMA": "DM", "GRN": "GD", "LCA": "LC", "VIN": "VC", "SKN": "KN",
    "ARU": "AW", "IVB": "VG", "ISV": "VI", "CAY": "KY",

    # Europe
    "ESP": "ES", "FRA": "FR", "GBR": "GB", "GER": "DE", "ITA": "IT", "NED": "NL",
    "SUI": "CH", "SWE": "SE", "NOR": "NO", "DEN": "DK", "BEL": "BE", "AUT": "AT",
    "POR": "PT", "POL": "PL", "CZE": "CZ", "SVK": "SK", "SLO": "SI", "CRO": "HR", "SRB": "RS",
    "UKR": "UA", "ROU": "RO", "GRE": "GR", "GRC": "GR",
    "HUN": "HU", "IRL": "IE", "ISL": "IS", "FIN": "FI", "LUX": "LU", "MLT": "MT", "CYP": "CY",
    "ALB": "AL", "ARM": "AM", "AZE": "AZ", "BLR": "BY", "BUL": "BG",
    "EST": "EE", "LAT": "LV", "LTU": "LT", "MDA": "MD", "GEO": "GE",
    "MON": "MC", "LIE": "LI", "AND": "AD", "SMR": "SM",
    "MKD": "MK", "MNE": "ME", "BIH": "BA", "KOS": "XK", "RUS": "RU",

    # Asia / Middle East
    "CHN": "CN", "JPN": "JP", "KOR": "KR", "PRK": "KP",
    "IND": "IN", "PAK": "PK", "BAN": "BD", "NEP": "NP", "BHU": "BT", "MDV": "MV", "SRI": "LK",
    "AFG": "AF", "KAZ": "KZ", "KGZ": "KG", "TJK": "TJ", "UZB": "UZ", "TKM": "TM", "MGL": "MN",
    "IRI": "IR", "IRQ": "IQ", "QAT": "QA", "UAE": "AE", "BRN": "BH", "OMA": "OM",
    "KSA": "SA", "YEM": "YE", "JOR": "JO", "LIB": "LB", "ISR": "IL", "PLE": "PS",
    "TUR": "TR", "CYP": "CY", "KUW": "KW", "SYR": "SY",
    "HKG": "HK", "TPE": "TW",

    # Southeast Asia
    "THA": "TH", "VIE": "VN", "PHI": "PH", "MAS": "MY", "INA": "ID", "SGP": "SG",
    "CAM": "KH", "LAO": "LA", "MYA": "MM", "BRU": "BN", "TLS": "TL",

    # Oceania
    "AUS": "AU", "NZL": "NZ",
    "FIJ": "FJ", "PNG": "PG", "SAM": "WS", "ASA": "AS", "TGA": "TO",
    "SOL": "SB", "VAN": "VU", "NRU": "NR", "KIR": "KI", "TUV": "TV",
    "COK": "CK", "PLW": "PW", "FSM": "FM", "MHL": "MH", "GUM": "GU",

    # Africa
    "EGY": "EG", "MAR": "MA", "TUN": "TN", "ALG": "DZ", "RSA": "ZA",
    "NGR": "NG", "NIG": "NE", "GUI": "GN", "GBS": "GW", "CPV": "CV",
    "SEN": "SN", "GAM": "GM", "GHA": "GH", "CIV": "CI", "BUR": "BF", "SLE": "SL", "LBR": "LR",
    "MLI": "ML", "MTN": "MR", "BEN": "BJ", "TOG": "TG",
    "CMR": "CM", "GAB": "GA", "GEQ": "GQ", "CAF": "CF", "CHA": "TD",
    "CGO": "CG", "COD": "CD",
    "UGA": "UG", "KEN": "KE", "TAN": "TZ", "RWA": "RW", "BDI": "BI", "ETH": "ET",
    "DJI": "DJ", "ERI": "ER", "SOM": "SO", "SUD": "SD", "SSD": "SS",
    "BOT": "BW", "NAM": "NA", "ZAM": "ZM", "ZIM": "ZW",
    "LES": "LS", "SWZ": "SZ", "MAD": "MG", "MAW": "MW", "MOZ": "MZ", "ANG": "AO",
    "STP": "ST", "SEY": "SC", "MRI": "MU", "COM": "KM",
}


def _flag_emoji(iso2: Optional[str]) -> str:
    """Convert ISO2 country code to flag emoji; fallback to tennis ball."""
    if not iso2:
        return "🎾"
    code = iso2.strip().upper()
    if len(code) != 2 or not code.isalpha():
        return "🎾"
    base = 0x1F1E6
    return chr(base + (ord(code[0]) - 65)) + chr(base + (ord(code[1]) - 65))

def _team_flags(team: Optional[list]) -> str:
    """
    Team shape in feed: [{ ..., nationA: 'USA', nationB: 'MEX', ... }]
    - Singles: one flag
    - Doubles same nation: one flag
    - Doubles mixed nations: '🇺🇸/🇲🇽'
    """
    t = (team or [{}])[0]
    iocs: List[Optional[str]] = [t.get("nationA"), t.get("nationB")]
    isos: List[str] = []
    for ioc in iocs:
        if not ioc:
            continue
        iso = IOC_TO_ISO2.get(ioc.strip().upper())
        if iso and iso not in isos:
            isos.append(iso)
    if not isos:
        return "🎾"
    if len(isos) == 1:
        return _flag_emoji(isos[0])
    # compact: show at most two distinct flags in order seen
    return "/".join(_flag_emoji(c) for c in isos[:2])

def _team_label(team: Optional[list]) -> str:
    """Compose '<flags> NameA & NameB' using the existing _join_names()."""
    names = _join_names(team)
    return f"{_team_flags(team)} {names}".strip()


# ---------- Core parsing ----------
def parse_schedule():
    schedule_data = fetch_json(BASE_URL)
    event_days = schedule_data.get("eventDays", [])
    matches_all = []

    for day in event_days:
        tourn_day = day.get("tournDay", 0)
        feed_url = day.get("feedUrl")
        # filter early practice/qualifying days if needed
        if not feed_url or (tourn_day is None or tourn_day < 7):
            continue

        day_data = fetch_json(feed_url)
        courts = day_data.get("courts", [])
        display_date = day_data.get("displayDate")

        for court in courts:
            court_name = court.get("courtName", "Unknown Court")
            for match_data in court.get("matches", []):
                # (changed) flags + names
                players_team1 = _team_label(match_data.get("team1"))
                players_team2 = _team_label(match_data.get("team2"))

                # Some feeds have startEpoch on match OR on court
                start_epoch = match_data.get("startEpoch") or court.get("startEpoch")
                start_time = (
                    datetime.fromtimestamp(start_epoch, tz=timezone.utc).astimezone(ET)
                    if start_epoch else None
                )

                title = f"{players_team1} vs {players_team2}".strip()
                # if both sides missing, avoid " vs " or "🎾 vs 🎾"
                if title.strip().lower() in {"vs", "🎾 vs 🎾"}:
                    title = "Match (TBD)"

                matches_all.append({
                    "title": title,
                    "court": court_name,
                    "description": f"{match_data.get('eventName')} - {match_data.get('roundName')} | {display_date}",
                    "start_time": start_time
                })

    return matches_all


# ---------- Calendar creation ----------
def _stable_uid(summary: str, location: str, begin_dt: Optional[datetime]) -> str:
    base = f"{summary}|{location}|{begin_dt.isoformat() if begin_dt else ''}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest() + "@github-pages"


def create_calendar(matches):
    cal = Calendar()

    # VCALENDAR metadata & refresh hints
    add_vcalendar_extras(cal, {
        "X-WR-CALNAME": "US Open 2025",
        "X-WR-TIMEZONE": "America/New_York",
        "REFRESH-INTERVAL": ("PT1H", {"VALUE": ["DURATION"]}),
        "X-PUBLISHED-TTL": "PT1H",
    })
    cal.method = "PUBLISH"
    cal.prodid = "-//Your Org//US Open 2025//EN"

    for m in matches:
        ev = Event()
        ev.summary = m["title"] or "Match (TBD)"
        ev.location = m["court"]
        ev.description = m["description"]

        if m["start_time"]:
            dt_et = m["start_time"]
            ev.begin = dt_et
            ev.end = dt_et + timedelta(hours=DEFAULT_EVENT_HOURS)

        # Transparent = doesn't block busy time in many clients
        ev.transparent = True

        # Deterministic UID so updates replace (not duplicate)
        ev.uid = _stable_uid(ev.summary, ev.location or "", getattr(ev, "begin", None))

        # Optional VEVENT extras (example if you want to add a URL)
        # add_vevent_extras(ev, {"URL": "https://www.usopen.org/"})

        cal.events.append(ev)

    return cal


# ---------- CLI entry ----------
def main(output_path: str = "usopen_schedule.ics"):
    matches = parse_schedule()
    cal = create_calendar(matches)
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize())
    print(f"✅ Created {output_path} with {len(matches)} matches")


if __name__ == "__main__":
    main()

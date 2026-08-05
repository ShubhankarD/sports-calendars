from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests
from ics import Calendar, Event
from ics.contentline import ContentLine
from ics.contentline import ContentLine as EventContentLine


ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/"
    "scoreboard?limit=200&dates=20260611-20260719"
)
# ESPN intermittently rejects GitHub Actions runner IPs at site.api.  The
# fittwo endpoint serves the same scoreboard payload and is our fallback.
ESPN_SCOREBOARD_FALLBACK_URL = (
    "https://site.web.api.espn.com/apis/fittwo/v3/sports/soccer/fifa.world/"
    "scoreboard?limit=200&dates=20260611-20260719"
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.espn.com/",
}
DEFAULT_EVENT_HOURS = 2
SHOW_SCORE_AFTER = timedelta(days=1)


def fetch_schedule(url: str = ESPN_SCOREBOARD_URL) -> Dict[str, Any]:
    """Fetch the ESPN scoreboard, falling back when site.api blocks a runner."""
    urls = [url]
    if url == ESPN_SCOREBOARD_URL:
        urls.append(ESPN_SCOREBOARD_FALLBACK_URL)

    errors = []
    for candidate_url in urls:
        try:
            response = requests.get(candidate_url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            errors.append(f"{candidate_url}: {error}")

    raise RuntimeError("Unable to fetch ESPN World Cup schedule. " + " | ".join(errors))


def parse_matches(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    updated_at = datetime.now(timezone.utc)
    matches = [_parse_event(event, updated_at) for event in data.get("events", [])]
    return sorted(matches, key=lambda match: match["start_time"])


def create_calendar(matches: Iterable[Dict[str, Any]]) -> Calendar:
    cal = Calendar()
    cal.method = "PUBLISH"
    cal.prodid = "-//Sports Calendars//FIFA World Cup 2026//EN"
    cal.extra.append(ContentLine(name="CALSCALE", params={}, value="GREGORIAN"))
    cal.extra.append(ContentLine(name="X-WR-CALNAME", params={}, value="FIFA World Cup 2026"))
    cal.extra.append(
        ContentLine(
            name="REFRESH-INTERVAL",
            params={"VALUE": ["DURATION"]},
            value="PT1H",
        )
    )
    cal.extra.append(ContentLine(name="X-PUBLISHED-TTL", params={}, value="PT1H"))

    for match in matches:
        event = Event()
        event.summary = match["summary"]
        event.begin = match["start_time"]
        event.duration = timedelta(hours=DEFAULT_EVENT_HOURS)
        event.location = match["location"]
        event.description = match["description"]
        event.transparent = True
        event.status = "CONFIRMED"
        event.uid = f"fifa-world-cup-2026-{match['id']}@github-pages"
        event.extra.append(EventContentLine(name="SEQUENCE", params={}, value="1"))
        cal.events.append(event)

    return cal


def build_calendar(url: str = ESPN_SCOREBOARD_URL) -> Calendar:
    return create_calendar(parse_matches(fetch_schedule(url)))


def _parse_event(event: Dict[str, Any], updated_at: datetime) -> Dict[str, Any]:
    competition = (event.get("competitions") or [{}])[0]
    competitors = _competitors(competition.get("competitors", []))
    home, away = _home_away(competitors)
    start_time = _parse_datetime(event.get("date") or competition.get("date"))
    stage = _stage_name((event.get("season") or {}).get("slug"))
    status = (competition.get("status") or {}).get("type") or {}
    matchup = _matchup_summary(home, away, status, start_time, updated_at)
    summary = f"{matchup} · {stage}" if stage else matchup

    return {
        "id": event["id"],
        "summary": summary,
        "start_time": start_time,
        "location": _venue(competition.get("venue") or {}),
        "description": _description(updated_at),
    }


def _parse_datetime(value: str) -> datetime:
    if not value:
        raise ValueError("Event is missing a start date")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _competitors(competitors: Iterable[Dict[str, Any]]) -> List[Dict[str, Optional[str]]]:
    parsed = []
    for item in competitors:
        team = item.get("team") or {}
        name = _team_name(team.get("displayName") or team.get("name") or "TBD")
        parsed.append(
            {
                "name": name,
                "label": _team_label(name, team.get("abbreviation")),
                "score": item.get("score"),
                "home_away": item.get("homeAway"),
                "order": item.get("order", 99),
            }
        )
    return parsed


def _home_away(competitors: List[Dict[str, Optional[str]]]) -> tuple:
    home = next((team for team in competitors if team.get("home_away") == "home"), None)
    away = next((team for team in competitors if team.get("home_away") == "away"), None)
    if home and away:
        return home, away

    ordered = sorted(competitors, key=lambda team: team.get("order") or 99)
    while len(ordered) < 2:
        ordered.append(
            {
                "name": "TBD",
                "label": "TBD",
                "score": None,
                "home_away": None,
                "order": 99,
            }
        )
    return ordered[0], ordered[1]


def _matchup_summary(
    home: Dict[str, Optional[str]],
    away: Dict[str, Optional[str]],
    status: Dict[str, Any],
    start_time: datetime,
    updated_at: datetime,
) -> str:
    if _should_show_score(home, away, status, start_time, updated_at):
        return f"{home['label']} {home['score']}-{away['score']} {away['label']}"
    return f"{home['label']} vs {away['label']}"


def _should_show_score(
    home: Dict[str, Optional[str]],
    away: Dict[str, Optional[str]],
    status: Dict[str, Any],
    start_time: datetime,
    updated_at: datetime,
) -> bool:
    if not status.get("completed"):
        return False
    if home.get("score") is None or away.get("score") is None:
        return False
    return updated_at - start_time >= SHOW_SCORE_AFTER


def _venue(venue: Dict[str, Any]) -> str:
    name = venue.get("fullName")
    address = venue.get("address") or {}
    city = address.get("city")
    return ", ".join(part for part in [name, city] if part)


def _team_name(name: str) -> str:
    names = {
        "United States": "USA",
    }
    return names.get(name, name)


def _team_label(name: str, abbreviation: Optional[str]) -> str:
    flag = _flag(abbreviation)
    return f"{flag} {name}" if flag else name


def _flag(abbreviation: Optional[str]) -> Optional[str]:
    flags = {
        "ALG": "🇩🇿",
        "ARG": "🇦🇷",
        "AUS": "🇦🇺",
        "AUT": "🇦🇹",
        "BEL": "🇧🇪",
        "BIH": "🇧🇦",
        "BRA": "🇧🇷",
        "CAN": "🇨🇦",
        "CPV": "🇨🇻",
        "COD": "🇨🇩",
        "COL": "🇨🇴",
        "CRO": "🇭🇷",
        "CUW": "🇨🇼",
        "CZE": "🇨🇿",
        "ECU": "🇪🇨",
        "EGY": "🇪🇬",
        "ENG": "🏴",
        "FRA": "🇫🇷",
        "GER": "🇩🇪",
        "GHA": "🇬🇭",
        "HAI": "🇭🇹",
        "IRN": "🇮🇷",
        "IRQ": "🇮🇶",
        "CIV": "🇨🇮",
        "JPN": "🇯🇵",
        "JOR": "🇯🇴",
        "KOR": "🇰🇷",
        "MEX": "🇲🇽",
        "MAR": "🇲🇦",
        "NED": "🇳🇱",
        "NZL": "🇳🇿",
        "NOR": "🇳🇴",
        "PAN": "🇵🇦",
        "PAR": "🇵🇾",
        "POR": "🇵🇹",
        "QAT": "🇶🇦",
        "KSA": "🇸🇦",
        "SCO": "🏴",
        "SEN": "🇸🇳",
        "RSA": "🇿🇦",
        "ESP": "🇪🇸",
        "SWE": "🇸🇪",
        "SUI": "🇨🇭",
        "TUN": "🇹🇳",
        "TUR": "🇹🇷",
        "USA": "🇺🇸",
        "URU": "🇺🇾",
        "UZB": "🇺🇿",
    }
    return flags.get(abbreviation or "")


def _stage_name(slug: Optional[str]) -> Optional[str]:
    names = {
        "group-stage": "Group Stage",
        "round-of-32": "Round of 32",
        "round-of-16": "Round of 16",
        "quarterfinals": "Quarterfinals",
        "semifinals": "Semifinals",
        "3rd-place-match": None,
        "final": "Final",
    }
    if not slug:
        return None
    return names.get(slug, slug.replace("-", " ").title())


def _description(updated_at: datetime) -> str:
    timestamp = _sync2cal_timestamp(updated_at)
    return f"Last updated: {timestamp}"


def _sync2cal_timestamp(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    return f"{value.strftime('%b')} {value.day}, {value.year} at {value:%H:%M} UTC"

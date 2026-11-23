from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from ics import Calendar, Event
from ics.contentline import ContentLine
from ics.contentline import ContentLine as EventContentLine

ESPN_UNL_SCOREBOARD_URL = (
    "https://site.web.api.espn.com/apis/v2/scoreboard/header?sport=soccer&league=uefa.nations"
)
ESPN_UNL_SCOREBOARD_FALLBACK_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.nations/scoreboard"
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

KNOCKOUT_STAGES = {
    "quarterfinals",
    "quarter-finals",
    "semifinals",
    "semi-finals",
    "final",
    "third place",
    "3rd place",
    "3rd-place",
}

TOP_TEAMS = {
    "spain",
    "france",
    "germany",
    "england",
    "portugal",
    "italy",
    "netherlands",
    "belgium",
    "croatia",
    "denmark",
    "switzerland",
    "austria",
    "norway",
    "sweden",
    "poland",
    "scotland",
}


def fetch_schedule(url: Optional[str] = None) -> Dict[str, Any]:
    """Fetch the ESPN UEFA Nations League scoreboard payload for the current season."""
    if url is None:
        now = datetime.now(timezone.utc)
        season_start_year = now.year if now.month >= 7 else now.year - 1
        season_end_year = season_start_year + 1
        dates_param = f"{season_start_year}0801-{season_end_year}0701"
        url = f"{ESPN_UNL_SCOREBOARD_URL}&dates={dates_param}&limit=500"

    urls = [url]
    if url.startswith(ESPN_UNL_SCOREBOARD_URL):
        urls.append(ESPN_UNL_SCOREBOARD_FALLBACK_URL)

    errors = []
    for candidate_url in urls:
        try:
            response = requests.get(candidate_url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            errors.append(f"{candidate_url}: {error}")

    raise RuntimeError("Unable to fetch ESPN UEFA Nations League schedule. " + " | ".join(errors))


def parse_matches(data: Dict[str, Any], group_before_knockouts: bool = True) -> List[Dict[str, Any]]:
    updated_at = datetime.now(timezone.utc)
    events = []

    if "sports" in data:
        leagues = (data.get("sports") or [{}])[0].get("leagues") or [{}]
        events = (leagues[0] or {}).get("events") or []
    else:
        events = data.get("events") or []

    parsed_events = [_parse_event(event, updated_at) for event in events]

    if not group_before_knockouts:
        return sorted(parsed_events, key=lambda match: match["start_time"])

    grouped: Dict[Tuple[datetime, str], List[Dict[str, Any]]] = defaultdict(list)
    individual: List[Dict[str, Any]] = []

    for item in parsed_events:
        stage = item["stage"] or "Group Stage"
        if _is_knockout_stage(stage):
            individual.append(item)
        else:
            bucket_stage = _group_bucket_stage(stage)
            grouped[(item["start_time"], bucket_stage)].append(item)

    final_matches: List[Dict[str, Any]] = list(individual)

    for (start_time, stage), items in grouped.items():
        if len(items) == 1:
            final_matches.append(items[0])
            continue

        # Sort so League A / top national teams appear first
        items.sort(
            key=lambda i: (
                0 if i["is_featured"] else 1,
                0 if (i.get("stage") or "").startswith("Group A") else 1,
                i["matchup"],
            )
        )

        venues = {i["location"] for i in items if i.get("location")}
        location = next(iter(venues)) if len(venues) == 1 else "Multiple Venues"

        header = f"UEFA Nations League | {stage}"
        plain_lines = []

        for idx, i in enumerate(items, start=1):
            matchup_text = i["matchup"]
            item_stage = i.get("stage")
            if item_stage and item_stage != stage:
                plain_lines.append(f"{idx}. {matchup_text} ({item_stage})  ")
            else:
                plain_lines.append(f"{idx}. {matchup_text}  ")

        plain_body = "\n".join(plain_lines)
        description = f"{header}\n{plain_body}\n\n{_description(updated_at)}"

        item_ids = "-".join(sorted(str(i["id"]) for i in items))
        group_id = f"group-{hashlib.sha1(item_ids.encode('utf-8')).hexdigest()[:10]}"

        final_matches.append(
            {
                "id": group_id,
                "summary": f"UEFA Nations League - {stage}",
                "start_time": start_time,
                "location": location,
                "description": description,
                "stage": stage,
            }
        )

    return sorted(final_matches, key=lambda match: match["start_time"])


def create_calendar(matches: Iterable[Dict[str, Any]]) -> Calendar:
    cal = Calendar()
    cal.method = "PUBLISH"
    cal.prodid = "-//Sports Calendars//UEFA Nations League//EN"
    cal.extra.append(ContentLine(name="CALSCALE", params={}, value="GREGORIAN"))
    cal.extra.append(ContentLine(name="X-WR-CALNAME", params={}, value="UEFA Nations League"))
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
        event.uid = f"unl-{match['id']}@github-pages"
        event.extra.append(EventContentLine(name="SEQUENCE", params={}, value="1"))
        cal.events.append(event)

    return cal


def build_calendar(url: Optional[str] = None) -> Calendar:
    return create_calendar(parse_matches(fetch_schedule(url)))


def _is_knockout_stage(stage: Optional[str]) -> bool:
    if not stage:
        return False
    stage_lower = stage.lower()
    return any(k in stage_lower for k in KNOCKOUT_STAGES)


def _group_bucket_stage(stage: str) -> str:
    if stage.lower().startswith("group "):
        return "Group Stage"
    return stage


def _is_top_team(name: Optional[str]) -> bool:
    if not name:
        return False
    return name.strip().lower() in TOP_TEAMS


def _parse_event(event: Dict[str, Any], updated_at: datetime) -> Dict[str, Any]:
    competition = (event.get("competitions") or [{}])[0]
    raw_competitors = event.get("competitors") or competition.get("competitors") or []
    competitors = _competitors(raw_competitors)
    home, away = _home_away(competitors)
    start_time = _parse_datetime(event.get("date") or competition.get("date"))
    stage = _stage_name(event)
    status = event.get("status") or competition.get("status") or {}
    if isinstance(status, dict) and "type" in status and isinstance(status["type"], dict):
        status_type = status["type"]
    else:
        status_type = status if isinstance(status, dict) else {}

    is_featured = _is_top_team(home.get("name")) or _is_top_team(away.get("name"))
    matchup = _matchup_summary(home, away, status_type, start_time, updated_at)
    summary = f"{matchup} · {stage}" if stage else matchup

    return {
        "id": event["id"],
        "summary": summary,
        "matchup": matchup,
        "start_time": start_time,
        "location": event.get("location") or _venue(competition.get("venue") or {}),
        "description": _description(updated_at),
        "stage": stage,
        "is_featured": is_featured,
        "home_name": home.get("name"),
        "away_name": away.get("name"),
    }


def _parse_datetime(value: Optional[str]) -> datetime:
    if not value:
        raise ValueError("Event is missing a start date")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _competitors(competitors: Iterable[Dict[str, Any]]) -> List[Dict[str, Optional[str]]]:
    parsed = []
    for item in competitors:
        team = item.get("team") if isinstance(item.get("team"), dict) else item
        name = team.get("displayName") or team.get("name") or "TBD"
        abbreviation = team.get("abbreviation") or item.get("abbreviation")
        parsed.append(
            {
                "name": name,
                "label": _team_label(name, abbreviation),
                "score": item.get("score"),
                "home_away": item.get("homeAway"),
                "order": item.get("order", 99),
            }
        )
    return parsed


def _team_label(name: str, abbreviation: Optional[str]) -> str:
    flag = _flag(abbreviation, name)
    return f"{flag} {name}" if flag else name


UEFA_FLAGS = {
    "ALB": "🇦🇱",
    "AND": "🇦🇩",
    "ARM": "🇦🇲",
    "AUT": "🇦🇹",
    "AZE": "🇦🇿",
    "BLR": "🇧🇾",
    "BEL": "🇧🇪",
    "BIH": "🇧🇦",
    "BUL": "🇧🇬",
    "CRO": "🇭🇷",
    "CYP": "🇨🇾",
    "CZE": "🇨🇿",
    "DEN": "🇩🇰",
    "ENG": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "EST": "🇪🇪",
    "FRO": "🇫🇴",
    "FIN": "🇫🇮",
    "FRA": "🇫🇷",
    "GEO": "🇬🇪",
    "GER": "🇩🇪",
    "GIB": "🇬🇮",
    "GRE": "🇬🇷",
    "HUN": "🇭🇺",
    "ISL": "🇮🇸",
    "ISR": "🇮🇱",
    "ITA": "🇮🇹",
    "KAZ": "🇰🇿",
    "KOS": "🇽🇰",
    "KVX": "🇽🇰",
    "LVA": "🇱🇻",
    "LAT": "🇱🇻",
    "LIE": "🇱🇮",
    "LTU": "🇱🇹",
    "LUX": "🇱🇺",
    "MLT": "🇲🇹",
    "MDA": "🇲🇩",
    "MNE": "🇲🇪",
    "NED": "🇳🇱",
    "MKD": "🇲🇰",
    "NIR": "🇬🇧",
    "NOR": "🇳🇴",
    "POL": "🇵🇱",
    "POR": "🇵🇹",
    "IRL": "🇮🇪",
    "ROU": "🇷🇴",
    "SMR": "🇸🇲",
    "SCO": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "SRB": "🇷🇸",
    "SVK": "🇸🇰",
    "SVN": "🇸🇮",
    "ESP": "🇪🇸",
    "SWE": "🇸🇪",
    "SUI": "🇨🇭",
    "TUR": "🇹🇷",
    "UKR": "🇺🇦",
    "WAL": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
}

UEFA_FLAGS_BY_NAME = {
    "albania": "🇦🇱",
    "andorra": "🇦🇩",
    "armenia": "🇦🇲",
    "austria": "🇦🇹",
    "azerbaijan": "🇦🇿",
    "belarus": "🇧🇾",
    "belgium": "🇧🇪",
    "bosnia and herzegovina": "🇧🇦",
    "bosnia & herzegovina": "🇧🇦",
    "bulgaria": "🇧🇬",
    "croatia": "🇭🇷",
    "cyprus": "🇨🇾",
    "czechia": "🇨🇿",
    "czech republic": "🇨🇿",
    "denmark": "🇩🇰",
    "england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "estonia": "🇪🇪",
    "faroe islands": "🇫🇴",
    "finland": "🇫🇮",
    "france": "🇫🇷",
    "georgia": "🇬🇪",
    "germany": "🇩🇪",
    "gibraltar": "🇬🇮",
    "greece": "🇬🇷",
    "hungary": "🇭🇺",
    "iceland": "🇮🇸",
    "israel": "🇮🇱",
    "italy": "🇮🇹",
    "kazakhstan": "🇰🇿",
    "kosovo": "🇽🇰",
    "latvia": "🇱🇻",
    "liechtenstein": "🇱🇮",
    "lithuania": "🇱🇹",
    "luxembourg": "🇱🇺",
    "malta": "🇲🇹",
    "moldova": "🇲🇩",
    "montenegro": "🇲🇪",
    "netherlands": "🇳🇱",
    "north macedonia": "🇲🇰",
    "northern ireland": "🇬🇧",
    "norway": "🇳🇴",
    "poland": "🇵🇱",
    "portugal": "🇵🇹",
    "republic of ireland": "🇮🇪",
    "ireland": "🇮🇪",
    "romania": "🇷🇴",
    "san marino": "🇸🇲",
    "scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "serbia": "🇷🇸",
    "slovakia": "🇸🇰",
    "slovenia": "🇸🇮",
    "spain": "🇪🇸",
    "sweden": "🇸🇪",
    "switzerland": "🇨🇭",
    "turkey": "🇹🇷",
    "türkiye": "🇹🇷",
    "ukraine": "🇺🇦",
    "wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
}


def _flag(abbreviation: Optional[str], name: Optional[str] = None) -> Optional[str]:
    if abbreviation:
        flag = UEFA_FLAGS.get(abbreviation.strip().upper())
        if flag:
            return flag
    if name:
        return UEFA_FLAGS_BY_NAME.get(name.strip().lower())
    return None


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
    if not home.get("score") or not away.get("score"):
        return False
    return updated_at - start_time >= SHOW_SCORE_AFTER


def _venue(venue: Dict[str, Any]) -> str:
    name = venue.get("fullName")
    address = venue.get("address") or {}
    city = address.get("city")
    return ", ".join(part for part in [name, city] if part)


def _stage_name(event: Dict[str, Any]) -> Optional[str]:
    group = event.get("group")
    if isinstance(group, dict):
        name = group.get("name") or group.get("shortName")
        if name:
            return name

    alt_note = event.get("altGameNote")
    if alt_note and "UEFA Nations League," in alt_note:
        return alt_note.replace("UEFA Nations League,", "").strip()
    elif alt_note:
        return alt_note

    season_slug = (event.get("season") or {}).get("slug") if isinstance(event.get("season"), dict) else None
    if season_slug:
        return season_slug.replace("-", " ").title()

    return None


def _description(updated_at: datetime) -> str:
    timestamp = _sync2cal_timestamp(updated_at)
    return f"Last updated: {timestamp}"


def _sync2cal_timestamp(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    return f"{value.strftime('%b')} {value.day}, {value.year} at {value:%H:%M} UTC"

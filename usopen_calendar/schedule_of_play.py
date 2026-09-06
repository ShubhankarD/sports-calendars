from datetime import datetime, timezone
from typing import Dict, List, Optional
from .config import ET, BASE_URL, INCLUDE_BEFORE_TOURNDAY
from .fetch import fetch_json
from .flags import team_label

Match = Dict[str, Optional[object]]

def parse_schedule(base_url: str = BASE_URL, min_tourn_day: int = INCLUDE_BEFORE_TOURNDAY) -> List[Match]:
    """Fetch schedule days, traverse individual day feeds, and build match dictionaries.

    Returns a list of matches with keys: title, court, description, start_time (aware datetime in ET or None)
    """
    schedule_data = fetch_json(base_url)
    event_days = schedule_data.get("eventDays", [])
    matches_all: List[Match] = []

    for day in event_days:
        tourn_day = day.get("tournDay", 0)
        feed_url = day.get("feedUrl")
        # Filter early practice/qualifying days if needed
        if not feed_url or (tourn_day is None or tourn_day < min_tourn_day):
            continue

        day_data = fetch_json(feed_url)
        courts = day_data.get("courts", [])
        display_date = day_data.get("displayDate")

        for court in courts:
            court_name = court.get("courtName", "Unknown Court")
            for match_data in court.get("matches", []):
                p1 = team_label(match_data.get("team1"))
                p2 = team_label(match_data.get("team2"))

                # Some feeds have startEpoch on match OR on court
                start_epoch = match_data.get("startEpoch") or court.get("startEpoch")
                start_time = (
                    datetime.fromtimestamp(start_epoch, tz=timezone.utc).astimezone(ET)
                    if start_epoch else None
                )

                if p1 == "TBD" and p2 == "TBD":
                    title = "Match (TBD)"
                else:
                    title = f"{p1} vs {p2}".strip()

                if title.lower() in {"vs", "tbd vs tbd", "match (tbd)"}:
                    title = "Match (TBD)"

                event_name = match_data.get("eventName")
                round_name = match_data.get("roundName")
                desc_parts = [p for p in [event_name, round_name, display_date] if p]
                description = " - ".join(desc_parts[:2])
                if len(desc_parts) > 2:
                    description += f" | {desc_parts[2]}"

                matches_all.append({
                    "title": title,
                    "court": court_name,
                    "description": description,
                    "start_time": start_time
                })

    matches_all.sort(key=_sort_key_for_output)
    return matches_all

def _sort_key_for_output(m: Match):
    st = m.get("start_time")
    if isinstance(st, datetime) and st.tzinfo is not None:
        return (False, st, m.get("court") or "", m.get("title") or "")
    return (True, datetime.max.replace(tzinfo=ET), m.get("court") or "", m.get("title") or "")

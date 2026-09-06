from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .config import ET, BASE_URL, INCLUDE_BEFORE_TOURNDAY, TOURNAMENT_URL
from .fetch import fetch_json
from .flags import team_label

Match = Dict[str, Optional[object]]

def parse_schedule(
    base_url: str = BASE_URL,
    min_tourn_day: int = INCLUDE_BEFORE_TOURNDAY,
    *,
    group_by_time_event: bool = False,
    tournament_schedule_url: str = TOURNAMENT_URL,
) -> List[Match]:
    """Fetch schedule days, traverse day feeds, and build match dictionaries.

    Returns a list of individual matches with keys: title, court, description, start_time (aware datetime in ET or None)
    """
    try:
        schedule_data = fetch_json(base_url)
    except Exception:
        schedule_data = {}
    event_days = schedule_data.get("eventDays", [])

    raw_items: List[Dict[str, Optional[object]]] = []

    for day in event_days:
        tourn_day = day.get("tournDay", 0)
        feed_url = day.get("feedUrl")

        # Skip early practice/qualifying days or days without a feedUrl
        if tourn_day is None or tourn_day < min_tourn_day or not feed_url:
            continue

        day_data = fetch_json(feed_url)
        courts = day_data.get("courts", [])
        display_date = day_data.get("displayDate")

        for court in courts:
            court_name = court.get("courtName", "Unknown Court")
            for match_data in court.get("matches", []):
                event_name = match_data.get("eventName")
                round_name = match_data.get("roundName")

                start_epoch = match_data.get("startEpoch") or court.get("startEpoch")
                start_time: Optional[datetime] = (
                    datetime.fromtimestamp(start_epoch, tz=timezone.utc).astimezone(ET)
                    if start_epoch
                    else None
                )

                t1_label = team_label(match_data.get("team1"))
                t2_label = team_label(match_data.get("team2"))

                raw_items.append(
                    {
                        "eventName": event_name,
                        "roundName": round_name,
                        "court": court_name,
                        "displayDate": display_date,
                        "tournDay": tourn_day,
                        "startEpoch": start_epoch,
                        "start_time": start_time,
                        "t1": t1_label,
                        "t2": t2_label,
                    }
                )

    if not group_by_time_event:
        matches_all: List[Match] = []
        for it in raw_items:
            p1 = str(it["t1"]).strip() if it.get("t1") else "TBD"
            p2 = str(it["t2"]).strip() if it.get("t2") else "TBD"

            if (p1 == "TBD" and p2 == "TBD") or not p1 or not p2:
                title = "Match (TBD)"
            else:
                title = f"{p1} vs {p2}"

            event_name = _nz(it.get("eventName"))
            round_name = _nz(it.get("roundName"))
            display_date = _nz(it.get("displayDate"))

            desc_parts = [p for p in [event_name, round_name] if p]
            description = " - ".join(desc_parts)
            if display_date:
                description = f"{description} | {display_date}" if description else display_date

            matches_all.append(
                {
                    "title": title,
                    "court": it.get("court") or "Unknown Court",
                    "description": description,
                    "start_time": it.get("start_time"),
                }
            )
        matches_all.sort(key=_sort_key_for_output)
        return matches_all

    # Grouped fallback if requested
    def _effective_group_key(it: Dict[str, Optional[object]]):
        se = it.get("startEpoch")
        if isinstance(se, int):
            key_epoch = se
        else:
            st = it.get("start_time")
            key_epoch = (
                int(st.timestamp()) if isinstance(st, datetime) else it.get("tournDay")
            )
        return (key_epoch, it.get("eventName"))

    groups: Dict[Tuple[object, Optional[str]], List[Dict[str, Optional[object]]]] = (
        defaultdict(list)
    )
    for it in raw_items:
        groups[_effective_group_key(it)].append(it)

    grouped_results: List[Match] = []

    for (_, event_name), items in groups.items():
        start_time = next(
            (i.get("start_time") for i in items if i.get("start_time")), None
        )
        round_names = {
            _nz(i.get("roundName")) for i in items if _nz(i.get("roundName"))
        }
        round_for_title = next(iter(round_names)) if len(round_names) == 1 else None
        courts_set = {i.get("court") for i in items if i.get("court")}
        court_field = (
            next(iter(courts_set)) if len(courts_set) == 1 else "Multiple Courts"
        )
        tourn_days = {i.get("tournDay") for i in items if i.get("tournDay") is not None}
        tourn_day_str = (
            f"Day {next(iter(tourn_days))}" if len(tourn_days) == 1 else None
        )

        title_bits = [_nz(event_name), _nz(round_for_title)]
        title = " - ".join([b for b in title_bits if b]) or "Match Group"

        header_bits = [_nz(event_name), _nz(round_for_title), _nz(tourn_day_str)]
        header = " | ".join([b for b in header_bits if b])

        line_items = [f"{i['t1']} vs {i['t2']}" for i in items]
        numbered_lines = [
            f"{idx}. {text}  " for idx, text in enumerate(line_items, start=1)
        ]
        body = "\n".join(numbered_lines)
        description = header + "\n" + body if header else body

        grouped_results.append(
            {
                "title": title,
                "court": court_field,
                "description": description,
                "start_time": start_time,
            }
        )

    grouped_results.sort(key=_sort_key_for_output)
    return grouped_results


def _sort_key_for_output(m: Match):
    st = m.get("start_time")
    if isinstance(st, datetime) and st.tzinfo is not None:
        return (False, st, m.get("court") or "", m.get("title") or "")
    return (True, datetime.max.replace(tzinfo=ET), m.get("court") or "", m.get("title") or "")


def _nz(s: Optional[object]) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip()
    return s if s else None

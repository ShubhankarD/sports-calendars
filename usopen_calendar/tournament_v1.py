from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .config import ET, BASE_URL, INCLUDE_BEFORE_TOURNDAY
from .fetch import fetch_json
from .flags import team_label

Match = Dict[str, Optional[object]]

def parse_schedule(
    base_url: str = BASE_URL,
    min_tourn_day: int = INCLUDE_BEFORE_TOURNDAY,
    *,
    group_by_time_event: bool = True,
) -> List[Match]:
    """Fetch schedule days, traverse day feeds, and build match/group dictionaries.

    Output item keys:
      - title: str         (clean: "<eventName> - <roundName>" if uniform round, else "<eventName>")
      - court: str         (single court or "Multiple Courts")
      - description: str   (grouped -> header + numbered list, each line ends with two spaces; ungrouped -> single pairing)
      - start_time: datetime|None (ET-aware if startEpoch present)

    Grouping (default):
      - Groups by (effective_start_epoch, eventName) where effective_start_epoch = match.startEpoch or court.startEpoch.
      - Header: "<eventName> | <roundName> | Day <N>: <displayDate>" (only present parts).
      - Body: numbered list of "<flag+name> vs <flag+name> (Court)" lines, with two spaces at line end for Markdown.
    """
    schedule_data = fetch_json(base_url)
    event_days = schedule_data.get("eventDays", [])

    raw_items: List[Dict[str, Optional[object]]] = []

    for day in event_days:
        tourn_day = day.get("tournDay", 0)
        feed_url = day.get("feedUrl")
        if not feed_url or (tourn_day is None or tourn_day < min_tourn_day):
            continue

        day_data = fetch_json(feed_url)
        courts = day_data.get("courts", [])
        display_date = day_data.get("displayDate")  # e.g., "Tuesday, August 26"

        for court in courts:
            court_name = court.get("courtName", "Unknown Court")
            for match_data in court.get("matches", []):
                event_name = match_data.get("eventName")
                round_name = match_data.get("roundName")

                # effective startEpoch: match-level takes precedence, else court-level
                start_epoch = match_data.get("startEpoch") or court.get("startEpoch")
                start_time: Optional[datetime] = (
                    datetime.fromtimestamp(start_epoch, tz=timezone.utc).astimezone(ET)
                    if start_epoch else None
                )

                # Team labels (with flags/emojis)
                t1_label = team_label(match_data.get("team1")) or "🎾 TBD"
                t2_label = team_label(match_data.get("team2")) or "🎾 TBD"

                raw_items.append({
                    "eventName": event_name,
                    "roundName": round_name,
                    "court": court_name,
                    "displayDate": display_date,  # raw display string from feed (weekday, month day)
                    "tournDay": tourn_day,
                    "startEpoch": start_epoch,
                    "start_time": start_time,
                    "t1": t1_label,
                    "t2": t2_label,
                })

    # ---- Ungrouped: one row per match; keep simple header and a single pairing ----
    if not group_by_time_event:
        matches_all: List[Match] = []
        for it in raw_items:
            title_bits = [it.get("eventName"), it.get("roundName")]
            title = " - ".join([b for b in title_bits if b]) or "Match"

            header_bits = [it.get("eventName"), it.get("roundName")]
            # For ungrouped we keep the original simple header (no Day N)
            header = " | ".join([b for b in header_bits if b])

            pair = f"{it['t1']} vs {it['t2']}"
            # Include date inline for ungrouped
            date_part = it.get("displayDate")
            if date_part:
                description = f"{header} | {date_part} — {pair}" if header else f"{date_part} — {pair}"
            else:
                description = f"{header} — {pair}" if header else pair

            matches_all.append({
                "title": title,
                "court": it.get("court") or "Unknown Court",
                "description": description,
                "start_time": it.get("start_time"),
            })
        matches_all.sort(key=_sort_key_for_output)
        return matches_all

    # ---- Grouped: by (startEpoch, eventName) ----
    groups: Dict[Tuple[Optional[int], Optional[str]], List[Dict[str, Optional[object]]]] = defaultdict(list)
    for it in raw_items:
        groups[(it.get("startEpoch"), it.get("eventName"))].append(it)

    grouped_results: List[Match] = []

    for (start_epoch, event_name), items in groups.items():
        start_time = (
            datetime.fromtimestamp(start_epoch, tz=timezone.utc).astimezone(ET)
            if start_epoch else None
        )

        # Round for title if uniform across the group
        round_names = {i.get("roundName") for i in items if i.get("roundName")}
        round_for_title = next(iter(round_names)) if len(round_names) == 1 else None

        # Courts involved
        courts_set = {i.get("court") for i in items if i.get("court")}
        multi_court = len(courts_set) > 1
        court_field = next(iter(courts_set)) if len(courts_set) == 1 else "Multiple Courts"

        # Day + displayDate (expect uniform within a feed/day)
        tourn_days = {i.get("tournDay") for i in items if i.get("tournDay") is not None}
        display_dates = {i.get("displayDate") for i in items if i.get("displayDate")}
        tourn_day_str = f"Day {next(iter(tourn_days))}" if len(tourn_days) == 1 else None
        display_date_str = next(iter(display_dates)) if len(display_dates) == 1 else None

        # Title
        title_bits = [event_name, round_for_title]
        title = " - ".join([b for b in title_bits if b]) or "Match Group"

        # Header: "<event> | <round> | Day N: <displayDate>"
        day_part = tourn_day_str

        header_bits = [event_name, round_for_title, day_part]
        header = " | ".join([b for b in header_bits if b])

        # Numbered list body, each line ends with two spaces for Markdown ("  ")
        line_items: List[str] = []
        for i in items:
            pair = f"{i['t1']} vs {i['t2']}"
            # if multi_court and i.get("court"):
            #     pair = f"{pair} ({i['court']})"
            line_items.append(pair)

        # Sort the pairs alphabetically for consistency (optional). Comment out if you prefer feed order.
        # line_items.sort()

        numbered_lines = [f"{idx}. {text}  " for idx, text in enumerate(line_items, start=1)]
        body = "\n".join(numbered_lines)

        # Final description: header on first line, then the numbered list
        description = header + "\n" + body if header else body

        grouped_results.append({
            "title": title,
            "court": court_field,
            "description": description,
            "start_time": start_time,
        })

    grouped_results.sort(key=_sort_key_for_output)
    return grouped_results


# ---- Helpers ----

def _sort_key_for_output(m: Match):
    """Sort by start_time (None at end) then by title for stability."""
    st = m.get("start_time")
    if isinstance(st, datetime) and st.tzinfo is not None:
        return (False, st, m.get("title") or "")
    return (True, datetime.max.replace(tzinfo=ET), m.get("title") or "")

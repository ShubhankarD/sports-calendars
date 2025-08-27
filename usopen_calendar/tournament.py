from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .config import ET, BASE_URL, INCLUDE_BEFORE_TOURNDAY, TOURNAMENT_URL
from .fetch import fetch_json
from .flags import team_label

Match = Dict[str, Optional[object]]

# Lazy cache for the tournament schedule feed (loaded inside parse_schedule)
_TOURN_CACHE: Optional[dict] = None


def parse_schedule(
    base_url: str = BASE_URL,
    min_tourn_day: int = INCLUDE_BEFORE_TOURNDAY,
    *,
    group_by_time_event: bool = True,
    tournament_schedule_url: str = TOURNAMENT_URL,
) -> List[Match]:
    """Fetch schedule days, traverse day feeds, and build match/group dictionaries.

    Output item keys:
      - title: str         (clean: "<eventName> - <roundName>" if uniform round, else "<eventName>")
      - court: str         (single court or "Multiple Courts")
      - description: str   (grouped -> header + numbered list, each line ends with two spaces; ungrouped -> single pairing)
      - start_time: datetime|None (ET-aware if startEpoch present)

    Grouping (default):
      - Groups by effective time + event:
          key = (startEpoch if present else start_time else tournDay, eventName)
      - Header: "<eventName> | <roundName> | Day <N>" (only present parts).
      - Body: numbered list of "<flag+name> vs <flag+name>" lines, each ending with two spaces for Markdown.
    """
    # Load the day list for the requested base_url (no side-effects at import)
    schedule_data = fetch_json(base_url)
    event_days = schedule_data.get("eventDays", [])

    # Lazy-load tournament schedule (honors function param)
    global _TOURN_CACHE
    if _TOURN_CACHE is None:
        try:
            _TOURN_CACHE = fetch_json(tournament_schedule_url) or {}
        except Exception:
            _TOURN_CACHE = {}

    raw_items: List[Dict[str, Optional[object]]] = []

    for day in event_days:
        tourn_day = day.get("tournDay", 0)
        feed_url = day.get("feedUrl")

        # Skip early days
        if tourn_day is None or tourn_day < min_tourn_day:
            continue

        # If no feed URL, synthesize placeholders from the tournament schedule
        if not feed_url:
            raw_items.extend(_build_placeholders_for_tourn_day(_TOURN_CACHE, tourn_day))
            continue

        # Normal day with a feed
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
                    if start_epoch
                    else None
                )

                # Team labels (with flags/emojis)
                t1_label = team_label(match_data.get("team1")) or "🎾 TBD"
                t2_label = team_label(match_data.get("team2")) or "🎾 TBD"

                raw_items.append(
                    {
                        "eventName": event_name,
                        "roundName": round_name,
                        "court": court_name,
                        "displayDate": display_date,  # raw display string from feed (weekday, month day)
                        "tournDay": tourn_day,
                        "startEpoch": start_epoch,
                        "start_time": start_time,
                        "t1": t1_label,
                        "t2": t2_label,
                    }
                )

    # ---- Ungrouped: one row per match; keep simple header and a single pairing ----
    if not group_by_time_event:
        matches_all: List[Match] = []
        for it in raw_items:
            title_bits = [_nz(it.get("eventName")), _nz(it.get("roundName"))]
            title = " - ".join([b for b in title_bits if b]) or "Match"

            header_bits = [_nz(it.get("eventName")), _nz(it.get("roundName"))]
            header = " | ".join([b for b in header_bits if b])

            pair = f"{it['t1']} vs {it['t2']}"
            # Include date inline for ungrouped if present
            date_part = _nz(it.get("displayDate"))
            if date_part:
                description = (
                    f"{header} | {date_part} — {pair}"
                    if header
                    else f"{date_part} — {pair}"
                )
            else:
                description = f"{header} — {pair}" if header else pair

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

    # ---- Grouped: by effective time (epoch or start_time or tournDay) and eventName ----
    def _effective_group_key(
        it: Dict[str, Optional[object]],
    ) -> Tuple[object, Optional[str]]:
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
        # start_time for group (take the first non-null start_time if any)
        start_time = next(
            (i.get("start_time") for i in items if i.get("start_time")), None
        )

        # Round for title if uniform across the group
        round_names = {
            _nz(i.get("roundName")) for i in items if _nz(i.get("roundName"))
        }
        round_for_title = next(iter(round_names)) if len(round_names) == 1 else None

        # Courts involved (for the card field only)
        courts_set = {i.get("court") for i in items if i.get("court")}
        court_field = (
            next(iter(courts_set)) if len(courts_set) == 1 else "Multiple Courts"
        )

        # Day (expect uniform within a feed/day)
        tourn_days = {i.get("tournDay") for i in items if i.get("tournDay") is not None}
        tourn_day_str = (
            f"Day {next(iter(tourn_days))}" if len(tourn_days) == 1 else None
        )

        # Title
        title_bits = [_nz(event_name), _nz(round_for_title)]
        title = " - ".join([b for b in title_bits if b]) or "Match Group"

        # Header: "<event> | <round> | Day N"   (keep only Day N per your preference)
        header_bits = [_nz(event_name), _nz(round_for_title), _nz(tourn_day_str)]
        header = " | ".join([b for b in header_bits if b])

        # Numbered list body, each line ends with two spaces for Markdown ("  ")
        line_items: List[str] = []
        for i in items:
            pair = f"{i['t1']} vs {i['t2']}"  # no court suffix (as requested)
            line_items.append(pair)

        # Keep original feed order; if you prefer alpha, uncomment next line
        # line_items.sort()

        numbered_lines = [
            f"{idx}. {text}  " for idx, text in enumerate(line_items, start=1)
        ]
        body = "\n".join(numbered_lines)

        # Final description: header on first line, then the numbered list
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


# ---- Helpers ----


def _sort_key_for_output(m: Match):
    """Sort by start_time (None at the end) then by title for stability."""
    st = m.get("start_time")
    if isinstance(st, datetime) and st.tzinfo is not None:
        return (False, st, m.get("title") or "")
    return (True, datetime.max.replace(tzinfo=ET), m.get("title") or "")


def _fmt_weekday_month_day(date_str: str) -> Optional[str]:
    """Convert 'YYYY-MM-DD' -> 'Tuesday, August 26' (portable)."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # Use dt.day to avoid %-d, which is unsupported on Windows
        return f"{dt.strftime('%A, %B')} {dt.day}"
    except Exception:
        return None


def _build_placeholders_for_tourn_day(
    schedule_json: dict, tourn_day_target: int
) -> List[Dict[str, Optional[object]]]:
    """
    Build placeholder raw_items for a given tournDay using the tournament schedule JSON.
    Each 'events' entry becomes a placeholder match with TBD players.
    """
    raw_items: List[Dict[str, Optional[object]]] = []
    draws = (schedule_json or {}).get("tournament_schedule", {}).get("draws", {})
    for _, draw in (draws or {}).items():
        for d in draw.get("dates", []) or []:
            if d.get("tournDay") != tourn_day_target:
                continue

            date_iso = d.get("date")  # "2025-08-19"
            display_date = _fmt_weekday_month_day(date_iso) or date_iso
            # Prefer the day's epoch if provided
            day_epoch = d.get("epoch")
            try:
                day_epoch = int(day_epoch) if day_epoch is not None else None
            except Exception:
                day_epoch = None

            for session in d.get("session", []) or []:
                # Each times[] can list multiple event strings
                for tslot in session.get("times", []) or []:
                    events = tslot.get("events", []) or []
                    start_str = tslot.get("start")  # e.g., "11:00 AM"

                    # Attempt a start_time using date + start_str; fallback to day_epoch; else None
                    start_time = None
                    if date_iso and start_str:
                        try:
                            dt = datetime.strptime(
                                f"{date_iso} {start_str}", "%Y-%m-%d %I:%M %p"
                            )
                            start_time = dt.replace(tzinfo=ET)
                        except Exception:
                            start_time = None
                    if start_time is None and day_epoch:
                        try:
                            start_time = datetime.fromtimestamp(
                                day_epoch, tz=timezone.utc
                            ).astimezone(ET)
                        except Exception:
                            start_time = None

                    for ev in events:
                        # Create a placeholder "match" row with TBD players
                        raw_items.append(
                            {
                                "eventName": ev,  # e.g., "Qualifying Matches"
                                "roundName": None,
                                "court": None,  # leave None; we don't want court names in the list
                                "displayDate": display_date,  # e.g., "Tuesday, August 26"
                                "tournDay": tourn_day_target,
                                "startEpoch": None,
                                "start_time": start_time,
                                "t1": "🎾 TBD",
                                "t2": "🎾 TBD",
                            }
                        )
    return raw_items


def _nz(s: Optional[object]) -> Optional[str]:
    """Normalize to a non-empty string or None."""
    if s is None:
        return None
    s = str(s).strip()
    return s if s else None

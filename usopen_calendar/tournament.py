# usopen_calendar/tournament.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .fetch import fetch_json
from .config import ET, INCLUDE_BEFORE_TOURNDAY

TOURNAMENT_SCHEDULE_URL = "https://www.usopen.org/en_US/cms/feeds/tournament_schedule.json"
Match = Dict[str, Optional[object]]

# ----------------- helpers -----------------
def _first(d: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return str(v)
    return None

def _combine_date_time_et(date_str: Optional[str], time_str: Optional[str]) -> Optional[datetime]:
    if not (date_str and time_str):
        return None
    for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M%p"):
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", fmt)
            return dt.replace(tzinfo=ET)
        except Exception:
            continue
    return None

def _epoch_to_et(epoch: Optional[str | int]) -> Optional[datetime]:
    if epoch in (None, "", []):
        return None
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).astimezone(ET)
    except Exception:
        return None

def _norm(s: str) -> str:
    return s.replace("’", "'").lower()

def _titles_for_events(events: List[str]) -> List[str]:
    """
    Return 0..N titles for this time block following rules:
      - keep exact text if it mentions both men's and women's singles
      - map men's singles -> "Men's single"
      - map women's singles -> "Women's single"
      - any doubles (incl. mixed) -> "Double and Mixed Double"
      - exclude wheelchair events
      - ignore ambiguous generic 'singles'
    """
    out: List[str] = []
    for raw in events:
        clean = str(raw).strip()
        n = _norm(clean)

        # remove wheelchair events entirely
        if "wheelchair" in n:
            continue

        has_single = "single" in n
        has_double = "double" in n  # matches "doubles", "mixed doubles"
        has_men = "men" in n or "men's" in n or "mens" in n
        has_women = "women" in n or "women's" in n or "womens" in n

        if has_single:
            # keep combined men's & women's singles EXACTLY as-is
            if has_men and has_women:
                out.append(clean)
            else:
                if has_men:
                    out.append("Men's single")
                if has_women:
                    out.append("Women's single")
                # skip generic "Singles" with no gender
        if has_double:
            out.append("Double and Mixed Double")

    # de-dup while preserving order
    seen: Set[str] = set()
    deduped = []
    for t in out:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped

# ----------------- parser -----------------
def parse_schedule(
    base_url: str = TOURNAMENT_SCHEDULE_URL,
    min_tourn_day: int = INCLUDE_BEFORE_TOURNDAY,
) -> List[Match]:
    """
    Fetch tournament_schedule.json and build match dictionaries.

    Returns a list of matches with keys: title, court, description, start_time (aware datetime in ET or None)
    """
    data = fetch_json(base_url) or {}
    ts = data.get("tournament_schedule", {})
    draws = ts.get("draws", {}) or {}

    matches_all: List[Match] = []
    seen_keys: Set[Tuple[str, str, str]] = set()  # (title, court, iso_start)

    for draw_key, draw_data in draws.items():
        draw_name = draw_data.get("name") or str(draw_key) or "US Open"
        for day in draw_data.get("dates", []):
            tourn_day = day.get("tournDay", 0)
            if tourn_day is None or tourn_day < min_tourn_day:
                continue

            day_date = day.get("date")  # "YYYY-MM-DD"
            day_epoch = day.get("epoch")
            day_epoch_dt = _epoch_to_et(day_epoch)

            for sess in day.get("session", []):
                session_id = sess.get("session_id") or ""
                link = (sess.get("link") or {}).get("url") or ""

                for t in sess.get("times", []):
                    gate = t.get("gate")
                    start_label = t.get("start")
                    events_list = t.get("events") or []

                    titles = _titles_for_events(events_list)
                    if not titles:
                        continue  # nothing to keep in this time block

                    # prefer precise date+start, else fallback to day epoch
                    start_time = _combine_date_time_et(day_date, start_label) or day_epoch_dt
                    court = draw_name  # treat draw as "location"

                    # build concise description
                    desc_parts = []
                    if draw_name:
                        desc_parts.append(draw_name)
                    if session_id:
                        desc_parts.append(f"Session {session_id}")
                    if gate:
                        desc_parts.append(f"Gates open: {gate}")
                    if day_date:
                        desc_parts.append(f"Date: {day_date}")
                    if link:
                        desc_parts.append(f"Tickets: {link}")
                    description = " | ".join(desc_parts)

                    for title in titles:
                        key = (title, court, start_time.isoformat() if isinstance(start_time, datetime) else "")
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        matches_all.append({
                            "title": title,
                            "court": court,
                            "description": description,
                            "start_time": start_time,
                        })

    return matches_all

# Optional alias if you prefer a distinct name elsewhere:
parse_tournament_schedule = parse_schedule

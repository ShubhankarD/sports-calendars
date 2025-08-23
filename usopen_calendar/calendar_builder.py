import hashlib
from datetime import timedelta, datetime
from typing import Dict, List, Optional, Union
from ics import Calendar, Event
from ics.contentline import ContentLine as CalendarContentLine
from ics.contentline import ContentLine as EventContentLine

from .config import DEFAULT_EVENT_HOURS, CAL_METADATA

def add_vcalendar_extras(cal: Calendar, extras: Dict[str, Union[str, tuple]]):
    """Add VCALENDAR-level extra properties.
    'extras' values:
      - "string" -> value with no params
      - ("value", {"PARAM": ["VAL"]}) -> value with params
    """
    for name, val in extras.items():
        if isinstance(val, tuple):
            value, params = val
            cal.extra.append(CalendarContentLine(name=name, params=params, value=value))
        else:
            cal.extra.append(CalendarContentLine(name=name, params={}, value=val))

def add_vevent_extras(event: Event, extras: Dict[str, Union[str, tuple]]):
    for name, val in extras.items():
        if isinstance(val, tuple):
            value, params = val
            event.extra.append(EventContentLine(name=name, params=params, value=value))
        else:
            event.extra.append(EventContentLine(name=name, params={}, value=val))

def _stable_uid(summary: str, location: str, begin_dt: Optional[datetime]) -> str:
    base = f"{summary}|{location}|{begin_dt.isoformat() if begin_dt else ''}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest() + "@github-pages"

def create_calendar(matches: List[dict], default_event_hours: int = DEFAULT_EVENT_HOURS) -> Calendar:
    cal = Calendar()

    # VCALENDAR metadata & refresh hints
    add_vcalendar_extras(cal, {
        "X-WR-CALNAME": CAL_METADATA.get("name", "US Open 2025"),
        "X-WR-TIMEZONE": CAL_METADATA.get("timezone", "America/New_York"),
        "REFRESH-INTERVAL": (CAL_METADATA.get("refresh_interval", "PT1H"), {"VALUE": ["DURATION"]}),
        "X-PUBLISHED-TTL": CAL_METADATA.get("published_ttl", "PT1H"),
    })
    cal.method = CAL_METADATA.get("method", "PUBLISH")
    cal.prodid = CAL_METADATA.get("prodid", "-//Your Org//US Open 2025//EN")

    for m in matches:
        ev = Event()
        ev.summary = m.get("title") or "Match (TBD)"
        ev.location = m.get("court")
        ev.description = m.get("description")

        start_time = m.get("start_time")
        if start_time:
            ev.begin = start_time
            ev.end = start_time + timedelta(hours=default_event_hours)

        # Transparent = doesn't block busy time in many clients
        ev.transparent = True

        # Deterministic UID so updates replace (not duplicate)
        ev.uid = _stable_uid(ev.summary, ev.location or "", getattr(ev, "begin", None))

        # Optional VEVENT extras (example if you want to add a URL)
        # add_vevent_extras(ev, {"URL": "https://www.usopen.org/"})

        cal.events.append(ev)

    return cal

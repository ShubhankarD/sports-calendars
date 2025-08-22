import requests
from datetime import datetime, timedelta
from ics import Calendar, Event

# US Open base schedule URL
BASE_URL = "https://www.usopen.org/en_US/scores/feeds/2025/schedule/scheduleDays.json"

# Headers (fake UA helps avoid blocking)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


def fetch_json(url):
    """Fetch JSON data from given URL with headers."""
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def parse_feed_to_events(feed_json):
    """Parse a feed (day) JSON object and return a list of ics.Event objects.

    Args:
        feed_json (dict): JSON returned for a single schedule day (courts + matches).

    Returns:
        List[Event]: list of configured ics.Event objects (may be empty).
    """
    events = []
    display_date = feed_json.get("displayDate", "Unknown Day")
    courts = feed_json.get("courts", [])

    for court in courts:
        court_name = court.get("courtName", "Unknown Court")
        session_time = court.get("time", "")
        matches = court.get("matches", [])

        for match in matches:
            # Player names
            team1 = match.get("team1", [])
            team2 = match.get("team2", [])
            players_team1 = " & ".join(
                filter(None, [
                    team1[0].get("displayNameA") if team1 else None,
                    team1[0].get("displayNameB") if team1 else None,
                ])
            )
            players_team2 = " & ".join(
                filter(None, [
                    team2[0].get("displayNameA") if team2 else None,
                    team2[0].get("displayNameB") if team2 else None,
                ])
            )
            title = f"{players_team1} vs {players_team2}"

            # Convert epoch → datetime if available
            start_epoch = match.get("startEpoch") or court.get("startEpoch")
            if start_epoch:
                start_time = datetime.utcfromtimestamp(start_epoch)
            else:
                start_time = None

            # Build the event using ics.Event attributes
            event = Event()
            event.name = title
            event.location = court_name
            event.description = f"{match.get('eventName', '')} - {match.get('roundName', '')} ({display_date})"
            if start_time:
                event.begin = start_time
                event.end = start_time + timedelta(hours=2)

            events.append(event)

    return events


def create_calendar():
    """Orchestrate fetching schedule days, parsing feeds, and returning a Calendar.

    This function is deliberately small: it fetches the top-level schedule days feed,
    fetches each day's feed, parses events with `parse_feed_to_events`, and adds them
    to an `ics.Calendar` which is returned.
    """
    cal = Calendar()
    # Leave metadata to the ics library defaults (avoid adding raw tuples to cal.extra)

    # Step 1: Get all schedule days
    raw_schedule = fetch_json(BASE_URL)

    # Normalize into a list of day entries. The top-level feed may be a list or a dict
    # that contains a list under common keys.
    if isinstance(raw_schedule, list):
        schedule_days = raw_schedule
    elif isinstance(raw_schedule, dict):
        # try several common keys where lists may appear
        for key in ("scheduleDays", "days", "eventDays", "items"):
            if key in raw_schedule and isinstance(raw_schedule[key], list):
                schedule_days = raw_schedule[key]
                break
        else:
            # Not a list-like structure we understand; try to extract any list value
            found = False
            for v in raw_schedule.values():
                if isinstance(v, list):
                    schedule_days = v
                    found = True
                    break
            if not found:
                schedule_days = []
    else:
        schedule_days = []

    for day in schedule_days:
        # If the feed contains plain URL strings, treat them as per-day feeds
        if isinstance(day, str):
            feed_url = day
            try:
                day_data = fetch_json(feed_url)
            except Exception:
                continue
            events = parse_feed_to_events(day_data)
            for ev in events:
                cal.events.add(ev)
            continue

        if not isinstance(day, dict):
            # unexpected type; skip
            continue

        # Newer feeds may nest per-day feeds inside `eventDays` on the day object.
        event_days = day.get("eventDays") or []

        if event_days and isinstance(event_days, list):
            for ed in event_days:
                if not isinstance(ed, dict):
                    continue
                feed_url = ed.get("feedUrl")
                if not feed_url:
                    continue

                # Step 2: Fetch the detailed matches for the event day
                day_data = fetch_json(feed_url)

                # Step 3: Parse into Event objects and add to calendar
                events = parse_feed_to_events(day_data)
                for ev in events:
                    cal.events.add(ev)
        else:
            # Fallback for older structure with a top-level feedUrl
            feed_url = day.get("feedUrl")
            if not feed_url:
                continue

            day_data = fetch_json(feed_url)
            events = parse_feed_to_events(day_data)
            for ev in events:
                cal.events.add(ev)

    return cal


if __name__ == "__main__":
    cal = create_calendar()
    # ics.Calendar.serialize() returns the ICS text
    with open("usopen_schedule.ics", "w", encoding="utf-8") as f:
        f.write(cal.serialize())
    print("✅ usopen_schedule.ics created")

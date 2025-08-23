import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from ics import Calendar, Event

ET = ZoneInfo("America/New_York")

BASE_URL = "https://www.usopen.org/en_US/scores/feeds/2025/schedule/scheduleDays.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def fetch_json(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def parse_schedule():
    schedule_data = fetch_json(BASE_URL)
    event_days = schedule_data.get("eventDays", [])
    matches_all = []

    for day in event_days:
        tourn_day = day.get("tournDay", 0)
        feed_url = day.get("feedUrl")

        if not feed_url or (tourn_day is None or tourn_day < 7):
            continue

        day_data = fetch_json(feed_url)
        courts = day_data.get("courts", [])
        display_date = day_data.get("displayDate")

        for court in courts:
            court_name = court.get("courtName", "Unknown Court")
            for match_data in court.get("matches", []):
                players_team1 = " & ".join(
                    filter(None, [
                        match_data["team1"][0].get("displayNameA"),
                        match_data["team1"][0].get("displayNameB")
                    ])
                )
                players_team2 = " & ".join(
                    filter(None, [
                        match_data["team2"][0].get("displayNameA"),
                        match_data["team2"][0].get("displayNameB")
                    ])
                )

                start_epoch = match_data.get("startEpoch") or court.get("startEpoch")
                if start_epoch:
                    # interpret epoch as UTC, then convert to ET (EST/EDT)
                    start_time = datetime.fromtimestamp(start_epoch, tz=timezone.utc).astimezone(ET)
                else:
                    start_time = None

                matches_all.append({
                    "title": f"{players_team1} vs {players_team2}",
                    "court": court_name,
                    "description": f"{match_data.get('eventName')} - {match_data.get('roundName')} | {display_date}",
                    "start_time": start_time
                })

    return matches_all

def create_calendar(matches):
    cal = Calendar()


    for m in matches:
        event = Event()
        event.summary = m["title"]
        event.location = m["court"]
        event.description = m["description"]

        if m["start_time"]:
            dt_et = m["start_time"]
            event.begin = dt_et
            event.end = dt_et + timedelta(hours=2)

        cal.events.append(event)

    return cal


if __name__ == "__main__":
    matches = parse_schedule()
    cal = create_calendar(matches)

    with open("usopen_schedule.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize())
    print(f"✅ Created usopen_schedule.ics with {len(matches)} matches")

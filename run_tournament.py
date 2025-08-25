from usopen_calendar.tournament_v1 import parse_schedule
from usopen_calendar.calendar_builder import create_calendar

if __name__ == "__main__":
    matches = parse_schedule(group_by_time_event=True)
    cal = create_calendar(matches, default_event_hours=2)
    with open("usopen_tournament_schedule.ics", "w", encoding="utf-8") as f:
        f.write(cal.serialize())
    print(f"✅ Created usopen_tournament_schedule.ics with {len(matches)} matches")
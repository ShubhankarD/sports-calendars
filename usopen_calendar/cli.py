import argparse
from .config import BASE_URL, INCLUDE_BEFORE_TOURNDAY, DEFAULT_EVENT_HOURS, TOURNAMENT_URL
from .tournament import parse_schedule
from .calendar_builder import create_calendar

def main():
    parser = argparse.ArgumentParser(description="Generate an iCalendar (.ics) file for the US Open schedule.")
    parser.add_argument("--output", "-o", default="usopen_schedule.ics", help="Output .ics file path")
    parser.add_argument("--base-url", default=BASE_URL, help="Root scheduleDays.json URL to start from")
    parser.add_argument("--tournament-url", default=TOURNAMENT_URL, help="Macro tournament_schedule.json URL for session placeholders")
    parser.add_argument("--min-day", type=int, default=INCLUDE_BEFORE_TOURNDAY, help="Minimum tournDay (inclusive) to include")
    parser.add_argument("--duration", type=int, default=DEFAULT_EVENT_HOURS, help="Default event duration in hours")
    parser.add_argument("--no-group", action="store_true", help="Disable grouping of matches by start time and event")
    parser.add_argument("--no-placeholders", action="store_true", help="Disable generating future round placeholder events")

    args = parser.parse_args()

    matches = parse_schedule(
        base_url=args.base_url,
        min_tourn_day=args.min_day,
        group_by_time_event=not args.no_group,
        include_placeholders=not args.no_placeholders,
        tournament_schedule_url=args.tournament_url,
    )
    cal = create_calendar(matches, default_event_hours=args.duration)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(cal.serialize())
    print(f"✅ Created {args.output} with {len(matches)} matches")


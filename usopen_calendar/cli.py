import argparse
from .config import BASE_URL, INCLUDE_BEFORE_TOURNDAY, DEFAULT_EVENT_HOURS
from .parsing import parse_schedule
from .calendar_builder import create_calendar

def main():
    parser = argparse.ArgumentParser(description="Generate an iCalendar (.ics) file for the US Open schedule.")
    parser.add_argument("--output", "-o", default="usopen_schedule.ics", help="Output .ics file path")
    parser.add_argument("--base-url", default=BASE_URL, help="Root scheduleDays.json URL to start from")
    parser.add_argument("--min-day", type=int, default=INCLUDE_BEFORE_TOURNDAY, help="Minimum tournDay (inclusive) to include")
    parser.add_argument("--duration", type=int, default=DEFAULT_EVENT_HOURS, help="Default event duration in hours")

    args = parser.parse_args()

    matches = parse_schedule(base_url=args.base_url, min_tourn_day=args.min_day)
    cal = create_calendar(matches, default_event_hours=args.duration)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(cal.serialize())
    print(f"✅ Created {args.output} with {len(matches)} matches")

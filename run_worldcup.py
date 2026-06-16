from worldcup_calendar import create_calendar, parse_matches, fetch_schedule


if __name__ == "__main__":
    schedule = fetch_schedule()
    matches = parse_matches(schedule)
    cal = create_calendar(matches)
    with open("worldcup_schedule.ics", "w", encoding="utf-8") as f:
        f.write(cal.serialize())
    print(f"Created worldcup_schedule.ics with {len(matches)} events")

from ucl_calendar import create_calendar, parse_matches, fetch_schedule


if __name__ == "__main__":
    schedule = fetch_schedule()
    matches = parse_matches(schedule)
    cal = create_calendar(matches)
    with open("ucl_schedule.ics", "w", encoding="utf-8") as f:
        f.write(cal.serialize())
    print(f"Created ucl_schedule.ics with {len(matches)} events")

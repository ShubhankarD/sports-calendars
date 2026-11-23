from nations_league_calendar import create_calendar, parse_matches, fetch_schedule


if __name__ == "__main__":
    schedule = fetch_schedule()
    matches = parse_matches(schedule)
    cal = create_calendar(matches)
    with open("nations_league_schedule.ics", "w", encoding="utf-8") as f:
        f.write(cal.serialize())
    print(f"Created nations_league_schedule.ics with {len(matches)} events")

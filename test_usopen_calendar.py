from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from usopen_calendar.flags import team_label
from usopen_calendar.tournament import parse_schedule
from usopen_calendar.calendar_builder import create_calendar


def test_team_label_plain_text():
    team = [
        {
            "displayNameA": "T. Paul",
            "displayNameB": None,
            "nationA": "USA",
            "nationB": None,
        }
    ]
    label = team_label(team)
    assert label == "T. Paul"
    assert "🇺🇸" not in label
    assert "🎾" not in label


def test_team_label_doubles():
    team = [
        {
            "displayNameA": "J. Peer",
            "displayNameB": "J. Murray",
            "nationA": "AUS",
            "nationB": "GBR",
        }
    ]
    label = team_label(team)
    assert label == "J. Peer & J. Murray"


@patch("usopen_calendar.tournament.fetch_json")
def test_parse_schedule_individual_matches(mock_fetch):
    def side_effect(url):
        if "scheduleDays.json" in url:
            return {
                "eventDays": [
                    {
                        "tournDay": 7,
                        "feedUrl": "https://www.usopen.org/en_US/scores/feeds/2026/schedule/schedule7.json",
                    }
                ]
            }
        elif "schedule7.json" in url:
            return {
                "displayDate": "Sunday, August 30",
                "courts": [
                    {
                        "courtName": "Arthur Ashe Stadium",
                        "startEpoch": 1788102000,
                        "matches": [
                            {
                                "eventName": "Men's Singles",
                                "roundName": "Round 1",
                                "team1": [{"displayNameA": "D. Medvedev"}],
                                "team2": [{"displayNameA": "H. Gaston"}],
                            }
                        ],
                    }
                ],
            }
        return {}

    mock_fetch.side_effect = side_effect

    matches = parse_schedule(min_tourn_day=7, group_by_time_event=False)
    assert len(matches) == 1
    m = matches[0]
    assert m["title"] == "D. Medvedev vs H. Gaston"
    assert m["court"] == "Arthur Ashe Stadium"
    assert m["description"] == "Men's Singles - Round 1 | Sunday, August 30"
    assert isinstance(m["start_time"], datetime)


@patch("usopen_calendar.tournament.fetch_json")
def test_parse_schedule_filters_boys_and_girls(mock_fetch):
    def side_effect(url):
        if "scheduleDays.json" in url:
            return {
                "eventDays": [
                    {
                        "tournDay": 7,
                        "feedUrl": "https://www.usopen.org/en_US/scores/feeds/2026/schedule/schedule7.json",
                    }
                ]
            }
        elif "schedule7.json" in url:
            return {
                "displayDate": "Sunday, August 30",
                "courts": [
                    {
                        "courtName": "Court 5",
                        "startEpoch": 1788102000,
                        "matches": [
                            {
                                "eventName": "Boys' Singles",
                                "roundName": "Round 1",
                                "team1": [{"displayNameA": "Player A"}],
                                "team2": [{"displayNameA": "Player B"}],
                            },
                            {
                                "eventName": "Girls' Singles",
                                "roundName": "Round 1",
                                "team1": [{"displayNameA": "Player C"}],
                                "team2": [{"displayNameA": "Player D"}],
                            },
                            {
                                "eventName": "Men's Singles",
                                "roundName": "Round 1",
                                "team1": [{"displayNameA": "D. Medvedev"}],
                                "team2": [{"displayNameA": "H. Gaston"}],
                            },
                        ],
                    }
                ],
            }
        return {}

    mock_fetch.side_effect = side_effect

    matches = parse_schedule(min_tourn_day=7, group_by_time_event=False)
    assert len(matches) == 1
    assert matches[0]["title"] == "D. Medvedev vs H. Gaston"


@patch("usopen_calendar.tournament.fetch_json")
def test_parse_schedule_grouped_matches(mock_fetch):
    def side_effect(url):
        if "scheduleDays.json" in url:
            return {
                "eventDays": [
                    {
                        "tournDay": 7,
                        "feedUrl": "https://www.usopen.org/en_US/scores/feeds/2026/schedule/schedule7.json",
                    }
                ]
            }
        elif "schedule7.json" in url:
            return {
                "displayDate": "Sunday, August 30",
                "courts": [
                    {
                        "courtName": "Arthur Ashe Stadium",
                        "startEpoch": 1788102000,
                        "matches": [
                            {
                                "eventName": "Men's Singles",
                                "roundName": "Round 1",
                                "team1": [{"displayNameA": "D. Medvedev"}],
                                "team2": [{"displayNameA": "H. Gaston"}],
                            }
                        ],
                    },
                    {
                        "courtName": "Louis Armstrong Stadium",
                        "startEpoch": 1788102000,
                        "matches": [
                            {
                                "eventName": "Men's Singles",
                                "roundName": "Round 1",
                                "team1": [{"displayNameA": "C. Alcaraz"}],
                                "team2": [{"displayNameA": "J. Sinner"}],
                            }
                        ],
                    },
                ],
            }
        return {}

    mock_fetch.side_effect = side_effect

    matches = parse_schedule(min_tourn_day=7, group_by_time_event=True)
    assert len(matches) == 1
    m = matches[0]
    assert m["title"] == "Men's Singles - Round 1"
    assert m["court"] == "Multiple Courts"
    assert "Men's Singles | Round 1 | Day 7" in m["description"]
    assert "1. D. Medvedev vs H. Gaston" in m["description"]
    assert "2. C. Alcaraz vs J. Sinner" in m["description"]


def test_create_calendar():
    matches = [
        {
            "title": "Carlos Alcaraz vs Jannik Sinner",
            "court": "Arthur Ashe Stadium",
            "description": "Men's Singles - Final | Sunday, September 13",
            "start_time": datetime(2026, 9, 13, 16, 0, tzinfo=timezone.utc),
        }
    ]

    cal = create_calendar(matches)
    assert len(cal.events) == 1
    event = list(cal.events)[0]
    assert event.summary == "Carlos Alcaraz vs Jannik Sinner"
    assert event.location == "Arthur Ashe Stadium"
    assert "Men's Singles - Final" in event.description
    assert event.uid.endswith("@github-pages")


@patch("usopen_calendar.tournament.fetch_json")
def test_parse_schedule_with_placeholders(mock_fetch):
    def side_effect(url):
        if "scheduleDays.json" in url:
            return {
                "eventDays": [
                    {
                        "tournDay": 7,
                        "feedUrl": "https://www.usopen.org/en_US/scores/feeds/2026/schedule/schedule7.json",
                    }
                ]
            }
        elif "schedule7.json" in url:
            return {
                "displayDate": "Sunday, August 30",
                "courts": [
                    {
                        "courtName": "Arthur Ashe Stadium",
                        "startEpoch": 1788102000,
                        "matches": [
                            {
                                "eventName": "Men's Singles",
                                "roundName": "Round 1",
                                "team1": [{"displayNameA": "D. Medvedev"}],
                                "team2": [{"displayNameA": "H. Gaston"}],
                            }
                        ],
                    }
                ],
            }
        elif "tournament_schedule.json" in url:
            return {
                "tournament_schedule": {
                    "draws": {
                        "week3": {
                            "dates": [
                                {
                                    "date": "2026-08-30",  # Same date as schedule7 -> should be skipped!
                                    "session": [
                                        {
                                            "session_id": "1",
                                            "times": [
                                                {
                                                    "start": "11:00 AM",
                                                    "events": ["Men's & Women's Singles 1st Round"],
                                                }
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "date": "2026-09-13",  # Future date -> should become placeholder!
                                    "session": [
                                        {
                                            "session_id": "27",
                                            "times": [
                                                {
                                                    "start": "2:00 PM",
                                                    "events": ["Men's Singles Final"],
                                                }
                                            ],
                                        }
                                    ],
                                },
                            ]
                        }
                    }
                }
            }
        return {}

    mock_fetch.side_effect = side_effect

    matches = parse_schedule(min_tourn_day=7, group_by_time_event=True, include_placeholders=True)
    # Expect 1 actual match group (Aug 30) + 1 placeholder (Sep 13)
    assert len(matches) == 2

    # 1st: Actual match
    assert matches[0]["title"] == "D. Medvedev vs H. Gaston"
    assert "D. Medvedev vs H. Gaston" in matches[0]["description"]

    # 2nd: Placeholder
    placeholder = matches[1]
    assert placeholder["title"] == "Men's Singles Final"
    assert placeholder["court"] == "Arthur Ashe Stadium"
    assert "Session 27" in placeholder["description"]
    assert "🎾 Matchup: TBD" in placeholder["description"]
    assert placeholder["start_time"].year == 2026
    assert placeholder["start_time"].month == 9
    assert placeholder["start_time"].day == 13


@patch("usopen_calendar.tournament.fetch_json")
def test_parse_schedule_no_placeholders(mock_fetch):
    def side_effect(url):
        if "scheduleDays.json" in url:
            return {
                "eventDays": [
                    {
                        "tournDay": 7,
                        "feedUrl": "https://www.usopen.org/en_US/scores/feeds/2026/schedule/schedule7.json",
                    }
                ]
            }
        elif "schedule7.json" in url:
            return {
                "displayDate": "Sunday, August 30",
                "courts": [
                    {
                        "courtName": "Arthur Ashe Stadium",
                        "startEpoch": 1788102000,
                        "matches": [
                            {
                                "eventName": "Men's Singles",
                                "roundName": "Round 1",
                                "team1": [{"displayNameA": "D. Medvedev"}],
                                "team2": [{"displayNameA": "H. Gaston"}],
                            }
                        ],
                    }
                ],
            }
        return {}

    mock_fetch.side_effect = side_effect

    matches = parse_schedule(min_tourn_day=7, group_by_time_event=True, include_placeholders=False)
    assert len(matches) == 1
    assert matches[0]["title"] == "D. Medvedev vs H. Gaston"


def test_team_display_label_flags():
    from usopen_calendar.flags import team_display_label

    singles = [{"displayNameA": "T. Paul", "nationA": "USA"}]
    assert team_display_label(singles) == "🇺🇸 T. Paul"

    doubles = [
        {
            "displayNameA": "J. Peer",
            "nationA": "AUS",
            "displayNameB": "J. Murray",
            "nationB": "GBR",
        }
    ]
    assert team_display_label(doubles) == "🇦🇺 J. Peer & 🇬🇧 J. Murray"

    neutral = [{"displayNameA": "D. Medvedev", "nationA": None}]
    assert team_display_label(neutral) == "D. Medvedev"


@patch("usopen_calendar.tournament.fetch_json")
def test_grouped_matches_with_country_flags(mock_fetch):
    def side_effect(url):
        if "scheduleDays.json" in url:
            return {
                "eventDays": [
                    {
                        "tournDay": 7,
                        "feedUrl": "https://www.usopen.org/en_US/scores/feeds/2026/schedule/schedule7.json",
                    }
                ]
            }
        elif "schedule7.json" in url:
            return {
                "displayDate": "Sunday, August 30",
                "courts": [
                    {
                        "courtName": "Arthur Ashe Stadium",
                        "startEpoch": 1788102000,
                        "matches": [
                            {
                                "eventName": "Men's Singles",
                                "roundName": "Round 1",
                                "team1": [{"displayNameA": "C. Alcaraz", "nationA": "ESP"}],
                                "team2": [{"displayNameA": "J. Sinner", "nationA": "ITA"}],
                            }
                        ],
                    }
                ],
            }
        return {}

    mock_fetch.side_effect = side_effect

    matches = parse_schedule(min_tourn_day=7, group_by_time_event=True, include_placeholders=False)
    assert len(matches) == 1
    # Country emojis in title for single match
    assert matches[0]["title"] == "🇪🇸 C. Alcaraz vs 🇮🇹 J. Sinner"
    # Country emojis before each player name in description
    assert "1. 🇪🇸 C. Alcaraz vs 🇮🇹 J. Sinner" in matches[0]["description"]


def test_estimate_duration():
    from usopen_calendar.tournament import _estimate_duration
    from datetime import datetime, timezone

    # Men's singles final
    assert _estimate_duration(event_name="Men's Singles", round_name="Final") == 4.0

    # Women's singles final
    assert _estimate_duration(event_name="Women's Singles", round_name="Final") == 2.5

    # Individual men's match
    assert _estimate_duration(event_name="Men's Singles", round_name="Round 1", match_count=1) == 3.5

    # Individual women's match
    assert _estimate_duration(event_name="Women's Singles", round_name="Round 1", match_count=1) == 2.0

    # Doubles match reminder style (15 minutes = 0.25h)
    assert _estimate_duration(event_name="Men's Doubles", round_name="Round 1", match_count=1) == 0.25
    assert _estimate_duration(event_name="Women's Doubles", round_name="Round 1", match_count=5) == 0.25
    assert _estimate_duration(event_name="Mixed Doubles", round_name="Final", match_count=1) == 0.25

    # Grouped Day session (11:30 AM)
    day_dt = datetime(2026, 9, 8, 11, 30, tzinfo=timezone.utc)
    assert _estimate_duration(event_name="Men's & Women's Singles", start_time=day_dt, match_count=4) == 4.5

    # Grouped Night session (7:00 PM)
    night_dt = datetime(2026, 9, 8, 19, 0, tzinfo=timezone.utc)
    assert _estimate_duration(event_name="Men's & Women's Singles", start_time=night_dt, match_count=2) == 3.5


def test_create_calendar_dynamic_duration():
    from datetime import datetime, timedelta, timezone

    dt = datetime(2026, 9, 13, 14, 0, tzinfo=timezone.utc)
    matches = [
        {
            "title": "Men's Singles Final",
            "court": "Arthur Ashe Stadium",
            "description": "Session 27",
            "start_time": dt,
            "duration_hours": 4.0,
        }
    ]

    cal = create_calendar(matches)
    ev = list(cal.events)[0]
    assert ev.begin == dt
    assert ev.end == dt + timedelta(hours=4.0)


@patch("usopen_calendar.tournament.fetch_json")
def test_parse_schedule_not_before(mock_fetch):
    from zoneinfo import ZoneInfo
    CT = ZoneInfo("America/Chicago")

    def side_effect(url):
        if "scheduleDays.json" in url:
            return {
                "eventDays": [
                    {
                        "tournDay": 17,
                        "feedUrl": "https://www.usopen.org/en_US/scores/feeds/2026/schedule/schedule17.json",
                    }
                ]
            }
        elif "schedule17.json" in url:
            return {
                "displayDate": "Tuesday, September 8",
                "epoch": 1788881400,
                "courts": [
                    {
                        "courtName": "Arthur Ashe Stadium",
                        "startEpoch": 1788881400,  # 11:30 AM EDT / 10:30 AM CDT
                        "matches": [
                            {
                                "order": 1,
                                "eventName": "Women's Singles",
                                "roundName": "Quarterfinals",
                                "team1": [{"displayNameA": "A. Sabalenka"}],
                                "team2": [{"displayNameA": "L. Noskova", "nationA": "CZE"}],
                            },
                            {
                                "order": 2,
                                "eventName": "Men's Singles",
                                "roundName": "Quarterfinals",
                                "notBefore": "1:00 PM",
                                "team1": [{"displayNameA": "F. Tiafoe", "nationA": "USA"}],
                                "team2": [{"displayNameA": "A. Michelsen", "nationA": "USA"}],
                            },
                        ],
                    }
                ],
            }
        return {}

    mock_fetch.side_effect = side_effect

    matches = parse_schedule(min_tourn_day=17, group_by_time_event=True, include_placeholders=False)
    assert len(matches) == 2

    # Match 1 starts at 11:30 AM EDT / 10:30 AM CDT
    m1 = matches[0]
    assert m1["title"] == "A. Sabalenka vs 🇨🇿 L. Noskova"
    assert m1["start_time"].hour == 11
    assert m1["start_time"].minute == 30
    assert m1["start_time"].astimezone(CT).hour == 10

    # Match 2 with notBefore: 1:00 PM EDT / 12:00 PM CDT (12 CDT)
    m2 = matches[1]
    assert m2["title"] == "🇺🇸 F. Tiafoe vs 🇺🇸 A. Michelsen"
    assert m2["start_time"].hour == 13
    assert m2["start_time"].minute == 0
    assert m2["start_time"].astimezone(CT).hour == 12


@patch("usopen_calendar.tournament.fetch_json")
def test_single_match_naming_exclusive_to_singles(mock_fetch):
    def side_effect(url):
        if "scheduleDays.json" in url:
            return {
                "eventDays": [
                    {
                        "tournDay": 7,
                        "feedUrl": "https://www.usopen.org/en_US/scores/feeds/2026/schedule/schedule7.json",
                    }
                ]
            }
        elif "schedule7.json" in url:
            return {
                "displayDate": "Sunday, August 30",
                "courts": [
                    {
                        "courtName": "Court 17",
                        "startEpoch": 1788102000,
                        "matches": [
                            {
                                "eventName": "Men's Doubles",
                                "roundName": "Quarterfinals",
                                "team1": [{"displayNameA": "Player 1", "displayNameB": "Player 2"}],
                                "team2": [{"displayNameA": "Player 3", "displayNameB": "Player 4"}],
                            }
                        ],
                    }
                ],
            }
        return {}

    mock_fetch.side_effect = side_effect

    matches = parse_schedule(min_tourn_day=7, group_by_time_event=True, include_placeholders=False)
    assert len(matches) == 1
    # Doubles single match should retain round/event name, NOT player names
    assert matches[0]["title"] == "Men's Doubles - Quarterfinals"
    assert "Player 1 & Player 2 vs Player 3 & Player 4" in matches[0]["description"]

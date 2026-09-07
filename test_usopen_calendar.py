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
    assert matches[0]["title"] == "Men's Singles - Round 1"
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
    assert matches[0]["title"] == "Men's Singles - Round 1"


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
    # Plain text in title
    assert matches[0]["title"] == "Men's Singles - Round 1"
    # Country emojis before each player name in description
    assert "1. 🇪🇸 C. Alcaraz vs 🇮🇹 J. Sinner" in matches[0]["description"]




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

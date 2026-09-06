from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from ucl_calendar import (
    create_calendar,
    fetch_schedule,
    parse_matches,
    _parse_event,
    _should_show_score,
)


def test_parse_matches_grouped_with_star_featured_matches():
    mock_data = {
        "sports": [
            {
                "leagues": [
                    {
                        "events": [
                            {
                                "id": "101",
                                "name": "2026-27 UEFA Champions League",
                                "date": "2026-09-08T16:45:00Z",
                                "location": "Stadium A",
                                "group": {"name": "League Phase"},
                                "competitors": [
                                    {"displayName": "LASK Linz", "homeAway": "home", "order": 1},
                                    {"displayName": "AEK Athens", "homeAway": "away", "order": 2},
                                ],
                            },
                            {
                                "id": "102",
                                "name": "2026-27 UEFA Champions League",
                                "date": "2026-09-08T16:45:00Z",
                                "location": "Stadium B",
                                "group": {"name": "League Phase"},
                                "competitors": [
                                    {"displayName": "Real Madrid", "homeAway": "home", "order": 1},
                                    {"displayName": "Arsenal", "homeAway": "away", "order": 2},
                                ],
                            },
                        ]
                    }
                ]
            }
        ]
    }

    matches = parse_matches(mock_data, group_before_knockouts=True)
    assert len(matches) == 1
    m = matches[0]
    assert m["summary"] == "⚽ UEFA Champions League - League Phase"
    assert "⭐ 1. Real Madrid vs Arsenal" in m["description"]
    assert "2. LASK Linz vs AEK Athens" in m["description"]
    assert "<b>⭐ Real Madrid vs Arsenal</b>" in m["html_description"]


def test_parse_matches_knockout_individual():
    mock_data = {
        "sports": [
            {
                "leagues": [
                    {
                        "events": [
                            {
                                "id": "201",
                                "name": "2026-27 UEFA Champions League",
                                "date": "2027-03-09T20:00:00Z",
                                "location": "Allianz Arena",
                                "group": {"name": "Round of 16"},
                                "competitors": [
                                    {"displayName": "Bayern Munich", "homeAway": "home", "order": 1},
                                    {"displayName": "Arsenal", "homeAway": "away", "order": 2},
                                ],
                            },
                        ]
                    }
                ]
            }
        ]
    }

    matches = parse_matches(mock_data, group_before_knockouts=True)
    assert len(matches) == 1
    assert matches[0]["summary"] == "⚽ ⭐ Bayern Munich vs Arsenal · Round of 16"


def test_create_calendar():
    matches = [
        {
            "id": "101",
            "summary": "⚽ UEFA Champions League - League Phase",
            "start_time": datetime(2026, 9, 8, 16, 45, tzinfo=timezone.utc),
            "location": "Multiple Venues",
            "description": "UEFA Champions League | League Phase\n⭐ 1. Real Madrid vs Arsenal\n2. LASK Linz vs AEK Athens",
            "html_description": "<html><body><b>⭐ 1. Real Madrid vs Arsenal</b></body></html>",
        }
    ]

    cal = create_calendar(matches)
    assert len(cal.events) == 1
    event = list(cal.events)[0]
    assert event.summary == "⚽ UEFA Champions League - League Phase"
    assert event.uid == "ucl-101@github-pages"
    assert event.location == "Multiple Venues"
    assert any("X-ALT-DESC" in line.name for line in event.extra)


def test_should_show_score():
    home = {"label": "Real Madrid", "score": "2"}
    away = {"label": "Barcelona", "score": "1"}
    status = {"completed": True}
    start_time = datetime(2026, 10, 20, 19, 0, tzinfo=timezone.utc)
    updated_at = datetime(2026, 10, 22, 19, 0, tzinfo=timezone.utc)  # 2 days later

    assert _should_show_score(home, away, status, start_time, updated_at) is True

    # Less than 1 day
    updated_at_recent = datetime(2026, 10, 20, 21, 0, tzinfo=timezone.utc)
    assert _should_show_score(home, away, status, start_time, updated_at_recent) is False


@patch("requests.get")
def test_fetch_schedule(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"sports": []}
    mock_get.return_value = mock_response

    data = fetch_schedule()
    assert data == {"sports": []}
    mock_get.assert_called_once()

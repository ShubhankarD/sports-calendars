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


def test_parse_matches_header_format():
    mock_data = {
        "sports": [
            {
                "leagues": [
                    {
                        "events": [
                            {
                                "id": "101",
                                "name": "2026-27 UEFA Champions League",
                                "date": "2026-10-21T19:00:00Z",
                                "location": "Allianz Arena",
                                "group": {"name": "League Phase"},
                                "competitors": [
                                    {"displayName": "Bayern Munich", "homeAway": "home", "order": 1, "score": "2"},
                                    {"displayName": "Arsenal", "homeAway": "away", "order": 2, "score": "1"},
                                ],
                                "status": {"type": {"completed": True}},
                            }
                        ]
                    }
                ]
            }
        ]
    }

    matches = parse_matches(mock_data)
    assert len(matches) == 1
    m = matches[0]
    assert m["id"] == "101"
    assert "Bayern Munich vs Arsenal" in m["summary"]
    assert "League Phase" in m["summary"]
    assert m["location"] == "Allianz Arena"


def test_create_calendar():
    matches = [
        {
            "id": "101",
            "summary": "⚽ Bayern Munich vs Arsenal · League Phase",
            "start_time": datetime(2026, 10, 21, 19, 0, tzinfo=timezone.utc),
            "location": "Allianz Arena",
            "description": "Last updated: Oct 21, 2026 at 19:00 UTC",
        }
    ]

    cal = create_calendar(matches)
    assert cal.extra[1].value == "UEFA Champions League"
    assert len(cal.events) == 1
    event = list(cal.events)[0]
    assert event.summary == "⚽ Bayern Munich vs Arsenal · League Phase"
    assert event.uid == "ucl-101@github-pages"
    assert event.location == "Allianz Arena"


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

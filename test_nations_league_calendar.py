from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from nations_league_calendar import (
    create_calendar,
    fetch_schedule,
    parse_matches,
    _should_show_score,
)


def test_parse_matches_grouped_across_groups_with_featured_first():
    mock_data = {
        "sports": [
            {
                "leagues": [
                    {
                        "events": [
                            {
                                "id": "101",
                                "name": "2026-27 UEFA Nations League",
                                "date": "2026-09-24T18:45:00Z",
                                "location": "Stadium D",
                                "group": {"name": "Group D1"},
                                "competitors": [
                                    {"displayName": "San Marino", "homeAway": "home", "order": 1},
                                    {"displayName": "Liechtenstein", "homeAway": "away", "order": 2},
                                ],
                            },
                            {
                                "id": "102",
                                "name": "2026-27 UEFA Nations League",
                                "date": "2026-09-24T18:45:00Z",
                                "location": "Stade de France",
                                "group": {"name": "Group A1"},
                                "competitors": [
                                    {"displayName": "France", "homeAway": "home", "order": 1},
                                    {"displayName": "Spain", "homeAway": "away", "order": 2},
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
    assert m["summary"] == "UEFA Nations League - Group Stage"
    assert "1. 🇫🇷 France vs 🇪🇸 Spain (Group A1)" in m["description"]
    assert "2. 🇸🇲 San Marino vs 🇱🇮 Liechtenstein (Group D1)" in m["description"]


def test_parse_matches_knockout_individual():
    mock_data = {
        "sports": [
            {
                "leagues": [
                    {
                        "events": [
                            {
                                "id": "201",
                                "name": "2026-27 UEFA Nations League",
                                "date": "2027-03-25T19:45:00Z",
                                "location": "Allianz Arena",
                                "group": {"name": "Quarterfinals"},
                                "competitors": [
                                    {"displayName": "Germany", "homeAway": "home", "order": 1},
                                    {"displayName": "Italy", "homeAway": "away", "order": 2},
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
    assert matches[0]["summary"] == "🇩🇪 Germany vs 🇮🇹 Italy · Quarterfinals"


def test_create_calendar():
    matches = [
        {
            "id": "101",
            "summary": "UEFA Nations League - Group Stage",
            "start_time": datetime(2026, 9, 24, 18, 45, tzinfo=timezone.utc),
            "location": "Multiple Venues",
            "description": "UEFA Nations League | Group Stage\n1. France vs Spain (Group A1)",
        }
    ]

    cal = create_calendar(matches)
    assert len(cal.events) == 1
    event = list(cal.events)[0]
    assert event.summary == "UEFA Nations League - Group Stage"
    assert event.uid == "unl-101@github-pages"
    assert event.location == "Multiple Venues"


def test_should_show_score():
    home = {"label": "Spain", "score": "2"}
    away = {"label": "France", "score": "1"}
    status = {"completed": True}
    start_time = datetime(2026, 9, 24, 18, 45, tzinfo=timezone.utc)
    updated_at = datetime(2026, 9, 26, 18, 45, tzinfo=timezone.utc)

    assert _should_show_score(home, away, status, start_time, updated_at) is True

    updated_at_recent = datetime(2026, 9, 24, 21, 0, tzinfo=timezone.utc)
    assert _should_show_score(home, away, status, start_time, updated_at_recent) is False


@patch("requests.get")
def test_fetch_schedule(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"sports": []}
    mock_get.return_value = mock_response

    data = fetch_schedule()
    assert data == {"sports": []}
    mock_get.assert_called_once()
    called_url = mock_get.call_args[0][0]
    assert "uefa.nations" in called_url
    assert "limit=500" in called_url

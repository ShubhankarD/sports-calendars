from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .config import ET, BASE_URL, INCLUDE_BEFORE_TOURNDAY, TOURNAMENT_URL
from .fetch import fetch_json
from .flags import team_label, team_display_label

Match = Dict[str, Optional[object]]


def _round_up_15min(dt: datetime) -> datetime:
    """Round a datetime up to the nearest 15-minute mark (:00, :15, :30, :45)."""
    minute = dt.minute
    remainder = minute % 15
    if remainder != 0:
        dt = dt + timedelta(minutes=(15 - remainder))
    return dt.replace(second=0, microsecond=0)


def parse_schedule(
    base_url: str = BASE_URL,
    min_tourn_day: int = INCLUDE_BEFORE_TOURNDAY,
    *,
    group_by_time_event: bool = False,
    include_placeholders: bool = True,
    tournament_schedule_url: str = TOURNAMENT_URL,
    now_dt: Optional[datetime] = None,
) -> List[Match]:
    """Fetch schedule days, traverse day feeds, and build match dictionaries.

    Returns a list of individual matches with keys: title, court, description, start_time (aware datetime in ET or None)
    """
    try:
        schedule_data = fetch_json(base_url)
    except Exception:
        schedule_data = {}
    event_days = schedule_data.get("eventDays", [])

    raw_items: List[Dict[str, Optional[object]]] = []
    covered_dates = set()

    current_et = now_dt if now_dt is not None else datetime.now(timezone.utc).astimezone(ET)

    for day in event_days:
        tourn_day = day.get("tournDay", 0)
        feed_url = day.get("feedUrl")

        # Skip early practice/qualifying days or days without a feedUrl
        if tourn_day is None or tourn_day < min_tourn_day or not feed_url:
            continue

        day_data = fetch_json(feed_url)
        courts = day_data.get("courts", [])
        display_date = day_data.get("displayDate")

        day_epoch = day_data.get("epoch")
        for court in courts:
            court_name = court.get("courtName", "Unknown Court")
            court_base_epoch = court.get("startEpoch") or day_epoch

            court_busy_until: Optional[datetime] = None
            active_match_desc: Optional[str] = None

            for match_data in court.get("matches", []):
                event_name = match_data.get("eventName")
                round_name = match_data.get("roundName")

                not_before = match_data.get("notBefore")
                start_time: Optional[datetime] = None
                start_epoch: Optional[int] = None

                if not_before and court_base_epoch:
                    base_dt = datetime.fromtimestamp(court_base_epoch, tz=timezone.utc).astimezone(ET)
                    date_str = base_dt.strftime("%Y-%m-%d")
                    try:
                        start_time = datetime.strptime(
                            f"{date_str} {not_before.strip()}", "%Y-%m-%d %I:%M %p"
                        ).replace(tzinfo=ET)
                        start_epoch = int(start_time.timestamp())
                    except Exception:
                        pass

                if start_time is None:
                    start_epoch = match_data.get("startEpoch") or court.get("startEpoch")
                    start_time = (
                        datetime.fromtimestamp(start_epoch, tz=timezone.utc).astimezone(ET)
                        if start_epoch
                        else None
                    )

                t1_label = team_label(match_data.get("team1"))
                t2_label = team_label(match_data.get("team2"))
                t1_desc = team_display_label(match_data.get("team1"), include_flag=True)
                t2_desc = team_display_label(match_data.get("team2"), include_flag=True)

                m_status = match_data.get("status")
                m_status_code = match_data.get("statusCode")
                is_in_progress = m_status == "In Progress" or m_status_code == "A"
                is_completed = m_status == "Completed" or m_status_code in {"D", "E"}

                is_delayed = False
                delayed_note: Optional[str] = None

                if start_time:
                    # Case 1: A prior match on the same court is currently In Progress
                    if court_busy_until and not is_completed and not is_in_progress:
                        if start_time < court_busy_until:
                            is_delayed = True
                            delayed_note = (
                                f"Estimated start delayed to {court_busy_until.strftime('%-I:%M %p')} ET "
                                f"(Court in use: {active_match_desc})"
                                if active_match_desc
                                else f"Estimated start delayed to {court_busy_until.strftime('%-I:%M %p')} ET"
                            )
                            start_time = court_busy_until
                            start_epoch = int(start_time.timestamp())

                    # Case 2: Today's match is still upcoming, but its scheduled start_time has already passed
                    elif (
                        start_time.date() == current_et.date()
                        and not is_completed
                        and not is_in_progress
                        and start_time <= current_et
                    ):
                        min_start = _round_up_15min(current_et + timedelta(minutes=15))
                        is_delayed = True
                        delayed_note = f"Estimated start delayed to {min_start.strftime('%-I:%M %p')} ET"
                        start_time = min_start
                        start_epoch = int(start_time.timestamp())

                # If this match is in progress, update court_busy_until for subsequent matches on this court
                if is_in_progress and start_time:
                    active_match_desc = f"{t1_label} vs {t2_label}"
                    est_dur = _estimate_duration(
                        event_name=event_name,
                        round_name=round_name,
                        start_time=start_time,
                        match_count=1,
                    )
                    est_finish = start_time + timedelta(hours=est_dur)
                    min_transition = current_et + timedelta(minutes=15)
                    court_busy_until = _round_up_15min(max(est_finish, min_transition))
                elif not is_completed and not is_in_progress and start_time and is_delayed:
                    # Subsequent upcoming matches on the same court follow this match
                    est_dur = _estimate_duration(
                        event_name=event_name,
                        round_name=round_name,
                        start_time=start_time,
                        match_count=1,
                    )
                    court_busy_until = _round_up_15min(start_time + timedelta(hours=est_dur) + timedelta(minutes=15))

                if start_time:
                    covered_dates.add(start_time.strftime("%Y-%m-%d"))

                # Filter out standalone empty TBD placeholder slots without event or round names
                if (
                    (not t1_label or t1_label == "TBD")
                    and (not t2_label or t2_label == "TBD")
                    and not event_name
                    and not round_name
                ):
                    continue

                # Filter out Boys' and Girls' junior events
                if event_name and ("boy" in event_name.lower() or "girl" in event_name.lower()):
                    continue

                match_id = match_data.get("match_id") or match_data.get("matchId")
                raw_items.append(
                    {
                        "eventName": event_name,
                        "roundName": round_name,
                        "court": court_name,
                        "displayDate": display_date,
                        "tournDay": tourn_day,
                        "startEpoch": start_epoch,
                        "start_time": start_time,
                        "t1": t1_label,
                        "t2": t2_label,
                        "t1_desc": t1_desc,
                        "t2_desc": t2_desc,
                        "match_id": match_id,
                        "is_delayed": is_delayed,
                        "delayed_note": delayed_note,
                        "status": m_status,
                    }
                )

    placeholders: List[Match] = []
    if include_placeholders:
        placeholders = _generate_placeholders(
            tournament_schedule_url=tournament_schedule_url,
            covered_dates=covered_dates,
        )

    if not group_by_time_event:
        matches_all: List[Match] = []
        for it in raw_items:
            p1 = str(it["t1"]).strip() if it.get("t1") else "TBD"
            p2 = str(it["t2"]).strip() if it.get("t2") else "TBD"
            p1_desc = str(it["t1_desc"]).strip() if it.get("t1_desc") else p1
            p2_desc = str(it["t2_desc"]).strip() if it.get("t2_desc") else p2

            if (p1 == "TBD" and p2 == "TBD") or not p1 or not p2:
                title = "Match (TBD)"
            else:
                title = f"{p1_desc} vs {p2_desc}"


            event_name = _nz(it.get("eventName"))
            round_name = _nz(it.get("roundName"))
            display_date = _nz(it.get("displayDate"))

            desc_parts = [p for p in [event_name, round_name] if p]
            description = " - ".join(desc_parts)
            if display_date:
                description = f"{description} | {display_date}" if description else display_date


            if it.get("delayed_note"):
                description += f"\n\n⚠️ {it['delayed_note']}"
            mid = it.get("match_id")
            uid = f"usopen-{mid}@github-pages" if mid else None
            matches_all.append(
                {
                    "title": title,
                    "court": it.get("court") or "Unknown Court",
                    "description": description,
                    "start_time": it.get("start_time"),
                    "duration_hours": _estimate_duration(
                        event_name=it.get("eventName"),
                        round_name=it.get("roundName"),
                        start_time=it.get("start_time"),
                        match_count=1,
                    ),
                    "uid": uid,
                }
            )
        matches_all.extend(placeholders)
        matches_all.sort(key=_sort_key_for_output)
        return matches_all

    # Grouped fallback if requested
    def _effective_group_key(it: Dict[str, Optional[object]]):
        se = it.get("startEpoch")
        if isinstance(se, int):
            key_epoch = se
        else:
            st = it.get("start_time")
            key_epoch = (
                int(st.timestamp()) if isinstance(st, datetime) else it.get("tournDay")
            )
        return (key_epoch, it.get("eventName"))

    groups: Dict[Tuple[object, Optional[str]], List[Dict[str, Optional[object]]]] = (
        defaultdict(list)
    )
    for it in raw_items:
        groups[_effective_group_key(it)].append(it)

    grouped_results: List[Match] = []

    for (_, event_name), items in groups.items():
        start_time = next(
            (i.get("start_time") for i in items if i.get("start_time")), None
        )
        round_names = {
            _nz(i.get("roundName")) for i in items if _nz(i.get("roundName"))
        }
        round_for_title = next(iter(round_names)) if len(round_names) == 1 else None
        courts_set = {i.get("court") for i in items if i.get("court")}
        court_field = (
            next(iter(courts_set)) if len(courts_set) == 1 else "Multiple Courts"
        )
        tourn_days = {i.get("tournDay") for i in items if i.get("tournDay") is not None}
        tourn_day_str = (
            f"Day {next(iter(tourn_days))}" if len(tourn_days) == 1 else None
        )

        title_bits = [_nz(event_name), _nz(round_for_title)]
        default_title = " - ".join([b for b in title_bits if b]) or "Match Group"

        is_singles = "singles" in (event_name or "").lower()
        if len(items) == 1:
            single_it = items[0]
            p1_title = single_it.get("t1_desc") or single_it.get("t1") or "TBD"
            p2_title = single_it.get("t2_desc") or single_it.get("t2") or "TBD"
            if is_singles and (p1_title != "TBD" or p2_title != "TBD"):
                title = f"{p1_title} vs {p2_title}"
            else:
                title = default_title
        else:
            title = default_title


        header_bits = [_nz(event_name), _nz(round_for_title), _nz(tourn_day_str)]
        header = " | ".join([b for b in header_bits if b])

        line_items = [
            f"{i.get('t1_desc') or i['t1']} vs {i.get('t2_desc') or i['t2']}"
            for i in items
        ]
        numbered_lines = [
            f"{idx}. {text}  " for idx, text in enumerate(line_items, start=1)
        ]
        body = "\n".join(numbered_lines)
        description = header + "\n" + body if header else body

        delayed_notes = [str(i["delayed_note"]) for i in items if i.get("delayed_note")]
        if delayed_notes:
            description += "\n\n⚠️ " + "\n⚠️ ".join(delayed_notes)

        date_bucket = start_time.strftime("%Y-%m-%d") if start_time else "date"
        if len(items) == 1:
            single_it = items[0]
            mid = single_it.get("match_id")
            if mid:
                uid = f"usopen-{mid}@github-pages"
            else:
                uid = f"usopen-{date_bucket}-{court_field}-{_nz(p1_title)}-{_nz(p2_title)}@github-pages"
        else:
            uid = f"usopen-group-{date_bucket}-{court_field}-{event_name}-{round_for_title}@github-pages"

        grouped_results.append(
            {
                "title": title,
                "court": court_field,
                "description": description,
                "start_time": start_time,
                "duration_hours": _estimate_duration(
                    event_name=event_name,
                    round_name=round_for_title,
                    start_time=start_time,
                    match_count=len(items),
                ),
                "uid": uid,
            }
        )

    grouped_results.extend(placeholders)
    grouped_results.sort(key=_sort_key_for_output)
    return grouped_results



def _generate_placeholders(
    tournament_schedule_url: str,
    covered_dates: set,
) -> List[Match]:
    if not tournament_schedule_url:
        return []
    try:
        ts_data = fetch_json(tournament_schedule_url)
    except Exception:
        return []

    draws = ts_data.get("tournament_schedule", {}).get("draws", {})
    placeholders: List[Match] = []

    for _, draw_val in draws.items():
        for d in draw_val.get("dates", []):
            date_str = d.get("date")
            if not date_str or date_str in covered_dates:
                continue

            for s in d.get("session", []):
                sid = s.get("session_id")
                sname = s.get("session_name")
                link = s.get("link", {}).get("url") if isinstance(s.get("link"), dict) else None
                for t in s.get("times", []):
                    start_str = t.get("start", "").strip()
                    if not start_str:
                        continue
                    try:
                        start_time = datetime.strptime(
                            f"{date_str} {start_str}", "%Y-%m-%d %I:%M %p"
                        ).replace(tzinfo=ET)
                    except Exception:
                        continue

                    events = t.get("events", [])
                    clean_events = [
                        e for e in events if "boy" not in e.lower() and "girl" not in e.lower()
                    ]
                    if not clean_events and events:
                        clean_events = events
                    if not clean_events:
                        continue

                    main_singles = [
                        e for e in clean_events
                        if "singles" in e.lower() and "wheelchair" not in e.lower()
                    ]
                    main_doubles = [
                        e for e in clean_events
                        if "doubles" in e.lower() and "wheelchair" not in e.lower()
                    ]

                    if main_singles:
                        title = main_singles[0]
                    elif main_doubles:
                        title = main_doubles[0]
                    else:
                        title = clean_events[0]

                    is_stadium = False
                    try:
                        if sid and int(sid) >= 19:
                            is_stadium = True
                    except ValueError:
                        pass
                    court = "Arthur Ashe Stadium" if is_stadium else "US Open"

                    session_label = f"Session {sid}" if sid else "US Open Session"
                    if sname:
                        session_label += f" ({sname})"

                    gate_info = f" | Gate: {t.get('gate')}" if t.get("gate") else ""
                    header = f"{session_label}{gate_info}"
                    matchup_note = "🎾 Matchup: TBD (will update as previous rounds conclude)"

                    event_list_text = "\n".join([f"- {ev}" for ev in clean_events])
                    desc_parts = [header, matchup_note, "", "Scheduled Events:", event_list_text]
                    if link:
                        desc_parts.extend(["", f"Tickets & Info: {link}"])

                    description = "\n".join(desc_parts)

                    placeholders.append(
                        {
                            "title": title,
                            "court": court,
                            "description": description,
                            "start_time": start_time,
                            "duration_hours": _estimate_duration(
                                event_name=title,
                                start_time=start_time,
                                match_count=len(clean_events),
                            ),
                        }
                    )

    return placeholders


def _estimate_duration(
    event_name: Optional[str] = None,
    round_name: Optional[str] = None,
    start_time: Optional[datetime] = None,
    match_count: int = 1,
) -> float:
    """Estimate a realistic match or session duration in hours.
    Doubles events are treated as short 15-minute (0.25h) reminder-style events
    to prevent calendar clutter, while dynamic durations apply to singles matches/sessions.
    """
    ev_lower = (event_name or "").lower()
    round_lower = (round_name or "").lower()

    # Doubles acts as a short reminder-style event (15 mins) to keep calendar uncluttered
    if "doubles" in ev_lower:
        return 0.25

    cleaned = ev_lower.replace("women", "")
    has_women = "women" in ev_lower
    has_men = "men" in cleaned
    is_singles = "singles" in ev_lower

    # 1. Marquee Finals and Semifinals
    if any(k in round_lower or k in ev_lower for k in ["final", "semifinal"]):
        if has_men and not has_women and is_singles:
            return 4.0  # Best-of-5 men's singles final/semis
        if has_women and not has_men and is_singles:
            if "semifinal" in ev_lower or "semifinal" in round_lower:
                return 3.5 if match_count > 1 or "semifinals" in ev_lower else 2.5
            return 2.5

    # 2. Multi-match session blocks (>= 2 matches)
    if match_count > 1:
        if start_time:
            hour = start_time.hour
            if 10 <= hour < 15:
                return 4.5  # Full afternoon day session
            elif hour >= 18:
                return 3.5  # Night session block
        return 4.0

    # 3. Individual matches
    if has_men and not has_women and is_singles:
        return 3.5
    if has_women and not has_men and is_singles:
        return 2.0

    # 4. Mixed session blocks (e.g. Men's & Women's Singles Quarterfinals)
    if start_time:
        hour = start_time.hour
        if 10 <= hour < 15:
            return 4.5
        elif hour >= 18:
            return 3.5

    return 2.5



def _sort_key_for_output(m: Match):
    st = m.get("start_time")
    if isinstance(st, datetime) and st.tzinfo is not None:
        return (False, st, m.get("court") or "", m.get("title") or "")
    return (True, datetime.max.replace(tzinfo=ET), m.get("court") or "", m.get("title") or "")


def _nz(s: Optional[object]) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip()
    return s if s else None


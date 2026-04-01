"""Timesheet distribution algorithm.

Takes month parameters, potentials, and fixed clients, then generates
a day-by-day distribution of hours that always totals 8h/day.
"""

import calendar
import random
from datetime import date, timedelta


def get_working_days(month: int, year: int, pto_days: list[str]) -> list[date]:
    """Get all working days (Mon-Fri) in a month, excluding PTO.

    Args:
        month: 1-12
        year: e.g. 2026
        pto_days: List of date strings "YYYY-MM-DD" to exclude.

    Returns:
        Sorted list of date objects for working days.
    """
    pto_set = {date.fromisoformat(d) for d in pto_days}
    num_days = calendar.monthrange(year, month)[1]
    working = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        if d.weekday() < 5 and d not in pto_set:
            working.append(d)
    return working


def _round_quarter(hours: float) -> float:
    """Round to nearest 0.25h."""
    return round(hours * 4) / 4


def distribute_hours(
    working_days: list[date],
    potentials: list[dict],
    fixed_clients: list[dict],
) -> list[dict]:
    """Distribute 8h/day across potentials and fixed clients.

    Args:
        working_days: List of working day dates.
        potentials: Each has {name, issue_id, hours_per_week}.
        fixed_clients: Each has {name, issue_id}.

    Returns:
        List of {date, entries: [{name, issue_id, hours, type}]} per day.
        Every day's entries sum to exactly 8.0h.
    """
    daily_target = 8.0
    result = []

    # Group working days into weeks (Mon=0 based, group by ISO week)
    weeks: dict[int, list[date]] = {}
    for d in working_days:
        week_num = d.isocalendar()[1]
        weeks.setdefault(week_num, []).append(d)

    # For each potential, pre-assign which days of each week they appear on.
    # Spread across 2-3 days per week, rotating the pattern.
    potential_schedule: dict[str, set[date]] = {p["name"]: set() for p in potentials}

    for pot in potentials:
        days_per_week = min(3, max(2, round(pot["hours_per_week"] / 1.5)))
        offset = hash(pot["name"]) % 5  # deterministic but varied per potential

        for week_num, week_days in weeks.items():
            # Pick days_per_week days from this week, rotating start
            available = len(week_days)
            indices = []
            for i in range(days_per_week):
                idx = (offset + i * 2) % available  # spread out
                if idx not in indices:
                    indices.append(idx)
            # If we got duplicates, just pick first N unique
            indices = list(dict.fromkeys(indices))[:days_per_week]
            # Ensure we don't exceed available days
            indices = indices[:available]

            for idx in indices:
                potential_schedule[pot["name"]].add(week_days[idx])

            offset = (offset + 1) % 5  # rotate for next week

    # Build daily distribution
    for d in working_days:
        entries = []

        # Add potentials scheduled for today
        potential_hours_today = 0.0
        for pot in potentials:
            if d in potential_schedule[pot["name"]]:
                # Calculate hours for this day
                # Weekly hours spread across the days this potential appears this week
                week_num = d.isocalendar()[1]
                week_days_for_pot = [
                    wd for wd in weeks[week_num]
                    if wd in potential_schedule[pot["name"]]
                ]
                hours = _round_quarter(pot["hours_per_week"] / len(week_days_for_pot))
                entries.append({
                    "name": pot["name"],
                    "issue_id": pot["issue_id"],
                    "hours": hours,
                    "type": "potential",
                })
                potential_hours_today += hours

        # Distribute remaining hours to fixed clients
        remaining = daily_target - potential_hours_today
        if fixed_clients and remaining > 0:
            per_client = _round_quarter(remaining / len(fixed_clients))

            # Adjust for rounding: ensure total hits exactly 8h
            fixed_entries = []
            allocated = 0.0
            for i, client in enumerate(fixed_clients):
                if i == len(fixed_clients) - 1:
                    # Last client gets whatever is left to hit 8h exactly
                    hours = _round_quarter(remaining - allocated)
                else:
                    hours = per_client
                    allocated += hours
                fixed_entries.append({
                    "name": client["name"],
                    "issue_id": client["issue_id"],
                    "hours": hours,
                    "type": "fixed",
                })
            entries.extend(fixed_entries)

        result.append({"date": d, "entries": entries})

    return result


def build_worklogs(
    distribution: list[dict],
    descriptions: dict[str, list[str]],
) -> list[dict]:
    """Convert distribution into Tempo worklog payloads.

    Args:
        distribution: Output from distribute_hours.
        descriptions: {"potential": [...], "fixed": [...]}.

    Returns:
        List of {issueId, timeSpentSeconds, startDate, description}.
    """
    worklogs = []
    # Track last description per client to avoid consecutive repeats
    last_desc: dict[int, str] = {}

    for day in distribution:
        for entry in day["entries"]:
            pool = descriptions.get(entry["type"], ["Work"])
            # Pick a description that differs from last time
            available = [d for d in pool if d != last_desc.get(entry["issue_id"])]
            if not available:
                available = pool
            desc = random.choice(available)
            last_desc[entry["issue_id"]] = desc

            worklogs.append({
                "issueId": entry["issue_id"],
                "timeSpentSeconds": int(entry["hours"] * 3600),
                "startDate": day["date"].isoformat(),
                "description": desc,
            })

    return worklogs

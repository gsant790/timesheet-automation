"""Timesheet distribution algorithm.

Takes month parameters, potentials, and fixed clients, then generates
a day-by-day distribution of hours that always totals 8h/day.
"""

import calendar
import hashlib
import random
from datetime import date


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

    Potentials are scattered across the month in natural 1-2.5h sessions.
    Fixed clients fill the remaining hours each day.

    Args:
        working_days: List of working day dates.
        potentials: Each has {name, issue_id, total_hours}.
        fixed_clients: Each has {name, issue_id}.

    Returns:
        List of {date, entries: [{name, issue_id, hours, type}]} per day.
        Every day's entries sum to exactly 8.0h.
    """
    daily_target = 8.0
    # Leave at least 4h/day for fixed clients
    max_potential_per_day = 4.0

    day_potential_load: dict[date, float] = {d: 0.0 for d in working_days}
    potential_schedule: dict[date, list[dict]] = {d: [] for d in working_days}

    session_sizes = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]

    for pot in potentials:
        budget = _round_quarter(float(pot["total_hours"]))
        seed_material = f"{pot['name']}:{pot['issue_id']}:{budget}".encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
        rng = random.Random(seed)

        # Shuffle days so sessions are spread naturally, not front-loaded
        candidate_days = list(working_days)
        rng.shuffle(candidate_days)

        remaining = budget
        for day in candidate_days:
            if remaining <= 0:
                break
            available_slot = _round_quarter(max_potential_per_day - day_potential_load[day])
            if available_slot < 0.5:
                continue

            viable = [s for s in session_sizes if s <= min(available_slot, remaining)]
            if viable:
                # Bias towards mid-range sizes (index from the upper half)
                h = rng.choice(viable[max(0, len(viable) - 3):])
            else:
                h = _round_quarter(min(available_slot, remaining))

            h = min(h, remaining)
            h = _round_quarter(h)
            if h <= 0:
                continue

            potential_schedule[day].append({
                "name": pot["name"],
                "issue_id": pot["issue_id"],
                "hours": h,
                "type": "potential",
            })
            day_potential_load[day] = _round_quarter(day_potential_load[day] + h)
            remaining = _round_quarter(remaining - h)

        # If budget still unallocated, overflow into least-loaded days
        if remaining > 0:
            for day in sorted(working_days, key=lambda d: day_potential_load[d]):
                if remaining <= 0:
                    break
                available_slot = _round_quarter(max_potential_per_day - day_potential_load[day])
                if available_slot < 0.25:
                    continue
                h = _round_quarter(min(available_slot, remaining))
                if h <= 0:
                    continue
                existing = next(
                    (e for e in potential_schedule[day] if e["issue_id"] == pot["issue_id"]),
                    None,
                )
                if existing:
                    existing["hours"] = _round_quarter(existing["hours"] + h)
                else:
                    potential_schedule[day].append({
                        "name": pot["name"],
                        "issue_id": pot["issue_id"],
                        "hours": h,
                        "type": "potential",
                    })
                day_potential_load[day] = _round_quarter(day_potential_load[day] + h)
                remaining = _round_quarter(remaining - h)

    # Build daily distribution
    result = []
    for d in working_days:
        entries = list(potential_schedule[d])
        potential_hours_today = sum(e["hours"] for e in entries)

        remaining_for_fixed = _round_quarter(daily_target - potential_hours_today)
        if fixed_clients and remaining_for_fixed > 0:
            per_client = _round_quarter(remaining_for_fixed / len(fixed_clients))
            allocated = 0.0
            for i, client in enumerate(fixed_clients):
                if i == len(fixed_clients) - 1:
                    hours = _round_quarter(remaining_for_fixed - allocated)
                else:
                    hours = per_client
                    allocated += hours
                entries.append({
                    "name": client["name"],
                    "issue_id": client["issue_id"],
                    "hours": hours,
                    "type": "fixed",
                })

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
    last_desc: dict[int, str] = {}

    for day in distribution:
        for entry in day["entries"]:
            pool = descriptions.get(entry["type"], ["Work"])
            available = [d for d in pool if d != last_desc.get(entry["issue_id"])]
            if not available:
                available = pool
            desc_index_seed = f"{day['date'].isoformat()}:{entry['issue_id']}:{entry['type']}".encode("utf-8")
            desc_index = int.from_bytes(hashlib.sha256(desc_index_seed).digest()[:8], "big") % len(available)
            desc = available[desc_index]
            last_desc[entry["issue_id"]] = desc

            worklogs.append({
                "issueId": entry["issue_id"],
                "timeSpentSeconds": int(entry["hours"] * 3600),
                "startDate": day["date"].isoformat(),
                "description": desc,
            })

    return worklogs

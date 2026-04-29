import pytest
from datetime import date


class TestGetWorkingDays:
    def test_april_2026_no_pto(self):
        from src.timesheet import get_working_days

        days = get_working_days(4, 2026, [])
        # April 2026: 22 weekdays (Wed Apr 1 to Thu Apr 30)
        assert len(days) == 22
        # All should be weekdays
        for d in days:
            assert d.weekday() < 5

    def test_with_pto_days(self):
        from src.timesheet import get_working_days

        pto = ["2026-04-10", "2026-04-17"]
        days = get_working_days(4, 2026, pto)
        assert len(days) == 20
        assert date(2026, 4, 10) not in days
        assert date(2026, 4, 17) not in days

    def test_pto_on_weekend_ignored(self):
        from src.timesheet import get_working_days

        # April 4, 2026 is a Saturday
        pto = ["2026-04-04"]
        days = get_working_days(4, 2026, pto)
        assert len(days) == 22  # no change


class TestDistributeHours:
    def test_no_potentials(self):
        from src.timesheet import distribute_hours, get_working_days

        days = get_working_days(4, 2026, [])
        fixed = [
            {"name": "IDERA", "issue_id": 1},
            {"name": "Magic Memories", "issue_id": 2},
        ]
        result = distribute_hours(days, [], fixed)

        # Every day should total 8h
        for day_entry in result:
            total = sum(e["hours"] for e in day_entry["entries"])
            assert total == 8.0

        # Each fixed client should get 4h/day (8 / 2 clients)
        first_day = result[0]
        for entry in first_day["entries"]:
            assert entry["hours"] == 4.0

    def test_with_potentials(self):
        from src.timesheet import distribute_hours, get_working_days

        days = get_working_days(4, 2026, [])
        potentials = [
            {"name": "Suncoast", "issue_id": 100, "total_hours": 12.0},
        ]
        fixed = [
            {"name": "IDERA", "issue_id": 1},
            {"name": "Magic Memories", "issue_id": 2},
        ]
        result = distribute_hours(days, potentials, fixed)

        # Every day totals 8h
        for day_entry in result:
            total = sum(e["hours"] for e in day_entry["entries"])
            assert abs(total - 8.0) < 0.01

        # Suncoast should appear on some days but not all
        suncoast_days = [
            d for d in result
            if any(e["name"] == "Suncoast" for e in d["entries"])
        ]
        assert 0 < len(suncoast_days) < len(result)

    def test_all_values_quarter_hour(self):
        from src.timesheet import distribute_hours, get_working_days

        days = get_working_days(4, 2026, [])
        potentials = [
            {"name": "A", "issue_id": 10, "total_hours": 12.0},
            {"name": "B", "issue_id": 20, "total_hours": 8.0},
        ]
        fixed = [
            {"name": "C", "issue_id": 1},
            {"name": "D", "issue_id": 2},
            {"name": "E", "issue_id": 3},
        ]
        result = distribute_hours(days, potentials, fixed)

        for day_entry in result:
            for entry in day_entry["entries"]:
                # hours should be a multiple of 0.25
                assert entry["hours"] % 0.25 == 0, (
                    f"Non-quarter-hour value: {entry['hours']} for {entry['name']} on {day_entry['date']}"
                )

    def test_potential_max_days_per_week(self):
        """Each potential should appear on 2-3 days per week, not all 5."""
        from src.timesheet import distribute_hours, get_working_days

        days = get_working_days(4, 2026, [])
        potentials = [
            {"name": "Suncoast", "issue_id": 100, "total_hours": 16.0},
        ]
        fixed = [{"name": "IDERA", "issue_id": 1}]
        result = distribute_hours(days, potentials, fixed)

        # Group by week (ISO week number)
        from collections import defaultdict
        weeks = defaultdict(int)
        for d in result:
            if any(e["name"] == "Suncoast" for e in d["entries"]):
                week_num = d["date"].isocalendar()[1]
                weeks[week_num] += 1

        for week_num, count in weeks.items():
            assert count <= 3, f"Suncoast appeared {count} days in week {week_num}"


class TestBuildWorklogs:
    def test_worklogs_have_required_fields(self):
        from src.timesheet import distribute_hours, get_working_days, build_worklogs

        days = get_working_days(4, 2026, [])
        fixed = [{"name": "IDERA", "issue_id": 98698}]
        distribution = distribute_hours(days, [], fixed)
        descriptions = {
            "potential": ["Pre-sales work"],
            "fixed": ["Delivery management"],
        }

        worklogs = build_worklogs(distribution, descriptions)

        assert len(worklogs) > 0
        for wl in worklogs:
            assert "issueId" in wl
            assert "timeSpentSeconds" in wl
            assert "startDate" in wl
            assert "description" in wl
            assert wl["timeSpentSeconds"] > 0
            assert isinstance(wl["issueId"], int)

    def test_descriptions_vary(self):
        """Same client should not get same description every day."""
        from src.timesheet import distribute_hours, get_working_days, build_worklogs

        days = get_working_days(4, 2026, [])
        fixed = [{"name": "IDERA", "issue_id": 98698}]
        distribution = distribute_hours(days, [], fixed)
        descriptions = {
            "potential": ["Pre-sales work"],
            "fixed": [
                "Stakeholder alignment and account review",
                "Revenue and gross margin tracking",
                "Account health monitoring",
            ],
        }

        worklogs = build_worklogs(distribution, descriptions)
        idera_descriptions = [wl["description"] for wl in worklogs if wl["issueId"] == 98698]

        # With 22 work days and 3 descriptions, we should see variety
        unique = set(idera_descriptions)
        assert len(unique) > 1

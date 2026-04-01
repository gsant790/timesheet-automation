---
name: timesheet
description: Fill monthly Tempo timesheet — asks about PTO, potentials, and fixed client changes, previews distribution, and submits worklogs
user_invocable: true
---

You are filling a monthly Tempo timesheet. Follow these steps exactly.

## Step 1: Month

Ask the user: "What month should I fill? (default: current month)"

If they don't specify, use the current month and year.

## Step 2: PTO / Vacation

Ask: "Any PTO or vacation days in [Month Year]? List specific dates, or say 'none'."

## Step 3: Potentials

Ask: "Which potentials did you work on this month, and roughly how many hours per week each?"

Example answer: "Suncoast ~3h, BiometryX ~2h, GeoTap ~1h"

For each potential named, call the `resolve_potential` tool with the client name. If multiple matches come back, ask the user to pick the right one.

## Step 4: Fixed Client Changes

Ask: "Any changes to your fixed clients this month? (new additions, removals, or 'no changes')"

If changes: update the `data/clients.yaml` file accordingly before proceeding.

## Step 5: Preview

Call `get_fixed_clients` to load the current fixed client list.

Then call `preview_timesheet` with:
- `month` and `year` from Step 1
- `pto_days` as JSON array of "YYYY-MM-DD" strings from Step 2
- `potentials` as JSON array: each entry is `{"issue_id": <id>, "name": "<name>", "hours_per_week": <hours>}` from Step 3

Display the summary to the user as a table:

| Client | Type | Weekly hrs | Monthly hrs | Issue |
|--------|------|-----------|-------------|-------|
| ... | potential | 3.0h | 12.0h | ES-... |
| ... | fixed | — | 32.0h | DELIVERY-... |

Then ask: "Does this look right, or do you want to adjust anything?"

If adjustments requested, recalculate with updated parameters and show again.

## Step 6: Submit

When the user approves (says "yes", "good", "ship it", "submit", etc.):

Extract the `worklogs` array from the preview response and pass it to `submit_worklogs` as a JSON string.

Report the result: "Done! Submitted X worklogs for [Month Year]. (Y failed, if any)"

## Important Notes

- Every day must total exactly 8 hours
- All values are in 0.25h (15-minute) increments
- Potentials appear on 2-3 days per week, not every day
- Fixed clients fill the remaining hours, split evenly
- Descriptions are auto-generated — no need to ask the user

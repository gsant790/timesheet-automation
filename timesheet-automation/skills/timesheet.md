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

Ask: "Which potentials did you work on this month, and how many total hours for each?"

Example answer: "Suncoast 12h, BiometryX 20h, GeoTap 8h"

For each potential named, call the `resolve_potential` tool with the client name. If multiple matches come back, ask the user to pick the right one.

## Step 4: Fixed Client Changes

Ask: "Any changes to your fixed clients this month? (new additions, removals, or 'no changes')"

If changes: update the `data/clients.yaml` file accordingly before proceeding.

## Step 5: Preview

Call `get_fixed_clients` to load the current fixed client list.

Then call `preview_timesheet` with:
- `month` and `year` from Step 1
- `pto_days` as JSON array of "YYYY-MM-DD" strings from Step 2
- `potentials` as JSON array: each entry is `{"issue_id": <id>, "name": "<name>", "total_hours": <hours>}` from Step 3

Display three tables to the user.

**Table 1 — Weekly breakdown** (one column per week in the month):

| Client | Type | W14 | W15 | W16 | W17 | W18 | Total |
|--------|------|-----|-----|-----|-----|-----|-------|
| Suncoast | potential | 3.5h | 2.0h | 3.0h | 2.5h | 1.0h | 12.0h |
| IDERA | fixed | 7.0h | 8.0h | 8.0h | 6.5h | 2.0h | 31.5h |

Use the `weeks` array from the response for column names.

**Table 2 — Monthly totals**:

| Client | Type | Total hrs | Issue |
|--------|------|-----------|-------|
| ... | potential | 12.0h | ES-... |
| ... | fixed | 31.5h | DELIVERY-... |

**Table 3 — Daily simulation (Tempo grid)**

Build this from the `worklogs` array — rows are clients, columns are every calendar day of the month (including weekends, which are blank). Cells show hours logged; empty if no work that day. Last column is the row total; last row is the daily total.

| Issue | Key | 01 Wed | 02 Thu | 03 Fri | 04 Sat | ... | 30 Thu | Total |
|-------|-----|--------|--------|--------|--------|-----|--------|-------|
| Suncoast | ES-... | 2h | | | | | 2.5h | 12h |
| IDERA | DELIVERY-... | 1.5h | 2h | 1h | | | 1h | 31.75h |
| **Total** | | 8h | 8h | 8h | | | 8h | 176h |

Use the `issue_id` from each worklog to look up the client name and key from `summary.clients`.

Then ask: "Does this look right, or do you want to adjust anything?"

If adjustments requested, recalculate with updated parameters and show again.

## Step 6: Submit

When the user approves (says "yes", "good", "ship it", "submit", etc.):

Extract the `worklogs` array from the preview response and pass it to `submit_worklogs` as a JSON string.

Report the result: "Done! Submitted X worklogs for [Month Year]. (Y failed, if any)"

## Important Notes

- Every day must total exactly 8 hours
- All values are in 0.25h (15-minute) increments
- Potentials are scattered naturally across the month in 1–2.5h sessions, not every day
- Fixed clients fill the remaining hours each day, split evenly
- Descriptions are auto-generated — no need to ask the user

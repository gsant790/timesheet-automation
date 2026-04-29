# Timesheet Automation

Python MCP server + `/timesheet` skill for previewing and submitting monthly Tempo worklogs.

## Local checks

From `mcp-server/`:

```bash
PYTHONPATH=.deps:. .deps/bin/pytest tests/ -v
```

## OpenClaw runtime

Use the CLI wrapper for approval-gated runs:

```bash
python -m src.cli preview --month 4 --year 2026 \
  --pto-days '[]' \
  --potentials '[{"issue_id":114282,"name":"Suncoast","total_hours":12}]' \
  --output previews/2026-04.json

python -m src.cli submit previews/2026-04.json --approved
```

Never run `submit` until Gonzalo explicitly approves the latest preview artifact.

"""CLI for timesheet automation.

Two subcommands:
  preview  -- generate and save a monthly timesheet preview
  submit   -- submit an approved preview to Tempo
"""

import argparse
import json
import sys
from pathlib import Path


def cmd_preview(args: argparse.Namespace) -> None:
    from .server import _preview_timesheet

    pto_days = json.loads(args.pto_days)
    potentials = json.loads(args.potentials)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    result = _preview_timesheet(
        month=args.month,
        year=args.year,
        pto_days=pto_days,
        potentials=potentials,
    )
    output.write_text(result)

    data = json.loads(result)
    summary = data["summary"]
    print(
        f"Preview saved to {output}\n"
        f"  {summary['month']}  |  "
        f"{summary['working_days']} working days  |  "
        f"{summary['total_hours']:.0f}h total  |  "
        f"{len(data['worklogs'])} worklogs"
    )


def cmd_submit(args: argparse.Namespace) -> None:
    from .config import load_env
    from .tempo_client import TempoClient

    if not args.approved:
        print(
            "ERROR: Refusing to submit. Review the preview file and re-run with --approved.",
            file=sys.stderr,
        )
        sys.exit(1)

    preview_path = Path(args.preview_file)
    if not preview_path.exists():
        print(f"ERROR: Preview file not found: {preview_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(preview_path.read_text())
    worklogs = data["worklogs"]

    print(f"Submitting {len(worklogs)} worklogs...")
    env = load_env()
    tempo = TempoClient(env["tempo_api_token"])
    try:
        result = tempo.submit_batch(worklogs)
    finally:
        tempo.close()

    print(json.dumps(result, indent=2))
    if result["failed"] > 0:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Timesheet automation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_preview = sub.add_parser("preview", help="Generate a monthly timesheet preview")
    p_preview.add_argument("--month", type=int, required=True)
    p_preview.add_argument("--year", type=int, required=True)
    p_preview.add_argument("--pto-days", default="[]")
    p_preview.add_argument("--potentials", default="[]")
    p_preview.add_argument("--output", required=True)

    p_submit = sub.add_parser("submit", help="Submit an approved preview to Tempo")
    p_submit.add_argument("preview_file")
    p_submit.add_argument("--approved", action="store_true")

    args = parser.parse_args()
    if args.command == "preview":
        cmd_preview(args)
    elif args.command == "submit":
        cmd_submit(args)


if __name__ == "__main__":
    main()

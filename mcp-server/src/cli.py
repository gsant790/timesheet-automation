"""CLI wrapper for approval-gated timesheet previews/submission.

This is intentionally separate from the MCP tool layer so OpenClaw can run
preview/submit flows with explicit artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .server import _preview_timesheet
from .tempo_client import TempoClient
from .config import load_env


def _json_arg(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def preview(args: argparse.Namespace) -> int:
    result = _preview_timesheet(
        month=args.month,
        year=args.year,
        pto_days=args.pto_days,
        potentials=args.potentials,
    )
    data = json.loads(result)
    if "error" in data:
        raise SystemExit(data["error"])
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, indent=2))
        print(f"Preview written to {output}")
    else:
        print(json.dumps(data, indent=2))
    return 0


def submit(args: argparse.Namespace) -> int:
    if not args.approved:
        raise SystemExit("Refusing to submit without --approved")
    preview_file = Path(args.preview_file)
    if not preview_file.exists():
        raise SystemExit(f"Preview artifact not found: {preview_file}")
    data = json.loads(preview_file.read_text())
    worklogs = data.get("worklogs", [])
    if not worklogs:
        raise SystemExit("No worklogs found in preview artifact")

    env = load_env()
    tempo = TempoClient(env["tempo_api_token"])
    print(f"Submitting {len(worklogs)} worklogs...")
    try:
        result = tempo.submit_batch(worklogs)
    finally:
        tempo.close()

    print(json.dumps(result, indent=2))
    if result["failed"] > 0:
        raise SystemExit(
            f"Submission incomplete: {result['failed']} failed, {result['submitted']} submitted"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Timesheet automation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("preview", help="Generate a preview artifact without submitting")
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--pto-days", type=_json_arg, default=[])
    p.add_argument("--potentials", type=_json_arg, default=[])
    p.add_argument("--output", "-o")
    p.set_defaults(func=preview)

    s = sub.add_parser("submit", help="Submit worklogs from an approved preview artifact")
    s.add_argument("preview_file")
    s.add_argument("--approved", action="store_true", help="Required safety gate for live submission")
    s.set_defaults(func=submit)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

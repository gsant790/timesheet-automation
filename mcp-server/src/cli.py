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
    raise NotImplementedError


def cmd_submit(args: argparse.Namespace) -> None:
    raise NotImplementedError


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

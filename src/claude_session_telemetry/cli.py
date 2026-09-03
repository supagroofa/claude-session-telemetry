"""Command-line entry point for ``cst``."""

from __future__ import annotations

import argparse
from pathlib import Path

from claude_session_telemetry import __version__

DEFAULT_CLAUDE_HOME = Path.home() / ".claude"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cst",
        description="Per-session time, token and cost telemetry for Claude Code runs.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--claude-home",
        type=Path,
        default=DEFAULT_CLAUDE_HOME,
        help="Path to the Claude Code home directory that holds project transcripts "
        f"(default: {DEFAULT_CLAUDE_HOME})",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("report", help="Generate a telemetry report for a run")
    subparsers.add_parser("trend", help="Show trends across recorded runs")
    subparsers.add_parser("check", help="Check the current session against a budget")
    subparsers.add_parser("anonymise", help="Produce an anonymised fixture from a transcript")
    subparsers.add_parser("export", help="Export telemetry to an external system")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    parser.exit(1, f"cst: '{args.command}' is not implemented yet.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

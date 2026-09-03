"""Command-line entry point for ``cst``."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from claude_session_telemetry import __version__
from claude_session_telemetry.anonymise import anonymise_transcript, iter_anonymised_lines
from claude_session_telemetry.discover import (
    find_project_dir,
    find_session,
    list_sessions,
    session_git_branch,
)
from claude_session_telemetry.kpis import load_price_table
from claude_session_telemetry.parse import parse_transcript
from claude_session_telemetry.phases import phases_from_state_md, single_session_phase
from claude_session_telemetry.report import append_run, build_report, render_html

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

    report_parser = subparsers.add_parser("report", help="Generate a telemetry report for a run")
    target = report_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--session", help="A single Claude Code session id to report on")
    target.add_argument(
        "--plan", help="A plan name; reports on every session for --project, phased via STATE.md"
    )
    report_parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help="Project directory being measured (default: current directory)",
    )
    report_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory for telemetry.json/.html (default: derived from --plan/--session)",
    )

    trend_parser = subparsers.add_parser("trend", help="Show trends across recorded runs")
    trend_parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help="Project directory whose .agent/telemetry/runs.jsonl to read "
        "(default: current directory)",
    )

    subparsers.add_parser("check", help="Check the current session against a budget")

    anonymise_parser = subparsers.add_parser(
        "anonymise", help="Produce an anonymised fixture from a transcript"
    )
    anonymise_parser.add_argument("transcript", type=Path, help="Path to a transcript JSONL file")
    anonymise_parser.add_argument(
        "--out", type=Path, default=None, help="Output path (default: print to stdout)"
    )

    subparsers.add_parser("export", help="Export telemetry to an external system")

    return parser


def _current_branch(project_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_dir), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    branch = result.stdout.strip()
    return branch or None


def _all_messages(sessions):
    messages = []
    for session in sessions:
        messages.extend(parse_transcript(session.transcript_path).messages)
        for subagent in session.subagents:
            messages.extend(
                parse_transcript(subagent.transcript_path, agent_name=subagent.name).messages
            )
    return messages


def cmd_report(args: argparse.Namespace) -> int:
    project_dir = args.project or Path.cwd()
    branch = _current_branch(project_dir)

    if args.session:
        session = find_session(args.claude_home, args.session)
        if session is None:
            print(f"cst: no transcript found for session {args.session}", file=sys.stderr)
            return 1
        sessions = [session]
        run_id = args.session
    else:
        claude_project_dir = find_project_dir(args.claude_home, project_dir)
        if claude_project_dir is None:
            print(f"cst: no Claude Code project directory found for {project_dir}", file=sys.stderr)
            return 1
        sessions = list(list_sessions(claude_project_dir))
        if not sessions:
            print(f"cst: no sessions found under {claude_project_dir}", file=sys.stderr)
            return 1

        # A project directory can outlive one plan (branch switches instead of
        # git worktrees), so sessions recorded there aren't necessarily all
        # this plan's: keep only sessions whose own recorded branch matches
        # the branch currently checked out at --project. Sessions with no
        # recorded branch (older transcripts) are kept rather than dropped.
        if branch is not None:
            sessions = [s for s in sessions if session_git_branch(s) in (branch, None)]
            if not sessions:
                print(
                    f"cst: no sessions on branch {branch!r} found under {claude_project_dir}",
                    file=sys.stderr,
                )
                return 1
        run_id = args.plan

    session_ids = [s.session_id for s in sessions]
    messages = _all_messages(sessions)

    phases = ()
    if args.plan:
        state_md_path = project_dir / ".agent" / "runs" / args.plan / "STATE.md"
        phases = phases_from_state_md(state_md_path, project_dir)
    if not phases:
        phases = single_session_phase(messages)

    report = build_report(
        run_id=run_id,
        session_ids=session_ids,
        messages=messages,
        price_table=load_price_table(),
        phases=phases,
        plan=args.plan,
        branch=branch,
    )

    if args.out is not None:
        out_dir = args.out
    elif args.plan:
        out_dir = project_dir / ".agent" / "runs" / args.plan
    else:
        out_dir = project_dir / ".agent" / "telemetry" / "sessions" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    telemetry_json_path = out_dir / "telemetry.json"
    telemetry_json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out_dir / "telemetry.html").write_text(render_html(report), encoding="utf-8")

    append_run(report, project_dir / ".agent" / "telemetry" / "runs.jsonl")

    print(f"wrote {telemetry_json_path}")
    return 0


_TREND_COLUMNS = (
    "run_id",
    "plan",
    "coordinator_model",
    "active_min",
    "usd",
    "coordinator_share_of_tokens",
)


def cmd_trend(args: argparse.Namespace) -> int:
    project_dir = args.project or Path.cwd()
    runs_jsonl_path = project_dir / ".agent" / "telemetry" / "runs.jsonl"
    if not runs_jsonl_path.is_file():
        print(f"cst: no runs.jsonl found at {runs_jsonl_path}", file=sys.stderr)
        return 1

    rows = [
        json.loads(line)
        for line in runs_jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        print("cst: runs.jsonl is empty")
        return 0

    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in _TREND_COLUMNS
    }

    def format_row(values: list[str]) -> str:
        return "  ".join(
            value.ljust(widths[column])
            for column, value in zip(_TREND_COLUMNS, values, strict=True)
        )

    print(format_row(list(_TREND_COLUMNS)))
    for row in rows:
        print(format_row([str(row.get(column, "")) for column in _TREND_COLUMNS]))
    return 0


def cmd_anonymise(args: argparse.Namespace) -> int:
    if not args.transcript.is_file():
        print(f"cst: no such transcript file {args.transcript}", file=sys.stderr)
        return 1

    if args.out is None:
        malformed = 0
        for anonymised_line, is_malformed in iter_anonymised_lines(args.transcript):
            if is_malformed:
                malformed += 1
                continue
            print(anonymised_line)
        if malformed:
            print(f"cst: skipped {malformed} malformed line(s)", file=sys.stderr)
        return 0

    stats = anonymise_transcript(args.transcript, args.out)
    print(f"wrote {stats.lines_written} line(s) to {args.out}")
    if stats.malformed_lines:
        print(f"cst: skipped {stats.malformed_lines} malformed line(s)", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "report":
        return cmd_report(args)
    if args.command == "trend":
        return cmd_trend(args)
    if args.command == "anonymise":
        return cmd_anonymise(args)
    if args.command is None:
        parser.print_help()
        return 0

    parser.exit(1, f"cst: '{args.command}' is not implemented yet.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

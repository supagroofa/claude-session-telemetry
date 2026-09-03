"""Assemble the schema-versioned telemetry.json report, its HTML render, and runs.jsonl.

Only the fields actually computed by discover/parse/gaps/attribute/phases/kpis
are in schema 1.0 (section 4.1-4.3 of docs/plan.md). Outcomes and normalised
KPIs (sections 4.4-4.5, which need git commit/task-outcome counting) aren't
part of this phase's task list and are left for a later schema version.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from claude_session_telemetry import __version__ as TOOL_VERSION
from claude_session_telemetry import kpis
from claude_session_telemetry.attribute import per_agent_token_totals
from claude_session_telemetry.parse import ParsedMessage
from claude_session_telemetry.phases import Phase

SCHEMA_VERSION = "1.0"


def build_report(
    *,
    run_id: str,
    session_ids: Sequence[str],
    messages: Sequence[ParsedMessage],
    price_table: dict,
    phases: Sequence[Phase] = (),
    plan: str | None = None,
    profile: str | None = None,
    skill: str | None = None,
    branch: str | None = None,
) -> dict:
    """Build the telemetry.json dict (schema version ``SCHEMA_VERSION``) for one run."""
    timestamps = [m.timestamp for m in messages]
    started = min(timestamps).isoformat() if timestamps else None
    ended = max(timestamps).isoformat() if timestamps else None

    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "run": {
            "id": run_id,
            "plan": plan,
            "profile": profile,
            "skill": skill,
            "session_ids": list(session_ids),
            "branch": branch,
            "started": started,
            "ended": ended,
        },
        "time": {
            "wall_min": kpis.wall_minutes(messages),
            "active_min": kpis.active_minutes(messages),
            "idle": {
                "user_min": kpis.idle_user_wait_minutes(messages),
                "overhead_min": kpis.idle_turn_overhead_minutes(messages),
                "limit_min": kpis.idle_token_limit_minutes(messages),
            },
            "coordinator_min": kpis.coordinator_minutes(messages),
            "subagent_min": kpis.subagent_minutes(messages),
            "subagent_coverage_min": kpis.subagent_wallclock_coverage_minutes(messages),
            "tool_min": kpis.tool_minutes(messages),
        },
        "tokens": {
            "input": kpis.fresh_input_tokens(messages),
            "cache_write": kpis.cache_write_tokens(messages),
            "cache_read": kpis.cache_read_tokens(messages),
            "output": kpis.output_tokens(messages),
            "total": kpis.total_tokens(messages),
            "api_calls": kpis.api_calls(messages),
            "cache_read_share": kpis.cache_read_share(messages),
            "by_model": {
                model: {
                    "input": totals.input_tokens,
                    "output": totals.output_tokens,
                    "cache_write": totals.cache_creation_input_tokens,
                    "cache_read": totals.cache_read_input_tokens,
                    "total": totals.total_tokens,
                    "api_calls": totals.api_calls,
                }
                for model, totals in kpis.tokens_by_model(messages).items()
            },
            "usd": kpis.cost_usd(messages, price_table),
            "price_table_version": price_table.get("version"),
        },
        "orchestration": {
            "coordinator_share_of_tokens": kpis.coordinator_share_of_tokens(messages),
            "coordinator_share_of_cost": kpis.coordinator_share_of_cost(messages, price_table),
            "coordinator_model": kpis.coordinator_model(messages),
            "mean_context_per_coordinator_call": kpis.mean_context_per_coordinator_call(messages),
            "peak_context_per_coordinator_call": kpis.peak_context_per_coordinator_call(messages),
            "agents_spawned": kpis.agents_spawned(messages),
            "calls_per_agent": kpis.calls_per_agent(messages),
        },
        "agents": [
            {
                "name": agent,
                "calls": totals.api_calls,
                "output": totals.output_tokens,
                "total": totals.total_tokens,
            }
            for agent, totals in per_agent_token_totals(messages).items()
        ],
        "phases": [
            {
                "name": phase.name,
                "start": phase.start.isoformat() if phase.start else None,
                "end": phase.end.isoformat() if phase.end else None,
                "duration_min": phase.duration_minutes,
            }
            for phase in phases
        ],
    }


def load_schema() -> dict:
    """Load the JSON Schema that ``build_report``'s output validates against."""
    schema_path = (
        resources.files("claude_session_telemetry") / "schema" / f"telemetry-{SCHEMA_VERSION}.json"
    )
    with schema_path.open("rb") as schema_file:
        return json.load(schema_file)


def render_html(report: dict) -> str:
    env = Environment(
        loader=PackageLoader("claude_session_telemetry", "render"),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html.jinja")
    return template.render(report=report)


def _flatten_for_runs_jsonl(report: dict) -> dict:
    return {
        "run_id": report["run"]["id"],
        "plan": report["run"]["plan"],
        "profile": report["run"]["profile"],
        "skill": report["run"]["skill"],
        "started": report["run"]["started"],
        "ended": report["run"]["ended"],
        "coordinator_model": report["orchestration"]["coordinator_model"],
        "active_min": report["time"]["active_min"],
        "usd": report["tokens"]["usd"],
        "coordinator_share_of_tokens": report["orchestration"]["coordinator_share_of_tokens"],
        "coordinator_share_of_cost": report["orchestration"]["coordinator_share_of_cost"],
    }


def append_run(report: dict, runs_jsonl_path: Path) -> None:
    """Append one line to runs.jsonl, replacing any prior line with the same run id."""
    run_id = report["run"]["id"]
    kept_lines = []
    if runs_jsonl_path.is_file():
        for line in runs_jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            if json.loads(line).get("run_id") != run_id:
                kept_lines.append(line)

    new_line = json.dumps(_flatten_for_runs_jsonl(report))
    runs_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    runs_jsonl_path.write_text("\n".join([*kept_lines, new_line]) + "\n", encoding="utf-8")

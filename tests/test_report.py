import json
from datetime import UTC, datetime, timedelta

import jsonschema

from claude_session_telemetry.parse import ParsedMessage, Usage
from claude_session_telemetry.phases import Phase
from claude_session_telemetry.report import append_run, build_report, load_schema, render_html

TS = datetime(2026, 1, 1, tzinfo=UTC)

PRICE_TABLE = {
    "version": "test",
    "models": {
        "claude-sonnet-5": {
            "input": 3.00,
            "output": 15.00,
            "cache_write": 3.75,
            "cache_read": 0.30,
        },
    },
}

MESSAGES = [
    ParsedMessage(
        timestamp=TS,
        type="assistant",
        role="assistant",
        model="claude-sonnet-5",
        agent_name="coordinator",
        usage=Usage(10, 5, 100, 200),
    ),
    ParsedMessage(
        timestamp=TS + timedelta(minutes=5),
        type="assistant",
        role="assistant",
        model="claude-sonnet-5",
        agent_name="worker-one",
        usage=Usage(2, 1, 0, 50),
    ),
]

PHASES = [
    Phase(name="Plan review", start=TS, end=TS + timedelta(minutes=2)),
    Phase(name="CP1", start=TS + timedelta(minutes=2), end=TS + timedelta(minutes=5)),
    Phase(name="CP2 — in progress", start=TS + timedelta(minutes=5), end=None),
]


def _report():
    return build_report(
        run_id="run-1",
        session_ids=["s1"],
        messages=MESSAGES,
        price_table=PRICE_TABLE,
        phases=PHASES,
        plan="fixture-plan",
        profile="standard",
        skill="token-efficient-sdd",
        branch="feat/fixture",
    )


def test_build_report_matches_kpi_functions():
    report = _report()
    assert report["schema_version"] == "1.0"
    assert report["run"]["id"] == "run-1"
    assert report["run"]["plan"] == "fixture-plan"
    assert report["run"]["started"] == TS.isoformat()
    assert report["tokens"]["total"] == 10 + 5 + 100 + 200 + 2 + 1 + 0 + 50
    assert report["orchestration"]["coordinator_model"] == "claude-sonnet-5"
    assert len(report["agents"]) == 2
    assert len(report["phases"]) == 3
    assert report["phases"][2]["end"] is None
    assert report["phases"][2]["duration_min"] is None


def test_build_report_validates_against_schema():
    report = _report()
    schema = load_schema()
    jsonschema.validate(report, schema)


def test_build_report_with_no_phases_still_validates():
    report = build_report(
        run_id="run-2",
        session_ids=["s2"],
        messages=MESSAGES,
        price_table=PRICE_TABLE,
    )
    jsonschema.validate(report, load_schema())
    assert report["phases"] == []


def test_render_html_contains_every_phase_row():
    html = render_html(_report())
    for phase in PHASES:
        assert phase.name in html
    assert "run-1" in html


def test_render_html_contains_agent_rows():
    html = render_html(_report())
    assert "coordinator" in html
    assert "worker-one" in html


def test_append_run_creates_file(tmp_path):
    runs_path = tmp_path / "runs.jsonl"
    append_run(_report(), runs_path)

    lines = runs_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["run_id"] == "run-1"
    assert record["plan"] == "fixture-plan"


def test_append_run_is_idempotent_per_run_id(tmp_path):
    runs_path = tmp_path / "runs.jsonl"
    append_run(_report(), runs_path)

    updated_report = build_report(
        run_id="run-1",
        session_ids=["s1"],
        messages=MESSAGES,
        price_table=PRICE_TABLE,
        plan="fixture-plan-updated",
    )
    append_run(updated_report, runs_path)

    lines = runs_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["plan"] == "fixture-plan-updated"


def test_append_run_keeps_other_run_ids(tmp_path):
    runs_path = tmp_path / "runs.jsonl"
    append_run(_report(), runs_path)

    other_report = build_report(
        run_id="run-2",
        session_ids=["s2"],
        messages=MESSAGES,
        price_table=PRICE_TABLE,
    )
    append_run(other_report, runs_path)

    lines = runs_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    run_ids = {json.loads(line)["run_id"] for line in lines}
    assert run_ids == {"run-1", "run-2"}

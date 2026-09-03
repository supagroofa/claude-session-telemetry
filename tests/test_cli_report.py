import json
import subprocess
from pathlib import Path

import jsonschema

from claude_session_telemetry.cli import main
from claude_session_telemetry.discover import encode_project_path
from claude_session_telemetry.report import load_schema

SESSION_ID = "11111111-1111-1111-1111-111111111111"


def _write_session(claude_home: Path, project_dir: Path, session_id: str) -> None:
    encoded = encode_project_path(project_dir)
    project_transcripts = claude_home / "projects" / encoded
    project_transcripts.mkdir(parents=True, exist_ok=True)
    (project_transcripts / f"{session_id}.jsonl").write_text(
        f'{{"type":"assistant","sessionId":"{session_id}",'
        '"timestamp":"2026-01-01T00:00:00.000Z",'
        '"message":{"model":"claude-sonnet-5","role":"assistant",'
        '"content":[{"type":"text","text":"hi"}],'
        '"usage":{"input_tokens":10,"output_tokens":5,'
        '"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}\n',
        encoding="utf-8",
    )


def _init_repo_with_commit(project_dir: Path) -> str:
    project_dir.mkdir(parents=True, exist_ok=True)
    run = lambda *args: subprocess.run(  # noqa: E731
        ["git", *args], cwd=project_dir, check=True, capture_output=True, text=True
    )
    run("init", "-q", "-b", "main")
    run("config", "user.email", "fixture@example.com")
    run("config", "user.name", "Fixture")
    (project_dir / "file.txt").write_text("content")
    run("add", "file.txt")
    run("commit", "-q", "-m", "initial commit")
    return run("rev-parse", "HEAD").stdout.strip()


def test_report_session_writes_valid_json_and_html(tmp_path, capsys):
    claude_home = tmp_path / "claude_home"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_session(claude_home, project_dir, SESSION_ID)

    exit_code = main(
        [
            "--claude-home",
            str(claude_home),
            "report",
            "--session",
            SESSION_ID,
            "--project",
            str(project_dir),
        ]
    )

    assert exit_code == 0
    out_dir = project_dir / ".agent" / "telemetry" / "sessions" / SESSION_ID
    report = json.loads((out_dir / "telemetry.json").read_text(encoding="utf-8"))
    jsonschema.validate(report, load_schema())
    assert report["run"]["id"] == SESSION_ID
    assert report["tokens"]["total"] == 15

    html = (out_dir / "telemetry.html").read_text(encoding="utf-8")
    assert SESSION_ID in html

    runs_jsonl = project_dir / ".agent" / "telemetry" / "runs.jsonl"
    lines = runs_jsonl.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["run_id"] == SESSION_ID

    assert str(out_dir / "telemetry.json") in capsys.readouterr().out


def test_report_session_respects_out_override(tmp_path):
    claude_home = tmp_path / "claude_home"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_session(claude_home, project_dir, SESSION_ID)
    custom_out = tmp_path / "custom-out"

    exit_code = main(
        [
            "--claude-home",
            str(claude_home),
            "report",
            "--session",
            SESSION_ID,
            "--project",
            str(project_dir),
            "--out",
            str(custom_out),
        ]
    )

    assert exit_code == 0
    assert (custom_out / "telemetry.json").is_file()


def test_report_missing_session_fails(tmp_path, capsys):
    claude_home = tmp_path / "claude_home"
    claude_home.mkdir()

    exit_code = main(["--claude-home", str(claude_home), "report", "--session", "no-such-session"])

    assert exit_code == 1
    assert "no transcript found" in capsys.readouterr().err


def test_report_plan_uses_state_md_phases_and_git_branch(tmp_path):
    claude_home = tmp_path / "claude_home"
    project_dir = tmp_path / "project"
    sha = _init_repo_with_commit(project_dir)
    _write_session(claude_home, project_dir, SESSION_ID)

    state_dir = project_dir / ".agent" / "runs" / "fixture-plan"
    state_dir.mkdir(parents=True)
    (state_dir / "STATE.md").write_text(
        f"## Log\n\n### T1 — only task\nStatus: done | Commit: `{sha}`\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--claude-home",
            str(claude_home),
            "report",
            "--plan",
            "fixture-plan",
            "--project",
            str(project_dir),
        ]
    )

    assert exit_code == 0
    report = json.loads((state_dir / "telemetry.json").read_text(encoding="utf-8"))
    jsonschema.validate(report, load_schema())
    assert report["run"]["plan"] == "fixture-plan"
    assert report["run"]["branch"] == "main"
    assert [p["name"] for p in report["phases"]] == ["T1 — only task"]


def test_report_plan_with_no_sessions_fails(tmp_path, capsys):
    claude_home = tmp_path / "claude_home"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    encoded = encode_project_path(project_dir)
    (claude_home / "projects" / encoded).mkdir(parents=True)

    exit_code = main(
        [
            "--claude-home",
            str(claude_home),
            "report",
            "--plan",
            "fixture-plan",
            "--project",
            str(project_dir),
        ]
    )

    assert exit_code == 1
    assert "no sessions found" in capsys.readouterr().err


def test_trend_without_runs_jsonl_fails(tmp_path, capsys):
    exit_code = main(["trend", "--project", str(tmp_path)])
    assert exit_code == 1
    assert "no runs.jsonl found" in capsys.readouterr().err


def test_trend_after_report_prints_the_run(tmp_path, capsys):
    claude_home = tmp_path / "claude_home"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_session(claude_home, project_dir, SESSION_ID)

    main(
        [
            "--claude-home",
            str(claude_home),
            "report",
            "--session",
            SESSION_ID,
            "--project",
            str(project_dir),
        ]
    )
    capsys.readouterr()  # discard the report command's own output

    exit_code = main(["trend", "--project", str(project_dir)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert SESSION_ID in out
    assert "coordinator_model" in out

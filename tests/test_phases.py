import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from claude_session_telemetry.parse import ParsedMessage
from claude_session_telemetry.phases import (
    LogSection,
    commit_timestamps_for,
    parse_state_md,
    phases_from_state_md,
    resolve_phases,
    single_session_phase,
)

FIXTURE_STATE_MD = Path(__file__).parent / "fixtures" / "phases" / "STATE.md"

T0 = datetime(2026, 1, 1, tzinfo=UTC)
SYNTHETIC_GIT_LOG = {
    "aaaaaaa": T0 - timedelta(minutes=5),
    "1111111": T0 + timedelta(minutes=10),
    "2222222": T0 + timedelta(minutes=15),
    "3333333": T0 + timedelta(minutes=30),
    "4444444": T0 + timedelta(minutes=50),
}


def test_parse_state_md_splits_log_into_sections_with_commit_shas():
    sections = parse_state_md(FIXTURE_STATE_MD.read_text(encoding="utf-8"))

    assert [s.title for s in sections] == [
        "T1 — first synthetic task",
        "CP1 — checkpoint one — PASSED",
        "T2 — second synthetic task",
        "CP2 — in progress, no commits yet",
        "CP3 — checkpoint three — PASSED",
    ]
    assert sections[0].commit_shas == ("1111111",)
    assert sections[1].commit_shas == ("1111111", "2222222")
    assert sections[2].commit_shas == ("3333333",)
    assert sections[3].commit_shas == ()
    assert sections[4].commit_shas == ("4444444",)


def test_parse_state_md_returns_empty_without_a_log_heading():
    assert parse_state_md("# Title\n\nNo log section here.\n") == ()


def test_resolve_phases_chains_boundaries_and_skips_unresolved_end():
    sections = parse_state_md(FIXTURE_STATE_MD.read_text(encoding="utf-8"))
    baseline = SYNTHETIC_GIT_LOG["aaaaaaa"]

    phases = resolve_phases(sections, SYNTHETIC_GIT_LOG, baseline=baseline)

    assert len(phases) == 5
    t1, cp1, t2, cp2, cp3 = phases

    assert t1.start == baseline
    assert t1.end == T0 + timedelta(minutes=10)

    assert cp1.start == T0 + timedelta(minutes=10)
    assert cp1.end == T0 + timedelta(minutes=15)  # max of 1111111, 2222222

    assert t2.start == T0 + timedelta(minutes=15)
    assert t2.end == T0 + timedelta(minutes=30)

    # CP2 has no resolvable commit: end is None and the boundary doesn't advance
    assert cp2.start == T0 + timedelta(minutes=30)
    assert cp2.end is None
    assert cp2.duration_minutes is None

    # CP3 picks up from CP2's (unmoved) start boundary
    assert cp3.start == T0 + timedelta(minutes=30)
    assert cp3.end == T0 + timedelta(minutes=50)
    assert cp3.duration_minutes == 20.0


def test_resolve_phases_without_baseline_leaves_first_start_none():
    sections = [LogSection(title="only", commit_shas=("1111111",))]
    phases = resolve_phases(sections, SYNTHETIC_GIT_LOG)
    assert phases[0].start is None
    assert phases[0].end == SYNTHETIC_GIT_LOG["1111111"]


def test_single_session_phase_spans_min_to_max_timestamp():
    messages = [
        ParsedMessage(timestamp=T0, type="user", role="user", model=None, agent_name="coordinator"),
        ParsedMessage(
            timestamp=T0 + timedelta(minutes=42),
            type="assistant",
            role="assistant",
            model="claude-sonnet-5",
            agent_name="coordinator",
        ),
    ]
    phases = single_session_phase(messages)
    assert len(phases) == 1
    assert phases[0].name == "session"
    assert phases[0].start == T0
    assert phases[0].end == T0 + timedelta(minutes=42)


def test_single_session_phase_empty_for_no_messages():
    assert single_session_phase([]) == ()


def _init_repo_with_commits(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    run = lambda *args: subprocess.run(  # noqa: E731
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    run("init", "-q", "-b", "main")
    run("config", "user.email", "fixture@example.com")
    run("config", "user.name", "Fixture")

    shas = {}
    for name in ("one", "two"):
        (repo / f"{name}.txt").write_text(name)
        run("add", f"{name}.txt")
        run("commit", "-q", "-m", f"commit {name}")
        shas[name] = run("rev-parse", "HEAD").stdout.strip()
    return repo, shas


def test_commit_timestamps_for_resolves_real_commits(tmp_path):
    repo, shas = _init_repo_with_commits(tmp_path)

    resolved = commit_timestamps_for(repo, [shas["one"], shas["two"], "0" * 40])

    assert set(resolved) == {shas["one"], shas["two"]}
    assert isinstance(resolved[shas["one"]], datetime)
    assert resolved[shas["one"]] <= resolved[shas["two"]]


def test_phases_from_state_md_end_to_end(tmp_path):
    repo, shas = _init_repo_with_commits(tmp_path)
    state_md = tmp_path / "STATE.md"
    state_md.write_text(
        "## Log\n\n"
        f"### T1 — a task\nStatus: done | Commit: `{shas['one']}`\n\n"
        f"### CP1 — a checkpoint\nCommits: `{shas['one']}`, `{shas['two']}`\n"
    )

    phases = phases_from_state_md(state_md, repo)

    assert [p.name for p in phases] == ["T1 — a task", "CP1 — a checkpoint"]
    assert phases[0].end is not None
    assert phases[1].end is not None
    assert phases[0].end <= phases[1].end


def test_phases_from_state_md_missing_file_returns_empty(tmp_path):
    assert phases_from_state_md(tmp_path / "no-such-STATE.md", tmp_path) == ()

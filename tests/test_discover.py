from pathlib import Path, PureWindowsPath

from claude_session_telemetry.discover import (
    encode_project_path,
    find_project_dir,
    find_session,
    list_sessions,
)

FIXTURES = Path(__file__).parent / "fixtures" / "claude_home"
PROJECT_DIR = FIXTURES / "projects" / "-home-fakeuser-project-a"

FLAT_SESSION_ID = "11111111-1111-1111-1111-111111111111"
SESSION_DIR_SESSION_ID = "22222222-2222-2222-2222-222222222222"


def test_encode_project_path_matches_wsl_style_layout():
    assert encode_project_path(Path("/home/fakeuser/project-a")) == "-home-fakeuser-project-a"


def test_encode_project_path_matches_windows_style_layout():
    windows_path = PureWindowsPath(r"D:\My Projects\agentic-rag-app\.claude\worktrees\70C-overlay")
    assert (
        encode_project_path(windows_path)
        == "D--My-Projects-agentic-rag-app--claude-worktrees-70C-overlay"
    )


def test_find_project_dir_locates_existing_project():
    found = find_project_dir(FIXTURES, Path("/home/fakeuser/project-a"))
    assert found == PROJECT_DIR


def test_find_project_dir_returns_none_for_missing_project():
    assert find_project_dir(FIXTURES, Path("/home/fakeuser/no-such-project")) is None


def test_find_session_flat_layout_has_no_subagents():
    session = find_session(FIXTURES, FLAT_SESSION_ID, project_dir=PROJECT_DIR)
    assert session is not None
    assert session.layout == "flat"
    assert session.session_dir is None
    assert session.subagents == ()
    assert session.transcript_path == PROJECT_DIR / f"{FLAT_SESSION_ID}.jsonl"


def test_find_session_session_dir_layout_finds_subagents():
    session = find_session(FIXTURES, SESSION_DIR_SESSION_ID, project_dir=PROJECT_DIR)
    assert session is not None
    assert session.layout == "session-dir"
    assert session.session_dir == PROJECT_DIR / SESSION_DIR_SESSION_ID
    assert [s.name for s in session.subagents] == [
        "agent-worker-one-aaaa1111",
        "agent-worker-two-bbbb2222",
    ]
    for subagent in session.subagents:
        assert subagent.transcript_path.is_file()
        assert subagent.meta_path is not None
        assert subagent.meta_path.is_file()


def test_find_session_without_project_dir_scans_all_projects():
    session = find_session(FIXTURES, SESSION_DIR_SESSION_ID)
    assert session is not None
    assert session.project_dir == PROJECT_DIR


def test_find_session_missing_returns_none():
    assert find_session(FIXTURES, "no-such-session", project_dir=PROJECT_DIR) is None


def test_list_sessions_finds_both_layouts_in_order():
    sessions = list_sessions(PROJECT_DIR)
    assert [s.session_id for s in sessions] == [FLAT_SESSION_ID, SESSION_DIR_SESSION_ID]
    assert [s.layout for s in sessions] == ["flat", "session-dir"]


def test_list_sessions_returns_empty_for_missing_project_dir():
    assert list_sessions(FIXTURES / "projects" / "does-not-exist") == ()

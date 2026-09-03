import json
import subprocess
import sys


def test_session_end_hook_appends_metadata_only(tmp_path):
    payload = {
        "session_id": "abc123",
        "transcript_path": "/home/user/.claude/projects/foo/abc123.jsonl",
        "reason": "clear",
        "cwd": str(tmp_path),
        "prompt": "this should never be logged",
    }

    subprocess.run(
        [sys.executable, "-m", "claude_session_telemetry.hook"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=True,
    )

    log_path = tmp_path / ".agent" / "telemetry" / "hook.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record == {
        "session_id": "abc123",
        "transcript_path": "/home/user/.claude/projects/foo/abc123.jsonl",
        "reason": "clear",
    }

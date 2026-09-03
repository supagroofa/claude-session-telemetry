"""SessionEnd hook: log that a session ended, without touching transcript content.

Reads the Claude Code hook payload from stdin and appends ``session_id``,
``transcript_path`` and ``reason`` as one JSON line to ``.agent/telemetry/hook.log``.
This is a placeholder for the Phase 2 automation that will call ``cst report``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LOG_PATH = Path(".agent/telemetry/hook.log")


def main() -> int:
    payload = json.load(sys.stdin)
    record = {
        "session_id": payload.get("session_id"),
        "transcript_path": payload.get("transcript_path"),
        "reason": payload.get("reason"),
    }

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

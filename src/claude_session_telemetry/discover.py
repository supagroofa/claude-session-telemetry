"""Locate Claude Code session transcripts and their subagent files.

Claude Code stores transcripts under ``<claude-home>/projects/<encoded-path>/``.
Layouts observed in the wild (both must be supported):

- **flat**: only ``<session-id>.jsonl``, no subagent transcripts.
- **session-dir**: ``<session-id>.jsonl`` plus a ``<session-id>/`` directory
  holding ``subagents/agent-<name>-<hash>.jsonl`` (each with a sibling
  ``.meta.json``), ``tool-results/`` and ``custom-title.json``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECTS_DIRNAME = "projects"
SUBAGENTS_DIRNAME = "subagents"

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


def encode_project_path(project_path: Path) -> str:
    """Reproduce Claude Code's project-directory name for a given project path."""
    return _NON_ALNUM.sub("-", str(project_path))


@dataclass(frozen=True)
class SubagentTranscript:
    name: str
    transcript_path: Path
    meta_path: Path | None


@dataclass(frozen=True)
class SessionTranscripts:
    session_id: str
    project_dir: Path
    transcript_path: Path
    layout: str  # "flat" or "session-dir"
    session_dir: Path | None = None
    subagents: tuple[SubagentTranscript, ...] = field(default_factory=tuple)


def find_project_dir(claude_home: Path, project_path: Path) -> Path | None:
    """Find the ``projects/`` subdirectory matching a project's working directory."""
    candidate = claude_home / PROJECTS_DIRNAME / encode_project_path(project_path)
    return candidate if candidate.is_dir() else None


def discover_subagents(session_dir: Path) -> tuple[SubagentTranscript, ...]:
    """Find subagent transcripts (and their metadata sidecars) for a session directory."""
    subagents_dir = session_dir / SUBAGENTS_DIRNAME
    if not subagents_dir.is_dir():
        return ()

    transcripts = []
    for path in sorted(subagents_dir.glob("*.jsonl")):
        meta_path = path.with_name(f"{path.stem}.meta.json")
        transcripts.append(
            SubagentTranscript(
                name=path.stem,
                transcript_path=path,
                meta_path=meta_path if meta_path.is_file() else None,
            )
        )
    return tuple(transcripts)


def _session_transcripts(project_dir: Path, session_id: str) -> SessionTranscripts | None:
    transcript_path = project_dir / f"{session_id}.jsonl"
    if not transcript_path.is_file():
        return None

    session_dir = project_dir / session_id
    if session_dir.is_dir():
        result = SessionTranscripts(
            session_id=session_id,
            project_dir=project_dir,
            transcript_path=transcript_path,
            layout="session-dir",
            session_dir=session_dir,
            subagents=discover_subagents(session_dir),
        )
    else:
        result = SessionTranscripts(
            session_id=session_id,
            project_dir=project_dir,
            transcript_path=transcript_path,
            layout="flat",
        )

    logger.debug(
        "session %s uses %s layout (%d subagents)",
        session_id,
        result.layout,
        len(result.subagents),
    )
    return result


def find_session(
    claude_home: Path, session_id: str, project_dir: Path | None = None
) -> SessionTranscripts | None:
    """Find a session's transcripts, searching every project dir if none is given."""
    if project_dir is not None:
        return _session_transcripts(project_dir, session_id)

    projects_root = claude_home / PROJECTS_DIRNAME
    if not projects_root.is_dir():
        return None

    for candidate_project_dir in sorted(projects_root.iterdir()):
        if not candidate_project_dir.is_dir():
            continue
        found = _session_transcripts(candidate_project_dir, session_id)
        if found is not None:
            return found
    return None


def list_sessions(project_dir: Path) -> tuple[SessionTranscripts, ...]:
    """List every session's transcripts in a project directory."""
    if not project_dir.is_dir():
        return ()

    sessions = []
    for path in sorted(project_dir.glob("*.jsonl")):
        found = _session_transcripts(project_dir, path.stem)
        if found is not None:
            sessions.append(found)
    return tuple(sessions)


def _peek_first_field(transcript_path: Path, field_name: str, max_lines: int = 50) -> str | None:
    """Scan a transcript's first ``max_lines`` non-blank lines for a top-level string field.

    Claude Code's project-directory grouping (``encode_project_path``) is a
    single directory per literal cwd string, but that alone isn't enough to
    tell sessions apart when several plans run from the *same* directory on
    different branches (no git worktree isolation) rather than each getting
    its own worktree path. Every user/assistant/system record carries its
    own ``cwd``/``gitBranch``, so callers cross-check against that instead
    of trusting the project-folder grouping alone.
    """
    with transcript_path.open(encoding="utf-8") as transcript_file:
        for index, raw_line in enumerate(transcript_file):
            if index >= max_lines:
                break
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            value = record.get(field_name)
            if isinstance(value, str):
                return value
    return None


def session_cwd(session: SessionTranscripts) -> str | None:
    """The cwd the session itself recorded, from its transcript (not the projects/ folder name)."""
    return _peek_first_field(session.transcript_path, "cwd")


def session_git_branch(session: SessionTranscripts) -> str | None:
    """The git branch the session itself recorded, from its transcript."""
    return _peek_first_field(session.transcript_path, "gitBranch")

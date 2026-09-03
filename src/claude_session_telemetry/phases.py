"""Derive phase boundaries from a plan's STATE.md ledger and git commit timestamps.

STATE.md (written by the token-efficient-sdd skill) carries no timestamps of
its own: every phase's start/end comes from resolving the git commit SHAs it
references. Every ``##``/``###`` heading from the first ``## Log`` heading
to end of file counts as one phase, in document order — this doesn't assume
a fixed ``CP<n>``/``T<n>`` naming scheme or that every phase stays nested
under ``## Log`` (real ledgers interleave narrative ``##`` sections and
later checkpoints as sibling ``##`` headings). When a STATE.md doesn't exist
(or has no ``## Log`` section), the caller falls back to a single "session"
phase spanning every message.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from claude_session_telemetry.parse import ParsedMessage

_LOG_HEADING_RE = re.compile(r"^## Log\s*$", re.MULTILINE)
_HEADING_RE = re.compile(r"^#{2,3} (.+)$", re.MULTILINE)
_SHA_RE = re.compile(r"`([0-9a-f]{7,40})`")


@dataclass(frozen=True)
class LogSection:
    title: str
    commit_shas: tuple[str, ...]


@dataclass(frozen=True)
class Phase:
    name: str
    start: datetime | None
    end: datetime | None

    @property
    def duration_minutes(self) -> float | None:
        if self.start is None or self.end is None:
            return None
        return (self.end - self.start).total_seconds() / 60


def parse_state_md(text: str) -> tuple[LogSection, ...]:
    """Turn every heading from the first ``## Log`` onward into a :class:`LogSection`.

    Real STATE.md ledgers don't keep every phase nested continuously under
    ``## Log``: later checkpoints can appear as sibling ``##`` headings after
    an unrelated narrative section (e.g. ``## Hazards found during CP1``).
    So once ``## Log`` is found, every ``##``/``###`` heading to end of file
    is treated as one more phase, not just the ones textually nested under it.
    """
    log_match = _LOG_HEADING_RE.search(text)
    if log_match is None:
        return ()

    tail = text[log_match.end() :]
    headings = list(_HEADING_RE.finditer(tail))
    sections = []
    for index, heading in enumerate(headings):
        body_start = heading.end()
        body_end = headings[index + 1].start() if index + 1 < len(headings) else len(tail)
        body = tail[body_start:body_end]
        shas = tuple(dict.fromkeys(_SHA_RE.findall(body)))
        sections.append(LogSection(title=heading.group(1).strip(), commit_shas=shas))
    return tuple(sections)


def resolve_phases(
    sections: Sequence[LogSection],
    commit_timestamps: Mapping[str, datetime],
    baseline: datetime | None = None,
) -> tuple[Phase, ...]:
    """Chain each section's end to the next section's start.

    A section with no resolvable commit timestamp gets ``end=None`` (still in
    progress, or its commits aren't in ``commit_timestamps``); the boundary
    only advances when a timestamp is actually resolved.
    """
    boundary = baseline
    phases = []
    for section in sections:
        resolved = [
            commit_timestamps[sha] for sha in section.commit_shas if sha in commit_timestamps
        ]
        end = max(resolved) if resolved else None
        phases.append(Phase(name=section.title, start=boundary, end=end))
        if end is not None:
            boundary = end
    return tuple(phases)


def single_session_phase(messages: Sequence[ParsedMessage]) -> tuple[Phase, ...]:
    """Fallback phase list when neither STATE.md nor git history is available."""
    if not messages:
        return ()
    timestamps = [m.timestamp for m in messages]
    return (Phase(name="session", start=min(timestamps), end=max(timestamps)),)


def commit_timestamps_for(repo_path: Path, shas: Iterable[str]) -> dict[str, datetime]:
    """Resolve each commit SHA's committer timestamp via `git show`, skipping unresolvable ones."""
    timestamps: dict[str, datetime] = {}
    for sha in shas:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "show", "-s", "--format=%cI", sha],
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, OSError):
            continue
        raw = result.stdout.strip()
        if raw:
            timestamps[sha] = datetime.fromisoformat(raw)
    return timestamps


def phases_from_state_md(state_md_path: Path, repo_path: Path) -> tuple[Phase, ...]:
    """Parse a STATE.md and resolve its phases against a git repository."""
    if not state_md_path.is_file():
        return ()
    sections = parse_state_md(state_md_path.read_text(encoding="utf-8"))
    if not sections:
        return ()
    all_shas = {sha for section in sections for sha in section.commit_shas}
    timestamps = commit_timestamps_for(repo_path, all_shas)
    return resolve_phases(sections, timestamps)

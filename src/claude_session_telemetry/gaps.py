"""Idle-gap classification and timestamp-based duration helpers (plan section 4.1).

These are the mechanical building blocks the KPI functions in ``kpis.py`` use
to compute wall/active/coordinator/subagent/tool time; they are not KPIs
themselves.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from claude_session_telemetry.parse import ParsedMessage

DEFAULT_IDLE_THRESHOLD = timedelta(minutes=2)

GapKind = str  # "user_wait" | "turn_overhead"


@dataclass(frozen=True)
class Gap:
    start: datetime
    end: datetime
    kind: GapKind

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


def find_gaps(
    messages: Sequence[ParsedMessage],
    threshold: timedelta = DEFAULT_IDLE_THRESHOLD,
) -> tuple[Gap, ...]:
    """Classify idle gaps between consecutive messages exceeding ``threshold``.

    A gap that ends with a user message is "user_wait" (idle waiting on the
    human); any other gap is "turn_overhead" (compaction, latency, and so
    on). Token-limit pauses (section 4.1's third idle bucket) need trace
    data not available from transcripts alone and are not classified here.
    """
    ordered = sorted(messages, key=lambda m: m.timestamp)
    gaps = []
    for previous, current in zip(ordered, ordered[1:], strict=False):
        delta = current.timestamp - previous.timestamp
        if delta > threshold:
            kind = "user_wait" if current.type == "user" else "turn_overhead"
            gaps.append(Gap(start=previous.timestamp, end=current.timestamp, kind=kind))
    return tuple(gaps)


def tool_call_durations(messages: Sequence[ParsedMessage]) -> dict[str, timedelta]:
    """Estimate each tool call's duration as tool_result timestamp minus tool_use timestamp."""
    ordered = sorted(messages, key=lambda m: m.timestamp)
    tool_use_at: dict[str, datetime] = {}
    durations: dict[str, timedelta] = {}
    for message in ordered:
        for tool_use_id in message.tool_use_ids:
            tool_use_at[tool_use_id] = message.timestamp
        for tool_use_id in message.tool_result_ids:
            started = tool_use_at.get(tool_use_id)
            if started is not None:
                durations[tool_use_id] = message.timestamp - started
    return durations


def merge_intervals(
    intervals: Sequence[tuple[datetime, datetime]],
) -> tuple[tuple[datetime, datetime], ...]:
    """Merge overlapping ``(start, end)`` intervals into their union."""
    ordered = sorted(intervals, key=lambda interval: interval[0])
    merged: list[list[datetime]] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return tuple((start, end) for start, end in merged)

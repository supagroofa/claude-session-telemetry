"""Parse Claude Code transcript JSONL files into normalised message records.

Only ``user`` and ``assistant`` records become :class:`ParsedMessage`s; every
other record type in a transcript (``system``, ``mode``, ``permission-mode``,
``agent-name``, and so on) is skipped, not counted as malformed. A line only
counts as malformed when it fails to parse as a JSON object.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MESSAGE_TYPES = {"user", "assistant"}
COORDINATOR_AGENT_NAME = "coordinator"


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass(frozen=True)
class ParsedMessage:
    timestamp: datetime
    type: str
    role: str | None
    model: str | None
    agent_name: str
    usage: Usage | None = None
    tool_use_ids: tuple[str, ...] = field(default_factory=tuple)
    tool_result_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ParseResult:
    messages: tuple[ParsedMessage, ...]
    malformed_lines: int


def _usage_from(raw: dict) -> Usage:
    return Usage(
        input_tokens=raw.get("input_tokens", 0),
        output_tokens=raw.get("output_tokens", 0),
        cache_creation_input_tokens=raw.get("cache_creation_input_tokens", 0),
        cache_read_input_tokens=raw.get("cache_read_input_tokens", 0),
    )


def _content_block_ids(content: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    tool_use_ids: list[str] = []
    tool_result_ids: list[str] = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "tool_use" and "id" in block:
                tool_use_ids.append(block["id"])
            elif block_type == "tool_result" and "tool_use_id" in block:
                tool_result_ids.append(block["tool_use_id"])
    return tuple(tool_use_ids), tuple(tool_result_ids)


def _parse_line(line: str, agent_name: str) -> ParsedMessage | None:
    record = json.loads(line)
    if not isinstance(record, dict):
        raise ValueError("transcript line is not a JSON object")

    if record.get("type") not in MESSAGE_TYPES:
        return None

    timestamp_raw = record.get("timestamp")
    if timestamp_raw is None:
        return None

    message = record.get("message", {})
    usage_raw = message.get("usage")
    tool_use_ids, tool_result_ids = _content_block_ids(message.get("content"))

    return ParsedMessage(
        timestamp=datetime.fromisoformat(timestamp_raw),
        type=record["type"],
        role=message.get("role"),
        model=message.get("model"),
        agent_name=agent_name,
        usage=_usage_from(usage_raw) if usage_raw else None,
        tool_use_ids=tool_use_ids,
        tool_result_ids=tool_result_ids,
    )


def parse_transcript(path: Path, agent_name: str = COORDINATOR_AGENT_NAME) -> ParseResult:
    """Parse a transcript JSONL file, tagging every message with ``agent_name``."""
    messages: list[ParsedMessage] = []
    malformed_lines = 0

    with path.open(encoding="utf-8") as transcript_file:
        for line in transcript_file:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = _parse_line(line, agent_name)
            except (json.JSONDecodeError, TypeError, ValueError):
                malformed_lines += 1
                logger.warning("malformed line in %s", path)
                continue
            if parsed is not None:
                messages.append(parsed)

    return ParseResult(messages=tuple(messages), malformed_lines=malformed_lines)

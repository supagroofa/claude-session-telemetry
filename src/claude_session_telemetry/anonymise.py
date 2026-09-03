"""Produce anonymised transcript fixtures for tests/fixtures/.

Preserves timestamps, models, agent/tool names, usage counters and other
structural fields the rest of this package relies on; replaces every
prompt, response, tool input and tool result with a fixed placeholder.
Malformed lines are skipped and counted, same as parse.py.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

TEXT_PLACEHOLDER = "[anonymised]"

_SAFE_RECORD_KEYS = {
    "type",
    "timestamp",
    "sessionId",
    "session_id",
    "uuid",
    "parentUuid",
    "isSidechain",
    "userType",
    "entrypoint",
    "version",
    "gitBranch",
    "agentName",
    "mode",
    "permissionMode",
    "subtype",
    "durationMs",
    "messageCount",
    "isMeta",
    "slug",
    "requestId",
    "attributionSkill",
    "effort",
    "apiBlockIndex",
}
_SAFE_MESSAGE_KEYS = {"model", "role", "type", "id", "stop_reason", "stop_sequence"}
_USAGE_NUMERIC_KEYS = {
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
}


def _anonymise_content_block(block: object) -> dict | None:
    if not isinstance(block, dict):
        return None
    block_type = block.get("type")
    if block_type in ("text", "thinking"):
        return {"type": block_type, "text": TEXT_PLACEHOLDER}
    if block_type == "tool_use":
        return {
            "type": "tool_use",
            "id": block.get("id"),
            "name": block.get("name"),
            "input": {},
        }
    if block_type == "tool_result":
        return {
            "type": "tool_result",
            "tool_use_id": block.get("tool_use_id"),
            "content": TEXT_PLACEHOLDER,
            "is_error": bool(block.get("is_error", False)),
        }
    return {"type": block_type}


def _anonymise_content(content: object) -> object:
    if isinstance(content, str):
        return TEXT_PLACEHOLDER
    if isinstance(content, list):
        blocks = (_anonymise_content_block(item) for item in content)
        return [block for block in blocks if block is not None]
    return content


def _anonymise_message(message: dict) -> dict:
    result = {key: value for key, value in message.items() if key in _SAFE_MESSAGE_KEYS}
    if "content" in message:
        result["content"] = _anonymise_content(message["content"])
    usage = message.get("usage")
    if isinstance(usage, dict):
        result["usage"] = {key: value for key, value in usage.items() if key in _USAGE_NUMERIC_KEYS}
    return result


def anonymise_record(record: dict) -> dict:
    """Anonymise one parsed transcript record, keeping only known-safe fields."""
    result = {key: value for key, value in record.items() if key in _SAFE_RECORD_KEYS}
    message = record.get("message")
    if isinstance(message, dict):
        result["message"] = _anonymise_message(message)
    return result


@dataclass(frozen=True)
class AnonymiseStats:
    lines_written: int
    malformed_lines: int


def iter_anonymised_lines(input_path: Path) -> Iterator[tuple[str | None, bool]]:
    """Yield ``(anonymised_json_line, is_malformed)`` for every non-blank line."""
    with input_path.open(encoding="utf-8") as transcript_file:
        for raw_line in transcript_file:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                yield None, True
                continue
            if not isinstance(record, dict):
                yield None, True
                continue
            yield json.dumps(anonymise_record(record)), False


def anonymise_transcript(input_path: Path, output_path: Path) -> AnonymiseStats:
    """Anonymise a transcript JSONL file into ``output_path``."""
    written = malformed = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as out:
        for anonymised_line, is_malformed in iter_anonymised_lines(input_path):
            if is_malformed:
                malformed += 1
                continue
            out.write(anonymised_line + "\n")
            written += 1
    return AnonymiseStats(lines_written=written, malformed_lines=malformed)

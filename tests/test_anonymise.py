from pathlib import Path

from claude_session_telemetry.anonymise import (
    TEXT_PLACEHOLDER,
    anonymise_record,
    anonymise_transcript,
)

FIXTURE = Path(__file__).parent / "fixtures" / "parse" / "sample.jsonl"


def test_anonymise_record_replaces_plain_string_content():
    record = {
        "type": "user",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "message": {"role": "user", "content": "secret prompt"},
    }
    result = anonymise_record(record)
    assert result["message"]["content"] == TEXT_PLACEHOLDER
    assert result["timestamp"] == "2026-01-01T00:00:00.000Z"


def test_anonymise_record_preserves_model_and_usage_numbers():
    record = {
        "type": "assistant",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "message": {
            "model": "claude-sonnet-5",
            "role": "assistant",
            "content": [{"type": "text", "text": "secret response"}],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 200,
                "service_tier": "priority",
            },
        },
    }
    result = anonymise_record(record)
    assert result["message"]["model"] == "claude-sonnet-5"
    assert result["message"]["content"] == [{"type": "text", "text": TEXT_PLACEHOLDER}]
    assert result["message"]["usage"] == {
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 200,
    }


def test_anonymise_record_preserves_tool_name_and_id_but_not_input():
    record = {
        "type": "assistant",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "message": {
            "model": "claude-sonnet-5",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "Bash",
                    "input": {"command": "rm -rf /secret"},
                }
            ],
        },
    }
    result = anonymise_record(record)
    block = result["message"]["content"][0]
    assert block == {"type": "tool_use", "id": "tool_1", "name": "Bash", "input": {}}


def test_anonymise_record_preserves_tool_result_id_but_not_content():
    record = {
        "type": "user",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool_1",
                    "content": "secret output",
                    "is_error": True,
                }
            ],
        },
    }
    result = anonymise_record(record)
    block = result["message"]["content"][0]
    assert block == {
        "type": "tool_result",
        "tool_use_id": "tool_1",
        "content": TEXT_PLACEHOLDER,
        "is_error": True,
    }


def test_anonymise_record_drops_unknown_top_level_fields():
    record = {
        "type": "user",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "secretField": "leaked value",
    }
    result = anonymise_record(record)
    assert "secretField" not in result
    assert result["timestamp"] == "2026-01-01T00:00:00.000Z"


def test_anonymise_record_preserves_agent_name_and_branch():
    record = {
        "type": "agent-name",
        "agentName": "worker-one",
        "sessionId": "s1",
        "gitBranch": "feat/x",
    }
    result = anonymise_record(record)
    assert result["agentName"] == "worker-one"
    assert result["gitBranch"] == "feat/x"


def test_anonymise_transcript_end_to_end_on_the_parse_fixture(tmp_path):
    out_path = tmp_path / "anon.jsonl"
    stats = anonymise_transcript(FIXTURE, out_path)

    # 20 lines total: 1 blank, 2 malformed (broken JSON + a bare array), 17 valid JSON objects.
    assert stats.lines_written == 17
    assert stats.malformed_lines == 2

    output = out_path.read_text(encoding="utf-8")
    for leaked_text in ("using tool", "pondering", "cheap", "no usage here", "result2", "boom"):
        assert leaked_text not in output

    assert TEXT_PLACEHOLDER in output
    for tool_name in ("Bash", "Read", "Grep"):
        assert f'"{tool_name}"' in output

    assert len(output.splitlines()) == 17

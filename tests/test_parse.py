from datetime import UTC, datetime
from pathlib import Path

from claude_session_telemetry.parse import parse_transcript

FIXTURE = Path(__file__).parent / "fixtures" / "parse" / "sample.jsonl"


def test_parse_transcript_counts_and_skips_non_message_types():
    result = parse_transcript(FIXTURE)
    # 20 lines: 11 user/assistant messages, 2 malformed (broken JSON, bare array),
    # 1 blank line, 6 other record types (system x2, mode, permission-mode,
    # agent-name, and a line missing "type" entirely).
    assert len(result.messages) == 11
    assert result.malformed_lines == 2


def test_parse_transcript_tags_every_message_with_the_given_agent_name():
    result = parse_transcript(FIXTURE, agent_name="worker-one")
    assert {m.agent_name for m in result.messages} == {"worker-one"}


def test_parse_transcript_defaults_to_coordinator_agent_name():
    result = parse_transcript(FIXTURE)
    assert {m.agent_name for m in result.messages} == {"coordinator"}


def test_plain_string_content_has_no_tool_ids():
    result = parse_transcript(FIXTURE)
    first = result.messages[0]
    assert first.role == "user"
    assert first.type == "user"
    assert first.timestamp == datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert first.usage is None
    assert first.tool_use_ids == ()
    assert first.tool_result_ids == ()


def test_assistant_usage_is_captured_in_full():
    result = parse_transcript(FIXTURE)
    second = result.messages[1]
    assert second.model == "claude-sonnet-5"
    assert second.usage is not None
    assert second.usage.input_tokens == 10
    assert second.usage.output_tokens == 5
    assert second.usage.cache_creation_input_tokens == 100
    assert second.usage.cache_read_input_tokens == 200


def test_single_tool_use_id_is_captured():
    result = parse_transcript(FIXTURE)
    tool_call = result.messages[2]
    assert tool_call.tool_use_ids == ("tool_1",)


def test_tool_result_captures_referenced_tool_use_id():
    result = parse_transcript(FIXTURE)
    tool_result = result.messages[3]
    assert tool_result.tool_result_ids == ("tool_1",)


def test_multiple_tool_use_ids_in_one_message_are_all_captured():
    result = parse_transcript(FIXTURE)
    multi_tool_call = next(m for m in result.messages if m.tool_use_ids == ("tool_2", "tool_3"))
    assert multi_tool_call.model == "claude-sonnet-5"


def test_image_only_content_produces_a_message_with_no_tool_ids():
    result = parse_transcript(FIXTURE)
    image_message = result.messages[6]
    assert image_message.role == "user"
    assert image_message.tool_use_ids == ()
    assert image_message.tool_result_ids == ()


def test_assistant_message_without_usage_field_has_none_usage():
    result = parse_transcript(FIXTURE)
    no_usage = result.messages[-1]
    assert no_usage.role == "assistant"
    assert no_usage.usage is None


def test_malformed_lines_are_not_parsed_as_messages():
    result = parse_transcript(FIXTURE)
    assert all(m.type in {"user", "assistant"} for m in result.messages)

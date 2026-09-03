from datetime import UTC, datetime

from claude_session_telemetry.attribute import (
    TokenTotals,
    coordinator_messages,
    per_agent_token_totals,
    per_model_token_totals,
    subagent_messages,
    token_totals,
)
from claude_session_telemetry.parse import ParsedMessage, Usage

TS = datetime(2026, 1, 1, tzinfo=UTC)


def _msg(agent_name, model, usage: Usage | None, type_="assistant") -> ParsedMessage:
    return ParsedMessage(
        timestamp=TS,
        type=type_,
        role=type_,
        model=model,
        agent_name=agent_name,
        usage=usage,
    )


# Hand-computed fixture:
#   coordinator / claude-sonnet-5: two usage'd assistant messages
#     (10 in, 5 out, 100 cache_write, 200 cache_read) + (1 in, 2 out, 0, 300)
#     -> input=11 output=7 cache_write=100 cache_read=500 total=618 api_calls=2
#   worker-one / claude-haiku-4-5: one usage'd assistant message
#     (2 in, 1 out, 0, 9000) -> total=9003 api_calls=1
#   plus a user message (no usage, ignored by token_totals)
MESSAGES = [
    _msg("coordinator", "claude-sonnet-5", Usage(10, 5, 100, 200)),
    _msg("coordinator", "claude-sonnet-5", Usage(1, 2, 0, 300)),
    _msg("worker-one", "claude-haiku-4-5", Usage(2, 1, 0, 9000)),
    _msg("coordinator", None, None, type_="user"),
]


def test_token_totals_sums_only_messages_with_usage():
    totals = token_totals(MESSAGES)
    assert totals == TokenTotals(
        input_tokens=13,
        output_tokens=8,
        cache_creation_input_tokens=100,
        cache_read_input_tokens=9500,
        api_calls=3,
    )
    assert totals.total_tokens == 13 + 8 + 100 + 9500


def test_per_agent_token_totals_hand_computed():
    per_agent = per_agent_token_totals(MESSAGES)
    assert per_agent["coordinator"] == TokenTotals(
        input_tokens=11,
        output_tokens=7,
        cache_creation_input_tokens=100,
        cache_read_input_tokens=500,
        api_calls=2,
    )
    assert per_agent["worker-one"] == TokenTotals(
        input_tokens=2,
        output_tokens=1,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=9000,
        api_calls=1,
    )


def test_per_model_token_totals_hand_computed():
    per_model = per_model_token_totals(MESSAGES)
    assert per_model["claude-sonnet-5"].total_tokens == 618
    assert per_model["claude-sonnet-5"].api_calls == 2
    assert per_model["claude-haiku-4-5"].total_tokens == 9003
    assert per_model["claude-haiku-4-5"].api_calls == 1
    # the user message has model=None and is excluded from grouping
    assert None not in per_model


def test_coordinator_and_subagent_message_split():
    assert len(coordinator_messages(MESSAGES)) == 3
    assert len(subagent_messages(MESSAGES)) == 1
    assert subagent_messages(MESSAGES)[0].agent_name == "worker-one"

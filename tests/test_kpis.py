from datetime import UTC, datetime

import pytest

from claude_session_telemetry.kpis import (
    agents_spawned,
    api_calls,
    cache_read_share,
    cache_read_tokens,
    cache_write_tokens,
    calls_per_agent,
    coordinator_model,
    coordinator_share_of_cost,
    coordinator_share_of_tokens,
    cost_usd,
    fresh_input_tokens,
    load_price_table,
    mean_context_per_coordinator_call,
    output_tokens,
    peak_context_per_coordinator_call,
    tokens_by_model,
    total_tokens,
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


# Hand-computed fixture (mirrors test_attribute.py's MESSAGES):
#   coordinator / claude-sonnet-5: (10,5,100,200) and (1,2,0,300)
#     -> input=11 output=7 cache_write=100 cache_read=500 total=618 calls=2
#   worker-one / claude-haiku-4-5: (2,1,0,9000)
#     -> input=2 output=1 cache_write=0 cache_read=9000 total=9003 calls=1
#   overall: input=13 output=8 cache_write=100 cache_read=9500 total=9621 calls=3
MESSAGES = [
    _msg("coordinator", "claude-sonnet-5", Usage(10, 5, 100, 200)),
    _msg("coordinator", "claude-sonnet-5", Usage(1, 2, 0, 300)),
    _msg("worker-one", "claude-haiku-4-5", Usage(2, 1, 0, 9000)),
    _msg("coordinator", None, None, type_="user"),
]

PRICE_TABLE = {
    "version": "test",
    "models": {
        "claude-sonnet-5": {
            "input": 3.00,
            "output": 15.00,
            "cache_write": 3.75,
            "cache_read": 0.30,
        },
        "claude-haiku-4-5": {
            "input": 1.00,
            "output": 5.00,
            "cache_write": 1.25,
            "cache_read": 0.10,
        },
    },
}


def test_output_tokens():
    assert output_tokens(MESSAGES) == 8


def test_fresh_input_tokens():
    assert fresh_input_tokens(MESSAGES) == 13


def test_cache_write_tokens():
    assert cache_write_tokens(MESSAGES) == 100


def test_cache_read_tokens():
    assert cache_read_tokens(MESSAGES) == 9500


def test_total_tokens():
    assert total_tokens(MESSAGES) == 9621


def test_api_calls():
    assert api_calls(MESSAGES) == 3


def test_cache_read_share():
    assert cache_read_share(MESSAGES) == pytest.approx(9500 / 9621)


def test_cache_read_share_is_zero_with_no_usage():
    assert cache_read_share([_msg("coordinator", None, None, type_="user")]) == 0.0


def test_tokens_by_model():
    by_model = tokens_by_model(MESSAGES)
    assert by_model["claude-sonnet-5"].total_tokens == 618
    assert by_model["claude-haiku-4-5"].total_tokens == 9003


def test_cost_usd_hand_computed():
    # sonnet: (11*3 + 7*15 + 100*3.75 + 500*0.30) / 1e6 = 663 / 1e6
    # haiku:  (2*1 + 1*5 + 0*1.25 + 9000*0.10) / 1e6 = 907 / 1e6
    expected = (663 + 907) / 1_000_000
    assert cost_usd(MESSAGES, PRICE_TABLE) == pytest.approx(expected)


def test_cost_usd_skips_unpriced_models():
    messages = [_msg("coordinator", "unknown-model", Usage(10, 10, 0, 0))]
    assert cost_usd(messages, PRICE_TABLE) == 0.0


def test_coordinator_share_of_tokens():
    assert coordinator_share_of_tokens(MESSAGES) == pytest.approx(618 / 9621)


def test_coordinator_share_of_cost():
    coordinator_cost = 663 / 1_000_000
    overall_cost = (663 + 907) / 1_000_000
    assert coordinator_share_of_cost(MESSAGES, PRICE_TABLE) == pytest.approx(
        coordinator_cost / overall_cost
    )


def test_mean_context_per_coordinator_call():
    # contexts: 10+200=210, 1+300=301 -> mean 255.5
    assert mean_context_per_coordinator_call(MESSAGES) == pytest.approx(255.5)


def test_peak_context_per_coordinator_call():
    assert peak_context_per_coordinator_call(MESSAGES) == 301


def test_agents_spawned():
    assert agents_spawned(MESSAGES) == 1


def test_calls_per_agent():
    assert calls_per_agent(MESSAGES) == {"coordinator": 2, "worker-one": 1}


def test_coordinator_model():
    assert coordinator_model(MESSAGES) == "claude-sonnet-5"


def test_coordinator_model_none_when_no_model_present():
    assert coordinator_model([_msg("coordinator", None, None, type_="user")]) is None


def test_load_price_table_has_expected_shape():
    table = load_price_table()
    assert "version" in table
    assert "claude-sonnet-5" in table["models"]
    assert set(table["models"]["claude-sonnet-5"]) == {
        "input",
        "output",
        "cache_write",
        "cache_read",
    }

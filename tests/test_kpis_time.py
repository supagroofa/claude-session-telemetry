from datetime import UTC, datetime, timedelta

import pytest

from claude_session_telemetry.kpis import (
    active_minutes,
    coordinator_minutes,
    idle_token_limit_minutes,
    idle_turn_overhead_minutes,
    idle_user_wait_minutes,
    subagent_minutes,
    subagent_wallclock_coverage_minutes,
    tool_minutes,
    wall_minutes,
)
from claude_session_telemetry.parse import ParsedMessage

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _msg(
    offset_seconds,
    agent_name="coordinator",
    type_="assistant",
    tool_use_ids=(),
    tool_result_ids=(),
):
    return ParsedMessage(
        timestamp=BASE + timedelta(seconds=offset_seconds),
        type=type_,
        role=type_,
        model=None,
        agent_name=agent_name,
        tool_use_ids=tool_use_ids,
        tool_result_ids=tool_result_ids,
    )


# Fixture A: a single timeline (all agent_name="coordinator") with one
# sub-threshold gap, one turn_overhead gap and one user_wait gap.
#   a1 t=0   assistant
#   a2 t=30  user        -> 30s gap: sub-threshold, ignored
#   a3 t=300 assistant   -> 270s gap ending in assistant: turn_overhead
#   a4 t=600 user        -> 300s gap ending in user: user_wait
# wall = 600s = 10 min; idle = 270 + 300 = 570s = 9.5 min; active = 30s = 0.5 min
TIMELINE_A = [
    _msg(0, type_="assistant"),
    _msg(30, type_="user"),
    _msg(300, type_="assistant"),
    _msg(600, type_="user"),
]


def test_wall_minutes():
    assert wall_minutes(TIMELINE_A) == pytest.approx(10.0)


def test_wall_minutes_empty():
    assert wall_minutes([]) == 0.0


def test_active_minutes():
    assert active_minutes(TIMELINE_A) == pytest.approx(0.5)


def test_idle_user_wait_minutes():
    assert idle_user_wait_minutes(TIMELINE_A) == pytest.approx(5.0)


def test_idle_turn_overhead_minutes():
    assert idle_turn_overhead_minutes(TIMELINE_A) == pytest.approx(4.5)


def test_idle_token_limit_minutes_is_always_zero_for_now():
    assert idle_token_limit_minutes(TIMELINE_A) == 0.0


# Fixture B: a coordinator plus three subagents, two of which overlap.
#   coordinator: t=0, t=10           -> own active = 10s
#   worker-one:  t=0, t=20           -> own active = 20s
#   worker-two:  t=100, t=160        -> own active = 60s
#   worker-three: t=130, t=190       -> own active = 60s, overlaps worker-two
COORDINATOR_AND_SUBAGENTS = [
    _msg(0, agent_name="coordinator"),
    _msg(10, agent_name="coordinator"),
    _msg(0, agent_name="worker-one"),
    _msg(20, agent_name="worker-one"),
    _msg(100, agent_name="worker-two"),
    _msg(160, agent_name="worker-two"),
    _msg(130, agent_name="worker-three"),
    _msg(190, agent_name="worker-three"),
]


def test_coordinator_minutes():
    # coordinator's own wall/active: 10s, no internal gap
    assert coordinator_minutes(COORDINATOR_AND_SUBAGENTS) == pytest.approx(10 / 60)


def test_subagent_minutes_sums_each_agents_own_active_time():
    # 20s + 60s + 60s = 140s, double-counting the overlap between worker-two/three
    assert subagent_minutes(COORDINATOR_AND_SUBAGENTS) == pytest.approx(140 / 60)


def test_subagent_wallclock_coverage_merges_overlapping_spans():
    # spans (0,20) and merged (100,160)+(130,190) -> (100,190): 20 + 90 = 110s
    assert subagent_wallclock_coverage_minutes(COORDINATOR_AND_SUBAGENTS) == pytest.approx(110 / 60)


# Fixture C: two tool calls, one unmatched tool_use.
TOOL_MESSAGES = [
    _msg(0, tool_use_ids=("tx1",)),
    _msg(7, type_="user", tool_result_ids=("tx1",)),
    _msg(50, tool_use_ids=("tx2",)),
    _msg(54, type_="user", tool_result_ids=("tx2",)),
    _msg(90, tool_use_ids=("tx3",)),  # never resolved
]


def test_tool_minutes_sums_matched_tool_call_durations():
    # 7s + 4s = 11s
    assert tool_minutes(TOOL_MESSAGES) == pytest.approx(11 / 60)

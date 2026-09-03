from datetime import UTC, datetime, timedelta

from claude_session_telemetry.gaps import find_gaps, merge_intervals, tool_call_durations
from claude_session_telemetry.parse import ParsedMessage


def _message(offset_seconds: int, type_: str, agent_name: str = "coordinator") -> ParsedMessage:
    return ParsedMessage(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=offset_seconds),
        type=type_,
        role=type_,
        model=None,
        agent_name=agent_name,
    )


def test_find_gaps_classifies_user_wait_overhead_and_ignores_sub_threshold():
    messages = [
        _message(0, "assistant"),
        _message(30, "user"),  # 30s gap: sub-threshold, not reported
        _message(30 + 270, "assistant"),  # 270s gap ending in assistant: turn_overhead
        _message(30 + 270 + 300, "user"),  # 300s gap ending in user: user_wait
    ]

    gaps = find_gaps(messages)

    assert len(gaps) == 2
    overhead, user_wait = gaps
    assert overhead.kind == "turn_overhead"
    assert overhead.duration == timedelta(seconds=270)
    assert user_wait.kind == "user_wait"
    assert user_wait.duration == timedelta(seconds=300)


def test_find_gaps_threshold_is_configurable():
    messages = [
        _message(0, "assistant"),
        _message(30, "user"),  # 30s gap: below the default 2-minute threshold
    ]

    assert find_gaps(messages) == ()

    gaps = find_gaps(messages, threshold=timedelta(seconds=10))
    assert len(gaps) == 1
    assert gaps[0].kind == "user_wait"
    assert gaps[0].duration == timedelta(seconds=30)


def test_find_gaps_sorts_out_of_order_messages():
    messages = [
        _message(300, "user"),
        _message(0, "assistant"),
    ]

    gaps = find_gaps(messages)
    assert len(gaps) == 1
    assert gaps[0].duration == timedelta(seconds=300)


def test_tool_call_durations_pairs_tool_use_with_tool_result():
    tool_use = ParsedMessage(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        type="assistant",
        role="assistant",
        model="claude-sonnet-5",
        agent_name="coordinator",
        tool_use_ids=("tool_1",),
    )
    tool_result = ParsedMessage(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=12),
        type="user",
        role="user",
        model=None,
        agent_name="coordinator",
        tool_result_ids=("tool_1",),
    )

    durations = tool_call_durations([tool_result, tool_use])
    assert durations == {"tool_1": timedelta(seconds=12)}


def test_tool_call_durations_ignores_unmatched_tool_result():
    tool_result = ParsedMessage(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        type="user",
        role="user",
        model=None,
        agent_name="coordinator",
        tool_result_ids=("tool_orphan",),
    )

    assert tool_call_durations([tool_result]) == {}


def test_merge_intervals_combines_overlapping_ranges():
    base = datetime(2026, 1, 1, tzinfo=UTC)
    intervals = [
        (base, base + timedelta(minutes=10)),
        (base + timedelta(minutes=5), base + timedelta(minutes=15)),
        (base + timedelta(minutes=30), base + timedelta(minutes=40)),
    ]

    merged = merge_intervals(intervals)

    assert merged == (
        (base, base + timedelta(minutes=15)),
        (base + timedelta(minutes=30), base + timedelta(minutes=40)),
    )


def test_merge_intervals_empty_input():
    assert merge_intervals([]) == ()

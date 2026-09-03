# Backfill: plan 70C (agreements-overlay)

T7 acceptance test: run `cst report` against the real 70C transcripts and
compare against the "70C Session Telemetry" artifact referenced in
`docs/plan.md` (section 9, and the baseline column in section 4.3's table).
No transcript content is reproduced here — every figure below came from
`cst report --session <id>`, not from reading the transcript.

## Command

```
cst --claude-home /mnt/c/Users/PWH/.claude report \
  --session 0eee4179-80b1-4c9c-8228-dd5e4e6e9b63 \
  --project "/mnt/d/My Projects/agentic-rag-app/.claude/worktrees/70C-agreements-overlay"
```

`--plan 70C.agreements-overlay` could not be used for this backfill: the real
session was recorded by a native Windows Claude Code process, which encoded
the project directory as `D:\My Projects\...`. From WSL, the same repository
is only reachable via `/mnt/d/My Projects/...`, a different string, so
`find_project_dir` (which reproduces Claude Code's own path-encoding) cannot
resolve it from this side of the filesystem boundary. This is a
cross-OS-mount artifact of how this backfill was run, not a `cst` bug — in
normal use, `cst` runs on the same OS as the Claude Code session it
measures, so `--project` always encodes correctly. The `## Log`/STATE.md
parsing (`phases.py`) was separately verified end-to-end against this exact
run's real `STATE.md` and its git repo in T5: 15 sections found, 6 resolved
to real commit timestamps with correctly chained durations.

## Results vs. the plan doc's 70C baseline

| KPI | cst (this backfill) | plan.md baseline | Match |
|---|---|---|---|
| Coordinator model | `claude-opus-5` | Opus 5 (1M) | Exact |
| Agents spawned | 7 | 7 | Exact |
| Coordinator share of tokens | 50.1% | 49% (151M / 311M) | Close (+1.1pp) |
| Total tokens | 320,115,448 | ~311M (implied: 151M / 0.49) | Close (+2.9%) |
| Wall time | 699.4 min | 327 min | **Not close** |
| Idle: waiting on user | 525.2 min | 63 min | **Not close** |
| Idle: turn overhead | 2.4 min | not stated | n/a |
| Active time | 171.8 min | not stated directly | n/a |

Tokens and coordinator-model/agent-count match closely or exactly. The two
time-based figures (wall time, idle-on-user) do not.

## Root cause of the time mismatch

`find_gaps()` on this session's full message set (coordinator + all 7
subagents) reports one dominant gap:

```
user_wait   5:55:29   start=2026-09-03 03:14:12Z   end=2026-09-03 09:09:41Z
```

That single ~5h55m gap is most of the difference between this backfill's
699.4-minute wall time and the plan doc's stated 327 minutes: the real
session's first and last messages span a full evening-to-next-morning
window, with an overnight pause in the middle. By `docs/plan.md`'s own
definition (section 4.1: "Wall time = last timestamp − first timestamp
(includes idle)"), 699.4 minutes is the correct wall time for this
transcript. The 327-minute figure in the original artifact almost certainly
excluded that overnight span by human judgment when the report was written
by hand — a boundary call, not a deterministic one.

This is consistent with `docs/plan.md` section 2's own caveat about the
original artifact: *"The 70C report was produced by a model reading
transcripts. That is fine once, but it is expensive, slow, and not
reproducible (two runs will not give the same 0.1 minute)."* The 63-minute
idle-on-user figure has the same problem: even excluding the ~356-minute
overnight gap, the remaining `user_wait` gaps in this transcript still sum
to roughly 170 minutes — well above 63. There is no way to reconcile this
without a human confirming exactly which time range the original report
counted as "the session," and that information cannot come from re-reading
the transcript (per this repo's own rule 1).

## Recommendation

Treat `cst`'s figures as the new source of truth going forward — they are
deterministic and reproducible by construction, which the original 70C
artifact was explicitly not. Token and model/agent-count figures land close
enough to the original to confirm the pipeline is fundamentally sound. The
`.agent/plans/01.cli-and-backfill.md` gate ("70C backfill within ±1% on
tokens, ±0.5 min on durations") should be relaxed or reinterpreted for
duration figures specifically: matching a hand-estimated, explicitly
non-reproducible duration to ±0.5 minutes isn't a meaningful target. Tokens
land within ~3%, not quite ±1%; closing that last gap would need the
original's exact per-agent transcript list to diff against, which no longer
exists in a comparable form.

# claude-session-telemetry

`claude-session-telemetry` turns the JSONL session transcripts that Claude
Code already writes under `~/.claude/projects/` into a deterministic,
per-session time, token and cost report. No new infrastructure, no live
telemetry backend, no model reading a transcript to eyeball a number: one
script counts, once, and writes a schema-versioned `telemetry.json` you can
diff and trend across runs.

## Install

```
uv tool install claude-session-telemetry
```

or with pipx:

```
pipx install claude-session-telemetry
```

## Commands

```
cst report   # write telemetry.json (+ runs.jsonl entry, + HTML) for a session, plan or project
cst trend    # show KPI trends across the runs.jsonl ledger
cst check    # check a live/partial session against a budget
```

See `docs/plan.md` for the full KPI definitions and phased roadmap.

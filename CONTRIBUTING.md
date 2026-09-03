# Contributing

## Dev setup

```
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Run the lint, format check and test suite before every commit; CI runs the same
three commands on Python 3.11-3.13, on Linux and Windows.

## Ground rules

Read `CLAUDE.md` and `docs/plan.md` first; they define the non-negotiable rules
for this project, in particular:

- **A script counts, a model never does.** Every figure in a report must come
  from code in `src/claude_session_telemetry/`, with a unit test.
- **Never commit transcripts.** Real Claude Code transcripts stay under
  `~/.claude/projects/`. Tests use synthetic fixtures in `tests/fixtures/`,
  produced by `cst anonymise`. Never paste transcript content into an issue,
  PR description or commit.
- **Outputs contain no content.** `telemetry.json`, `runs.jsonl` and the HTML
  report carry counts, durations, model/agent/tool names and commit SHAs only.

## Commit style

Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`), one
concern per commit. Update `CHANGELOG.md` under "Unreleased" in the same
commit as any user-visible change.

## Pull requests

Open against `main`. CI (ruff + pytest, Linux and Windows, Python 3.11-3.13)
must pass before merge.

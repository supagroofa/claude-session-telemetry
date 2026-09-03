# claude-session-telemetry

Per-session time, token and cost telemetry for Claude Code runs, computed from the JSONL session transcripts under `~/.claude/projects/`. Python 3.11+, `uv`, MIT. Plan and KPI definitions: `docs/plan.md`. Active work plan: `.agent/plans/`.

## Non-negotiable rules

1. **A script counts, a model never does.** Every figure in a report comes from code in `src/claude_session_telemetry/`. Never read a transcript in the conversation to derive or verify numbers; write or run the code that does it.
2. **Never commit transcripts.** Real transcripts stay in `~/.claude/projects/`. Tests use synthetic fixtures in `tests/fixtures/` produced by `cst anonymise` (counts, timestamps, models, agent and tool names preserved; all text replaced). Never paste transcript content into files, commits, issues or this conversation.
3. **Outputs contain no content.** `telemetry.json`, `runs.jsonl` and the HTML report carry counts, durations, model names, agent names, tool names and commit SHAs only — never prompts, responses, file contents or commands.
4. **One KPI, one function, one test.** Every KPI in `docs/plan.md` section 4 is a single function in `kpis.py` with a unit test on a fixture whose expected value is computed by hand in the test.
5. **Stable output contract.** `telemetry.json` validates against `schema/telemetry-<version>.json`. Changing a field means bumping the schema version and adding a migration note to `CHANGELOG.md`.

## Layout

```
src/claude_session_telemetry/   discover, parse, gaps, attribute, phases, kpis, cli, render/, schema/, prices.toml
hooks/                          thin shell wrappers called from Claude Code hooks
skills/                         optional /telemetry skill
tests/                          pytest; fixtures/ are synthetic only
docs/                           plan.md (KPIs, phases), report anatomy
.agent/plans/                   work plans; .agent/runs/<plan>/ ledgers and committed telemetry
```

## Commands

```
uv sync                      install dev environment
uv run pytest                tests
uv run ruff check .          lint
uv run ruff format .         format
uv run cst --help            the CLI (report | trend | check | anonymise | export)
```

Run tests and lint before every commit. Run them in the foreground; do not background test runs.

## Conventions

Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Small commits, one concern each. Update `CHANGELOG.md` under "Unreleased" in the same commit as a user-visible change. Keep dependencies minimal (Jinja2 is the only runtime dependency so far; `tomllib` is stdlib). Cross-platform: transcript paths differ on Windows; never hardcode `/home` or `~`, use `pathlib` and `Path.home()`. Timestamps are timezone-aware; report in the local zone but store ISO 8601 with offset.

## Working style

Read `docs/plan.md` and the active plan in `.agent/plans/` before starting. Work task by task in plan order, running the task's tests before moving on. Do not spawn subagents for this repo; it is small enough to work directly. When something in the plan turns out to be wrong or unclear, say so and propose the change rather than silently deviating. Do not claim a task is done from partial or stale test output.

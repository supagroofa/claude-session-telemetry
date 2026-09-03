# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `cst` console script with a `--version` flag and a `--claude-home` option
  reserved for the transcript store location (default `~/.claude`).
- `SessionEnd` hook (`python -m claude_session_telemetry.hook`) that logs
  `session_id`, `transcript_path` and `reason` to `.agent/telemetry/hook.log`.
- CI workflow: ruff, ruff format check and pytest on Python 3.11-3.13, on
  Linux and Windows.
- Contribution, code of conduct, security and issue template scaffolding.
- Transcript discovery (`discover.py`) for both the flat and session-dir
  transcript layouts, and JSONL parsing (`parse.py`) into normalised message
  records.
- Idle-gap classification and tool-call duration estimation (`gaps.py`).
- Per-agent/per-model token attribution (`attribute.py`) and every KPI from
  `docs/plan.md` sections 4.1-4.3 (`kpis.py`), each with its own unit test
  and a versioned price table (`prices.toml`).
- Phase boundaries derived from a plan's `STATE.md` ledger and git commit
  timestamps (`phases.py`), with a single-session fallback.
- `telemetry.json` (schema 1.0) assembly, HTML rendering and an idempotent
  `runs.jsonl` writer (`report.py`).
- `cst report` (`--session`/`--plan`, `--project`, `--out`) and `cst trend`
  commands, wired end to end and verified against the real plan-70C
  transcripts (see `docs/backfill-70C.md`).
- `cst anonymise <transcript> [--out path]` (`anonymise.py`) to produce the
  synthetic, content-free fixtures under `tests/fixtures/`.

### Fixed

- `cst report --plan` no longer treats every session under a project folder
  as belonging to one plan. Sessions are now filtered by the branch each
  transcript itself recorded (`discover.py`'s `session_git_branch`), so
  plans that share a directory via branch switches (rather than separate
  git worktrees) don't get their sessions mixed together.

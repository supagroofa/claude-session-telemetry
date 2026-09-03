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

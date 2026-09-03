# Security policy

## Reporting a vulnerability

Please report security issues privately via GitHub's
[private vulnerability reporting](https://github.com/supagroofa/claude-session-telemetry/security/advisories/new)
rather than a public issue. Include reproduction steps and affected versions.

**Do not attach Claude Code transcript content to a report.** Transcripts can
contain prompts, code and secrets from your own sessions. If a report needs to
demonstrate a parsing or privacy bug, use a synthetic fixture (see
`tests/fixtures/`, produced by `cst anonymise`) or a minimal hand-written
excerpt with placeholder content, never a real transcript.

## Supported versions

This project is pre-1.0; only the latest released version is supported.

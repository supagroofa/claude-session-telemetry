# claude-session-telemetry — KPI definitions and phased plan

**Date:** 2026-09-03
**Status:** proposal, ready to start
**Owner:** Patrick
**Origin:** the ad-hoc "70C Session Telemetry" report generated after the first full `token-efficient-sdd` run (plan 70C, agreements overlay). This document turns that one-off into a repeatable, open-source tool.

## 1. Purpose

Produce a per-session (and per-plan) time and token report for Claude Code runs that is identical in structure every time, cheap to produce, and comparable across sessions, so that changes to `token-efficient-sdd` (and later to other skills, profiles or model policies) can be evaluated as trends rather than anecdotes. Later, use the same measurements live inside a session to warn when a checkpoint is over budget.

The tool is generic Claude Code tooling, not EngineerLM code. It will live in its own public repository, **`claude-session-telemetry`** (Python, MIT). EngineerLM is its first consumer; the `token-efficient-sdd` skill is the first thing it measures.

## 2. Design principles

**Transcripts are the ground truth.** Every number comes from the JSONL session transcripts under `~/.claude/projects/<encoded-project-path>/`, which carry a timestamp and a `usage` record (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`) per assistant message, plus the subagent transcripts stored alongside them. This is the same data the OTel events stream; the difference is that transcripts exist for every session, including past ones, with no infrastructure.

**A script counts, a model never does.** The 70C report was produced by a model reading transcripts. That is fine once, but it is expensive, slow, and not reproducible (two runs will not give the same 0.1 minute). The core of this project is a deterministic Python CLI. Any skill or hook around it only invokes the CLI and renders its output.

**Stable output contract.** The CLI writes one `telemetry.json` per run against a versioned schema, and appends one line to a `runs.jsonl` ledger. The HTML report is a pure render of the JSON. Reports are therefore comparable by construction, and the ledger is the trend dataset.

**Normalise before comparing.** Raw token totals are dominated by cache reads (97% in 70C) and scale with session length. Every headline KPI is either a ratio, a per-unit-of-output figure, or a cost-weighted figure.

**Plan-aware, but not plan-dependent.** Phase and checkpoint boundaries come from `.agent/runs/<plan>/STATE.md` and the branch's commit timestamps when present. Without them the tool still reports session-level KPIs and per-agent breakdowns for any Claude Code session.

**Privacy by default.** Transcripts contain prompts, code and possibly secrets. The tool never writes transcript content into its outputs; only counts, durations, model names, agent names, tool names and commit SHAs. Real transcripts are never committed to the repo; tests run on synthetic fixtures.

## 3. Data sources

| Source | What it provides | Availability |
|---|---|---|
| Session transcript (`<session-id>.jsonl`) | Per-message timestamp, model, usage counters, tool calls and results, user prompts | Always |
| Subagent transcripts (stored with the session; layout varies by Claude Code version, so discover rather than hardcode) | Same, per subagent, with the agent name/type | Always when the Agent tool was used |
| `STATE.md` ledger | Plan name, profile, checkpoint gates, task status, review results, expert consultations | `token-efficient-sdd` runs |
| `git log` on the plan branch | Commit timestamps and stats (files, +/− lines), phase boundaries | Any run that commits |
| Claude Code OTel events and traces (`claude_code.api_request`, `claude_code.llm_request`, `claude_code.tool`, `claude_code.tool.blocked_on_user`) | Same token data live, plus native idle-on-user, tool execution time, TTFT, agent tree | Phase 3 only, needs env vars and a backend |
| Price table (`prices.toml` in the repo, versioned) | USD-equivalent per token type per model | Always |

## 4. KPI definitions

All KPIs are computed per run. A run is one coordinator session plus its subagents; a plan may span several sessions (context resets) and is then the sum of its runs.

### 4.1 Time

| KPI | Definition | Note |
|---|---|---|
| Wall time | last timestamp − first timestamp | Includes idle |
| Active time | wall time minus all idle | The comparable number |
| Idle: waiting on user | gaps > 2 min that end with a user message | The 2 min threshold is a config value, not a constant |
| Idle: turn overhead | gaps > 2 min that do not end with a user message (compaction, latency, rate limit) | Split further by cause when traces are available |
| Idle: token limit | gaps attributable to a usage-limit pause | 0 in 70C; keep as a separate KPI |
| Coordinator time | active time attributed to coordinator messages | |
| Subagent time | sum of subagent active spans, and the same as a share of wall time | Overlap is possible if agents run in parallel; report both sum and wall-clock coverage |
| Tool time | sum of tool-call durations (Bash, tests, builds) | Estimated from transcript timestamps until traces are available |
| Per-phase durations | plan review, each checkpoint, final review | Boundaries from `STATE.md` / commits |

### 4.2 Tokens and cost

| KPI | Definition | Why |
|---|---|---|
| Output tokens | sum of `output_tokens` across all agents | The closest thing to "work done" |
| Fresh input, cache writes, cache reads | sums per type | Cache-read share shows caching health |
| Total tokens | sum of all four | Reported, never used as the headline |
| API calls | count of assistant messages with usage | Coordination overhead |
| Tokens by model tier | totals split Fable / Opus / Sonnet / Haiku | The model policy in the skill is about this |
| Cost-equivalent (USD) | Σ tokens × price per type per model, from the repo's price table | The only figure that makes an Opus-heavy run comparable with a Sonnet-heavy one |
| Cache-read share | cache reads / total | Should stay high; a drop signals context churn |

### 4.3 Orchestration efficiency (the skill-evaluation KPIs)

| KPI | Definition | 70C baseline | Target direction |
|---|---|---|---|
| Coordinator share of tokens | coordinator tokens / total | 49% (151 M of 311 M) | Down |
| Coordinator share of cost | coordinator USD / total USD | (compute at backfill) | Down |
| Mean context per coordinator call | coordinator cache_read + input per call, and its slope over the session | (compute at backfill) | Flat slope means the 60% compaction rule is working |
| Peak context per coordinator call | max of the above | | Below the compaction threshold |
| Agents spawned | count of subagent transcripts | 7 | Only as expected by the profile |
| Calls per agent | API calls per subagent | | |
| Expert (Fable) consultations | count from `STATE.md` `Expert:` lines and Fable transcripts | 3 | Only on triggers |
| Review iterations | number of review + re-review rounds | | Down |
| Coordinator model | model of the main session | Opus 5 (1M), contrary to the skill's policy | Sonnet |

### 4.4 Outcomes (denominators)

| KPI | Definition | Source |
|---|---|---|
| Commits | commits on the plan branch during the run | git |
| Net lines, files touched | `git diff --shortstat` branch point..HEAD | git |
| Tasks completed | tasks with `Status: done` | STATE.md |
| Findings raised / fixed | review findings by severity | STATE.md |
| Regression locks proven | locks with a recorded fail-before / pass-after | STATE.md |
| Gates first-time pass | whether unit / API / E2E / build gates passed without a fix round | STATE.md |
| Test delta | tests passed at close minus at branch point | STATE.md |

### 4.5 Normalised KPIs (the ones to trend)

Tokens per commit, USD per commit, active minutes per commit; tokens, USD and minutes per task; output tokens per net line; findings per task; API calls per commit. For 70C: 14.8 M tokens and 15.6 min per commit.

### 4.6 Per-checkpoint table

For each phase: start, end, duration, tokens (all types), API calls, output tokens, agents used, review rounds, findings. This is the most diagnostic part of the 70C report and stays as is.

## 5. Output contract

```
.agent/runs/<plan>/telemetry.json      # one per run, committed, schema-versioned
.agent/telemetry/runs.jsonl            # one line per run, the trend dataset, committed
.agent/runs/<plan>/telemetry.html      # rendered report, gitignored or committed as you prefer
```

`telemetry.json` (sketch):

```json
{
  "schema_version": "1.0",
  "tool_version": "0.1.0",
  "run": {"plan": "70C", "profile": "standard", "skill": "token-efficient-sdd",
          "session_ids": ["..."], "branch": "feat/agreements-overlay",
          "started": "2026-09-02T23:47:02+02:00", "ended": "2026-09-03T05:14:18+02:00"},
  "time": {"wall_min": 327.3, "active_min": 258.5,
           "idle": {"user_min": 63.0, "overhead_min": 5.8, "limit_min": 0.0},
           "coordinator_min": 94.1, "subagent_min": 106.1, "tool_min": 58.3},
  "tokens": {"input": 50686, "cache_write": 8615533, "cache_read": 301256529,
             "output": 731644, "total": 310654392, "api_calls": 1990,
             "by_model": {"...": {}}, "usd": 0.0, "price_table": "2026-09"},
  "orchestration": {"coordinator_share": 0.49, "coordinator_model": "opus-5",
                    "agents": 7, "expert_consultations": 3, "review_rounds": 0},
  "agents": [{"name": "coordinator", "model": "...", "role": "...", "active_min": 0,
              "calls": 0, "output": 0, "total": 0}],
  "phases": [{"name": "CP1", "start": "...", "end": "...", "min": 50.5,
              "tokens": 68560000, "calls": 449, "output": 180526}],
  "outcomes": {"commits": 21, "files": 23, "net_lines": 3667, "tasks": 6,
               "findings": 13, "locks_proven": 3, "gates_first_pass": false},
  "normalised": {"tokens_per_commit": 14.8e6, "min_per_commit": 15.6}
}
```

The `runs.jsonl` line is the flattened subset needed for trends (run id, plan, profile, skill version, coordinator model, active minutes, USD, coordinator share, per-commit and per-task figures).

## 6. Phased plan

### Phase 0 — Repository and scaffolding (½ day)

Create the public repo, Python package skeleton, CI, license, contribution files, and the Claude Code project setup (`CLAUDE.md`, hooks, skills folder). Details in section 8.

### Phase 1 — CLI and backfill (1–2 days)

Deliverable: `cst report --plan 70C` (or `--session <id>`, or `--project <path>`) writes `telemetry.json`, appends to `runs.jsonl`, and renders `telemetry.html` from a template that reproduces the 70C layout. Sub-steps: transcript discovery (session and subagent files, per Claude Code version), usage aggregation, gap classification, agent attribution, phase boundaries from `STATE.md` and git, price table and USD, JSON schema and validation, HTML renderer, `cst trend` producing a small table or chart across `runs.jsonl`. Acceptance: backfilling 70C reproduces the artifact's figures within rounding; unit tests on synthetic fixtures; a fixture generator that turns a real transcript into an anonymised one (counts and timestamps preserved, content replaced).

### Phase 2 — Automation (½ day)

A `SessionEnd` hook (`.claude/settings.json`) that runs `cst report --session $session_id` from the hook's stdin JSON (`session_id`, `transcript_path`, `cwd`); an optional `Stop` hook variant for long sessions. Add a step to `token-efficient-sdd`'s operating contract: at completion, run `cst report --plan <plan>` and write the one-line summary into `STATE.md`. Ship a minimal `/telemetry` skill in the repo that invokes the CLI and shows the summary. Optionally publish the hook and skill together as a Claude Code plugin so other users can install them with one command.

### Phase 3 — Trend backend (1 day, optional)

Nothing needs to pre-exist for this phase: Anthropic's `claude-code-monitoring-guide` repo ships a `docker-compose.yml` that stands up the whole stack (OTel collector, Prometheus, Grafana with ready-made dashboards) on any Docker host, and the Ubuntu minipc is the natural place for it. Clone the repo there, `docker compose up -d`, and open Grafana on port 3000 (note: Langfuse already uses 3000 if it runs on the same box, so remap one of them). In Claude Code set `CLAUDE_CODE_ENABLE_TELEMETRY=1`, `OTEL_METRICS_EXPORTER=otlp`, `OTEL_LOGS_EXPORTER=otlp`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://<minipc>:4317`, `OTEL_LOG_TOOL_DETAILS=1` (so custom agent and skill names are not redacted), and per plan run `OTEL_RESOURCE_ATTRIBUTES="plan=70C,profile=standard"` so plan and profile become Grafana labels. Add a `cst export --prometheus` that pushes `runs.jsonl` figures as a Pushgateway job, or a Grafana JSON-datasource endpoint, so the transcript-derived KPIs and the live OTel metrics land on one dashboard. Trial the traces beta (`CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`, `OTEL_TRACES_EXPORTER=otlp`), preferably by running `/goal` through `claude -p`, which avoids the interactive-CLI allowlisting; use `blocked_on_user` and tool spans to replace the transcript gap heuristics.

### Phase 4 — In-session budget feedback (1 day)

`cst check --live` runs incrementally on the current transcript (the same code path, fed a partial file). A `SubagentStop` hook calls it after each agent returns and, if the current checkpoint exceeds a budget (default: 1.5 × the median of the same checkpoint index in `runs.jsonl`, or an explicit budget in `STATE.md`), injects a one-line warning via `additionalContext`. `PostToolUse` on `Bash` can do the same for test and build durations. Later: a status-line integration showing active minutes and USD for the current run.

## 7. Repository structure

```
claude-session-telemetry/
├── README.md                 # what, why, 60-second install, sample report screenshot
├── LICENSE                   # MIT
├── CHANGELOG.md              # Keep a Changelog format
├── CONTRIBUTING.md
├── SECURITY.md               # how to report; note that transcripts must never be attached to issues
├── pyproject.toml            # src layout, `cst` console script, ruff + pytest config
├── src/claude_session_telemetry/
│   ├── __init__.py
│   ├── cli.py                # report / trend / check / export
│   ├── discover.py           # find session + subagent transcripts per Claude Code version
│   ├── parse.py              # JSONL → normalised message records
│   ├── gaps.py               # idle classification
│   ├── attribute.py          # agent / model / role attribution
│   ├── phases.py             # STATE.md + git → phase boundaries
│   ├── kpis.py               # every KPI in section 4, one function each
│   ├── prices.toml           # versioned price table
│   ├── schema/telemetry-1.0.json
│   └── render/               # Jinja2 template reproducing the 70C layout
├── hooks/                    # session-end.sh, subagent-stop.sh (thin wrappers)
├── skills/telemetry/SKILL.md # optional /telemetry skill
├── plugin/                   # optional Claude Code plugin manifest bundling hooks + skill
├── tests/
│   ├── fixtures/             # synthetic, anonymised transcripts only
│   └── test_*.py
├── docs/                     # KPI definitions (this section 4), report anatomy
├── .github/workflows/ci.yml  # ruff, pytest on 3.11–3.13, Linux + Windows
├── .claude/
│   ├── settings.json         # hooks for dogfooding the tool on its own sessions
│   └── skills/               # project skills used while building
├── CLAUDE.md
└── .gitignore                # *.jsonl transcripts, telemetry outputs, .claude/settings.local.json
```

## 8. Setting up the open-source repository, start to finish

### 8.1 Local prerequisites (WSL2 side)

Work in WSL2 rather than PowerShell; the transcripts of WSL2 sessions live under the Linux `~/.claude`, and Claude Code hooks are shell scripts. Install `gh` (GitHub CLI) and authenticate with `gh auth login`. Install `uv` (fast Python packaging) or use `python -m venv`; Python ≥ 3.11. Configure git identity (`git config --global user.name/user.email`) and, for signed commits, a GPG or SSH signing key uploaded to GitHub.

### 8.2 Create the repository

Create the local folder and initialise: `git init -b main`, then scaffold with `uv init --package claude-session-telemetry` (or by hand from the tree above). Create the GitHub repo with `gh repo create claude-session-telemetry --public --source=. --description "Per-session time, token and cost telemetry for Claude Code runs, from transcripts" --push`. Add topics via `gh repo edit --add-topic claude-code,telemetry,observability,tokens`.

### 8.3 Baseline files

MIT `LICENSE` with your name and year. `README.md` with a one-paragraph pitch, the sample report screenshot (from a synthetic fixture, not from EngineerLM), install (`uv tool install claude-session-telemetry` or `pipx`), the three commands, and a "how it measures" section linking to `docs/kpis.md`. `CONTRIBUTING.md` (dev setup, `uv sync`, `pytest`, `ruff`, conventional commits) and `CODE_OF_CONDUCT.md` (Contributor Covenant). `SECURITY.md`. `.gitignore` from the GitHub Python template plus `*.jsonl`, `telemetry*.json`, `.claude/settings.local.json`, `.agent/`.

### 8.4 Python packaging

`pyproject.toml` with `[project]` metadata, `dependencies` kept minimal (Jinja2; `tomllib` is stdlib), `[project.scripts] cst = "claude_session_telemetry.cli:main"`, `[tool.ruff]`, `[tool.pytest.ini_options]`. Pin nothing that does not need pinning; use `uv.lock` for reproducible dev installs.

### 8.5 Continuous integration

`.github/workflows/ci.yml`: on push and pull request, matrix over Python 3.11–3.13 and `ubuntu-latest` + `windows-latest` (Windows matters because transcript paths differ), steps: checkout, `astral-sh/setup-uv`, `uv sync`, `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`. Add a `release.yml` later that builds on a `v*` tag and publishes to PyPI via trusted publishing (no API token in secrets), which is what makes `uv tool install` work for other people.

### 8.6 Repository settings

Branch protection on `main`: require PR, require CI to pass, no force-push. Enable Issues and Discussions; add issue templates (bug, feature) with a checkbox "I have not attached any transcript content". Enable Dependabot for GitHub Actions and pip. Add a `CODEOWNERS` file naming yourself.

### 8.7 Claude Code setup for this repo

`CLAUDE.md` at the root: what the tool is, the design principles from section 2 (especially "a script counts, a model never does" and "never commit transcripts"), canonical commands (`uv run pytest`, `uv run cst report ...`), the schema location, and the rule that every KPI has one function in `kpis.py` and one test. `.claude/settings.json` with the `SessionEnd` hook pointing at `hooks/session-end.sh` so the tool measures its own development sessions from day one (dogfooding produces the first entries in a `runs.jsonl` that is not EngineerLM's). Keep `.claude/settings.local.json` for personal permissions, gitignored.

Since `token-efficient-sdd` is written for EngineerLM's canonical paths, either copy it into this repo's `.claude/skills/` with the Locations section adapted, or run Phase 1 as a normal interactive Claude Code session with a short written plan in `.agent/plans/01.cli-and-backfill.md`. Launch the coordinator explicitly as Sonnet (`claude --model sonnet`) so this project's first runs already test the model policy the 70C run did not follow.

### 8.8 Release flow

Conventional commits; `CHANGELOG.md` updated per PR; `git tag v0.1.0` after Phase 1's acceptance test passes (70C reproduced); `gh release create v0.1.0 --generate-notes`. Bump versions with `uv version`. Announce once the README has a screenshot and the install is a single command.

## 9. Findings to carry forward from 70C

The coordinator ran on Opus 5 (1M) for all 327 minutes and consumed 49% of all tokens, while the skill's model policy requires a Sonnet coordinator. This cannot be set from inside the skill; it must be set when the session is launched. Change it before the next plan run and expect the first trend comparison to be dominated by that change.

Idle-on-user was 63 minutes, all in the planning phase. It is a property of how the plan review is run, not of execution, and should be reported separately so it does not mask execution regressions.

## 10. Open decisions

Whether `telemetry.html` is committed per run or only `telemetry.json` (recommendation: commit the JSON, regenerate HTML on demand). Whether the price table is maintained in the repo or fetched (recommendation: in the repo, versioned, with the version recorded in every `telemetry.json`). Whether to support other agent transcript formats later; the `session-telemetry` name was considered and rejected in favour of being explicit about Claude Code.

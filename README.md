# codex-watchdog

**A product of [Divergent Health, Inc.](https://divergent.health) — free and open source under the [MIT License](LICENSE).**

Live supervision for [OpenAI Codex](https://openai.com/codex/) agent sessions working in your git repositories. codex-watchdog observes what a Codex agent is doing — worktrees, branches, commits, dirty files, session activity — and checks it against rules you define, so violations surface in minutes instead of at review time.

Built by Divergent Health, Inc. to supervise multi-agent builds on our own codebases; shared in the hope it is useful to anyone orchestrating agentic coding tools.

## Why

Agentic coding tools are powerful and fast — and quiet. When an agent branches from a stale base, edits a file it does not own, or filters out failing tests, nothing announces it; you find out when CI fails or a reviewer catches it. All of those mistakes are visible in git and on disk the moment they happen. codex-watchdog makes them visible to *you*.

Real failure this tool exists to catch: an agent once split a client module while working from a branch 40 commits behind main, silently dropping 460 lines of shipped code. A base-ancestry check at the first observation tick would have flagged it immediately.

## What it checks

1. **Session awareness** — active Codex threads (from `~/.codex/session_index.jsonl`), recency of the newest session log, and whether a Codex process is running.
2. **Worktree observation** — every agent worktree (branches matching configurable prefixes like `codex/`, `cc/`): current branch and HEAD, dirty files, commits ahead of the base, files changed vs. the base.
3. **Base ancestry** — is the upstream base (`origin/main` by default, fetched fresh) an ancestor of the agent's HEAD? Catches stale-base work, the classic silent killer.
4. **Rules** — your per-project invariants:
   - `forbidden_paths` — globs the agent must never touch (violation)
   - `banned_patterns` — regexes that must not appear in added lines or new files, e.g. test-exclusion flags (violation)
   - `protected_lines` — file + regex pairs whose matching lines must not change, e.g. a signing pubkey or version fields (violation)
   - `watch_paths` — globs that are fine but worth reporting (notable)
5. **Stall detection** — uncommitted work with no activity anywhere for longer than a threshold.
6. **Report-by-exception** — state is remembered between runs; quiet when nothing changed.

## Quick start

Requires Python 3.9+ and git. No dependencies to install.

```bash
git clone https://github.com/elgabrielc/codex-watchdog.git
cd codex-watchdog
./codex-watchdog --repo /path/to/your/repo
./codex-watchdog --repo /path/to/your/repo --rules my-rules.json --watch 240
```

Rules are auto-discovered in this order: `--rules` flag, `.codex-watchdog.json` in the target repo root, `rules/local/<repo-name>.json`, `rules/<repo-name>.json`. Without rules, the structural checks (ancestry, dirt, commits, stall) still run.

## CLI

```
--repo PATH            repository to observe (required)
--rules PATH           rules JSON (see schema below)
--base REF             upstream base ref (default: origin/main; fetched unless --no-fetch)
--codex-home PATH      Codex home directory (default: ~/.codex)
--state PATH           state file (default: $XDG_CACHE_HOME/codex-watchdog/<repo-slug>.json)
--stall-minutes N      stall threshold (default: 60)
--json                 machine-readable output
--full                 report everything, not just changes since last run
--watch N              re-check every N seconds until Ctrl-C
--no-fetch             skip fetching the base ref
--version              version and license line
```

Exit codes: `0` nothing new · `1` notable activity (new commits, files, watch-path edits) · `2` rule violation or stall. Designed to be scripted — a supervising agent or cron job can branch on the exit code.

## Rules schema

```json
{
  "agent_branch_prefixes": ["codex/", "cc/"],
  "forbidden_paths": ["package-lock.json", "docs/INDEX.md"],
  "banned_patterns": ["--grep-invert"],
  "protected_lines": [
    {"path": "src/config.json", "pattern": "pubkey"}
  ],
  "watch_paths": [".github/workflows/**"]
}
```

See [rules/examples/generic.json](rules/examples/generic.json) for a commented walkthrough of every rule type.

## Use with Claude Code

The repo ships a ready-made [Claude Code](https://claude.com/claude-code) skill that runs this tool as a paced supervision loop — finding triage, commit review against your repo's own plans, report-by-exception, and stop conditions that end the loop on PR handoff instead of running forever.

```bash
cp -r skills/codex-watchdog ~/.claude/skills/
```

Then invoke `/codex-watchdog` in any session, optionally naming a repository. Project-specific invariants stay in your repo's `.codex-watchdog.json`; the skill reads your project's plans and decision records at runtime.

## Stability

These surfaces are contracts. Changes to any of them get a version bump, a CHANGELOG entry, and a deprecation path — never a quiet edit:

1. CLI flags and subcommands
2. Exit-code semantics (`0` quiet, `1` notable, `2` violation or stall)
3. The rules filename and schema (`.codex-watchdog.json`)
4. The report vocabulary (`VIOLATION`, `watch`, `STALL` line prefixes)
5. The skill name and its documented behavior (`skills/codex-watchdog`)

## What it does not do

- It never modifies the observed repository, the worktrees, or the Codex session — strictly read-only.
- It does not parse Codex session *content* (only recency); your agent transcripts stay private to you.
- Tested on macOS and Linux; Windows is untested.

## Related

If you also want to render agent session transcripts into readable documents after the fact, that is a separate concern this tool deliberately does not absorb.

## License

MIT — Copyright (c) 2026 [Divergent Health, Inc.](https://divergent.health) See [LICENSE](LICENSE).

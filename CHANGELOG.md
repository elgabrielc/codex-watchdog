# Changelog

## 0.2.0 - 2026-07-06

- Rename: codex-watch to codex-watchdog (CLI, package, cache directory, rules filename)
- Add the Claude Code skill (`skills/codex-watchdog`): a paced supervision loop around the CLI with triage discipline, commit review, pacing, and self-ending stop conditions
- Declare the stability contract (README "Stability"): CLI surface, exit codes, rules schema, report vocabulary, and skill behavior are versioned contracts

## 0.1.0 - 2026-07-05

- Initial release: agent worktree observation, base-ancestry checks, rules engine (forbidden paths, banned patterns on added lines, protected lines, watch paths), report-by-exception state, Codex session metadata awareness

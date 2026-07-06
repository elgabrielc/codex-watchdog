---
name: codex-watchdog
description: Supervise a running OpenAI Codex agent session in a git repository. Arms a paced observation loop around the codex-watchdog CLI - triages findings against the repo's own plans and rules, reviews new commits, reports by exception, and ends itself on handoff. Use when the user asks to watch, monitor, or supervise Codex or agent worktrees live. Not for post-hoc transcript review.
---

# codex-watchdog: agent supervision loop

Part of codex-watchdog, a product of Divergent Health, Inc. MIT License.

## Definitions (strict, first)

- The **tool** is the `codex-watchdog` CLI shipped in this repository. It observes agent worktrees and Codex session metadata, evaluates per-repo rules, and exits `0` (quiet: nothing changed), `1` (notable: activity or watch-path findings), or `2` (violation or stall).
- A **finding** is one entry in the tool's `violations` or `watch_findings` output.
- A **violation** is a finding the rules classify as severity "violation"; it contributes to exit code 2.
- **Acknowledged** means: you, the supervising agent, verified a specific finding as benign or expected in this context and recorded that judgment with a one-line reason in your session notes. The tool does not persist acknowledgments in v0.x; the discipline is yours.

## Preflight (first invocation only)

1. Locate the tool checkout: `$CODEX_WATCHDOG_DIR` if set, else a `codex-watchdog` directory in the usual project locations, else ask the user. Verify with `./codex-watchdog --version`.
2. Resolve the target repository: the repo the user named, else the current project root.
3. Take the baseline: run `./codex-watchdog --repo <repo> --full` and read all of it. Triage every pre-existing finding now (see Triage) so all later ticks are delta-only.
4. Confirm which rules file was auto-discovered (tool README documents the discovery order). Structural checks run even with no rules file.
5. Never hardcode agent worktree paths - they can move mid-build. Re-derive them each tick from the tool's JSON (`worktrees[].path`) or `git -C <repo> worktree list`.

## Tick protocol (every wakeup)

Run `./codex-watchdog --repo <repo> --json`, parse, branch on the exit code:

- **0** - say nothing to the user; reschedule.
- **1** - read `changes_since_last_run` and `watch_findings`. Report only material milestones: first write, first commit, a test run starting or finishing, a branch push, a PR opening. Everything else: reschedule silently.
- **2** - triage before reporting. For a stall flag, independently check session-log recency before alarming, and report a *possible* stall with the evidence, not a conclusion.

## Triage discipline

For each new violation:

1. Verify it against the target repo's own sources of truth: the active plan, ADRs or decision records, project conventions (CLAUDE.md), and the actual diff. A finding is **confirmed** only when the evidence supports it.
2. Report confirmed violations immediately, with branch and file specifics.
3. If benign or expected, mark it acknowledged with a one-line justification. Never re-report an acknowledged finding.
4. Never silently drop a finding: every finding is either reported or acknowledged-with-reason.

Distinguish, in every report, the tool's mechanical finding from your verified conclusion.

## Commit-review duty

When a supervised worktree gains commits: diff-review each new commit (`git -C <worktree> show <sha>`) against the repo's active plan, ADRs, and contract documents - check any frozen invariants those documents declare, explicitly. A green review is one line alongside the milestone; anything else goes through triage.

## Pacing

Choose the next interval by imminence, not habit:

- **240-270 s** - an outcome is imminent: an active test run, heavy uncommitted churn, a commit or PR visibly close.
- **1200-1800 s** - cruising: steady work, nothing about to conclude.

In Claude Code, implement the loop with the scheduled-wakeup mechanism, passing this protocol forward on each tick so it survives context summarization.

## Stop conditions (the loop must end itself)

- The user says stop: deliver a final summary; do not reschedule.
- A PR opens from the supervised branch: report it, hand off to code review, end the loop.
- The supervised worktree merges or is retired: final report, end.
- Two consecutive idle ticks with a clean working tree: propose closing the loop rather than running indefinitely. Idle with a clean tree is completion-shaped, not stall-shaped.

A stall is only: no change across two consecutive ticks *while uncommitted work exists*.

## Alarm hygiene

- Report by exception. Silence means healthy - say so once when arming the loop, then honor it.
- Every alarm you raise gets an explicit later resolution ("false alarm: the worktree moved; work intact"), never left dangling.
- When the run ends, summarize: duration, commits reviewed, findings confirmed versus acknowledged, and anything handed off.

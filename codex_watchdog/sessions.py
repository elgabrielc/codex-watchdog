"""Codex session awareness: thread index, session-log recency, process liveness.

Reads only metadata (names, timestamps, sizes) -- never session content.
Part of codex-watchdog, a product of Divergent Health, Inc. MIT License.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

MAX_THREADS_REPORTED = 5
# Match a codex binary or the Codex desktop app in a process listing, while
# ignoring incidental hits (e.g. unrelated processes whose environment or
# arguments merely contain the substring "codex").
_PROCESS_PATTERN = re.compile(r"(Codex\.app|(^|[/\s])codex(\s|$))")


def _read_index(index_path):
    threads = []
    try:
        lines = Path(index_path).read_text().splitlines()
    except OSError:
        return threads
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if "thread_name" in entry:
            threads.append(
                {
                    "thread_name": entry.get("thread_name", ""),
                    "updated_at": entry.get("updated_at", ""),
                }
            )
    threads.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
    return threads[:MAX_THREADS_REPORTED]


def _newest_rollout(sessions_dir):
    newest = None
    try:
        candidates = Path(sessions_dir).rglob("rollout-*.jsonl")
        for candidate in candidates:
            stat = candidate.stat()
            if newest is None or stat.st_mtime > newest["mtime"]:
                newest = {
                    "path": str(candidate),
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                }
    except OSError:
        pass
    return newest or {}


def _codex_processes(run=None):
    """List running Codex processes. `run` is injectable for tests."""
    if run is None:
        def run():
            proc = subprocess.run(
                ["pgrep", "-fl", "codex"], capture_output=True, text=True, timeout=10
            )
            return proc.stdout
    try:
        output = run()
    except (OSError, subprocess.TimeoutExpired):
        return []
    processes = []
    for line in output.splitlines():
        pid, _, command = line.partition(" ")
        if _PROCESS_PATTERN.search(command):
            processes.append({"pid": pid, "command": command[:160]})
    return processes


def observe(codex_home=None, process_runner=None):
    """Observe Codex session metadata under `codex_home` (default ~/.codex)."""
    home = Path(codex_home) if codex_home else Path.home() / ".codex"
    return {
        "codex_home": str(home),
        "threads": _read_index(home / "session_index.jsonl"),
        "newest_rollout": _newest_rollout(home / "sessions"),
        "processes": _codex_processes(process_runner),
    }

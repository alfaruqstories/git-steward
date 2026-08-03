from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config, is_path_under, path_hash, redacted_path

SAFE_ENV_EXAMPLES = {
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.sentry.example",
}
SECRET_NAME_RE = re.compile(
    r"(^|/)(\.env(\..*)?|id_rsa|id_dsa|id_ed25519|auth\.json|account\.json|mcp-auth\.json|.*credentials.*\.json)$",
    re.IGNORECASE,
)
SECRET_EXT_RE = re.compile(r"\.(pem|p12|pfx|key)$", re.IGNORECASE)
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    ".next",
    ".venv",
    "venv",
    ".cache",
    "dist",
    "build",
    ".turbo",
}


@dataclass
class CommandResult:
    code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


@dataclass
class RepoStatus:
    raw_path: Path
    display_name: str
    path: str
    path_hash: str
    archive_like: bool = False
    quarantined: bool = False
    active_git_operation: bool = False
    branch: str | None = None
    upstream: str | None = None
    ahead: int | None = None
    behind: int | None = None
    dirty: int = 0
    staged: int = 0
    unstaged: int = 0
    untracked: int = 0
    deleted: int = 0
    stash_count: int = 0
    sample_changes: list[dict[str, str]] = field(default_factory=list)
    suspect_untracked: list[str] = field(default_factory=list)
    status_error: str | None = None
    untracked_error: str | None = None
    ahead_behind_error: str | None = None
    fetch: str = "not_run"
    local_only: bool = False
    blocked_reason: str | None = None
    timed_out: bool = False

    def public_dict(self) -> dict[str, object]:
        return {
            "display_name": self.display_name,
            "path": self.path,
            "path_hash": self.path_hash,
            "archive_like": self.archive_like,
            "quarantined": self.quarantined,
            "active_git_operation": self.active_git_operation,
            "branch": self.branch,
            "upstream": self.upstream,
            "ahead": self.ahead,
            "behind": self.behind,
            "dirty": self.dirty,
            "staged": self.staged,
            "unstaged": self.unstaged,
            "untracked": self.untracked,
            "deleted": self.deleted,
            "stash_count": self.stash_count,
            "sample_changes": self.sample_changes,
            "suspect_untracked": self.suspect_untracked,
            "status_error": self.status_error,
            "untracked_error": self.untracked_error,
            "ahead_behind_error": self.ahead_behind_error,
            "fetch": self.fetch,
            "local_only": self.local_only,
            "blocked_reason": self.blocked_reason,
        }


def run(cmd: list[str], timeout: int) -> CommandResult:
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        return CommandResult(proc.returncode, proc.stdout.strip(), proc.stderr.strip())
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", "timeout", timed_out=True)
    except Exception as exc:
        return CommandResult(999, "", str(exc))


def discover_repos(config: Config) -> list[Path]:
    repos: set[Path] = set()
    for repo in config.repos:
        if repo.exists() and not is_path_under(repo, config.exclude_paths):
            repos.add(repo.resolve())
    for root in config.roots:
        base = root.path
        if not base.exists():
            continue
        base_depth = len(base.parts)
        found = _discover_in_root(base, base_depth, root.depth, config)
        repos.update(found)
    return sorted(repos, key=lambda p: str(p).lower())


def _discover_in_root(base: Path, base_depth: int, depth: int, config: Config) -> set[Path]:
    repos: set[Path] = set()

    def walk() -> None:
        for current, dirs, files in os.walk(base):
            current_path = Path(current)
            if is_path_under(current_path, config.exclude_paths):
                dirs[:] = []
                continue
            if len(current_path.parts) - base_depth > depth:
                dirs[:] = []
                continue
            if ".git" in dirs or ".git" in files:
                repos.add(current_path.resolve())
                dirs[:] = []
                continue
            dirs[:] = [
                d
                for d in dirs
                if d not in SKIP_DIR_NAMES and not _archive_like(str(current_path / d), config.archive_markers)
            ]

    thread = threading.Thread(target=walk, daemon=True)
    thread.start()
    thread.join(timeout=config.scan_timeout_seconds)
    return repos


def scan_all(config: Config, fetch: bool = False) -> tuple[dict[str, object], list[RepoStatus]]:
    started = _now()
    repos = discover_repos(config)
    statuses: list[RepoStatus] = []
    workers = max(1, min(config.scan_workers, 16))
    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = {executor.submit(scan_repo, config, repo, fetch): repo for repo in repos}
        completed = 0
        for future in as_completed(futures):
            repo = futures[future]
            completed += 1
            try:
                statuses.append(future.result())
            except Exception as exc:
                statuses.append(
                    RepoStatus(
                        raw_path=repo,
                        display_name=repo.name,
                        path=redacted_path(config, repo),
                        path_hash=path_hash(repo),
                        status_error=str(exc),
                        blocked_reason="scan_exception",
                        local_only=True,
                    )
                )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    statuses.sort(key=lambda status: (not status.local_only, status.path.lower()))
    totals = {
        "repos": len(statuses),
        "dirty_repos": sum(1 for s in statuses if s.dirty or s.untracked),
        "ahead_repos": sum(1 for s in statuses if (s.ahead or 0) > 0),
        "stash_repos": sum(1 for s in statuses if s.stash_count),
        "blocked_repos": sum(1 for s in statuses if s.blocked_reason),
        "local_only_repos": sum(1 for s in statuses if s.local_only),
        "files_missing_repos": sum(1 for s in statuses if s.deleted > 0),
        "files_missing_total": sum(s.deleted for s in statuses),
    }
    finished = _now()
    summary = {
        "tool": "git-steward",
        "schema_version": 1,
        "started_at": started,
        "finished_at": finished,
        "totals": totals,
        "config": {
            "path": redacted_path(config, config.path),
            "redact_paths": config.redact_paths,
        },
        "paths": {
            "latest_json": redacted_path(config, config.latest_json_path),
            "dashboard_html": redacted_path(config, config.dashboard_html_path),
            "history_sqlite": redacted_path(config, config.history_sqlite_path),
        },
        "repos": [status.public_dict() for status in statuses],
    }
    return summary, statuses


def scan_repo(config: Config, repo: Path, fetch: bool = False) -> RepoStatus:
    status = RepoStatus(
        raw_path=repo,
        display_name=repo.name,
        path=redacted_path(config, repo),
        path_hash=path_hash(repo),
        archive_like=_archive_like(str(repo), config.archive_markers),
    )
    if is_path_under(repo, config.quarantine_paths):
        status.quarantined = True
        status.blocked_reason = "quarantined_by_config"
        status.local_only = True
        return status

    status.active_git_operation = active_git_operation(repo, config.git_timeout_seconds)

    remote = git(config, repo, ["remote"])
    remotes = remote.stdout.splitlines() if remote.code == 0 and remote.stdout else []
    if fetch and remotes:
        fetched = git(config, repo, ["fetch", "--all", "--prune", "--quiet"], timeout=20)
        status.fetch = "ok" if fetched.code == 0 else f"error:{fetched.stderr or fetched.code}"

    porcelain = git(config, repo, ["status", "--porcelain=v1", "-z", "--untracked-files=no"])
    if porcelain.code != 0:
        status.status_error = porcelain.stderr or str(porcelain.code)
        status.timed_out = porcelain.timed_out
    tracked_entries = parse_status_z(porcelain.stdout if porcelain.code == 0 else "")
    counts = status_counts(tracked_entries)

    untracked = git(config, repo, ["ls-files", "--others", "--exclude-standard"])
    untracked_paths: list[str] = []
    if untracked.code == 0:
        untracked_paths = untracked.stdout.splitlines() if untracked.stdout else []
    else:
        status.untracked_error = untracked.stderr or str(untracked.code)
        if untracked.timed_out:
            status.timed_out = True
    untracked_entries = [{"xy": "??", "path": p} for p in untracked_paths]

    counts["dirty"] += len(untracked_entries)
    counts["untracked"] = len(untracked_entries)
    for key, value in counts.items():
        setattr(status, key, value)
    status.sample_changes = _redact_secret_paths((tracked_entries + untracked_entries)[:20])
    status.suspect_untracked = suspect_untracked(untracked_paths)[:25]

    branch = git(config, repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    status.branch = branch.stdout if branch.code == 0 and branch.stdout else None
    upstream = git(config, repo, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    status.upstream = upstream.stdout if upstream.code == 0 and upstream.stdout else None
    if status.upstream:
        ahead = git(config, repo, ["rev-list", "--left-right", "--count", f"{status.upstream}...HEAD"], timeout=6)
        if ahead.code == 0 and ahead.stdout:
            behind, ahead_count = ahead.stdout.split()[:2]
            status.behind = int(behind)
            status.ahead = int(ahead_count)
        else:
            status.ahead_behind_error = ahead.stderr or str(ahead.code)

    stash = git(config, repo, ["stash", "list"], timeout=3)
    status.stash_count = len(stash.stdout.splitlines()) if stash.code == 0 and stash.stdout else 0
    status.local_only = bool(status.dirty or status.stash_count or (status.ahead or 0) > 0)
    status.blocked_reason = blocked_reason(status)
    return status


def git(config: Config, repo: Path, args: list[str], timeout: int | None = None) -> CommandResult:
    return run(["git", "-C", str(repo), *args], timeout=timeout or config.git_timeout_seconds)


def active_git_operation(repo: Path, timeout: int) -> bool:
    result = run(["git", "-C", str(repo), "rev-parse", "--git-dir"], timeout=timeout)
    if result.code != 0 or not result.stdout:
        return False
    git_dir = Path(result.stdout)
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    markers = ["MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-merge", "rebase-apply"]
    return any((git_dir / marker).exists() for marker in markers)


def parse_status_z(raw: str) -> list[dict[str, str]]:
    entries = [part for part in raw.split("\0") if part]
    parsed: list[dict[str, str]] = []
    for entry in entries:
        if len(entry) >= 3:
            parsed.append({"xy": entry[:2], "path": entry[3:]})
    return parsed


def status_counts(entries: list[dict[str, str]]) -> dict[str, int]:
    return {
        "dirty": len(entries),
        "staged": sum(1 for e in entries if e["xy"][0] not in (" ", "?")),
        "unstaged": sum(1 for e in entries if e["xy"][1] not in (" ", "?")),
        "untracked": sum(1 for e in entries if e["xy"] == "??"),
        "deleted": sum(1 for e in entries if "D" in e["xy"]),
    }


def suspect_untracked(paths: list[str]) -> list[str]:
    suspects: list[str] = []
    for rel in paths:
        name = Path(rel).name
        if name in SAFE_ENV_EXAMPLES:
            continue
        if SECRET_NAME_RE.search(rel) or SECRET_EXT_RE.search(rel):
            suspects.append(rel)
    return suspects


def _redact_secret_paths(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    redacted: list[dict[str, str]] = []
    for entry in entries:
        path = entry.get("path", "")
        if SECRET_NAME_RE.search(path) or SECRET_EXT_RE.search(path):
            redacted.append({"xy": entry["xy"], "path": "***redacted***"})
        else:
            redacted.append(entry)
    return redacted


FS_STALL_MARKERS = ["Resource deadlock avoided", "mmap failed"]


def blocked_reason(status: RepoStatus) -> str | None:
    if status.quarantined:
        return "quarantined_by_config"
    if status.active_git_operation:
        return "active_git_operation"
    if status.suspect_untracked:
        return "suspect_untracked"
    if status.timed_out:
        return "fs_stall"
    if status.status_error:
        if any(m in status.status_error for m in FS_STALL_MARKERS):
            return "fs_stall"
        return "status_error"
    if status.untracked_error:
        return "untracked_error"
    return None


def _archive_like(path: str, markers: list[str]) -> bool:
    return any(marker in path for marker in markers)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")

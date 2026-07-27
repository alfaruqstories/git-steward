from __future__ import annotations

import time
from dataclasses import dataclass

from .config import Config
from .git_status import RepoStatus, git, scan_repo
from .history import record_checkpoint


@dataclass
class CheckpointResult:
    path: str
    ok: bool
    reason: str
    commit: str | None = None
    error: str | None = None

    def public_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "ok": self.ok,
            "reason": self.reason,
            "commit": self.commit,
            "error": self.error,
        }


def checkpoint_safe(config: Config, message: str | None = None) -> list[CheckpointResult]:
    from .git_status import discover_repos

    results: list[CheckpointResult] = []
    subject = message or config.checkpoint_message
    for repo in discover_repos(config):
        status = scan_repo(config, repo, fetch=False)
        if not status.dirty:
            continue
        if status.blocked_reason:
            results.append(CheckpointResult(status.path, False, f"blocked:{status.blocked_reason}"))
            continue
        result = checkpoint_repo(config, status, subject)
        results.append(result)
    return results


def checkpoint_repo(config: Config, status: RepoStatus, subject: str) -> CheckpointResult:
    body = (
        "No-loss local checkpoint created by Git Steward.\n\n"
        "This commit preserves dirty or untracked local work. It was created "
        "with --no-verify and has not been pushed."
    )
    added = git(config, status.raw_path, ["add", "-A"], timeout=60)
    if added.code != 0:
        return CheckpointResult(status.path, False, "git_add_failed", error=added.stderr or str(added.code))
    diff = git(config, status.raw_path, ["diff", "--cached", "--quiet"], timeout=10)
    if diff.code == 0:
        return CheckpointResult(status.path, True, "nothing_to_commit")
    committed = git(config, status.raw_path, ["commit", "--no-verify", "-m", subject, "-m", body], timeout=90)
    if committed.code != 0:
        return CheckpointResult(status.path, False, "git_commit_failed", error=committed.stderr or committed.stdout)
    head = git(config, status.raw_path, ["rev-parse", "--short", "HEAD"], timeout=5)
    commit = head.stdout if head.code == 0 else None
    if commit:
        record_checkpoint(config, status.path_hash, commit, subject, time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    return CheckpointResult(status.path, True, "committed", commit=commit)

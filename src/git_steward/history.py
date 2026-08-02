from __future__ import annotations

import json
import sqlite3
import stat
from pathlib import Path

from .config import Config
from .git_status import RepoStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL,
  tool_version TEXT,
  status TEXT NOT NULL,
  totals_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  stable_key TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  redacted_path TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repo_observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  repo_id INTEGER NOT NULL,
  branch TEXT,
  upstream TEXT,
  dirty_count INTEGER NOT NULL,
  untracked_count INTEGER NOT NULL,
  ahead_count INTEGER,
  behind_count INTEGER,
  stash_count INTEGER NOT NULL,
  blocked_reason TEXT,
  local_only INTEGER NOT NULL,
  sample_json TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id),
  FOREIGN KEY(repo_id) REFERENCES repos(id)
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER,
  repo_id INTEGER,
  event_type TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id),
  FOREIGN KEY(repo_id) REFERENCES repos(id)
);

CREATE TABLE IF NOT EXISTS checkpoints (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  repo_id INTEGER,
  commit_sha TEXT NOT NULL,
  subject TEXT NOT NULL,
  created_at TEXT NOT NULL,
  pushed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(repo_id) REFERENCES repos(id)
);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.parent.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
    if db_path.exists():
        db_path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def record_run(config: Config, summary: dict[str, object], statuses: list[RepoStatus]) -> int:
    init_db(config.history_sqlite_path)
    with sqlite3.connect(config.history_sqlite_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO runs(started_at, finished_at, tool_version, status, totals_json) VALUES (?, ?, ?, ?, ?)",
            (
                str(summary["started_at"]),
                str(summary["finished_at"]),
                "0.1.0",
                "ok",
                json.dumps(summary["totals"], sort_keys=True),
            ),
        )
        assert cur.lastrowid is not None
        run_id = cur.lastrowid
        for status in statuses:
            repo_id = upsert_repo(conn, status, str(summary["finished_at"]))
            cur.execute(
                """
                INSERT INTO repo_observations(
                  run_id, repo_id, branch, upstream, dirty_count, untracked_count,
                  ahead_count, behind_count, stash_count, blocked_reason, local_only, sample_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    repo_id,
                    status.branch,
                    status.upstream,
                    status.dirty,
                    status.untracked,
                    status.ahead,
                    status.behind,
                    status.stash_count,
                    status.blocked_reason,
                    1 if status.local_only else 0,
                    json.dumps(status.sample_changes),
                ),
            )
            if status.blocked_reason:
                cur.execute(
                    "INSERT INTO events(run_id, repo_id, event_type, message, created_at) VALUES (?, ?, ?, ?, ?)",
                    (run_id, repo_id, "blocked", status.blocked_reason, str(summary["finished_at"])),
                )
        conn.commit()
        return run_id


def upsert_repo(conn: sqlite3.Connection, status: RepoStatus, seen_at: str) -> int:
    cur = conn.cursor()
    cur.execute("SELECT id FROM repos WHERE stable_key = ?", (status.path_hash,))
    row = cur.fetchone()
    if row:
        repo_id = int(row[0])
        cur.execute(
            "UPDATE repos SET display_name = ?, redacted_path = ?, last_seen_at = ? WHERE id = ?",
            (status.display_name, status.path, seen_at, repo_id),
        )
        return repo_id
    cur.execute(
        "INSERT INTO repos(stable_key, display_name, redacted_path, first_seen_at, last_seen_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (status.path_hash, status.display_name, status.path, seen_at, seen_at),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def record_checkpoint(config: Config, repo_hash: str, commit_sha: str, subject: str, created_at: str) -> None:
    init_db(config.history_sqlite_path)
    with sqlite3.connect(config.history_sqlite_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM repos WHERE stable_key = ?", (repo_hash,))
        row = cur.fetchone()
        repo_id = int(row[0]) if row else None
        cur.execute(
            "INSERT INTO checkpoints(repo_id, commit_sha, subject, created_at, pushed) VALUES (?, ?, ?, ?, 0)",
            (repo_id, commit_sha, subject, created_at),
        )
        conn.commit()


def blocked_trend(db_path: Path, limit: int = 48) -> list[tuple[str, int]]:
    """Return (started_at, blocked_count) pairs from the most recent scan runs, oldest first."""
    if not db_path.exists():
        return []
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT started_at, totals_json FROM runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    except sqlite3.Error:
        return []
    result: list[tuple[str, int]] = []
    for started_at, totals_json in rows:
        try:
            totals = json.loads(totals_json)
        except (ValueError, TypeError):
            continue
        result.append((str(started_at), int(totals.get("blocked_repos", 0) or 0)))
    result.reverse()
    return result

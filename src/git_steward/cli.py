from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .checkpoint import checkpoint_safe
from .config import default_config_paths, find_config_path, load_config, write_initial_config
from .dashboard import render_dashboard
from .git_status import scan_all
from .history import record_run
from .scheduler import install_launchagent
from .state import read_latest, write_latest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="git-steward", description="Local-first Git worktree hygiene.")
    parser.add_argument("--config", help="Path to local Git Steward config.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a local private config.")
    init.add_argument("--root", action="append", default=[], help="Repo root to scan. Can be repeated.")
    init.add_argument("--force", action="store_true", help="Overwrite existing config.")

    scan = sub.add_parser("scan", help="Scan configured repos and write latest.json/history.sqlite.")
    scan.add_argument("--fetch", action="store_true", help="Fetch remotes before ahead/behind checks.")
    scan.add_argument("--dashboard", action="store_true", help="Render dashboard.html after scanning.")

    sub.add_parser("dashboard", help="Render dashboard.html from latest.json.")

    checkpoint = sub.add_parser("checkpoint", help="Create guarded local checkpoint commits.")
    checkpoint.add_argument("--safe", action="store_true", required=True, help="Only checkpoint repos that pass safety checks.")
    checkpoint.add_argument("--message", help="Checkpoint commit subject.")
    checkpoint.add_argument("--dashboard", action="store_true", help="Rescan and render dashboard after checkpointing.")

    agent = sub.add_parser("install-launchagent", help="Install a macOS LaunchAgent for scan-only recurrence.")
    agent.add_argument("--interval", type=int, default=3600, help="Scan interval in seconds.")
    agent.add_argument("--executable", help="Path to git-steward executable.")

    sub.add_parser("where", help="Print config and state paths.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            return cmd_init(args)
        if args.command == "scan":
            return cmd_scan(args)
        if args.command == "dashboard":
            return cmd_dashboard(args)
        if args.command == "checkpoint":
            return cmd_checkpoint(args)
        if args.command == "install-launchagent":
            return cmd_install_launchagent(args)
        if args.command == "where":
            return cmd_where(args)
    except Exception as exc:
        print(f"git-steward: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    roots = args.root or ["~/Code"]
    path = find_config_path(args.config) if args.config else default_config_paths()[0]
    assert path is not None
    write_initial_config(path, roots, force=args.force)
    print(path)
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    summary, statuses = scan_all(config, fetch=args.fetch)
    record_run(config, summary, statuses)
    latest = write_latest(config, summary)
    print(latest)
    if args.dashboard:
        dashboard = render_dashboard(config, summary)
        print(dashboard)
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    summary = read_latest(config)
    path = render_dashboard(config, summary)
    print(path)
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if not config.allow_checkpoint:
        raise PermissionError("Checkpointing is disabled in config. Set allow_checkpoint = true to enable it.")
    results = checkpoint_safe(config, message=args.message)
    for result in results:
        print(json.dumps(result.public_dict(), sort_keys=True))
    if args.dashboard:
        summary, statuses = scan_all(config, fetch=False)
        record_run(config, summary, statuses)
        write_latest(config, summary)
        print(render_dashboard(config, summary))
    return 0


def cmd_install_launchagent(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    executable = args.executable or shutil.which("git-steward") or sys.argv[0]
    path = install_launchagent(config, executable=executable, interval=args.interval)
    print(path)
    print("Load with: launchctl bootstrap gui/$(id -u) " + str(path))
    return 0


def cmd_where(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    print(f"config={config.path}")
    print(f"state_dir={config.state_dir}")
    print(f"latest_json={config.latest_json_path}")
    print(f"dashboard_html={config.dashboard_html_path}")
    print(f"history_sqlite={config.history_sqlite_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

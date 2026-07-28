from __future__ import annotations

import argparse
import json
import shutil
import sys
from typing import Any

from .checkpoint import checkpoint_safe
from .config import default_config_paths, find_config_path, load_config, write_initial_config
from .dashboard import render_dashboard
from .git_status import scan_all
from .history import record_run
from .scheduler import install_launchagent
from .serve import ServeServer
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
    scan.add_argument("--notify", action="store_true", help="Show macOS notification with results.")

    sub.add_parser("dashboard", help="Render dashboard.html from latest.json.")

    checkpoint = sub.add_parser("checkpoint", help="Create guarded local checkpoint commits.")
    checkpoint.add_argument(
        "--safe", action="store_true", required=True, help="Only checkpoint repos that pass safety checks"
    )
    checkpoint.add_argument("--message", help="Checkpoint commit subject.")
    checkpoint.add_argument("--dashboard", action="store_true", help="Rescan and render dashboard after checkpointing.")

    agent = sub.add_parser("install-launchagent", help="Install a macOS LaunchAgent for scan-only recurrence.")
    agent.add_argument("--interval", type=int, default=3600, help="Scan interval in seconds.")
    agent.add_argument("--executable", help="Path to git-steward executable.")

    serve = sub.add_parser("serve", help="Start dashboard HTTP server with live refresh and port detection.")
    serve.add_argument("--port", type=int, default=8199, help="HTTP port (default 8199).")
    serve.add_argument("--refresh", type=int, default=0, help="Override config refresh_seconds for scan interval.")
    serve.add_argument("--open", action="store_true", help="Open dashboard in browser.")

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
        if args.command == "serve":
            return cmd_serve(args)
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
    import subprocess

    config = load_config(args.config)
    summary, statuses = scan_all(config, fetch=args.fetch)
    record_run(config, summary, statuses)
    latest = write_latest(config, summary)
    print(latest)
    if args.dashboard:
        dashboard = render_dashboard(config, summary)
        print(dashboard)
    if args.notify:
        totals: dict[str, Any] = summary.get("totals", {})  # type: ignore[assignment]
        parts = []
        d = totals.get("dirty_repos", 0) or 0
        a = totals.get("ahead_repos", 0) or 0
        b = totals.get("blocked_repos", 0) or 0
        s = totals.get("stash_repos", 0) or 0
        if d:
            parts.append(f"{d} dirty")
        if a:
            parts.append(f"{a} ahead")
        if b:
            parts.append(f"{b} blocked")
        if s:
            parts.append(f"{s} stashes")
        body = " · ".join(parts) if parts else "all clean"
        subprocess.run(
            ["osascript", "-e", f'display notification "{body}" with title "Git Steward"'],
            capture_output=True,
        )
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


def cmd_serve(args: argparse.Namespace) -> int:
    import webbrowser

    config = load_config(args.config)
    refresh = args.refresh if args.refresh > 0 else config.refresh_seconds
    server = ServeServer(config, port=args.port, refresh_seconds=refresh)
    if args.open:
        webbrowser.open(f"http://127.0.0.1:{args.port}/")
    server.serve_forever()
    return 0


def cmd_install_launchagent(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    executable = args.executable or shutil.which("git-steward") or sys.argv[0]
    path = install_launchagent(config, executable=executable, interval=args.interval)
    print(path)
    print("Load with: launchctl bootstrap gui/$(id -u) " + str(path))
    return 0


def cmd_where(args: argparse.Namespace) -> int:
    from .config import redacted_path

    config = load_config(args.config)
    print(f"config={redacted_path(config, config.path)}")
    print(f"state_dir={redacted_path(config, config.state_dir)}")
    print(f"latest_json={redacted_path(config, config.latest_json_path)}")
    print(f"dashboard_html={redacted_path(config, config.dashboard_html_path)}")
    print(f"history_sqlite={redacted_path(config, config.history_sqlite_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

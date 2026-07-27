# Git Steward

[![License](https://img.shields.io/github/license/alfaruqstories/git-steward)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![CI](https://img.shields.io/github/actions/workflow/status/alfaruqstories/git-steward/ci.yml)]()
[![Last commit](https://img.shields.io/github/last-commit/alfaruqstories/git-steward)]()

Local-first Git worktree hygiene, status dashboards, no-loss checkpointing, and dev server lifecycle management.

```bash
pip install git-steward
git-steward init --root ~/Code
git-steward scan --dashboard
```

## Features

- **Scan** — discover repos under configured roots, report branch, dirty/untracked/stashed state, ahead/behind counts
- **Dashboard** — local HTML dashboard rendered from scan data
- **Checkpoint** — guarded local checkpoint commits for dirty repos (never pushes)
- **Serve** — detect running dev servers, check health, start/stop, focus their terminal
- **History** — SQLite timeline of scans, blockages, blockages, checkpoints
- **Safe by default** — skips active Git operations, secret-looking untracked paths, quarantined repos; never pushes

## Install

```bash
pip install git-steward
```

Or from source:

```bash
git clone https://github.com/alfaruqstories/git-steward
cd git-steward
pip install -e .
```

Requires Python 3.11+.

## Quick Start

```bash
# Create a config that scans ~/Code (depth 3 for nested repos)
git-steward init --root ~/Code

# Scan all discovered repos and open the dashboard
git-steward scan --dashboard

# See where config and state files live
git-steward where
```

Config lives at `~/.config/git-steward/config.toml` by default. State files go to `~/.local/state/git-steward/`.

## Usage

### Scanning

```bash
git-steward scan                          # scan and write latest.json + history.sqlite
git-steward scan --fetch                  # fetch remotes before ahead/behind checks
git-steward scan --dashboard              # also render dashboard.html
```

### Dashboard

```bash
git-steward dashboard                     # render dashboard.html from latest scan
```

Open the generated HTML file in any browser. It shows a summary tile grid plus per-repo cards with branch, dirty count, ahead/behind, stashes, and blockers.

### Checkpointing

```bash
git-steward checkpoint --safe             # commit dirty work in every safe repo
git-steward checkpoint --safe --message "wip: before refactor"
```

Checkpointing is opt-in (`allow_checkpoint = true` in config). It skips repos with active Git operations, suspect untracked paths (`.env`, keys), and status errors.

### Dev Server Lifecycle

```bash
git-steward serve ls                      # list running dev servers per project
git-steward serve start <project>         # start a dev server
git-steward serve stop <project>          # stop a running dev server
git-steward serve focus <project>         # focus the terminal it's running in
git-steward serve health <project>        # probe HTTP/TCP health check
```

Detects projects by matching known dev commands (`next dev`, `vite`, `uvicorn`, `manage.py runserver`, etc.) against repo paths. Ports and process info are tracked in the state directory.

### Scheduled Scanning (macOS)

```bash
git-steward install-launchagent --interval 3600
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.git-steward.scan.plist
```

### Menu Bar Integration (SwiftBar/xBar)

Copy `examples/swiftbar.git-steward.example.sh` to your SwiftBar plugins folder.

## Configuration

Reference: `examples/git-steward.config.example.toml`

```toml
version = 1
redact_paths = true
scan_timeout_seconds = 4
git_timeout_seconds = 4
scan_workers = 8
allow_checkpoint = false          # enable with caution
checkpoint_message = "chore: checkpoint local work"

[output]
state_dir = "~/.local/state/git-steward"

[[roots]]
path = "~/Code"
depth = 3

# Optional: scan specific repos outside roots
# [[repos]]
# path = "~/other-project"

archive_markers = ["/Archive/", "/Backups/", "all-repos"]
exclude_paths = []
quarantine_paths = []
```

## Safety

- Never pushes to any remote
- Skips repos during active merge/rebase/cherry-pick/bisect
- Blocks checkpointing on secret-looking paths (`.env`, `id_*`, `*.pem`, `*credentials*.json`)
- Quarantined repos are reported as blocked without being probed
- Paths are redacted in JSON and HTML output (default)
- State files use restricted permissions (0600)

## Development

```bash
git clone https://github.com/alfaruqstories/git-steward
cd git-steward
pip install -e .
pip install ruff mypy pre-commit   # or use pipx
pre-commit install                  # hooks run ruff + mypy
python3 -m pytest tests/
```

## License

MIT

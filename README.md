# Git Steward

Git Steward is a local-first tool for watching over Git worktrees so local work is not lost. It scans configured repo roots, writes the current state to JSON, records history in SQLite, renders a local dashboard, and can create safe local checkpoint commits on demand.

It is designed so the public repo can be released without exposing private machine paths. Tool code, examples, and templates live in this repo. Real roots, excludes, quarantine paths, and state files live outside the repo in a local config directory.

## Core Model

- `latest.json` is the current machine-readable status for dashboards and status bars.
- `history.sqlite` is the private local timeline of scans, blockers, and checkpoints.
- `dashboard.html` is generated from `latest.json`.
- No remote push is performed by Git Steward.
- Normal scans do not read file contents.
- Repos with active Git operations, secret-looking untracked paths, unreadable scans, or configured quarantine paths are marked blocked.

## Quick Start

```bash
git-steward init --root ~/Code
git-steward scan --dashboard
git-steward checkpoint --safe
```

By default Git Steward looks for config in this order:

1. `--config /path/to/config.toml`
2. `GIT_STEWARD_CONFIG`
3. `~/.config/git-steward/config.toml`
4. `~/Library/Application Support/git-steward/config.toml`

If no config exists, the tool exits and asks you to run `git-steward init`. It does not blindly scan the whole machine.

## Private State

Recommended local layout:

```text
~/.config/git-steward/config.toml
~/.local/state/git-steward/latest.json
~/.local/state/git-steward/history.sqlite
~/.local/state/git-steward/dashboard.html
```

The config and state files should not be committed to this repo.

## Recurrence

The intended recurrence stack is:

1. Scheduled scan writes `latest.json` and `history.sqlite`.
2. Dashboard renders from `latest.json`.
3. Optional menu bar/status bar reads `latest.json`.
4. Safe checkpointing remains manual until the scan path has been stable on a machine.

Install a macOS LaunchAgent after the config is working:

```bash
git-steward install-launchagent --interval 3600
```

## Safety

Git Steward is deliberately conservative:

- It never pushes.
- It skips active merge, rebase, cherry-pick, revert, and bisect states.
- It skips secret-looking untracked paths such as real `.env` files and private keys.
- It treats configured quarantine paths as blocked instead of probing them.
- It records path hashes in SQLite and can redact paths in JSON/HTML.

## Development

```bash
python3 -m unittest discover -s tests
```

from __future__ import annotations

import hashlib
import os
import stat
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - pyproject requires 3.11+
    tomllib = None  # type: ignore[assignment]


APP_NAME = "git-steward"
CONFIG_ENV = "GIT_STEWARD_CONFIG"

DEFAULT_ARCHIVE_MARKERS = [
    "/Archive/",
    "/Backups/",
    " backup",
    "-backup-",
    "corrupt-backup",
    "all-repos",
]


@dataclass(frozen=True)
class Root:
    path: Path
    depth: int = 3


@dataclass(frozen=True)
class Config:
    path: Path
    roots: list[Root]
    state_dir: Path
    repos: list[Path] = field(default_factory=list)
    redact_paths: bool = True
    scan_timeout_seconds: int = 30
    git_timeout_seconds: int = 10
    scan_workers: int = 8
    allow_checkpoint: bool = False
    checkpoint_message: str = "chore: checkpoint local work"
    refresh_seconds: int = 43200
    archive_markers: list[str] = field(default_factory=lambda: list(DEFAULT_ARCHIVE_MARKERS))
    exclude_paths: list[Path] = field(default_factory=list)
    quarantine_paths: list[Path] = field(default_factory=list)

    @property
    def latest_json_path(self) -> Path:
        return self.state_dir / "latest.json"

    @property
    def dashboard_html_path(self) -> Path:
        return self.state_dir / "dashboard.html"

    @property
    def history_sqlite_path(self) -> Path:
        return self.state_dir / "history.sqlite"


def expand_path(value: str | os.PathLike[str]) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(value)))).resolve()


def default_config_paths() -> list[Path]:
    paths: list[Path] = []
    env_path = os.environ.get(CONFIG_ENV)
    if env_path:
        paths.append(expand_path(env_path))
    paths.append(expand_path(f"~/.config/{APP_NAME}/config.toml"))
    if sys.platform == "darwin":
        paths.append(expand_path(f"~/Library/Application Support/{APP_NAME}/config.toml"))
    return paths


def find_config_path(explicit: str | None = None) -> Path | None:
    if explicit:
        p = expand_path(explicit)
        return p if p.exists() else p
    for candidate in default_config_paths():
        if candidate.exists():
            return candidate
    return None


def load_config(explicit: str | None = None) -> Config:
    config_path = find_config_path(explicit)
    if not config_path or not config_path.exists():
        searched = "\n".join(f"  - {p}" for p in default_config_paths())
        raise FileNotFoundError(
            "No Git Steward config found. Run `git-steward init --root ~/Code` or pass --config.\n"
            f"Searched:\n{searched}"
        )
    if tomllib is None:
        raise RuntimeError("Git Steward requires Python 3.11+ for TOML config parsing.")
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    roots = [Root(path=expand_path(item["path"]), depth=int(item.get("depth", 3))) for item in data.get("roots", [])]
    repos = [expand_path(item["path"]) for item in data.get("repos", [])]
    if not roots and not repos:
        raise ValueError(f"No [[roots]] or [[repos]] entries found in {config_path}")
    output = data.get("output", {})
    state_dir = expand_path(output.get("state_dir", f"~/.local/state/{APP_NAME}"))
    return Config(
        path=config_path,
        roots=roots,
        repos=repos,
        state_dir=state_dir,
        redact_paths=bool(data.get("redact_paths", True)),
        scan_timeout_seconds=int(data.get("scan_timeout_seconds", 30)),
        git_timeout_seconds=int(data.get("git_timeout_seconds", 10)),
        scan_workers=int(data.get("scan_workers", 8)),
        allow_checkpoint=bool(data.get("allow_checkpoint", False)),
        checkpoint_message=str(data.get("checkpoint_message", "chore: checkpoint local work")),
        refresh_seconds=int(data.get("refresh_seconds", 30)),
        archive_markers=[str(v) for v in data.get("archive_markers", DEFAULT_ARCHIVE_MARKERS)],
        exclude_paths=[expand_path(v) for v in data.get("exclude_paths", [])],
        quarantine_paths=[expand_path(v) for v in data.get("quarantine_paths", [])],
    )


def write_initial_config(path: Path, roots: list[str], force: bool = False) -> Path:
    if path.exists() and not force:
        raise FileExistsError(f"Config already exists: {path}")
    root_blocks = "\n".join(f'[[roots]]\npath = "{_toml_string(root)}"\ndepth = 3\n' for root in roots)
    body = f"""\
    version = 1
    redact_paths = true
    scan_timeout_seconds = 30
    git_timeout_seconds = 10
    allow_checkpoint = false
    checkpoint_message = "chore: checkpoint local work"
    refresh_seconds = 43200

    [output]
    state_dir = "~/.local/state/git-steward"

    {root_blocks}
    archive_markers = [
      "/Archive/",
      "/Backups/",
      " backup",
      "-backup-",
      "all-repos",
    ]

    exclude_paths = []
    quarantine_paths = []
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path


def redacted_path(config: Config, path: Path) -> str:
    raw = str(path)
    home = str(Path.home())
    if raw == home:
        value = "~"
    elif raw.startswith(home + os.sep):
        value = "~" + raw[len(home) :]
    else:
        value = raw
    return value if config.redact_paths else raw


def path_hash(path: Path) -> str:
    raw = str(path.resolve())
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def is_path_under(path: Path, candidates: list[Path]) -> bool:
    resolved = path.resolve()
    for candidate in candidates:
        try:
            resolved.relative_to(candidate.resolve())
            return True
        except ValueError:
            continue
    return False


def _toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')

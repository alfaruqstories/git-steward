from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import cast

from .config import Config


def _set_private_file(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _set_private_dir(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


def write_latest(config: Config, summary: dict[str, object]) -> Path:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    _set_private_dir(config.state_dir)
    config.latest_json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _set_private_file(config.latest_json_path)
    return config.latest_json_path


def read_latest(config: Config) -> dict[str, object]:
    return cast("dict[str, object]", json.loads(config.latest_json_path.read_text(encoding="utf-8")))

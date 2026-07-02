from __future__ import annotations

from pathlib import Path
import json

from .config import Config


def write_latest(config: Config, summary: dict[str, object]) -> Path:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.latest_json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return config.latest_json_path


def read_latest(config: Config) -> dict[str, object]:
    return json.loads(config.latest_json_path.read_text(encoding="utf-8"))

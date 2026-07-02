from __future__ import annotations

from pathlib import Path
import os
import plistlib
import stat

from .config import Config


DEFAULT_LABEL = "com.git-steward.scan"


def launchagent_path(label: str = DEFAULT_LABEL) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def install_launchagent(config: Config, executable: str, interval: int = 3600, label: str = DEFAULT_LABEL) -> Path:
    plist_path = launchagent_path(label)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    log_dir = config.state_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    program_arguments = [
        executable,
        "--config",
        str(config.path),
        "scan",
        "--dashboard",
    ]
    data = {
        "Label": label,
        "ProgramArguments": program_arguments,
        "StartInterval": int(interval),
        "RunAtLoad": True,
        "StandardOutPath": str(log_dir / "launchagent.out.log"),
        "StandardErrorPath": str(log_dir / "launchagent.err.log"),
        "EnvironmentVariables": {
            "GIT_STEWARD_CONFIG": str(config.path),
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        },
    }
    plist_path.write_bytes(plistlib.dumps(data, sort_keys=False))
    current_mode = plist_path.stat().st_mode
    plist_path.chmod(current_mode | stat.S_IRUSR | stat.S_IWUSR)
    return plist_path

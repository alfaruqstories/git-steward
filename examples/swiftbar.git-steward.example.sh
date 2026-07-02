#!/usr/bin/env bash
# SwiftBar/xbar example. Set STATE_JSON if your state path differs.

STATE_JSON="${STATE_JSON:-$HOME/.local/state/git-steward/latest.json}"

if [[ ! -f "$STATE_JSON" ]]; then
  echo "Git Steward: no scan"
  echo "---"
  echo "Run git-steward scan --dashboard"
  exit 0
fi

python3 - "$STATE_JSON" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
totals = data.get("totals", {})
dirty = totals.get("dirty_repos", 0)
blocked = totals.get("blocked_repos", 0)
ahead = totals.get("ahead_repos", 0)

icon = "OK" if dirty == blocked == ahead == 0 else "WARN"
if blocked:
    icon = "BLOCK"
print(f"Git Steward: {icon} D:{dirty} A:{ahead} B:{blocked}")
print("---")
print(f"Repos scanned: {totals.get('repos', 0)}")
print(f"Dirty repos: {dirty}")
print(f"Ahead repos: {ahead}")
print(f"Blocked repos: {blocked}")
dashboard = data.get("paths", {}).get("dashboard_html")
if dashboard:
    print(f"Open dashboard | href=file://{dashboard}")
PY

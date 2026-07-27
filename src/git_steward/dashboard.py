# ruff: noqa: E501 — CSS embedded in f-strings, long lines are intentional

from __future__ import annotations

import html
import stat
from pathlib import Path
from typing import Any

from .config import Config


def render_dashboard(config: Config, summary: dict[str, Any]) -> Path:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.dashboard_html_path.write_text(render_html(summary, config.refresh_seconds), encoding="utf-8")
    config.dashboard_html_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return config.dashboard_html_path


def render_html(summary: dict[str, Any], refresh_seconds: int = 0) -> str:
    totals = summary.get("totals", {})
    repos = summary.get("repos", [])
    rows = "\n".join(_render_repo(repo) for repo in repos)
    generated = html.escape(str(summary.get("finished_at", "unknown")))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{f'<meta http-equiv="refresh" content="{refresh_seconds}">' if refresh_seconds > 0 else ""}
<title>Git Steward</title>
<style>
:root {{
  --bg: #f5f7f3;
  --panel: #fff;
  --ink: #17201c;
  --muted: #65736c;
  --line: #d9dfd8;
  --ok: #1f8f5f;
  --warn: #b7791f;
  --bad: #b42318;
  --info: #3267c9;
}}
body {{ margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
header {{ position: sticky; top: 0; z-index: 1; background: var(--panel);
  border-bottom: 1px solid var(--line); padding: 24px 32px 18px; }}
h1 {{ margin: 0 0 4px; font-size: 24px; letter-spacing: 0; }}
h2 {{ margin: 0; font-size: 17px; letter-spacing: 0; }}
p {{ margin: 0; color: var(--muted); }}
main {{ padding: 22px 32px 48px; display: grid; gap: 12px; }}
.summary {{ display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 10px; margin-top: 16px; }}
.tile, .repo {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
.tile {{ padding: 12px; }}
.tile strong {{ display: block; font-size: 24px; color: var(--ink); }}
.repo {{ border-left: 5px solid var(--ok); padding: 13px 15px; display: grid; gap: 8px; }}
.repo.dirty {{ border-left-color: var(--warn); }}
.repo.ahead {{ border-left-color: var(--info); }}
.repo.blocked {{ border-left-color: var(--bad); }}
.path {{ overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.chip {{ border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; background: #fafbf8; color: var(--muted); }}
ul {{ margin: 0; padding-left: 20px; color: var(--muted); }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
@media (max-width: 760px) {{ header, main {{ padding-left: 16px; padding-right: 16px; }}
  .summary {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }} }}
</style>
</head>
<body>
<header>
  <h1>Git Steward</h1>
  <p>Generated {generated}. Local dashboard; nothing is pushed.</p>
  <section class="summary">
    <div class="tile"><strong>{totals.get("repos", 0)}</strong>repos scanned</div>
    <div class="tile"><strong>{totals.get("dirty_repos", 0)}</strong>dirty repos</div>
    <div class="tile"><strong>{totals.get("ahead_repos", 0)}</strong>ahead of upstream</div>
    <div class="tile"><strong>{totals.get("stash_repos", 0)}</strong>with stashes</div>
    <div class="tile"><strong>{totals.get("blocked_repos", 0)}</strong>blocked</div>
  </section>
</header>
<main>
{rows}
</main>
</body>
</html>
"""


def _render_repo(repo: object) -> str:
    item = repo if isinstance(repo, dict) else {}
    state = "clean"
    if item.get("blocked_reason"):
        state = "blocked"
    elif item.get("dirty") or item.get("untracked"):
        state = "dirty"
    elif item.get("ahead"):
        state = "ahead"
    changes = "\n".join(
        f"<li><code>{html.escape(str(ch.get('xy', '')))}</code> {html.escape(str(ch.get('path', '')))}</li>"
        for ch in item.get("sample_changes", [])[:8]
        if isinstance(ch, dict)
    )
    blocked = item.get("blocked_reason")
    blocked_chip = f'<span class="chip">blocked: {html.escape(str(blocked))}</span>' if blocked else ""
    return f"""
<article class="repo {state}">
  <div>
    <h2>{html.escape(str(item.get("display_name") or "unknown"))}</h2>
    <p class="path">{html.escape(str(item.get("path") or ""))}</p>
  </div>
  <div class="chips">
    <span class="chip">branch {html.escape(str(item.get("branch") or "none"))}</span>
    <span class="chip">upstream {html.escape(str(item.get("upstream") or "none"))}</span>
    <span class="chip">{html.escape(str(item.get("dirty", 0)))} dirty</span>
    <span class="chip">{html.escape(str(item.get("untracked", 0)))} untracked</span>
    <span class="chip">ahead {html.escape(str(item.get("ahead")))}</span>
    <span class="chip">behind {html.escape(str(item.get("behind")))}</span>
    <span class="chip">{html.escape(str(item.get("stash_count", 0)))} stashes</span>
    {blocked_chip}
  </div>
  <ul>{changes}</ul>
</article>
"""

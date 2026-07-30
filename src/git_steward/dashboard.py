# ruff: noqa: E501

from __future__ import annotations

import html
import stat
from collections import Counter
from pathlib import Path
from typing import Any

from .config import Config

DASHBOARD_META_REFRESH = 60


def render_dashboard(config: Config, summary: dict[str, Any]) -> Path:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.dashboard_html_path.write_text(render_html(summary), encoding="utf-8")
    config.dashboard_html_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return config.dashboard_html_path


def render_html(summary: dict[str, Any], refresh_seconds: int = DASHBOARD_META_REFRESH) -> str:
    totals = summary.get("totals", {})
    repos = summary.get("repos", [])
    generated = html.escape(str(summary.get("finished_at", "unknown")))

    blocked_breakdown = Counter(r.get("blocked_reason") for r in repos if r.get("blocked_reason"))
    chart_svg = _blocked_chart(blocked_breakdown, totals.get("repos", 0))

    rows = "\n".join(_render_repo(repo) for repo in repos)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{f'<meta http-equiv="refresh" content="{refresh_seconds}">' if refresh_seconds > 0 else ""}
<title>Git Steward</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#f4f5f7;--surface:#fff;--ink:#1a1d21;--muted:#6b7280;
  --line:#e5e7eb;--accent:#2563eb;--green:#16a34a;--amber:#d97706;--red:#dc2626;
  --chart-fs:#94a3b8;--chart-err:#fca5a5;--chart-other:#fde68a;
}}
body{{background:var(--bg);color:var(--ink);font:13.5px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}}
.wrap{{max-width:1120px;margin:0 auto;padding:32px 24px 64px;}}

h1{{font-size:20px;font-weight:600;letter-spacing:-0.01em;}}
.stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:24px 0;}}
.stat-card{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px;}}
.stat-card .num{{font-size:28px;font-weight:600;letter-spacing:-0.02em;line-height:1;}}
.stat-card .label{{font-size:12px;color:var(--muted);margin-top:4px;}}

.chart-section{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:20px;margin-bottom:24px;}}
.chart-section h2{{font-size:14px;font-weight:600;margin-bottom:16px;}}
.bar-row{{display:flex;align-items:center;gap:12px;margin-bottom:8px;}}
.bar-row .bar-label{{width:100px;font-size:12px;color:var(--muted);text-align:right;flex-shrink:0;}}
.bar-track{{flex:1;height:20px;background:var(--bg);border-radius:4px;overflow:hidden;}}
.bar-fill{{height:100%;border-radius:4px;transition:width 0.3s;}}
.bar-count{{width:40px;font-size:12px;font-weight:600;text-align:right;flex-shrink:0;}}

#search{{width:100%;padding:8px 12px;border:1px solid var(--line);border-radius:6px;font-size:13px;background:var(--surface);margin-bottom:16px;}}
#search:focus{{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(37,99,235,0.1);}}

.repo-list{{display:flex;flex-direction:column;gap:6px;}}
.repo-row{{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:12px 16px;display:flex;align-items:center;gap:12px;cursor:default;transition:border-color 0.15s;}}
.repo-row:hover{{border-color:#c4c8cf;}}
.repo-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;}}
.dot-clean{{background:var(--green);}}
.dot-dirty{{background:var(--amber);}}
.dot-ahead{{background:var(--accent);}}
.dot-blocked{{background:var(--red);}}
.repo-name{{font-weight:500;font-size:13px;min-width:140px;}}
.repo-path{{font-size:11px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;}}
.repo-meta{{display:flex;gap:8px;align-items:center;flex-shrink:0;}}
.meta-tag{{font-size:11px;padding:2px 8px;border-radius:4px;background:var(--bg);color:var(--muted);white-space:nowrap;}}
.meta-tag.dirty{{background:#fef3c7;color:#92400e;}}
.meta-tag.ahead{{background:#dbeafe;color:#1e40af;}}
.meta-tag.stash{{background:#f3e8ff;color:#6b21a8;}}
.meta-tag.blocked{{background:#fee2e2;color:#991b1b;}}

.empty{{text-align:center;padding:48px 0;color:var(--muted);}}
#count{{font-size:12px;color:var(--muted);margin-top:12px;}}
</style>
</head>
<body>
<div class="wrap">
  <div style="display:flex;justify-content:space-between;align-items:baseline;">
    <h1>Git Steward</h1>
    <span style="font-size:12px;color:var(--muted);">{generated}</span>
  </div>

  <div class="stats-grid">
    <div class="stat-card"><div class="num">{totals.get("repos", 0)}</div><div class="label">repos</div></div>
    <div class="stat-card"><div class="num">{totals.get("dirty_repos", 0)}</div><div class="label">dirty</div></div>
    <div class="stat-card"><div class="num">{totals.get("ahead_repos", 0)}</div><div class="label">ahead</div></div>
    <div class="stat-card"><div class="num">{totals.get("stash_repos", 0)}</div><div class="label">stashes</div></div>
    <div class="stat-card"><div class="num">{totals.get("blocked_repos", 0)}</div><div class="label">blocked</div></div>
  </div>

  <div class="chart-section">
    <h2>Blocked breakdown</h2>
    {chart_svg}
  </div>

  <input id="search" type="text" placeholder="Filter repos…" autocomplete="off">

  <div class="repo-list" id="repos">
{rows}
  </div>
  <div id="count">{len(repos)} repos</div>
</div>

<script>
const input = document.getElementById('search');
const rows = document.querySelectorAll('.repo-row');
input.addEventListener('input', () => {{
  const q = input.value.toLowerCase();
  let n = 0;
  for (const row of rows) {{
    const match = row.textContent.toLowerCase().includes(q);
    row.style.display = match ? '' : 'none';
    if (match) n++;
  }}
  document.getElementById('count').textContent = n + ' repos';
}});
</script>
</body>
</html>
"""


def _blocked_chart(breakdown: Counter[str], total: int) -> str:
    if not breakdown or total == 0:
        return '<p style="color:var(--muted);font-size:12px;">No blocked repos.</p>'

    colors = {"fs_stall": "var(--chart-fs)", "status_error": "var(--chart-err)", "untracked_error": "var(--chart-err)"}
    bars = ""
    for reason, count in breakdown.most_common():
        pct = count / total * 100
        color = colors.get(reason, "var(--chart-other)")
        bars += f"""<div class="bar-row">
  <span class="bar-label">{reason}</span>
  <div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%;background:{color};"></div></div>
  <span class="bar-count">{count}</span>
</div>"""
    return bars


def _render_repo(repo: object) -> str:
    item = repo if isinstance(repo, dict) else {}

    state = "clean"
    if item.get("blocked_reason"):
        state = "blocked"
    elif item.get("dirty") or item.get("untracked"):
        state = "dirty"
    elif item.get("ahead"):
        state = "ahead"

    name = html.escape(str(item.get("display_name") or "unknown"))
    path_s = html.escape(str(item.get("path") or ""))
    reason = item.get("blocked_reason")
    dirty = item.get("dirty", 0) or 0
    untracked = item.get("untracked", 0) or 0
    ahead = item.get("ahead") or 0
    stash = item.get("stash_count", 0) or 0

    tags = ""
    if dirty or untracked:
        n = dirty + untracked
        tags += f'<span class="meta-tag dirty">{n} dirty</span>'
    if ahead:
        tags += f'<span class="meta-tag ahead">+{ahead}</span>'
    if stash:
        tags += f'<span class="meta-tag stash">{stash} stashed</span>'
    if reason:
        tags += f'<span class="meta-tag blocked">{html.escape(str(reason))}</span>'

    return f"""<div class="repo-row">
  <span class="repo-dot dot-{state}"></span>
  <span class="repo-name">{name}</span>
  <span class="repo-path">{path_s}</span>
  <div class="repo-meta">{tags}</div>
</div>"""

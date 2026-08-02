# ruff: noqa: E501

from __future__ import annotations

import html
import stat
from collections import Counter
from pathlib import Path
from typing import Any

from .config import Config
from .history import blocked_trend

DASHBOARD_META_REFRESH = 60


def render_dashboard(config: Config, summary: dict[str, Any]) -> Path:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.dashboard_html_path.write_text(
        render_html(summary, trend=blocked_trend(config.history_sqlite_path)),
        encoding="utf-8",
    )
    config.dashboard_html_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return config.dashboard_html_path


def render_html(
    summary: dict[str, Any],
    refresh_seconds: int = DASHBOARD_META_REFRESH,
    trend: list[tuple[str, int]] | None = None,
) -> str:
    totals = summary.get("totals", {})
    repos = summary.get("repos", [])
    generated = html.escape(str(summary.get("finished_at", "unknown")))

    blocked = [r for r in repos if r.get("blocked_reason")]
    dirty = [r for r in repos if not r.get("blocked_reason") and ((r.get("dirty") or 0) > 0 or r.get("untracked"))]
    clean = [r for r in repos if not r.get("blocked_reason") and not (r.get("dirty") or 0) and not r.get("untracked")]

    n_total = len(repos) or int(totals.get("repos", 0) or 0)
    n_blocked, n_dirty, n_clean = len(blocked), len(dirty), len(clean)
    healthy_pct = round((n_total - n_blocked) / n_total * 100) if n_total else 0

    reasons = Counter(r.get("blocked_reason") for r in blocked if r.get("blocked_reason"))
    chart = _blocked_chart(reasons, n_total)

    rows = (
        _section("BLOCKED", "blocked", n_blocked, blocked, "var(--err)")
        + _section("DIRTY", "dirty", n_dirty, dirty, "var(--warn)")
        + _section("CLEAN", "clean", n_clean, clean, "var(--ok)")
    )

    hero = _health_card(healthy_pct, n_clean, n_dirty, n_blocked, n_total)
    if trend and len(trend) >= 2:
        hero += _trend_card(trend)

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
  --bg:#0f1117;--panel:#181b23;--raised:#12141c;--border:#262a33;--border-hi:#3a4150;
  --fg:#e4e7eb;--fg-2:#9ca3af;--fg-3:#6b7280;
  --ok:#4ade80;--warn:#eab308;--err:#f97316;--info:#60a5fa;--stash:#c084fc;--accent:#a3e635;
  --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
}}
body[data-theme="light"]{{
  --bg:#f6f7f9;--panel:#ffffff;--raised:#eef0f3;--border:#e3e6ea;--border-hi:#c9ced6;
  --fg:#1a1d21;--fg-2:#5f6672;--fg-3:#8b929e;
  --ok:#16a34a;--warn:#ca8a04;--err:#c2410c;--info:#2563eb;--stash:#9333ea;--accent:#65a30d;
}}
html{{background:var(--bg)}}
body{{background:var(--bg);color:var(--fg);font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  -webkit-font-smoothing:antialiased}}
.wrap{{max-width:1180px;margin:0 auto;padding:28px 32px 56px}}
.num{{font-variant-numeric:tabular-nums}}

.top{{display:flex;align-items:center;gap:16px;padding-bottom:20px;border-bottom:1px solid var(--border)}}
.wordmark{{font:600 15px var(--mono);letter-spacing:-0.02em}}
.wordmark b{{color:var(--accent)}}
.scanned{{font:11px var(--mono);color:var(--fg-3);margin-left:auto}}
#theme{{background:var(--raised);border:1px solid var(--border);border-radius:6px;padding:6px 8px;
  display:inline-flex;align-items:center;color:var(--fg-2);cursor:pointer}}
#theme:hover{{color:var(--fg);border-color:var(--border-hi)}}
#theme svg{{display:block}}
#theme .icon-light{{display:none}}
body[data-theme="light"] #theme .icon-dark{{display:none}}
body[data-theme="light"] #theme .icon-light{{display:block}}

.hero{{display:grid;grid-template-columns:1.2fr 1fr;gap:16px;margin:20px 0 16px}}
.hero.single{{grid-template-columns:1fr}}
.card{{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:20px}}
.card h2{{font:600 11px var(--mono);color:var(--fg-2);text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px}}
.health-num{{font:600 44px var(--mono);letter-spacing:-0.03em;line-height:1}}
.health-num .pct{{color:var(--err)}}
.health-sub{{font:12px var(--mono);color:var(--fg-3);margin-top:6px}}
.stack{{display:flex;height:10px;border-radius:5px;overflow:hidden;margin:18px 0 12px;gap:1px;background:var(--raised)}}
.seg{{height:100%}}
.legend{{display:flex;gap:18px;font:11px var(--mono);color:var(--fg-2)}}
.legend i{{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px;vertical-align:0}}
.spark{{width:100%;height:96px;display:block}}
.spark-labels{{display:flex;justify-content:space-between;font:10px var(--mono);color:var(--fg-3);margin-top:4px}}
.spark-range{{display:flex;justify-content:space-between;font:10px var(--mono);color:var(--fg-3);margin-top:10px;
  padding-top:10px;border-top:1px solid var(--border)}}

.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-bottom:16px}}
.kpi{{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px 18px}}
.kpi .k-num{{font:600 22px var(--mono);letter-spacing:-0.02em}}
.kpi .k-label{{font:11px var(--mono);color:var(--fg-3);margin-top:3px}}
.kpi.err .k-num{{color:var(--err)}}.kpi.warn .k-num{{color:var(--warn)}}
.kpi.info .k-num{{color:var(--info)}}.kpi.stash .k-num{{color:var(--stash)}}

.row2{{display:grid;grid-template-columns:380px 1fr;gap:16px;margin-bottom:16px}}
.rbar{{margin-bottom:14px}}
.rbar-top{{display:flex;justify-content:space-between;font:12px var(--mono);margin-bottom:6px}}
.rbar-n{{color:var(--fg-2)}}
.rbar-track{{height:8px;background:var(--raised);border-radius:4px;overflow:hidden}}
.fill{{height:100%;border-radius:4px}}
.empty-text{{font:12px var(--mono);color:var(--fg-3)}}

.filters{{display:flex;gap:8px;align-items:center}}
.search{{flex:1;background:var(--raised);border:1px solid var(--border);border-radius:6px;padding:8px 12px;
  color:var(--fg);font:12px var(--mono);outline:none}}
.search::placeholder{{color:var(--fg-3)}}
.search:focus{{border-color:var(--accent)}}
.chip-btn{{background:var(--raised);border:1px solid var(--border);border-radius:6px;padding:7px 12px;
  font:11px var(--mono);color:var(--fg-2);cursor:pointer}}
.chip-btn:hover{{color:var(--fg)}}
.chip-btn.on{{background:var(--fg);color:var(--bg);border-color:var(--fg);font-weight:600}}

.table-card{{background:var(--panel);border:1px solid var(--border);border-radius:10px;overflow:hidden}}
.scroll{{max-height:430px;overflow-y:auto}}
table{{width:100%;border-collapse:collapse}}
thead th{{position:sticky;top:0;background:var(--raised);font:10px var(--mono);color:var(--fg-3);text-transform:uppercase;
  letter-spacing:.08em;text-align:left;padding:10px 14px;border-bottom:1px solid var(--border)}}
td{{padding:8px 14px;border-bottom:1px solid var(--border);font:12px var(--mono);white-space:nowrap;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:var(--raised)}}
tr.sec td{{background:var(--panel);padding:8px 14px;border-bottom:1px solid var(--border)}}
.sec-name{{font:700 11px var(--mono);letter-spacing:.06em}}
.sec-count{{font:11px var(--mono);color:var(--fg-3);margin-left:8px}}
.empty-row td{{color:var(--fg-3);font-style:italic}}
.c-dot{{width:20px;padding-right:0}}
.dot{{width:7px;height:7px;border-radius:50%;display:inline-block}}
.dot.blocked{{background:var(--err)}}.dot.dirty{{background:var(--warn)}}
.dot.ahead{{background:var(--info)}}.dot.clean{{background:var(--ok)}}
.c-name{{font-weight:600}}
.c-branch{{color:var(--fg-3)}}
.c-num{{text-align:right;min-width:40px;color:var(--fg-3)}}
.c-num.warn{{color:var(--warn);font-weight:600}}
.c-num.info{{color:var(--info)}}
.c-num.stash{{color:var(--stash)}}
.c-path{{color:var(--fg-3);max-width:360px;overflow:hidden;text-overflow:ellipsis}}
.c-reason{{text-align:right}}
.chip{{font:11px var(--mono);padding:2px 9px;border-radius:4px;border:1px solid;display:inline-block}}
.foot{{display:flex;justify-content:space-between;margin-top:14px;font:11px var(--mono);color:var(--fg-3)}}
.foot .refresh{{color:var(--accent)}}
.empty-all{{text-align:center;padding:48px 0;color:var(--fg-3);font:12px var(--mono)}}
</style>
</head>
<body data-theme="dark">
<div class="wrap">
  <div class="top">
    <div class="wordmark">git<b>-</b>steward</div>
    <span class="scanned">last scan {generated}</span>
    <button id="theme" type="button" aria-label="toggle light and dark theme">
      <svg class="icon-dark" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      <svg class="icon-light" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
    </button>
  </div>

  <div class="hero{' single' if not (trend and len(trend) >= 2) else ''}">
    {hero}
  </div>

  <div class="kpis">
    <div class="kpi"><div class="k-num num">{n_total}</div><div class="k-label">repos</div></div>
    <div class="kpi err"><div class="k-num num">{n_blocked}</div><div class="k-label">blocked</div></div>
    <div class="kpi warn"><div class="k-num num">{n_dirty}</div><div class="k-label">dirty</div></div>
    <div class="kpi info"><div class="k-num num">{totals.get("ahead_repos", 0)}</div><div class="k-label">ahead</div></div>
    <div class="kpi stash"><div class="k-num num">{totals.get("stash_repos", 0)}</div><div class="k-label">stashes</div></div>
  </div>

  <div class="row2">
    <div class="card">
      <h2>Blocked breakdown</h2>
      {chart}
    </div>
    <div class="card">
      <h2 style="margin-bottom:14px">Repos</h2>
      <div class="filters">
        <input id="search" class="search" type="text" placeholder="filter repos…" autocomplete="off">
        <button class="chip-btn on" data-chip="all">all</button>
        <button class="chip-btn" data-chip="blocked">blocked</button>
        <button class="chip-btn" data-chip="dirty">dirty</button>
        <button class="chip-btn" data-chip="clean">clean</button>
      </div>
      <div class="scroll" style="margin-top:14px;border:1px solid var(--border);border-radius:8px">
      <table>
        <thead><tr>
          <th></th><th>repo</th><th>branch</th><th style="text-align:right">dirty</th>
          <th style="text-align:right">ahead</th><th style="text-align:right">stash</th><th>path</th><th></th>
        </tr></thead>
        <tbody>
        {rows}
        </tbody>
      </table>
      </div>
      <div class="foot">
        <span id="count">{n_total} repos</span>
        <span class="refresh">auto-refresh 60s</span>
      </div>
    </div>
  </div>

  <div class="foot">
    <span>generated {generated} · {n_total} repos</span>
    <span>{' · '.join(f'{label} {count}' for label, count in [("blocked", n_blocked), ("dirty", n_dirty), ("clean", n_clean)] if count)}</span>
  </div>
</div>

<script>
const input = document.getElementById('search');
const countEl = document.getElementById('count');
let chip = 'all';

function apply() {{
  const q = input.value.toLowerCase();
  let n = 0;
  document.querySelectorAll('tbody tr').forEach(tr => {{
    const sec = tr.dataset.sec || '';
    if (tr.classList.contains('sec')) {{
      tr.style.display = (chip === 'all' || sec === chip) ? '' : 'none';
      return;
    }}
    const okSec = chip === 'all' || sec === chip;
    const okQ = tr.textContent.toLowerCase().includes(q);
    const show = okSec && okQ;
    tr.style.display = show ? '' : 'none';
    if (show && !tr.classList.contains('empty-row')) n++;
  }});
  countEl.textContent = n + ' repos';
}}

document.querySelectorAll('.chip-btn').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('.chip-btn').forEach(x => x.classList.remove('on'));
  b.classList.add('on');
  chip = b.dataset.chip;
  apply();
}}));
input.addEventListener('input', apply);

const tbtn = document.getElementById('theme');
function setTheme(m) {{ document.body.dataset.theme = m; }}
tbtn.addEventListener('click', () => setTheme(document.body.dataset.theme === 'dark' ? 'light' : 'dark'));
setTheme('dark');
</script>
</body>
</html>
"""


def _health_card(healthy_pct: int, n_clean: int, n_dirty: int, n_blocked: int, n_total: int) -> str:
    def pct(n: int) -> float:
        return (n / n_total * 100) if n_total else 0

    return f"""<div class="card">
      <h2>Health</h2>
      <div class="health-num num"><span class="pct">{healthy_pct}%</span></div>
      <div class="health-sub num">{n_clean} clean · {n_dirty} dirty · {n_blocked} blocked of {n_total} repos</div>
      <div class="stack">
        <div class="seg" style="width:{pct(n_blocked):.2f}%;background:var(--err)"></div>
        <div class="seg" style="width:{pct(n_dirty):.2f}%;background:var(--warn)"></div>
        <div class="seg" style="width:{pct(n_clean):.2f}%;background:var(--ok)"></div>
      </div>
      <div class="legend">
        <span><i style="background:var(--ok)"></i>clean</span>
        <span><i style="background:var(--warn)"></i>dirty</span>
        <span><i style="background:var(--err)"></i>blocked</span>
      </div>
    </div>"""


def _trend_card(trend: list[tuple[str, int]]) -> str:
    w, h = 320, 72
    pad = 4
    xs = [i / (len(trend) - 1) * (w - 2 * pad) + pad for i in range(len(trend))]
    lo = min(v for _, v in trend)
    hi = max(v for _, v in trend)
    span = max(hi - lo, 1)
    ys = [h - pad - (v - lo) / span * (h - 2 * pad) for _, v in trend]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    fill = f"{pts} {xs[-1]:.1f},{h} {xs[0]:.1f},{h}"
    first_ts = trend[0][0].replace("T", " ")[5:16]
    last_ts = trend[-1][0].replace("T", " ")[5:16]
    return f"""<div class="card">
      <h2>Blocked over recent scans</h2>
      <svg viewBox="0 0 {w} {h}" class="spark">
        <defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" style="stop-color:var(--err);stop-opacity:.25"/>
          <stop offset="1" style="stop-color:var(--err);stop-opacity:0"/>
        </linearGradient></defs>
        <polygon points="{fill}" fill="url(#sg)"/>
        <polyline points="{pts}" fill="none" stroke="var(--err)" stroke-width="1.5"/>
      </svg>
      <div class="spark-labels num"><span>min {lo}</span><span>max {hi}</span></div>
      <div class="spark-range num"><span>{html.escape(first_ts)}</span><span>{html.escape(last_ts)}</span><span>{len(trend)} scans</span></div>
    </div>"""


def _blocked_chart(breakdown: Counter[str], total: int) -> str:
    if not breakdown or total == 0:
        return '<p class="empty-text">No blocked repos.</p>'

    colors = {
        "fs_stall": "#94a3b8",
        "quarantined_by_config": "var(--warn)",
        "suspect_untracked": "var(--warn)",
    }
    bars = ""
    for reason, count in breakdown.most_common():
        pct = count / total * 100
        color = colors.get(reason, "var(--err)")
        bars += f"""<div class="rbar"><div class="rbar-top"><span style="color:{color}">{html.escape(str(reason))}</span>
        <span class="rbar-n">{count}</span></div>
        <div class="rbar-track"><div class="fill" style="width:{pct:.1f}%;background:{color}"></div></div></div>"""
    return bars


def _section(title: str, key: str, count: int, repos: list[dict[str, Any]], accent: str) -> str:
    head = (
        f'<tr class="sec" data-sec="{key}"><td colspan="8">'
        f'<span class="sec-name" style="color:{accent}">{title}</span>'
        f'<span class="sec-count">{count}</span></td></tr>'
    )
    if count == 0:
        return head + f'<tr class="empty-row" data-sec="{key}"><td colspan="8">no {title.lower()} repos right now</td></tr>'
    if key == "blocked":
        repos = sorted(repos, key=lambda r: str(r.get("display_name") or ""))
    elif key == "dirty":
        repos = sorted(repos, key=lambda r: -((r.get("dirty") or 0) + (r.get("untracked") or 0)))
    else:
        repos = sorted(repos, key=lambda r: str(r.get("display_name") or ""))
    return head + "".join(_render_repo(r, key) for r in repos)


def _render_repo(repo: dict[str, Any], section_key: str) -> str:
    reason = repo.get("blocked_reason")
    dirty_n = (repo.get("dirty") or 0) + (repo.get("untracked") or 0)
    ahead = repo.get("ahead") or 0
    stash = repo.get("stash_count") or 0

    if reason:
        state = "blocked"
    elif dirty_n:
        state = "dirty"
    elif ahead:
        state = "ahead"
    else:
        state = "clean"

    name = html.escape(str(repo.get("display_name") or "unknown"))
    path = html.escape(str(repo.get("path") or ""))
    branch = html.escape(str(repo.get("branch") or "—"))

    chips = ""
    if reason:
        chips = f'<td class="c-reason">{_reason_chip(reason)}</td>'
    else:
        chips = '<td class="c-reason"></td>'

    return f"""<tr data-sec="{section_key}">
  <td class="c-dot"><span class="dot {state}"></span></td>
  <td class="c-name">{name}</td>
  <td class="c-branch">{branch}</td>
  <td class="c-num{' warn' if dirty_n else ''}">{dirty_n if dirty_n else ''}</td>
  <td class="c-num{' info' if ahead else ''}">{ahead if ahead else ''}</td>
  <td class="c-num{' stash' if stash else ''}">{stash if stash else ''}</td>
  <td class="c-path">{path}</td>
  {chips}
</tr>"""


def _reason_chip(reason: object) -> str:
    label = html.escape(str(reason))
    color = "var(--err)"
    if reason == "fs_stall":
        label, color = "fs stall (iCloud)", "#94a3b8"
    elif reason == "quarantined_by_config":
        label, color = "quarantined", "var(--warn)"
    elif reason == "suspect_untracked":
        label, color = "suspect untracked", "var(--warn)"
    elif reason == "status_error":
        label = "status error"
    return f'<span class="chip" style="color:{color};border-color:currentColor;background:transparent">{label}</span>'

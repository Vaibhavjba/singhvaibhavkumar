#!/usr/bin/env python3
"""
sanity_report_generator.py

Generates a standalone Plotly HTML report from a sanity_results.json file.
The JSON schema matches the output of ArcGIS Enterprise upgrade validation suites:
  {
    "pre_upgrade":  { "CATEGORY: Test Name": {"status": "PASS"|"FAIL", "message": "..."}, ... },
    "post_upgrade": { "CATEGORY: Test Name": {"status": "PASS"|"FAIL", "message": "..."}, ... }
  }

Includes:
  - Summary stats (executed / pass / fail / post-only)
  - Pass rate progress bar
  - Pre vs post delta table (highlights regressions and fixes)
  - Category breakdown bar chart (Plotly)
  - Failures detail section

Usage:
    python sanity_report_generator.py --input sanity_results_sample.json
    python sanity_report_generator.py --input sanity_results.json --output report.html --title "Build 8230"

Requirements:
    pip install plotly
"""

import argparse
import json
import pathlib
import sys
from collections import defaultdict
from typing import Optional

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("WARNING  plotly not installed — category chart will be skipped. pip install plotly")


# ── Category colour palette (consistent with email template) ─────────────────
CAT_COLORS: dict[str, str] = {
    "ADMIN API":        "#6366F1",
    "NOTEBOOK":         "#8B5CF6",
    "RASTER":           "#7C3AED",
    "SERVICES":         "#0EA5E9",
    "LOGGING":          "#64748B",
    "SECURITY":         "#DC2626",
    "PORTAL HOME":      "#0284C7",
    "SOE/SOI":          "#0369A1",
    "GP SERVICES":      "#D97706",
    "PUBLISHING":       "#B45309",
    "IMAGE SERVICES":   "#059669",
    "NETWORK ANALYSIS": "#0D9488",
    "GEOCODE SERVICES": "#0891B2",
    "UI TEST":          "#7C3AED",
    "DATASTORE":        "#475569",
    "UPGRADE":          "#EA580C",
    "GENERAL":          "#94A3B8",
}

STATUS_COLOR = {"PASS": "#059669", "FAIL": "#DC2626"}


def load_phase(data: dict, key: str) -> dict:
    """Load a phase from the JSON — handles both raw dict and JSON-encoded string."""
    val = data.get(key, {})
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except json.JSONDecodeError:
            val = {}
    return val or {}


def category_of(key: str) -> str:
    return key.split(":")[0].strip() if ":" in key else "GENERAL"


def cat_color(category: str) -> str:
    return CAT_COLORS.get(category.upper(), CAT_COLORS["GENERAL"])


# ── Report builder ────────────────────────────────────────────────────────────
def build_report(data: dict, title: str) -> str:
    pre  = load_phase(data, "pre_upgrade")
    post = load_phase(data, "post_upgrade")

    all_keys = sorted(set(list(pre.keys()) + list(post.keys())))

    rows = []
    for k in all_keys:
        pre_entry  = pre.get(k, {})
        post_entry = post.get(k, {})
        pre_s  = pre_entry.get("status", "—")
        post_s = post_entry.get("status", "—")
        cat    = category_of(k)

        # Determine phase membership
        in_pre  = k in pre
        in_post = k in post
        phase   = ("BOTH" if in_pre and in_post
                   else "PRE" if in_pre else "POST")

        # Detect regression / fix
        delta = "—"
        if pre_s == "PASS" and post_s == "FAIL":
            delta = "🔴 Regression"
        elif pre_s == "FAIL" and post_s == "PASS":
            delta = "🟢 Fixed"
        elif pre_s == post_s:
            delta = "No change"

        rows.append({
            "test":     k,
            "category": cat,
            "pre":      pre_s,
            "post":     post_s,
            "phase":    phase,
            "delta":    delta,
            "pre_msg":  pre_entry.get("message", ""),
            "post_msg": post_entry.get("message", ""),
        })

    # ── Stats ─────────────────────────────────────────────────────────────
    pre_total  = len(pre)
    post_total = len(post)
    pre_pass   = sum(1 for r in rows if r["pre"]  == "PASS")
    pre_fail   = sum(1 for r in rows if r["pre"]  == "FAIL")
    post_pass  = sum(1 for r in rows if r["post"] == "PASS")
    post_fail  = sum(1 for r in rows if r["post"] == "FAIL")
    post_only  = sum(1 for r in rows if r["phase"] == "POST")
    total_fail = pre_fail + post_fail
    total_exec = pre_total + post_only   # unique test runs
    pass_rate  = round(100 * (pre_pass + post_pass) / max(pre_total + post_total, 1), 1)

    failures   = [r for r in rows if r["pre"] == "FAIL" or r["post"] == "FAIL"]

    # ── Category chart (Plotly) ───────────────────────────────────────────
    chart_html = ""
    if PLOTLY_AVAILABLE:
        by_cat: dict[str, dict] = defaultdict(lambda: {"pass": 0, "fail": 0})
        for r in rows:
            if r["pre"]  == "PASS": by_cat[r["category"]]["pass"] += 1
            if r["pre"]  == "FAIL": by_cat[r["category"]]["fail"] += 1
            if r["post"] == "PASS": by_cat[r["category"]]["pass"] += 1
            if r["post"] == "FAIL": by_cat[r["category"]]["fail"] += 1

        cats   = sorted(by_cat.keys())
        passes = [by_cat[c]["pass"] for c in cats]
        fails  = [by_cat[c]["fail"] for c in cats]
        colors = [cat_color(c) for c in cats]

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Pass", x=cats, y=passes,
                             marker_color="#059669", opacity=0.85))
        fig.add_trace(go.Bar(name="Fail", x=cats, y=fails,
                             marker_color="#DC2626", opacity=0.85))
        fig.update_layout(
            barmode="stack", title="Results by Category",
            xaxis_tickangle=-30,
            plot_bgcolor="#fff", paper_bgcolor="#F8FAFC",
            font=dict(family="system-ui, sans-serif", size=12),
            margin=dict(l=40, r=40, t=50, b=120),
            height=380,
        )
        chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    # ── Table rows HTML ───────────────────────────────────────────────────
    def status_span(s: str) -> str:
        c = STATUS_COLOR.get(s, "#94A3B8")
        return f'<span style="color:{c};font-weight:600">{s}</span>'

    def phase_badge(p: str) -> str:
        colors = {"BOTH": "#6366F1", "PRE": "#0369A1", "POST": "#059669"}
        c = colors.get(p, "#94A3B8")
        return (f'<span style="display:inline-block;padding:1px 8px;border-radius:20px;'
                f'background:{c}22;color:{c};font-size:11px;font-weight:600">{p}</span>')

    table_rows = ""
    for r in rows:
        if r["pre"] == "FAIL" or r["post"] == "FAIL":
            row_bg = 'background:#FFF5F5'
        elif r["delta"] == "🟢 Fixed":
            row_bg = 'background:#F0FDF4'
        else:
            row_bg = ''

        c = cat_color(r["category"])
        cat_pill = (f'<span style="display:inline-block;padding:1px 8px;border-radius:20px;'
                    f'background:{c}22;color:{c};font-size:11px">{r["category"]}</span>')

        table_rows += (
            f'<tr style="{row_bg}">'
            f'<td style="padding:7px 10px">{cat_pill}</td>'
            f'<td style="padding:7px 10px;font-size:12px">{r["test"]}</td>'
            f'<td style="padding:7px 10px;text-align:center">{phase_badge(r["phase"])}</td>'
            f'<td style="padding:7px 10px;text-align:center">{status_span(r["pre"])}</td>'
            f'<td style="padding:7px 10px;text-align:center">{status_span(r["post"])}</td>'
            f'<td style="padding:7px 10px;font-size:11px;color:#64748B">{r["delta"]}</td>'
            f'</tr>\n'
        )

    # ── Progress bar ─────────────────────────────────────────────────────
    if total_fail == 0:
        bar_html = '<div style="height:8px;border-radius:4px;background:linear-gradient(90deg,#059669,#34D399);"></div>'
        bar_label = f'<span style="color:#059669;font-weight:600">{pass_rate}% — All tests passed</span>'
    else:
        pass_pct = pass_rate
        fail_pct = round(100 - pass_pct, 1)
        bar_html = (
            f'<div style="height:8px;border-radius:4px;overflow:hidden;display:flex;">'
            f'<div style="flex:{pass_pct};background:#059669;"></div>'
            f'<div style="flex:{fail_pct};background:#DC2626;"></div>'
            f'</div>'
        )
        bar_label = f'<span style="color:#DC2626;font-weight:600">{pass_rate}% passed — {total_fail} failure(s)</span>'

    # ── Full HTML ─────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sanity Report — {title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
         background: #F0F4F8; color: #1E293B; font-size: 14px; padding: 28px; }}
  .card {{ background: #fff; border-radius: 12px; box-shadow: 0 2px 16px rgba(0,0,0,0.07);
           max-width: 1100px; margin: 0 auto 24px; overflow: hidden; }}
  .header {{ padding: 22px 28px 16px; border-bottom: 1px solid #F1F5F9; }}
  h1 {{ font-size: 20px; font-weight: 700; color: #0F172A; }}
  h2 {{ font-size: 14px; font-weight: 700; color: #334155; margin-bottom: 12px; }}
  .meta {{ font-size: 12px; color: #94A3B8; margin-top: 5px; }}
  .stats {{ display: flex; gap: 12px; padding: 20px 28px; border-bottom: 1px solid #F1F5F9; }}
  .stat {{ flex: 1; text-align: center; padding: 14px 8px; border-radius: 10px; border: 1px solid #E2E8F0; }}
  .stat .n {{ font-size: 28px; font-weight: 800; line-height: 1; }}
  .stat .label {{ font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
                  margin-top: 5px; color: #94A3B8; }}
  .section {{ padding: 20px 28px; border-bottom: 1px solid #F1F5F9; }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead th {{ background: #F8FAFC; padding: 9px 10px; text-align: left; font-size: 11px;
              font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #64748B;
              border-bottom: 2px solid #E2E8F0; }}
  tbody tr:hover {{ background: #F8FAFC; }}
  .bar-section {{ padding: 0 28px 20px; }}
  .bar-label {{ display: flex; justify-content: space-between; font-size: 12px; color: #64748B; margin-bottom: 6px; }}
</style>
</head>
<body>

<div class="card">
  <div style="height:4px;background:{'linear-gradient(90deg,#059669,#34D399)' if total_fail == 0 else 'linear-gradient(90deg,#059669 {0}%,#DC2626 {0}%)'.format(pass_rate)};"></div>
  <div class="header">
    <h1>Sanity Report &mdash; {title}</h1>
    <div class="meta">Pre-upgrade: {pre_total} tests &nbsp;|&nbsp; Post-upgrade: {post_total} tests</div>
  </div>

  <!-- Stats -->
  <div class="stats">
    <div class="stat"><div class="n" style="color:#6366F1">{total_exec}</div><div class="label">Executed</div></div>
    <div class="stat"><div class="n" style="color:#059669">{pre_pass + post_pass}</div><div class="label">Passed</div></div>
    <div class="stat"><div class="n" style="color:#DC2626">{total_fail}</div><div class="label">Failed</div></div>
    <div class="stat"><div class="n" style="color:#94A3B8">{post_only}</div><div class="label">Post-Only</div></div>
  </div>

  <!-- Pass rate bar -->
  <div class="bar-section" style="padding-top:20px;">
    <div class="bar-label"><span>Pass rate</span>{bar_label}</div>
    {bar_html}
  </div>
</div>

<!-- Chart -->
{f'<div class="card"><div class="section">{chart_html}</div></div>' if chart_html else ''}

<!-- Full results table -->
<div class="card">
  <div class="section">
    <h2>All Test Results</h2>
    <table>
      <thead>
        <tr>
          <th>Category</th><th>Test</th><th>Phase</th>
          <th style="text-align:center">Pre</th>
          <th style="text-align:center">Post</th>
          <th>Delta</th>
        </tr>
      </thead>
      <tbody>
        {table_rows}
      </tbody>
    </table>
  </div>
</div>

</body>
</html>"""

    return html


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Plotly HTML sanity report from a sanity_results.json file"
    )
    parser.add_argument("--input",  required=True, help="Path to sanity_results.json")
    parser.add_argument("--output", default="report.html", help="Output HTML file (default: report.html)")
    parser.add_argument("--title",  default="", help="Report title (e.g. 'Build 8230')")
    args = parser.parse_args()

    try:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR  Input file not found: {args.input}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR  Invalid JSON: {exc}")
        sys.exit(1)

    title = args.title or pathlib.Path(args.input).stem
    html  = build_report(data, title)
    pathlib.Path(args.output).write_text(html, encoding="utf-8")
    print(f"Report written → {args.output}")


if __name__ == "__main__":
    main()

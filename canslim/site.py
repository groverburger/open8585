"""Static-site generation: the weekly list page, the full-universe ratings
spreadsheet, and the project page for groverburger.xyz.

The canslim-8585 GitHub Pages site (force-pushed `site` branch) hosts the
heavy artifacts — per-stock charts and the full sortable ratings table.
The groverburger.xyz page is a small self-contained HTML file regenerated
weekly and committed to the site repo (which deploys via GitHub Pages).
"""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

PAGES_BASE = "https://groverburger.github.io/canslim-8585"
REPO_URL = "https://github.com/groverburger/canslim-8585"

DISCLAIMER = (
    "Educational reconstruction of a proprietary methodology from public data; "
    "ratings are approximations. Not investment advice. Not affiliated with "
    "Investor's Business Daily or William O'Neil + Co."
)

_BASE_CSS = """
:root { --ink:#0b0b0b; --ink2:#52514e; --muted:#898781; --line:#e1e0d9;
        --surface:#fcfcfb; --up:#2a78d6; --down:#e34948; }
* { box-sizing:border-box; }
body { font-family:system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--ink);
       background:var(--surface); margin:0 auto; max-width:1080px; padding:24px 16px; }
h1 { font-size:1.5rem; margin:0 0 4px; } h2 { font-size:1.1rem; margin:28px 0 8px; }
p { color:var(--ink2); line-height:1.5; } a { color:var(--up); }
.meta { color:var(--muted); font-size:0.85rem; }
.gate { display:inline-block; padding:4px 10px; border-radius:6px; font-weight:700;
        font-size:0.9rem; margin:8px 0; }
.gate.on  { background:#e7f0fb; color:#1c5cab; }
.gate.off { background:#fbeaea; color:#a83232; }
table { border-collapse:collapse; width:100%; font-size:0.85rem; }
th,td { padding:5px 8px; text-align:right; border-bottom:1px solid var(--line);
        white-space:nowrap; }
th { color:var(--ink2); position:sticky; top:0; background:var(--surface); cursor:pointer; }
td:nth-child(-n+3), th:nth-child(-n+3) { text-align:left; }
tr:hover td { background:#f4f3f0; }
.new { color:#006300; font-weight:700; font-size:0.75rem; }
.pos { color:#006300; } .neg { color:#a83232; }
.disclaimer { color:var(--muted); font-size:0.78rem; margin-top:32px; }
input.filter { padding:6px 10px; margin:8px 0; width:260px; border:1px solid var(--line);
               border-radius:6px; background:var(--surface); color:var(--ink);
               font-size:0.9rem; }
img.chart { max-width:100%; height:auto; border:1px solid var(--line); border-radius:6px; }
"""

_SORT_JS = """
document.querySelectorAll("th").forEach((th, i) => th.addEventListener("click", () => {
  const tb = th.closest("table").tBodies[0];
  const dir = th.dataset.dir = th.dataset.dir === "asc" ? "desc" : "asc";
  const rows = [...tb.rows].sort((a, b) => {
    const [x, y] = [a.cells[i].dataset.v ?? a.cells[i].textContent,
                    b.cells[i].dataset.v ?? b.cells[i].textContent];
    const [nx, ny] = [parseFloat(x), parseFloat(y)];
    const cmp = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : String(x).localeCompare(String(y));
    return dir === "asc" ? cmp : -cmp;
  });
  rows.forEach(r => tb.appendChild(r));
}));
const box = document.querySelector("input.filter");
if (box) box.addEventListener("input", () => {
  const q = box.value.toLowerCase();
  document.querySelectorAll("tbody tr").forEach(r =>
    r.style.display = r.textContent.toLowerCase().includes(q) ? "" : "none");
});
"""


def _fmt(val, kind="num"):
    if pd.isna(val):
        return "<td>–</td>"
    if kind == "chg":
        cls = "pos" if val >= 0 else "neg"
        return f'<td class="{cls}" data-v="{val:.2f}">{val:+.1f}</td>'
    if kind == "int":
        return f'<td data-v="{int(val)}">{int(val)}</td>'
    if kind == "cap999":
        v = max(min(val, 999), -999)
        return f'<td data-v="{v:.0f}">{v:.0f}</td>'
    return f'<td data-v="{val:.2f}">{val:,.2f}</td>'


def _screen_rows(screen: pd.DataFrame, debuts: set[str], chart_base: str) -> str:
    rows = []
    for _, r in screen.iterrows():
        star = ' <span class="new">NEW</span>' if r["symbol"] in debuts else ""
        name = html.escape(str(r.get("name", ""))[:40])
        industry = html.escape(str(r.get("industry", ""))[:38])
        rows.append(
            "<tr>"
            f'<td data-v="{r["symbol"]}"><a href="{chart_base}/{r["symbol"]}.png">{r["symbol"]}</a>{star}</td>'
            f"<td>{name}</td><td>{industry}</td>"
            + _fmt(r.get("industry_rank"), "int")
            + _fmt(r.get("price"))
            + _fmt(r.get("price_day_chg"), "chg")
            + _fmt(r.get("vol_pct_chg"), "chg")
            + _fmt(r.get("eps_q0_growth"), "cap999")
            + _fmt(r.get("sales_growth"), "cap999")
            + _fmt(r.get("rs_rating"), "int")
            + _fmt(r.get("eps_rating"), "int")
            + f'<td data-v="{r.get("ad_rating") or ""}">{r.get("ad_rating") or "–"}</td>'
            + "</tr>"
        )
    return "\n".join(rows)


SCREEN_HEADERS = ("Symbol,Company,Industry Group,Grp Rank,Price,Price %Chg,Vol %Chg,"
                  "EPS %Chg,Sales %Chg,RS,EPS,A/D").split(",")


def _table(headers: list[str], body: str) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    return f"<table><thead><tr>{head}</tr></thead><tbody>\n{body}\n</tbody></table>"


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>{_BASE_CSS}</style>\n</head>\n<body>\n"
        f"{body}\n<script>{_SORT_JS}</script>\n</body>\n</html>\n"
    )


def gate_banner(gate_on: bool) -> str:
    if gate_on:
        return '<span class="gate on">85-85 index above its 50-day line — market gate ON</span>'
    return '<span class="gate off">85-85 index below its 50-day line — market gate OFF</span>'


def build_pages_site(screen: pd.DataFrame, rated: pd.DataFrame, debuts: set[str],
                     dropoffs: set[str], run_date: str, gate_on: bool, site_dir: Path) -> None:
    """index.html + ratings.html + data files for the canslim-8585 Pages branch."""
    site_dir = Path(site_dir)
    (site_dir / "data").mkdir(parents=True, exist_ok=True)

    drop_note = ""
    if dropoffs:
        drop_note = ("<p class='meta'>Dropped since last week: "
                     + ", ".join(sorted(dropoffs)) + "</p>")
    body = (
        f"<h1>The open 85-85 list</h1>"
        f'<p class="meta">Computed {run_date} · {len(screen)} stocks · '
        f'<a href="{REPO_URL}">methodology &amp; source</a> · '
        f'<a href="ratings.html">full ratings table</a></p>'
        f"<p>Stocks with EPS and RS ratings of 85+ (percentile-ranked 1&ndash;99 against "
        f"the full US stock universe), priced $10+, within 15% of their 52-week closing "
        f"high, average volume 10,000+ shares. Click a symbol for its weekly chart.</p>"
        + gate_banner(gate_on)
        + f'<div><img class="chart" src="charts/_index.png" alt="85-85 index with 50-day moving average"></div>'
        + drop_note
        + _table(SCREEN_HEADERS, _screen_rows(screen, debuts, "charts"))
        + f'<p class="disclaimer">{DISCLAIMER}</p>'
    )
    (site_dir / "index.html").write_text(_page("The open 85-85 list", body))

    rcols = rated.dropna(subset=["rs_rating"]).sort_values("rs_rating", ascending=False)
    rows = []
    for _, r in rcols.iterrows():
        rows.append(
            "<tr>"
            f'<td data-v="{r["symbol"]}">{r["symbol"]}</td>'
            f'<td>{html.escape(str(r.get("name", ""))[:40])}</td>'
            f'<td>{html.escape(str(r.get("industry", ""))[:38])}</td>'
            + _fmt(r.get("price")) + _fmt(r.get("pct_off_high"), "chg")
            + _fmt(r.get("rs_rating"), "int")
            + (_fmt(r.get("eps_rating"), "int") if "eps_rating" in r and pd.notna(r.get("eps_rating")) else "<td>–</td>")
            + f'<td data-v="{r.get("ad_rating") or ""}">{r.get("ad_rating") or "–"}</td>'
            + _fmt(r.get("industry_rank"), "int")
            + "</tr>"
        )
    rbody = (
        f"<h1>Full ratings table</h1>"
        f'<p class="meta">Computed {run_date} · {len(rcols)} stocks · '
        f'<a href="index.html">the 85-85 list</a> · <a href="{REPO_URL}">methodology</a></p>'
        '<input class="filter" placeholder="Filter by symbol, name, industry…">'
        + _table(["Symbol", "Company", "Industry", "Price", "% off high", "RS", "EPS", "A/D", "Grp Rank"],
                 "\n".join(rows))
        + f'<p class="disclaimer">{DISCLAIMER}</p>'
    )
    (site_dir / "ratings.html").write_text(_page("Full ratings — open 85-85", rbody))

    screen.to_csv(site_dir / "data" / f"screen_{run_date}.csv", index=False)
    keep = [c for c in ("symbol", "name", "industry", "industry_rank", "price", "pct_off_high",
                        "rs_rating", "eps_rating", "ad_rating") if c in rated.columns]
    rated[keep].to_csv(site_dir / "data" / f"ratings_{run_date}.csv", index=False)


def build_groverburger_page(screen: pd.DataFrame, debuts: set[str], run_date: str,
                            gate_on: bool) -> str:
    """The projects/canslim-8585 page for groverburger.xyz — self-contained,
    matches the site's hand-written template conventions, works without JS."""
    table = _table(SCREEN_HEADERS, _screen_rows(screen, debuts, f"{PAGES_BASE}/charts"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Open 85-85 — Zach Booth</title>
<meta name="description" content="An open-source reconstruction of IBD's proprietary CANSLIM ratings — RS, EPS, and Accumulation/Distribution — recomputed weekly from free data.">
<link rel="icon" href="/static/images/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/css/style.css">
<style>{_BASE_CSS}
body {{ max-width:none; padding:0; }}
.list-wrap {{ overflow-x:auto; }}
</style>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>

<header class="site-head wrap">
  <a class="site-name" href="/">Zach Booth<span class="handle">groverburger</span></a>
  <nav class="site-nav" aria-label="Site">
    <a href="/#work" aria-current="page">Work</a>
    <a href="/notes.html">Notes</a>
    <a href="/#contact">Contact</a>
  </nav>
</header>

<main id="main">

  <section class="detail-hero wrap">
    <p class="kicker">Project</p>
    <h1 class="display">The Open 85-85</h1>
  </section>

  <section class="wrap">
    <div class="feature-text" data-reveal>
      <p class="dek">An open-source reconstruction of IBD&rsquo;s proprietary CANSLIM ratings &mdash; Relative Strength, EPS, and Accumulation/Distribution &mdash; recomputed weekly from free data by a GitHub Action.</p>
    </div>

    <dl class="detail-facts" data-reveal>
      <div>
        <dt>Stack</dt>
        <dd>Python &middot; pandas &middot; GitHub Actions</dd>
      </div>
      <div>
        <dt>Type</dt>
        <dd>Open-source screener &amp; weekly list</dd>
      </div>
      <div>
        <dt>Updated</dt>
        <dd>{run_date}</dd>
      </div>
    </dl>

    <div class="prose" data-reveal>
      <p>William O&rsquo;Neil&rsquo;s 85-85 list screens for stocks rated 85 or better on both Earnings Per Share and Relative Price Strength &mdash; ratings IBD has kept proprietary for four decades. This project reverse-engineers the methodology: every rating is a percentile rank (1&ndash;99) computed against the full US stock universe from free public data, validated against captured IBD lists and per-stock rating vectors. The formulas, the validation work, and every divergence from IBD&rsquo;s numbers are documented in the repository.</p>
      <p>The list below regenerates every Saturday. <strong>NEW</strong> marks stocks debuting on the list this week &mdash; historically the highest-signal event in the methodology. Symbols link to weekly charts; the <a href="{PAGES_BASE}/ratings.html">full ratings table</a> covers all ~5,400 rated stocks.</p>
    </div>

    <div class="feature-text" data-reveal>
      {gate_banner(gate_on)}
    </div>

    <div class="list-wrap" data-reveal>
      {table}
    </div>

    <div class="feature-text" data-reveal>
      <div class="fact-row">
        <a class="cta" href="{REPO_URL}">GitHub Repository</a>
        <a class="cta" href="{PAGES_BASE}/ratings.html">Full ratings table</a>
      </div>
    </div>

    <p class="disclaimer">{DISCLAIMER}</p>

    <p class="note-more"><a class="backlink" href="/#work">&larr; Back to work</a></p>
  </section>

</main>

<footer class="site-foot wrap">
  <span>&copy; 2026 Zach Booth</span>
  <span>Hand-built HTML, CSS, and 50 lines of JS. No frameworks.</span>
</footer>
</body>
</html>
"""

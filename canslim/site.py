"""Static-site generation: the weekly list page and the full-universe
ratings spreadsheet, published to the repo's GitHub Pages (`site` branch).

Tables are set in Berkeley Mono with tabular figures. The filter box
accepts stackable expressions ANDed together, e.g.:

    semiconductor rs>=90 eps>=85 ad>=B-

Bare words text-match symbol/name/industry; `col>=value` (also >, <=, <,
=) compares numeric columns; A/D grades compare on the A+..E- scale.
"""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

REPO_URL = "https://github.com/groverburger/canslim-8585"

DISCLAIMER = (
    "Educational reconstruction of a proprietary methodology from public data; "
    "ratings are approximations. Not investment advice. Not affiliated with "
    "Investor's Business Daily or William O'Neil + Co."
)

_CSS = """
@font-face { font-family:"Berkeley Mono"; src:url("fonts/BerkeleyMono-Regular.woff2") format("woff2");
             font-weight:400; font-display:swap; }
@font-face { font-family:"Berkeley Mono"; src:url("fonts/BerkeleyMono-Bold.woff2") format("woff2");
             font-weight:700; font-display:swap; }
:root { --ink:#0b0b0b; --ink2:#52514e; --muted:#898781; --line:#e1e0d9;
        --surface:#fcfcfb; --accent:#2a78d6; --down:#a83232; --up-t:#006300; }
* { box-sizing:border-box; }
body { font-family:"Berkeley Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
       color:var(--ink); background:var(--surface); margin:0; padding:18px 20px;
       font-size:13px; }
h1 { font-size:17px; margin:0 0 2px; }
p { color:var(--ink2); line-height:1.45; max-width:88ch; margin:6px 0; }
a { color:var(--accent); }
.meta { color:var(--muted); font-size:12px; }
input.filter { font:inherit; padding:5px 9px; margin:10px 0 6px; width:min(560px,100%);
               border:1px solid var(--line); border-radius:4px;
               background:var(--surface); color:var(--ink); }
.hint { color:var(--muted); font-size:11px; margin:0 0 8px; }
.count { color:var(--ink2); font-size:12px; margin-left:8px; }
.tbl { overflow-x:auto; }
table { border-collapse:collapse; font-variant-numeric:tabular-nums; }
th,td { padding:3px 9px; text-align:right; border-bottom:1px solid var(--line);
        white-space:nowrap; }
th { color:var(--ink2); font-weight:700; position:sticky; top:0;
     background:var(--surface); cursor:pointer; user-select:none; }
th:after { content:""; }
th.asc:after { content:" \\2191"; } th.desc:after { content:" \\2193"; }
td.l, th.l { text-align:left; }
tr:hover td { background:#f4f3f0; }
.new { color:var(--up-t); font-weight:700; font-size:11px; }
.pos { color:var(--up-t); } .neg { color:var(--down); }
.disclaimer { color:var(--muted); font-size:11px; margin-top:28px; max-width:88ch; }
"""

_JS = """
const SCALE = ["A+","A","A-","B+","B","B-","C+","C","C-","D+","D","D-","E+","E","E-"];
const gradeRank = g => { const i = SCALE.indexOf(g); return i < 0 ? 99 : i; };

function headers(table) {
  return [...table.tHead.rows[0].cells].map(th => ({
    key: th.dataset.key, type: th.dataset.type || "text", el: th }));
}

// --- sorting ---
document.querySelectorAll("table").forEach(table => {
  const hs = headers(table);
  hs.forEach((h, i) => h.el.addEventListener("click", () => {
    const dir = h.el.classList.contains("asc") ? "desc" : "asc";
    hs.forEach(x => x.el.classList.remove("asc", "desc"));
    h.el.classList.add(dir);
    const rows = [...table.tBodies[0].rows].sort((a, b) => {
      let x = a.cells[i].dataset.v ?? a.cells[i].textContent;
      let y = b.cells[i].dataset.v ?? b.cells[i].textContent;
      let cmp;
      if (h.type === "grade") cmp = gradeRank(y) - gradeRank(x);
      else if (h.type === "num") cmp = (parseFloat(x) || -1e12) - (parseFloat(y) || -1e12);
      else cmp = String(x).localeCompare(String(y));
      return dir === "asc" ? cmp : -cmp;
    });
    rows.forEach(r => table.tBodies[0].appendChild(r));
  }));
});

// --- stackable filters: bare words AND col-op-value expressions ---
const OPS = [">=", "<=", ">", "<", "="];
function parseQuery(q) {
  const terms = q.trim().toLowerCase().split(/\\s+/).filter(Boolean);
  return terms.map(t => {
    for (const op of OPS) {
      const i = t.indexOf(op);
      if (i > 0) return { key: t.slice(0, i), op, val: t.slice(i + op.length) };
    }
    return { text: t };
  });
}
function rowPasses(row, hs, terms) {
  for (const t of terms) {
    if (t.text !== undefined) {
      if (!row.textContent.toLowerCase().includes(t.text)) return false;
      continue;
    }
    const hi = hs.findIndex(h => h.key === t.key);
    if (hi < 0) return false;
    const cell = row.cells[hi];
    const raw = cell.dataset.v ?? cell.textContent;
    let a, b;
    if (hs[hi].type === "grade") { a = -gradeRank(raw.toUpperCase()); b = -gradeRank(t.val.toUpperCase()); }
    else { a = parseFloat(raw); b = parseFloat(t.val); }
    if (isNaN(a) || isNaN(b)) return false;
    const ok = { ">=": a >= b, "<=": a <= b, ">": a > b, "<": a < b, "=": a === b }[t.op];
    if (!ok) return false;
  }
  return true;
}
const box = document.querySelector("input.filter");
if (box) {
  const table = document.querySelector("table");
  const hs = headers(table);
  const count = document.querySelector(".count");
  const apply = () => {
    const terms = parseQuery(box.value);
    let shown = 0;
    for (const row of table.tBodies[0].rows) {
      const ok = rowPasses(row, hs, terms);
      row.style.display = ok ? "" : "none";
      if (ok) shown++;
    }
    if (count) count.textContent = shown + " shown";
  };
  box.addEventListener("input", apply);
  apply();
}
"""

# (header label, filter key, type, css class)
SCREEN_COLS = [
    ("Symbol", "symbol", "text", "l"), ("Company", "name", "text", "l"),
    ("Industry Group", "industry", "text", "l"), ("Grp", "grp", "num", ""),
    ("Price", "price", "num", ""), ("Chg%", "chg", "num", ""),
    ("Vol%", "volchg", "num", ""), ("EPS%", "epschg", "num", ""),
    ("Sales%", "saleschg", "num", ""), ("RS", "rs", "num", ""),
    ("EPS", "eps", "num", ""), ("EPS+RS", "epsrs", "num", ""),
    ("A/D", "ad", "grade", ""),
]

RATINGS_COLS = [
    ("Symbol", "symbol", "text", "l"), ("Company", "name", "text", "l"),
    ("Industry", "industry", "text", "l"), ("Price", "price", "num", ""),
    ("OffHi%", "offhigh", "num", ""), ("RS", "rs", "num", ""),
    ("EPS", "eps", "num", ""), ("EPS+RS", "epsrs", "num", ""),
    ("A/D", "ad", "grade", ""), ("Grp", "grp", "num", ""),
]


def _fmt(val, kind="num", cls=""):
    c = f' class="{cls}"' if cls else ""
    if val is None or pd.isna(val):
        return f"<td{c}>–</td>"
    if kind == "chg":
        cls2 = ("pos" if val >= 0 else "neg") + (f" {cls}" if cls else "")
        return f'<td class="{cls2}" data-v="{val:.2f}">{val:+.1f}</td>'
    if kind == "int":
        return f'<td{c} data-v="{int(val)}">{int(val)}</td>'
    if kind == "cap999":
        v = max(min(val, 999), -999)
        return f'<td{c} data-v="{v:.0f}">{v:.0f}</td>'
    return f'<td{c} data-v="{val:.2f}">{val:,.2f}</td>'


def _thead(cols) -> str:
    ths = "".join(
        f'<th class="{cls}" data-key="{key}" data-type="{typ}">{label}</th>'
        for label, key, typ, cls in cols
    )
    return f"<thead><tr>{ths}</tr></thead>"


def _eps_rs(row):
    eps, rs = row.get("eps_rating"), row.get("rs_rating")
    if pd.isna(eps) or pd.isna(rs):
        return float("nan")
    return int(eps) + int(rs)


def _screen_rows(screen: pd.DataFrame, debuts: set[str]) -> str:
    rows = []
    for _, r in screen.iterrows():
        star = ' <span class="new">NEW</span>' if r["symbol"] in debuts else ""
        rows.append(
            "<tr>"
            f'<td class="l" data-v="{r["symbol"]}"><a href="charts/{r["symbol"]}.png">{r["symbol"]}</a>{star}</td>'
            f'<td class="l">{html.escape(str(r.get("name", ""))[:36])}</td>'
            f'<td class="l">{html.escape(str(r.get("industry", ""))[:34])}</td>'
            + _fmt(r.get("industry_rank"), "int")
            + _fmt(r.get("price"))
            + _fmt(r.get("price_day_chg"), "chg")
            + _fmt(r.get("vol_pct_chg"), "chg")
            + _fmt(r.get("eps_q0_growth"), "cap999")
            + _fmt(r.get("sales_growth"), "cap999")
            + _fmt(r.get("rs_rating"), "int")
            + _fmt(r.get("eps_rating"), "int")
            + _fmt(_eps_rs(r), "int")
            + f'<td data-v="{r.get("ad_rating") or ""}">{r.get("ad_rating") or "–"}</td>'
            + "</tr>"
        )
    return "\n".join(rows)


def _ratings_rows(rated: pd.DataFrame) -> str:
    rows = []
    for _, r in rated.iterrows():
        rows.append(
            "<tr>"
            f'<td class="l" data-v="{r["symbol"]}">{r["symbol"]}</td>'
            f'<td class="l">{html.escape(str(r.get("name", ""))[:36])}</td>'
            f'<td class="l">{html.escape(str(r.get("industry", ""))[:34])}</td>'
            + _fmt(r.get("price"))
            + _fmt(r.get("pct_off_high"), "chg")
            + _fmt(r.get("rs_rating"), "int")
            + _fmt(r.get("eps_rating"), "int")
            + _fmt(_eps_rs(r), "int")
            + f'<td data-v="{r.get("ad_rating") or ""}">{r.get("ad_rating") or "–"}</td>'
            + _fmt(r.get("industry_rank"), "int")
            + "</tr>"
        )
    return "\n".join(rows)


FILTER_UI = (
    '<input class="filter" placeholder="filter: e.g.  semiconductor rs>=90 ad>=B-"'
    ' spellcheck="false"><span class="count"></span>'
    '<p class="hint">bare words match symbol/name/industry &middot; col&gt;=value filters numerically'
    " (keys: rs, eps, epsrs, ad, price, grp&hellip;) &middot; expressions stack with AND"
    " &middot; click headers to sort</p>"
)


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n"
        f"{body}\n<script>{_JS}</script>\n</body>\n</html>\n"
    )


def build_pages_site(screen: pd.DataFrame, rated: pd.DataFrame, debuts: set[str],
                     dropoffs: set[str], run_date: str, site_dir: Path,
                     assets_dir: Path | None = None) -> None:
    site_dir = Path(site_dir)
    (site_dir / "data").mkdir(parents=True, exist_ok=True)

    if assets_dir and Path(assets_dir).exists():
        import shutil
        fonts_out = site_dir / "fonts"
        fonts_out.mkdir(exist_ok=True)
        for f in Path(assets_dir).glob("*.woff2"):
            shutil.copy(f, fonts_out / f.name)

    drop_note = ""
    if dropoffs:
        drop_note = ("<p class='meta'>dropped since last week: "
                     + ", ".join(sorted(dropoffs)) + "</p>")
    body = (
        "<h1>The open 85-85 list</h1>"
        f'<p class="meta">computed {run_date} · {len(screen)} stocks · '
        f'<a href="{REPO_URL}">methodology &amp; source</a> · '
        f'<a href="ratings.html">full ratings table</a></p>'
        "<p>Stocks with EPS and RS ratings of 85+ (percentile-ranked 1&ndash;99 against "
        "the full US stock universe), priced $10+, within 15% of their 52-week closing "
        "high, average volume 10,000+ shares. NEW marks this week's debuts. "
        "Symbols link to weekly charts.</p>"
        + FILTER_UI + drop_note
        + f'<div class="tbl"><table>{_thead(SCREEN_COLS)}<tbody>\n'
        + _screen_rows(screen, debuts)
        + "\n</tbody></table></div>"
        + f'<p class="disclaimer">{DISCLAIMER}</p>'
    )
    (site_dir / "index.html").write_text(_page("The open 85-85 list", body))

    rsorted = rated.dropna(subset=["rs_rating"]).sort_values("rs_rating", ascending=False)
    rbody = (
        "<h1>Full ratings table</h1>"
        f'<p class="meta">computed {run_date} · {len(rsorted)} stocks · '
        f'<a href="index.html">the 85-85 list</a> · <a href="{REPO_URL}">methodology</a></p>'
        + FILTER_UI
        + f'<div class="tbl"><table>{_thead(RATINGS_COLS)}<tbody>\n'
        + _ratings_rows(rsorted)
        + "\n</tbody></table></div>"
        + f'<p class="disclaimer">{DISCLAIMER}</p>'
    )
    (site_dir / "ratings.html").write_text(_page("Full ratings — open 85-85", rbody))

    screen.to_csv(site_dir / "data" / f"screen_{run_date}.csv", index=False)
    keep = [c for c in ("symbol", "name", "industry", "industry_rank", "price", "pct_off_high",
                        "rs_rating", "eps_rating", "ad_rating") if c in rated.columns]
    rated[keep].to_csv(site_dir / "data" / f"ratings_{run_date}.csv", index=False)

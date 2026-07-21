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
import json
from pathlib import Path

import pandas as pd

REPO_URL = "https://github.com/groverburger/open8585"
PAGES_URL = "https://groverburger.github.io/open8585"
TAGLINE = "The 85-85 growth screen, rebuilt in the open"
DESCRIPTION = (
    "A weekly screen for stocks rated 85+ on both earnings growth and price "
    "strength. Proprietary Wall Street ratings reverse-engineered from public "
    "data, validated against the originals, recomputed every Friday."
)

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
td.t999 { text-decoration:underline dotted var(--muted); text-underline-offset:2px; cursor:help; }
.foot-actions { margin-top:14px; }
button.dlcsv { font:inherit; padding:5px 10px; border:1px solid var(--line); border-radius:4px;
               background:var(--surface); color:var(--ink); cursor:pointer; }
button.dlcsv:hover { background:#f4f3f0; }
#lightbox { position:fixed; inset:0; background:rgba(11,11,11,0.55); display:flex;
            align-items:center; justify-content:center; z-index:10; }
#lightbox[hidden] { display:none; }
.lb-inner { background:var(--surface); border-radius:6px; padding:10px 10px 6px;
            max-width:min(96vw, 1000px); box-shadow:0 8px 40px rgba(11,11,11,0.35); }
.lb-inner img { display:block; max-width:100%; max-height:82vh; }
.lb-cap { display:flex; justify-content:space-between; color:var(--muted);
          font-size:11px; padding:6px 2px 2px; }
.lb-cap a { color:var(--accent); }
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

// --- stackable filters: bare words AND col-op-value expressions,
//     `-term` negates, quotes group phrases: -"real estate" excludes REITs ---
const OPS = [">=", "<=", ">", "<", "="];
function parseQuery(q) {
  const tokens = q.toLowerCase().match(/-?"[^"]*"|\\S+/g) || [];
  return tokens.map(tok => {
    const neg = tok.startsWith("-") && tok.length > 1;
    let t = neg ? tok.slice(1) : tok;
    t = t.replace(/^"|"$/g, "");
    if (!t) return null;
    for (const op of OPS) {
      const i = t.indexOf(op);
      if (i > 0) return { neg, key: t.slice(0, i), op, val: t.slice(i + op.length) };
    }
    return { neg, text: t };
  }).filter(Boolean);
}
function termMatches(row, hs, t) {
  if (t.text !== undefined) return row.textContent.toLowerCase().includes(t.text);
  const hi = hs.findIndex(h => h.key === t.key);
  if (hi < 0) return false;
  const cell = row.cells[hi];
  const raw = cell.dataset.v ?? cell.textContent;
  let a, b;
  if (hs[hi].type === "grade") { a = -gradeRank(raw.toUpperCase()); b = -gradeRank(t.val.toUpperCase()); }
  else { a = parseFloat(raw); b = parseFloat(t.val); }
  if (isNaN(a) || isNaN(b)) return false;
  return { ">=": a >= b, "<=": a <= b, ">": a > b, "<": a < b, "=": a === b }[t.op];
}
function rowPasses(row, hs, terms) {
  return terms.every(t => t.neg ? !termMatches(row, hs, t) : termMatches(row, hs, t));
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
    // keep the query in the URL so filters are bookmarkable
    const url = box.value.trim()
      ? "#q=" + encodeURIComponent(box.value.trim())
      : location.pathname + location.search;
    history.replaceState(null, "", url);
  };
  const fromUrl = () => {
    const m = location.hash.match(/^#q=(.*)$/);
    box.value = m ? decodeURIComponent(m[1]) : "";
    apply();
  };
  box.addEventListener("input", apply);
  window.addEventListener("hashchange", fromUrl);
  fromUrl();
}

// --- chart lightbox: click a symbol -> floating popup; arrow keys walk
//     the visible (filtered/sorted) listing; plain links are the no-JS fallback ---
const lb = document.getElementById("lightbox");
if (lb) {
  const img = lb.querySelector("img");
  const capSym = lb.querySelector(".lb-sym");
  const capLink = lb.querySelector(".lb-link");
  let current = null;

  const chartLinks = () =>
    [...document.querySelectorAll("tbody tr")]
      .filter(r => r.style.display !== "none")
      .map(r => r.querySelector('a[href^="charts/"]'))
      .filter(Boolean);

  function show(link) {
    current = link;
    img.src = link.getAttribute("href");
    const sym = link.textContent.trim();
    capSym.textContent = sym;
    capLink.href = link.getAttribute("href");
    lb.hidden = false;
    const links = chartLinks();
    const i = links.indexOf(link);
    for (const n of [links[i - 1], links[i + 1]])
      if (n) new Image().src = n.getAttribute("href"); // preload neighbors
  }
  function step(delta) {
    const links = chartLinks();
    const i = links.indexOf(current);
    if (i < 0) return;
    const next = links[i + delta];
    if (next) show(next);
  }
  document.addEventListener("click", e => {
    const a = e.target.closest('a[href^="charts/"]');
    if (a && !e.metaKey && !e.ctrlKey) { e.preventDefault(); show(a); }
    else if (!lb.hidden && !e.target.closest(".lb-inner")) lb.hidden = true;
  });
  document.addEventListener("keydown", e => {
    if (lb.hidden) return;
    if (e.key === "Escape") lb.hidden = true;
    else if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); step(1); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); step(-1); }
  });
}

// --- download the current (filtered, sorted) view as CSV ---
const dl = document.querySelector("button.dlcsv");
if (dl) {
  dl.addEventListener("click", () => {
    const table = document.querySelector("table");
    const esc = s => '"' + String(s).replaceAll('"', '""') + '"';
    const head = [...table.tHead.rows[0].cells].map(c => esc(c.textContent.trim()));
    const lines = [head.join(",")];
    for (const row of table.tBodies[0].rows) {
      if (row.style.display === "none") continue;
      lines.push([...row.cells].map(c =>
        esc((c.dataset.v ?? c.textContent).replace(/\\s*NEW$/, "").trim())).join(","));
    }
    const blob = new Blob([lines.join("\\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = dl.dataset.filename || "table.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  });
}
"""

# (header label, filter key, type, css class)
SCREEN_COLS = [
    ("Symbol", "symbol", "text", "l"), ("Company", "name", "text", "l"),
    ("Industry Group", "industry", "text", "l"),
    ("Price", "price", "num", ""), ("Chg%", "chg", "num", ""),
    ("Vol%", "volchg", "num", ""), ("EPS%", "epschg", "num", ""),
    ("RS", "rs", "num", ""),
    ("EPS", "eps", "num", ""), ("EPS+RS", "epsrs", "num", ""),
    ("A/D", "ad", "grade", ""),
]

RATINGS_COLS = [
    ("Symbol", "symbol", "text", "l"), ("Company", "name", "text", "l"),
    ("Industry", "industry", "text", "l"), ("Price", "price", "num", ""),
    ("OffHi%", "offhigh", "num", ""), ("RS", "rs", "num", ""),
    ("EPS", "eps", "num", ""), ("EPS+RS", "epsrs", "num", ""),
    ("A/D", "ad", "grade", ""),
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
        if abs(v) >= 999:
            tip = ("Turned profitable (growth off a non-positive base "
                   "is not a meaningful %), or real growth beyond 999% — the classic 999 convention"
                   if v > 0 else
                   "Still unprofitable in the latest period (classic -999 convention)")
            return f'<td class="t999" data-v="{v:.0f}" title="{tip}">{v:.0f}</td>'
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
            f'<td class="l">{html.escape(str(r.get("industry") or "").strip()[:34]) or "–"}</td>'
            + _fmt(r.get("price"))
            + _fmt(r.get("price_day_chg"), "chg")
            + _fmt(r.get("vol_pct_chg"), "chg")
            + _fmt(r.get("eps_q0_growth"), "cap999")
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
            + "</tr>"
        )
    return "\n".join(rows)


FILTER_UI = (
    '<input class="filter" placeholder="filter: e.g.  semiconductor rs>=90 ad>=B-"'
    ' spellcheck="false"><span class="count"></span>'
    '<p class="hint">bare words match symbol/name/industry &middot; col&gt;=value filters numerically'
    " (keys: rs, eps, epsrs, ad, price&hellip;) &middot; -term excludes"
    ' (quote phrases: -&quot;real estate&quot; drops REITs) &middot; expressions stack with AND'
    " &middot; click headers to sort &middot; the query lives in the URL, bookmark it</p>"
)

LIGHTBOX = (
    '<div id="lightbox" hidden><div class="lb-inner"><img alt="weekly chart">'
    '<div class="lb-cap"><span class="lb-sym"></span>'
    '<span>&larr; &rarr; navigate &middot; esc closes &middot; '
    '<a class="lb-link" href="#">open PNG</a></span></div></div></div>'
)


def csv_button(filename: str, raw_href: str) -> str:
    return (
        f'<div class="foot-actions"><button class="dlcsv" data-filename="{filename}">'
        "download CSV (current view)</button>"
        f' &middot; <a href="{raw_href}">raw CSV</a></div>'
    )


def _page(title: str, body: str, path: str = "") -> str:
    og = (
        f'<meta name="description" content="{DESCRIPTION}">\n'
        f'<meta property="og:title" content="{html.escape(title)}">\n'
        f'<meta property="og:description" content="{DESCRIPTION}">\n'
        f'<meta property="og:type" content="website">\n'
        f'<meta property="og:url" content="{PAGES_URL}/{path}">\n'
        f'<meta property="og:image" content="{PAGES_URL}/og.png">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n{og}<style>{_CSS}</style>\n</head>\n<body>\n"
        f"{body}\n<script>{_JS}</script>\n</body>\n</html>\n"
    )


def _jsonable(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if pd.isna(v):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


def write_list_json(screen: pd.DataFrame, debuts: set[str], dropoffs: set[str],
                    run_date: str, run_stamp: str, site_dir: Path) -> None:
    """Machine-readable list at api/list.json — a stable URL other scripts
    can consume (GitHub Pages serves it with open CORS)."""
    stocks = []
    for _, r in screen.iterrows():
        eps_chg = r.get("eps_q0_growth")
        if pd.notna(eps_chg):
            eps_chg = float(max(min(eps_chg, 999), -999))
        stocks.append({
            "symbol": r["symbol"],
            "name": str(r.get("name") or ""),
            "industry": str(r.get("industry") or "") or None,
            "group_rank": _jsonable(r.get("industry_rank")),
            "price": _jsonable(round(r["price"], 2) if pd.notna(r.get("price")) else None),
            "price_day_chg_pct": _jsonable(round(r["price_day_chg"], 2) if pd.notna(r.get("price_day_chg")) else None),
            "vol_vs_50d_pct": _jsonable(round(r["vol_pct_chg"], 1) if pd.notna(r.get("vol_pct_chg")) else None),
            "eps_chg_pct": _jsonable(eps_chg),
            "eps_source": str(r.get("eps_source") or "") or None,
            "rs": _jsonable(r.get("rs_rating")),
            "eps": _jsonable(r.get("eps_rating")),
            "eps_rs": _jsonable(r.get("eps_rs_sum")),
            "ad": str(r.get("ad_rating") or "") or None,
            "new_this_week": r["symbol"] in debuts,
            "chart": f"{PAGES_URL}/charts/{r['symbol']}.png",
        })
    payload = {
        "generated_at": run_stamp,
        "data_through": run_date,
        "count": len(stocks),
        "screen": "EPS>=85, RS>=85, price>=$10, within 15% of 52-week closing high, ADV>=10k shares",
        "debuts": sorted(debuts),
        "dropoffs": sorted(dropoffs),
        "stocks": stocks,
        "docs": REPO_URL,
        "disclaimer": DISCLAIMER,
    }
    api = site_dir / "api"
    api.mkdir(parents=True, exist_ok=True)
    (api / "list.json").write_text(json.dumps(payload, indent=1))


def build_pages_site(screen: pd.DataFrame, rated: pd.DataFrame, debuts: set[str],
                     dropoffs: set[str], run_date: str, site_dir: Path,
                     assets_dir: Path | None = None, run_stamp: str | None = None) -> None:
    site_dir = Path(site_dir)
    (site_dir / "data").mkdir(parents=True, exist_ok=True)
    stamp = run_stamp or run_date

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
    from .charts import render_og_card
    render_og_card(site_dir / "og.png", len(screen), int(rated["rs_rating"].notna().sum()))

    body = (
        f"<h1>The open 85-85 list</h1>"
        f'<p class="meta">{TAGLINE.lower()} &middot; formulas public &middot; '
        f'validated against the commercial originals</p>'
        f'<p class="meta">computed {stamp} · {len(screen)} stocks · '
        f'<a href="{REPO_URL}">methodology &amp; source</a> · '
        f'<a href="ratings.html">full ratings table</a> · '
        f'<a href="api/list.json">JSON</a></p>'
        "<p>Stocks with EPS and RS ratings of 85+ (percentile-ranked 1&ndash;99 against "
        "the full US stock universe), priced $10+, within 15% of their 52-week closing "
        "high, average volume 10,000+ shares. NEW marks first appearance vs the "
        "prior week's list &mdash; the methodology's highest-signal event. "
        "Symbols link to weekly charts.</p>"
        + FILTER_UI + drop_note
        + f'<div class="tbl"><table>{_thead(SCREEN_COLS)}<tbody>\n'
        + _screen_rows(screen, debuts)
        + "\n</tbody></table></div>"
        + csv_button(f"open8585_{run_date}.csv", f"data/screen_{run_date}.csv")
        + f'<p class="disclaimer">{DISCLAIMER}</p>'
        + LIGHTBOX
    )
    (site_dir / "index.html").write_text(_page(f"open8585 — {TAGLINE}", body))

    rsorted = rated.dropna(subset=["rs_rating"]).sort_values("rs_rating", ascending=False)
    rbody = (
        "<h1>Full ratings table</h1>"
        f'<p class="meta">computed {stamp} · {len(rsorted)} stocks · '
        f'<a href="index.html">the 85-85 list</a> · <a href="{REPO_URL}">methodology</a></p>'
        + FILTER_UI
        + f'<div class="tbl"><table>{_thead(RATINGS_COLS)}<tbody>\n'
        + _ratings_rows(rsorted)
        + "\n</tbody></table></div>"
        + csv_button(f"ratings_{run_date}.csv", f"data/ratings_{run_date}.csv")
        + f'<p class="disclaimer">{DISCLAIMER}</p>'
    )
    (site_dir / "ratings.html").write_text(_page("open8585 — full ratings, every US stock", rbody, "ratings.html"))

    write_list_json(screen, debuts, dropoffs, run_date, stamp, site_dir)
    screen.to_csv(site_dir / "data" / f"screen_{run_date}.csv", index=False)
    keep = [c for c in ("symbol", "name", "industry", "industry_rank", "price", "pct_off_high",
                        "rs_rating", "eps_rating", "ad_rating") if c in rated.columns]
    rated[keep].to_csv(site_dir / "data" / f"ratings_{run_date}.csv", index=False)

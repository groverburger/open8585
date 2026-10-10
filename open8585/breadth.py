"""A/D breadth: the daily share of the universe in each A/D letter grade.

One row per trading session in archive/ad_breadth.csv, plus a PNG chart.
Rows already recorded are never rewritten (Yahoo re-adjusts old bars, so
recomputing would quietly revise history); rebuild=True recomputes all.

Denominator: stocks with an A/D rating that session (63+ sessions of
history and a bar that day).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .ratings import ad_score_history

LETTERS = "ABCDE"
BACKFILL_START = pd.Timestamp("2025-01-02")
# Diverging: accumulation blue, neutral gray C, distribution red.
COLORS = {"A": "#184f95", "B": "#4f93e6", "C": "#b2b1aa", "D": "#e86663", "E": "#a32a28"}
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#686762", "#e1e0d9"


def letter_shares(prices: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    """Per-session % of rated stocks in each letter grade, from `start` on."""
    letters = []
    for _, frame in prices.groupby("symbol", sort=False):
        history = ad_score_history(frame)
        history = history[history["date"] >= start]
        if not history.empty:
            letters.append(pd.DataFrame({"date": history["date"], "letter": history["ad_rating"].str[0]}))
    if not letters:
        return pd.DataFrame(columns=["date", "rated", *LETTERS])
    counts = pd.concat(letters).groupby(["date", "letter"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=list(LETTERS), fill_value=0)
    rated = counts.sum(axis=1)
    out = counts.div(rated, axis=0).mul(100).round(2)
    out.insert(0, "rated", rated)
    return out.reset_index()


def plot(history: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10.2, 5.6), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    last = history.iloc[-1]
    for letter in LETTERS:
        ax.plot(history["date"], history[letter], color=COLORS[letter], linewidth=1.6, label=letter)
        ax.annotate(f"{letter} {last[letter]:.1f}%", (last["date"], last[letter]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK)
    fig.text(0.07, 0.965, "A/D grade breadth", fontsize=14, fontweight="bold", color=INK)
    fig.text(0.07, 0.928, f"Daily share of rated stocks in each A/D letter grade · "
             f"{int(last['rated']):,} rated on {last['date']:%Y-%m-%d}", fontsize=9, color=MUTED)
    ax.set_ylabel("Share of rated stocks (%)", color=MUTED)
    ax.set_ylim(0, max(25.0, float(history[list(LETTERS)].max().max()) * 1.12))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, length=0)
    ax.legend(title="A/D letter", ncol=5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.1))
    fig.subplots_adjust(left=0.07, right=0.9, top=0.88, bottom=0.18)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def update(prices: pd.DataFrame, csv_path: Path, start: pd.Timestamp = BACKFILL_START,
           rebuild: bool = False) -> tuple[pd.DataFrame, int]:
    """Append sessions newer than the CSV, redraw the PNG beside it.

    Returns (full history, number of new sessions).
    """
    csv_path = Path(csv_path)
    existing = None
    if csv_path.exists() and not rebuild:
        existing = pd.read_csv(csv_path, parse_dates=["date"])
        start = existing["date"].max() + pd.Timedelta(days=1)

    prices = prices[["date", "symbol", "open", "high", "low", "close", "volume"]].copy()
    prices["date"] = pd.to_datetime(prices["date"]).dt.tz_localize(None)
    new = letter_shares(prices, start)
    if existing is not None and new.empty:
        # leave the files untouched: a redraw alone differs byte-for-byte
        # across matplotlib builds and would make empty commits
        return existing, 0
    history = new if existing is None else pd.concat([existing, new], ignore_index=True)
    history["date"] = pd.to_datetime(history["date"])
    if history.empty:
        raise ValueError("no rated sessions in range")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(csv_path, index=False, date_format="%Y-%m-%d")
    plot(history, csv_path.with_suffix(".png"))
    return history, len(new)

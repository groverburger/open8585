"""A/D breadth: the daily share of the universe in each A/D letter grade.

One row per trading session in archive/ad_breadth.csv, plus a PNG chart.
The last REVISE_SESSIONS rows are recomputed on every run, so a run made
soon after the close is corrected by later ones; older rows are frozen
(Yahoo re-adjusts old bars, so recomputing would quietly revise history).
rebuild=True recomputes all.

Denominator: stocks with an A/D rating that session (63+ sessions of
history and a bar that day).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .ratings import ad_score_history

LETTERS = "ABCDE"
BACKFILL_START = pd.Timestamp("2025-01-02")
REVISE_SESSIONS = 2
# a session rating fewer than this share of the recent median is a data gap
SPARSE_FRACTION = 0.9
# Diverging: accumulation blue, neutral gray C, distribution red.
COLORS = {"A": "#184f95", "B": "#4f93e6", "C": "#b2b1aa", "D": "#e86663", "E": "#a32a28"}
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#686762", "#e1e0d9"
UP, DOWN = COLORS["B"], COLORS["D"]
# Plotted under the A/D lines so breadth reads against the tape.
INDEXES = {"S&P 500": "^GSPC", "NASDAQ Composite": "^IXIC"}
FAST_SMA, SLOW_SMA = 8, 21


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


def fetch_indexes(start: pd.Timestamp, attempts: int = 3) -> pd.DataFrame:
    """Daily closes for INDEXES from `start`, one column per index name."""
    import time

    import yfinance as yf

    for attempt in range(attempts):
        try:
            raw = yf.download(list(INDEXES.values()), start=start.date().isoformat(),
                              auto_adjust=True, progress=False)["Close"]
            closes = raw.rename(columns={t: n for n, t in INDEXES.items()})[list(INDEXES)]
            closes.index = pd.to_datetime(closes.index).tz_localize(None)
            if closes.dropna(how="all").empty or closes.iloc[-5:].isna().all().any():
                raise ValueError("index closes missing")
            return closes
        except Exception as exc:  # noqa: BLE001 - network layer varies
            if attempt == attempts - 1:
                raise RuntimeError(f"index download failed: {exc}") from exc
            time.sleep(10 * (attempt + 1))


def ma_signal(close: pd.Series, fast: int = FAST_SMA, slow: int = SLOW_SMA) -> pd.Series:
    """+1 while the fast SMA is above the slow SMA, -1 while below (NaN in warm-up)."""
    fast_ma, slow_ma = close.rolling(fast).mean(), close.rolling(slow).mean()
    return pd.Series(np.where(fast_ma > slow_ma, 1.0, -1.0), index=close.index).where(slow_ma.notna())


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, length=0)


def plot(history: pd.DataFrame, path: Path, indexes: pd.DataFrame) -> None:
    """Chart the trailing year: A/D letter shares, then each index with its
    8/21-day SMA step, all on one date axis. The CSV keeps the full history."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    history = history[history["date"] >= history["date"].iloc[-1] - pd.DateOffset(years=1)]
    dates = pd.DatetimeIndex(history["date"])
    # never use an index bar newer than the breadth (an intraday partial)
    indexes = indexes[indexes.index <= dates[-1]]

    ratios = [3.2]
    for _ in INDEXES:
        ratios += [1.5, 0.55]
    fig, axes = plt.subplots(len(ratios), 1, figsize=(10.2, 11.4), dpi=160, sharex=True,
                             gridspec_kw={"height_ratios": ratios, "hspace": 0.38})
    fig.patch.set_facecolor(SURFACE)

    ax = axes[0]
    _style(ax)
    last = history.iloc[-1]
    top = max(25.0, float(history[list(LETTERS)].max().max()) * 1.12)
    for letter in LETTERS:
        ax.plot(dates, history[letter], color=COLORS[letter], linewidth=1.6, label=letter)
    # end labels, nudged apart so close values never overprint
    ys, gap = {}, top * 0.045
    for letter in sorted(LETTERS, key=lambda g: last[g]):
        ys[letter] = max(last[letter], max(ys.values(), default=-gap) + gap)
    for letter, y in ys.items():
        ax.annotate(f"{letter} {last[letter]:.1f}%", (dates[-1], y), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK)
    ax.set_title("A/D grade breadth: share of rated stocks (%)", loc="left", fontsize=10, color=INK)
    ax.set_ylim(0, top)
    ax.legend(ncol=5, frameon=False, loc="upper left", fontsize=8, handlelength=1.6)

    for i, name in enumerate(INDEXES):
        close = indexes[name].dropna()
        signal = ma_signal(close).reindex(dates, method="ffill")
        # SMAs from the full series (incl. the warm-up before the window)
        smas = {n: close.rolling(n).mean().reindex(dates, method="ffill") for n in (FAST_SMA, SLOW_SMA)}
        close = close.reindex(dates, method="ffill")
        price_ax, step_ax = axes[1 + 2 * i], axes[2 + 2 * i]
        _style(price_ax)
        for n, color in ((FAST_SMA, UP), (SLOW_SMA, DOWN)):
            price_ax.plot(dates, smas[n], color=color, linewidth=1.0, alpha=0.55, label=f"{n}-day SMA")
        price_ax.plot(dates, close, color=INK, linewidth=1.3)
        price_ax.legend(frameon=False, loc="upper left", fontsize=8, handlelength=1.6)
        price_ax.annotate(f"{close.iloc[-1]:,.0f}", (dates[-1], close.iloc[-1]), xytext=(6, 0),
                          textcoords="offset points", va="center", fontsize=9, color=INK)
        price_ax.set_title(name, loc="left", fontsize=10, color=INK)
        price_ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))

        _style(step_ax)
        # repeat the last value one session on, so a flip on the latest
        # session gets width instead of vanishing at the right edge
        step_x = dates.append(pd.DatetimeIndex([dates[-1] + pd.offsets.BDay(1)]))
        step_y = pd.concat([signal, signal.iloc[-1:]]).to_numpy()
        step_ax.fill_between(step_x, 0, np.clip(step_y, 0, None), step="post", color=UP, linewidth=0)
        step_ax.fill_between(step_x, 0, np.clip(step_y, None, 0), step="post", color=DOWN, linewidth=0)
        step_ax.set_ylim(-1.3, 1.3)
        step_ax.set_yticks([-1, 1])
        step_ax.axhline(0, color="#c3c2b7", linewidth=0.8)
        state = "above" if signal.iloc[-1] > 0 else "below"
        step_ax.set_title(f"{name}: {FAST_SMA}-day SMA vs {SLOW_SMA}-day SMA "
                          f"(+1 above, \u22121 below) \u00b7 now {state}",
                          loc="left", fontsize=9, color=MUTED)

    fig.text(0.07, 0.975, "A/D breadth and the tape", fontsize=14, fontweight="bold", color=INK)
    fig.text(0.07, 0.958, f"Trailing year through {dates[-1]:%Y-%m-%d} \u00b7 "
             f"{int(last['rated']):,} stocks rated", fontsize=9, color=MUTED)
    fig.subplots_adjust(left=0.07, right=0.9, top=0.93, bottom=0.03)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def update(prices: pd.DataFrame, csv_path: Path, start: pd.Timestamp = BACKFILL_START,
           rebuild: bool = False) -> tuple[pd.DataFrame, int, bool]:
    """Append new sessions and revise the last few, redraw the PNG beside it.

    Returns (full history, number of new sessions, whether the files changed).
    """
    csv_path = Path(csv_path)
    existing = None
    if csv_path.exists() and not rebuild:
        existing = pd.read_csv(csv_path, parse_dates=["date"])
        start = existing["date"].iloc[-min(REVISE_SESSIONS, len(existing))]

    prices = prices[["date", "symbol", "open", "high", "low", "close", "volume"]].copy()
    prices["date"] = pd.to_datetime(prices["date"]).dt.tz_localize(None)
    recent = letter_shares(prices, start)
    recent["date"] = pd.to_datetime(recent["date"])
    if existing is None:
        history, added = recent, len(recent)
    else:
        kept = existing[existing["date"] < start]
        # Yahoo sometimes serves the latest bar for only a sliver of the
        # universe (seen ~8 PM ET); such a session is not breadth. Keep the
        # row we already had, or wait for a later run to add it.
        floor = SPARSE_FRACTION * kept["rated"].tail(5).median() if len(kept) else 0
        sparse = recent["rated"] < floor
        for _, row in recent[sparse].iterrows():
            print(f"skipping sparse session {row['date']:%Y-%m-%d}: {row['rated']} rated "
                  f"(< {floor:,.0f})")
        prior = existing[existing["date"].isin(recent.loc[sparse, "date"])]
        recent = pd.concat([recent[~sparse], prior]).sort_values("date")
        history = pd.concat([kept, recent], ignore_index=True)
        added = int((recent["date"] > existing["date"].max()).sum())
        unchanged = (len(history) == len(existing)
                     and history.reset_index(drop=True).equals(existing.reset_index(drop=True)))
        if unchanged:
            # leave the files untouched: a redraw alone differs byte-for-byte
            # across matplotlib builds and would make empty commits
            return existing, 0, False
    if history.empty:
        raise ValueError("no rated sessions in range")
    # fetch before writing anything, so a failed download leaves CSV and PNG in step
    indexes = fetch_indexes(history["date"].iloc[-1] - pd.DateOffset(years=1, days=60))

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(csv_path, index=False, date_format="%Y-%m-%d")
    plot(history, csv_path.with_suffix(".png"), indexes)
    return history, added, True

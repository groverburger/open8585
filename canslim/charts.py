"""Static weekly chart rendering for the published site.

IBD-style weekly charts: high-low-close price bars (~2 years), 10- and
40-week moving averages, a relative-strength line vs the S&P 500 in its
own sub-panel (one scale per panel), and up/down-colored volume with its
10-week average. Rendered to PNG with matplotlib.
"""

from __future__ import annotations

import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402

# Validated reference palette (dataviz skill); light mode.
C = {
    "surface": "#fcfcfb",
    "ink": "#0b0b0b",
    "ink2": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "baseline": "#c3c2b7",
    "up": "#2a78d6",  # diverging cool pole
    "down": "#e34948",  # diverging warm pole
    "ma10": "#eda100",  # categorical slot 3 (direct-labeled: relief rule)
    "ma40": "#4a3aa7",  # categorical slot 5
    "rs": "#1baf7a",  # categorical slot 2 (own labeled panel)
}

WEEKS = 104
BENCH_CACHE_HOURS = 20

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 8.5,
        "axes.edgecolor": C["baseline"],
        "axes.linewidth": 0.8,
        "xtick.color": C["muted"],
        "ytick.color": C["muted"],
        "text.color": C["ink"],
    }
)


def get_benchmark(cache_path: Path, lookback_days: int = 900) -> pd.Series:
    """S&P 500 daily closes for the RS line, parquet-cached."""
    cache_path = Path(cache_path)
    if cache_path.exists() and (time.time() - cache_path.stat().st_mtime) / 3600 < BENCH_CACHE_HOURS:
        return pd.read_parquet(cache_path)["close"]
    start = (pd.Timestamp.today() - pd.Timedelta(days=lookback_days)).date()
    raw = yf.download("^GSPC", start=str(start), auto_adjust=True, progress=False)
    close = raw["Close"]
    if isinstance(close, pd.DataFrame):  # multi-index single ticker
        close = close.iloc[:, 0]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    out = close.rename("close").to_frame()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache_path)
    return out["close"]


def weekly_bars(daily: pd.DataFrame) -> pd.DataFrame:
    """Resample tidy daily OHLCV (date-indexed) to weekly bars."""
    return (
        daily.resample("W-FRI")
        .agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
             close=("close", "last"), volume=("volume", "sum"))
        .dropna(subset=["close"])
    )


def _style_axis(ax):
    ax.set_facecolor(C["surface"])
    ax.grid(True, axis="y", color=C["grid"], linewidth=0.6)
    ax.tick_params(length=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def render_chart(symbol: str, name: str, daily: pd.DataFrame, spx: pd.Series, out_path: Path) -> None:
    """Render one weekly chart PNG. `daily` is date-indexed OHLCV."""
    wk_all = weekly_bars(daily)
    wk_all["ma10"] = wk_all["close"].rolling(10).mean()
    wk_all["ma40"] = wk_all["close"].rolling(40).mean()
    wk = wk_all.tail(WEEKS)
    if len(wk) < 8:
        return
    x = np.arange(len(wk))
    up = (wk["close"] >= wk["close"].shift(1).fillna(wk["open"])).to_numpy()
    bar_colors = np.where(up, C["up"], C["down"])

    spx_wk = spx.resample("W-FRI").last().reindex(wk.index).ffill()
    rs = (wk["close"] / spx_wk).to_numpy()

    fig = plt.figure(figsize=(8.6, 5.6), dpi=110)
    fig.patch.set_facecolor(C["surface"])
    gs = fig.add_gridspec(3, 1, height_ratios=[5.2, 1.15, 1.5], hspace=0.07,
                          left=0.055, right=0.93, top=0.9, bottom=0.07)
    axp = fig.add_subplot(gs[0])
    axr = fig.add_subplot(gs[1], sharex=axp)
    axv = fig.add_subplot(gs[2], sharex=axp)

    # price panel: high-low bars with a close tick, log scale
    axp.vlines(x, wk["low"], wk["high"], colors=bar_colors, linewidth=1.0)
    axp.hlines(wk["close"], x, x + 0.45, colors=bar_colors, linewidth=1.0)
    axp.plot(x, wk["ma10"], color=C["ma10"], linewidth=1.4)
    axp.plot(x, wk["ma40"], color=C["ma40"], linewidth=1.4)
    hi52 = wk["high"].tail(52).max()
    axp.axhline(hi52, color=C["muted"], linewidth=0.7, linestyle=(0, (4, 3)))
    axp.set_yscale("log")
    lo, hi = wk["low"].min() * 0.97, wk["high"].max() * 1.03
    ticks = [t for t in
             (0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30, 40, 60, 80, 100, 150, 200,
              300, 400, 600, 800, 1000, 1500, 2000, 3000)
             if lo <= t <= hi]
    if len(ticks) >= 2:
        axp.yaxis.set_major_locator(plt.FixedLocator(ticks))
    axp.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    axp.yaxis.set_minor_locator(plt.NullLocator())
    axp.yaxis.set_minor_formatter(plt.NullFormatter())
    axp.set_ylim(lo, hi)
    _style_axis(axp)
    plt.setp(axp.get_xticklabels(), visible=False)

    # direct labels (relief rule for the amber line)
    def edge_label(yval, text, color):
        axp.annotate(text, (len(wk) - 1, yval), xytext=(6, 0), textcoords="offset points",
                     color=color, fontsize=7.5, va="center", fontweight="bold",
                     annotation_clip=False)

    if np.isfinite(wk["ma10"].iloc[-1]):
        edge_label(wk["ma10"].iloc[-1], "10w", C["ma10"])
    if np.isfinite(wk["ma40"].iloc[-1]):
        edge_label(wk["ma40"].iloc[-1], "40w", C["ma40"])
    edge_label(hi52, "52w high", C["muted"])

    # RS panel (own scale — never overlaid on price)
    axr.plot(x, rs, color=C["rs"], linewidth=1.3)
    axr.text(0.005, 0.82, "RS line (vs S&P 500)", transform=axr.transAxes,
             color=C["ink2"], fontsize=7)
    axr.set_yticks([])
    _style_axis(axr)
    plt.setp(axr.get_xticklabels(), visible=False)

    # volume panel
    axv.bar(x, wk["volume"], color=bar_colors, alpha=0.55, width=0.75)
    axv.plot(x, wk["volume"].rolling(10).mean(), color=C["muted"], linewidth=1.0)
    axv.set_yticks([])
    axv.text(0.005, 0.78, "weekly volume · 10w avg", transform=axv.transAxes,
             color=C["ink2"], fontsize=7)
    _style_axis(axv)

    # quarterly x labels
    months = wk.index.to_period("Q").astype(str)
    ticks = [i for i in range(1, len(wk)) if months[i] != months[i - 1]]
    axv.set_xticks(ticks)
    axv.set_xticklabels([wk.index[i].strftime("%b %y") for i in ticks], fontsize=7)
    axp.set_xlim(-1, len(wk) + 4)

    last, prev = wk["close"].iloc[-1], wk["close"].iloc[-2]
    chg = (last / prev - 1) * 100
    fig.text(0.055, 0.945, f"{symbol}", fontsize=13, fontweight="bold", color=C["ink"])
    fig.text(0.055, 0.912, name[:60], fontsize=8, color=C["ink2"])
    fig.text(0.93, 0.945, f"{last:,.2f}  {chg:+.1f}% wk", fontsize=10, ha="right",
             color=C["ink"])
    fig.text(0.93, 0.912, "weekly · 2y · log scale", fontsize=7.5, ha="right", color=C["muted"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor=C["surface"])
    plt.close(fig)


def render_index_chart(index: pd.Series, out_path: Path) -> None:
    """The 85-85 index (price-weighted, current members) with its 50-day MA."""
    ma50 = index.rolling(50).mean()
    fig, ax = plt.subplots(figsize=(8.6, 2.6), dpi=110)
    fig.patch.set_facecolor(C["surface"])
    ax.plot(index.index, index, color=C["up"], linewidth=1.4)
    ax.plot(ma50.index, ma50, color=C["ma10"], linewidth=1.2)
    ax.annotate("50d", (ma50.index[-1], ma50.iloc[-1]), xytext=(6, 0),
                textcoords="offset points", color=C["ma10"], fontsize=7.5,
                va="center", fontweight="bold", annotation_clip=False)
    ax.annotate("index", (index.index[-1], index.iloc[-1]), xytext=(6, 0),
                textcoords="offset points", color=C["up"], fontsize=7.5,
                va="center", fontweight="bold", annotation_clip=False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    _style_axis(ax)
    fig.subplots_adjust(left=0.055, right=0.9, top=0.92, bottom=0.16)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor=C["surface"])
    plt.close(fig)

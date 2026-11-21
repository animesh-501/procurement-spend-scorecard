"""Static charts for the README."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from config import CHART_DIR, DAYS_PER_MONTH, SERVICE_TARGET  # noqa: E402

INK, MUTED, ACCENT, LIGHT, WARM = "#1f2328", "#656d76", "#1f6feb", "#afb8c1", "#bf8700"

plt.rcParams.update({
    "figure.dpi": 150, "font.size": 10, "axes.edgecolor": "#d0d7de", "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
    "axes.grid": True, "grid.color": "#eaeef2", "grid.linewidth": 0.8, "legend.frameon": False,
})

LABELS = {
    "demand_only": "Demand variability only",
    "demand_and_lead_time": "+ lead-time variability",
    "empirical": "Empirical lead-time demand",
    "replan_12m": "Re-planned monthly (12 mo)",
    "replan_6m": "Re-planned monthly (6 mo)",
    "mrp_booked": "MRP on booked orders",
}


def short(item):
    parts = item.split(",")
    name = ", ".join(parts[:2]) if item.startswith("HIV") else parts[0]
    return name.replace("Tenofovir Disoproxil Fumarate", "TDF")


def _save(fig, name):
    fig.tight_layout()
    fig.savefig(CHART_DIR / name, bbox_inches="tight")
    plt.close(fig)


def lead_time_spread(stock, lt_obs, n=12):
    top = stock.head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for i, r in enumerate(top.itertuples()):
        x = lt_obs[r.item]
        p10, p50, p90 = np.percentile(x, [10, 50, 90])
        ax.plot([p10, p90], [i, i], color=LIGHT, lw=6, solid_capstyle="round")
        ax.plot(p50, i, "o", color=ACCENT, ms=7, mec="white", mew=1.5)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels([f"{short(i)}  ({o})" for i, o in zip(top.item, top.lt_obs)], fontsize=8.5)
    ax.set_xlabel("Days from PO sent to delivered (dot = median, bar = 10th to 90th percentile)")
    ax.set_xlim(0, None)
    ax.grid(axis="y", visible=False)
    ax.set_title("Supplier lead times are long and wide: 12 largest stock items (observations)")
    _save(fig, "01_lead_time_spread.png")


def service_vs_stock(summ):
    s = summ[summ.scope == "All 33 stock items"]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    for r in s.itertuples():
        color = ACCENT if r.method == "mrp_booked" else (WARM if r.method.startswith("replan") else INK)
        ax.plot(r.avg_stock_usd / 1e6, r.fill_rate_value_weighted * 100, "o", color=color, ms=9,
                mec="white", mew=1.5)
        ax.annotate(f"{LABELS[r.method]}\n{r.fill_rate_value_weighted:.0%} fill, ${r.avg_stock_usd / 1e6:.0f}M",
                    (r.avg_stock_usd / 1e6, r.fill_rate_value_weighted * 100), textcoords="offset points",
                    xytext=(9, -22) if r.method == "demand_and_lead_time" else (9, -4),
                    fontsize=8, color=INK, va="center")
    ax.axhline(SERVICE_TARGET * 100, color=MUTED, lw=1, ls="--")
    x0 = s.avg_stock_usd.min() / 1e6 - 5
    ax.set_xlim(x0, s.avg_stock_usd.max() / 1e6 + 30)
    ax.text(x0 + 1, SERVICE_TARGET * 100 + 0.6, f"{SERVICE_TARGET:.0%} target", color=MUTED, fontsize=8)
    ax.set_ylim(60, 102)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlabel("Average stock on hand in the test year, $ millions")
    ax.set_ylabel("Fill rate (share of demand $ shipped from stock)")
    ax.set_title("Test-year replay, 33 stock items: planning on booked orders wins")
    _save(fig, "02_service_vs_stock.png")


def order_visibility(vis, lt_median_days):
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(vis.months_ahead, vis.booked_share_usd * 100, color=ACCENT, width=0.7)
    for r in vis.itertuples():
        ax.text(r.months_ahead, r.booked_share_usd * 100 + 1.5, f"{r.booked_share_usd:.0%}", ha="center",
                fontsize=8.5, color=INK)
    lt_m = lt_median_days / DAYS_PER_MONTH
    ax.axvline(lt_m + 0.5, color=MUTED, lw=1, ls="--")
    ax.text(lt_m + 0.6, 104, f"median supplier lead time ({lt_median_days:.0f} days)", fontsize=8, color=MUTED,
            va="center")
    ax.set_xticks(vis.months_ahead)
    ax.set_xlabel("Months ahead of the planning date")
    ax.set_ylim(0, 112)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.grid(axis="x", visible=False)
    ax.set_title("Share of future demand ($) already quoted to the country, stock items")
    _save(fig, "03_order_visibility.png")


def mrp_record(rec, item):
    rec = rec.copy()
    x = np.arange(len(rec))
    labels = [pd.Timestamp(m).strftime("%b %y") for m in rec.month]
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    booked = rec.booked_orders / 1e6
    extra = (rec.gross_requirement - rec.booked_orders) / 1e6
    ax.bar(x, booked, color=ACCENT, width=0.65, label="Booked orders")
    ax.bar(x, extra, bottom=booked, color=LIGHT, width=0.65, label="Forecast on top (not yet booked)")
    ax.plot(x, rec.actual_demand / 1e6, color=INK, marker="o", ms=5, lw=2, label="Actual demand")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Packs, millions")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", fontsize=8.5)
    ax.set_title(f"MRP gross requirements at end of Aug 2014: {short(item)}")
    _save(fig, "04_mrp_record.png")


def make_all(stock, lt_obs, summ, vis, lt_median_days, tle_record, tle):
    lead_time_spread(stock, lt_obs)
    service_vs_stock(summ)
    order_visibility(vis, lt_median_days)
    mrp_record(tle_record, tle)

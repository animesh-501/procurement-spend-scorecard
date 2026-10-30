"""Static charts for the README."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402

from config import CHART_DIR  # noqa: E402
from scorecard import ON_TIME_TARGET, PRICE_LIMIT, short_name  # noqa: E402

INK, MUTED, ACCENT, LIGHT = "#1f2328", "#656d76", "#1f6feb", "#afb8c1"
TIER_COLORS = {"Preferred": "#2da44e", "Fix delivery": "#bf8700", "Fix price": "#cf222e",
               "Review: price and delivery": "#8250df"}

plt.rcParams.update({
    "figure.dpi": 150, "font.size": 10, "axes.edgecolor": "#d0d7de", "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
    "axes.grid": True, "grid.color": "#eaeef2", "grid.linewidth": 0.8, "legend.frameon": False,
})


def _save(fig, name):
    fig.tight_layout()
    fig.savefig(CHART_DIR / name, bbox_inches="tight")
    plt.close(fig)


def spend_by_year(sby):
    p = sby.pivot(index="year", columns="channel", values="spend").fillna(0) / 1e6
    fig, ax = plt.subplots(figsize=(8, 3))
    bottom = 0
    for col, color in [("Direct from vendor", ACCENT), ("From regional warehouse", LIGHT)]:
        ax.bar(p.index, p[col], bottom=bottom, color=color, label=col)
        bottom = bottom + p[col]
    ax.set_title("Spend by year and channel")
    ax.set_ylabel("$ millions")
    ax.set_xticks(p.index)
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)
    _save(fig, "01_spend_by_year.png")


def pareto(vp):
    top = vp.head(15)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.bar(range(len(top)), top.spend / 1e6, color=ACCENT)
    ax.set_xticks(range(len(top)))
    ax.set_xticklabels([short_name(v) for v in top.vendor], rotation=55, ha="right", fontsize=8.5)
    ax.set_ylabel("Direct spend, $ millions")
    ax.grid(axis="x", visible=False)
    ax2 = ax.twinx()
    ax2.plot(range(len(top)), top.cumulative_share * 100, color=INK, marker="o", ms=3.5, lw=1.4)
    ax2.set_ylim(0, 105)
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    ax.set_title("Direct spend is concentrated: top 5 vendors = "
                 f"{vp.cumulative_share.iloc[4]:.0%} of it")
    _save(fig, "02_vendor_pareto.png")


def quadrant(card):
    c = card.dropna(subset=["price_index"])
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    x_cap = 1.6
    for tier, g in c.groupby("tier"):
        ax.scatter(g.price_index.clip(upper=x_cap), g.on_time_rate * 100, s=g.spend / 6e5 + 15,
                   color=TIER_COLORS[tier], alpha=0.75, edgecolor="white", lw=0.8, label=tier)
    label = c[(c.spend > 2e7) | ((c.tier != "Preferred") & (c.spend > 5e6))]
    for _, r in label.iterrows():
        dy = -11 if r.vendor.startswith("HETERO") else -3
        ax.annotate(short_name(r.vendor), (min(r.price_index, x_cap), r.on_time_rate * 100),
                    xytext=(6, dy), textcoords="offset points", fontsize=8.5, color=INK)
    for _, r in c[c.price_index > x_cap].iterrows():
        ax.annotate(f"{short_name(r.vendor)} ({r.price_index:.2f}x)", (x_cap, r.on_time_rate * 100),
                    xytext=(-8, 6), textcoords="offset points", fontsize=8, color=MUTED, ha="right")
    ax.axvline(PRICE_LIMIT, color=MUTED, ls=":", lw=1)
    ax.axhline(ON_TIME_TARGET * 100, color=MUTED, ls=":", lw=1)
    ax.set_xlabel("Price index (1.00 = item median price that year; lower is cheaper)")
    ax.set_ylabel("Lines delivered on time")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_title("Supplier scorecard: price vs. delivery (bubble = spend)")
    ax.legend(loc="lower right", markerscale=0.6, fontsize=8.5)
    _save(fig, "03_supplier_scorecard.png")


def item_excess(items):
    top = items.head(10)[::-1]
    fig, ax = plt.subplots(figsize=(9, 4))
    y = range(len(top))
    ax.barh([i + 0.2 for i in y], top.excess_usd / 1e6, height=0.4, color=ACCENT, label="vs. item median price")
    ax.barh([i - 0.2 for i in y], top.excess_usd_same_terms / 1e6, height=0.4, color=LIGHT,
            label="vs. median under same delivery terms")
    ax.set_yticks(list(y))
    ax.set_yticklabels([(", ".join(t.split(", ")[:2]) if t.startswith("HIV") else t.split(", ")[0])[:52]
                        for t in top.item], fontsize=8.5)
    ax.set_xlabel("$ millions paid above benchmark")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title("Where price variance sits: top 10 items")
    _save(fig, "04_price_variance_items.png")


def freight(fm):
    f = fm.dropna(subset=["shipment_mode"]).set_index("shipment_mode").loc[["Air", "Air Charter", "Ocean", "Truck"]]
    fig, axes = plt.subplots(1, 2, figsize=(9, 2.8))
    for ax, col, title, fmt in [
        (axes[0], "freight_pct_of_value", "Freight as % of goods value", lambda v: f"{v:.1%}"),
        (axes[1], "freight_usd_per_kg", "Freight $ per kg", lambda v: f"${v:.2f}"),
    ]:
        bars = ax.barh(f.index, f[col], color=[ACCENT if m == "Air" else LIGHT for m in f.index])
        ax.bar_label(bars, labels=[fmt(v) for v in f[col]], padding=3, fontsize=9, color=INK)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=10.5)
        ax.grid(axis="y", visible=False)
        ax.set_xticks([])
        ax.set_xlim(0, f[col].max() * 1.3)
    _save(fig, "05_freight_by_mode.png")


def make_all(t, card, items):
    spend_by_year(t["spend_by_year"])
    pareto(t["vendor_pareto"])
    quadrant(card)
    item_excess(items)
    freight(t["freight_by_mode"])

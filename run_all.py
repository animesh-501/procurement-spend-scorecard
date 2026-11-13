"""Run the full analysis: SQL spend cube -> price variance -> supplier scorecard -> charts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd  # noqa: E402

import charts  # noqa: E402
import data  # noqa: E402
import scorecard  # noqa: E402
from config import CHART_DIR, OUT_DIR  # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    CHART_DIR.mkdir(exist_ok=True)

    t = data.build()
    lines, pv, items = t["lines"], t["price_variance"], t["item_opportunity"]
    card = scorecard.tiers(t["vendor_scorecard"])
    tiers = scorecard.tier_summary(card)

    print("\nVendor concentration (direct)\n", t["vendor_pareto"].head(10).round(3).to_string(index=False))
    print("\nTop items by price variance\n", items.head(10).round(3).to_string(index=False))
    print("\nSupplier scorecard\n", card.round(3).to_string(index=False))
    print("\nTiers\n", tiers.round(3).to_string(index=False))
    print("\nFreight by shipment mode\n", t["freight_by_mode"].round(3).to_string(index=False))

    direct = lines[lines.channel == "Direct from vendor"]
    top3 = card.head(3)
    summary = {
        "lines": len(lines),
        "total_spend_usd": lines.line_value.sum(),
        "years": f"{lines.year.min()}-{lines.year.max()}",
        "direct_spend_usd": direct.line_value.sum(),
        "direct_vendors": direct.vendor.nunique(),
        "top5_vendor_share_of_direct": t["vendor_pareto"].cumulative_share.iloc[4],
        "benchmarked_spend_usd": pv.line_value.sum(),
        "benchmarked_share_of_spend": pv.line_value.sum() / lines.line_value.sum(),
        "excess_vs_item_median_usd": pv.excess_usd.sum(),
        "excess_vs_item_median_pct": pv.excess_usd.sum() / pv.line_value.sum(),
        "excess_same_terms_usd": pv.excess_usd_same_terms.sum(),
        "excess_same_terms_pct": pv.excess_usd_same_terms.sum() / pv.line_value.sum(),
        "scorecard_vendors": len(card),
        "scorecard_share_of_direct_spend": card.spend.sum() / direct.line_value.sum(),
        "top3_vendors_share_of_direct": top3.spend.sum() / direct.line_value.sum(),
        "top3_vendors_on_time_min": top3.on_time_rate.min(),
        "top3_vendors_on_time_max": top3.on_time_rate.max(),
        "direct_on_time_rate": direct.on_time.mean(),
        "warehouse_on_time_rate": lines[lines.channel != "Direct from vendor"].on_time.mean(),
    }
    print("\nSummary\n", pd.Series(summary).to_string())

    for name in ["spend_by_year", "vendor_pareto", "item_opportunity", "freight_by_mode"]:
        t[name].to_csv(OUT_DIR / f"{name}.csv", index=False)
    card.to_csv(OUT_DIR / "supplier_scorecard.csv", index=False)
    tiers.to_csv(OUT_DIR / "scorecard_tiers.csv", index=False)
    pv.to_csv(OUT_DIR / "price_variance_by_line.csv", index=False)
    pd.Series(summary).to_csv(OUT_DIR / "summary.csv", header=["value"])

    charts.make_all(t, card, items)
    print("\nOutputs written to outputs and charts")


if __name__ == "__main__":
    main()

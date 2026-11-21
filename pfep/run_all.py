"""Run everything: SQL item master -> PFEP planning fields -> test-year replay -> MRP records -> charts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import charts  # noqa: E402
import data  # noqa: E402
import mrp  # noqa: E402
import policy  # noqa: E402
import replay  # noqa: E402
from config import (CHART_DIR, FIT_END, FIT_START, OUT_DIR, TEST_END, TEST_START,  # noqa: E402
                    WARMUP_START)

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_colwidth", 60)

PFEP_COLUMNS = [
    "item", "product_group", "sub_class", "dosage_form", "units_per_pack", "abc_class", "stock_decision",
    "main_vendor", "main_vendor_share", "direct_vendors", "manufacturing_sites", "main_inco_term",
    "main_shipment_mode", "kg_per_pack", "fit_pack_price", "fit_spend", "fit_months_with_demand",
    "fit_monthly_mean", "fit_monthly_sd", "fit_demand_cv", "lt_source", "lt_obs", "lt_p50_days",
    "lt_mean_days", "lt_sd_days", "lt_p90_days", "lt_cv", "direct_on_time_rate", "protection_months",
    "cycle_stock_packs", "ss_demand_only", "ss_demand_and_lead_time", "ss_empirical", "s_empirical",
    "lines", "spend", "first_delivery", "last_delivery",
]
PLANNING_DATE = pd.Timestamp(FIT_END)          # month-end of the last fit month
RECORD_ITEMS = 3


def test_window_lead_times(lt_obs_table, items):
    """Lead times actually achieved on POs sent during the replay window (for a sensitivity run)."""
    x = lt_obs_table[lt_obs_table.item.isin(items) & (lt_obs_table.po_sent_date >= WARMUP_START)]
    return {k: g.lead_time_days.to_numpy() for k, g in x.groupby("item") if len(g) >= 5}


def main():
    OUT_DIR.mkdir(exist_ok=True)
    CHART_DIR.mkdir(exist_ok=True)

    t = data.build()
    lines = t["lines"]
    plan, lt_obs, fit = policy.build(t)
    plan = plan.sort_values(["fit_spend", "item"], ascending=[False, True], ignore_index=True)
    stock = plan[plan.stock_decision.str.startswith("Stock")]

    print(f"\nFit window {FIT_START[:7]} to {FIT_END[:7]}, test year {TEST_START[:7]} to {TEST_END[:7]}")
    decision = plan.groupby("stock_decision").agg(items=("item", "size"), fit_spend=("fit_spend", "sum"))
    decision["share_of_fit_spend"] = decision.fit_spend / decision.fit_spend.sum()
    print("\nStock decision\n", decision.round(3).to_string())
    print("\nLead-time source for stock items\n", stock.lt_source.value_counts().to_string())

    ss_usd = {m: (stock[f"ss_{m}"] * stock.fit_pack_price).sum() for m in policy.METHODS}
    lt_cols = ["item", "abc_class", "fit_monthly_mean", "fit_demand_cv", "lt_p50_days", "lt_mean_days",
               "lt_sd_days", "lt_p90_days", "lt_obs", "ss_demand_only", "ss_demand_and_lead_time", "ss_empirical"]
    print("\nTop 12 stock items: demand, lead time, safety stock (packs)\n",
          stock[lt_cols].head(12).round(2).to_string(index=False))
    print("\nSafety stock value by method ($)\n", pd.Series(ss_usd).round(0).to_string())

    res = replay.run(plan, t["monthly_demand"], lt_obs, lines)
    summ = replay.summarise(res)
    summ.loc[~summ.method.isin(policy.METHODS), "safety_stock_usd"] = np.nan
    summ.insert(1, "scope", "All 33 stock items")
    tle = stock.item.iloc[0]
    tle_share = res[(res.item == tle)].demand_packs.iloc[0] * res[(res.item == tle)].pack_price.iloc[0] \
        / summ.demand_usd.iloc[0]
    ex = replay.summarise(res[res.item != tle])
    ex.loc[~ex.method.isin(policy.METHODS), "safety_stock_usd"] = np.nan
    ex.insert(1, "scope", "Excluding the largest item")
    summ = pd.concat([summ, ex], ignore_index=True)
    summ.insert(2, "description", summ.method.map(replay.ALL_METHODS))
    print("\nReplay of the test year (500 runs per item, lead times drawn from observed history)\n",
          summ.drop(columns="description").round(3).to_string(index=False))
    print(f"\nLargest item: {tle} = {tle_share:.0%} of test-year demand value")
    by_item = res.pivot(index="item", columns="method", values="fill_rate")[list(replay.ALL_METHODS)]
    print("\nFill rate by item, largest items\n", by_item.loc[stock.item.head(12)].round(3).to_string())

    # Sensitivity: draw replay lead times from what suppliers actually achieved in the replay window
    override = test_window_lead_times(t["lead_time_obs"], stock.item)
    sens = replay.summarise(replay.run(plan, t["monthly_demand"], lt_obs, lines, lt_override=override))
    sens.insert(1, "lead_times_drawn_from", f"POs sent from {WARMUP_START[:7]} ({len(override)} items with 5+ obs)")
    print("\nSensitivity: replay lead times from the replay window itself\n",
          sens[["method", "fill_rate_value_weighted", "avg_stock_usd", "in_stock_months"]].round(3).to_string(index=False))

    # Order visibility: how much of each future month was already quoted to the country
    asof = pd.date_range(WARMUP_START, TEST_END, freq="MS")
    vis = mrp.visibility(lines, stock.item, asof)
    print("\nShare of future demand already booked at the planning date (stock items)\n",
          vis.round(3).to_string(index=False))
    pq_lead = (lines.delivered_date - lines.pq_sent_date).dt.days[
        lines.item.isin(stock.item) & (lines.month >= WARMUP_START)]
    stock_lt_median = np.median(np.concatenate([lt_obs[i] for i in stock.item]))
    print(f"Quote -> delivery, median days: {pq_lead.median():.0f}; supplier lead time (PO -> delivered) "
          f"median for stock items: {stock_lt_median:.0f}")

    # Time-phased MRP records at the planning date for the largest items
    full = policy.month_matrix(t["monthly_demand"], FIT_START, TEST_END)
    pd_months = pd.date_range(FIT_START, PLANNING_DATE, freq="MS")
    booked = mrp.booked_matrix(lines, stock.item.head(RECORD_ITEMS), [PLANNING_DATE])
    records = []
    for r in stock.head(RECORD_ITEMS).itertuples():
        hist = full.loc[r.item, pd_months].to_numpy()
        rec = mrp.record(r.item, pd_months, hist, booked[r.item][0], r, PLANNING_DATE)
        actual = full.loc[r.item]
        rec["actual_demand"] = [actual.get(pd.Timestamp(m), np.nan) for m in rec.month]
        records.append(rec)
    records = pd.concat(records, ignore_index=True)
    print(f"\nMRP record at end of {PLANNING_DATE:%b %Y}, {tle}\n",
          records[records.item == tle].drop(columns=["item", "planning_date"]).round(0).to_string(index=False))

    summary = {
        "lines": len(lines),
        "items": len(plan),
        "stock_items": len(stock),
        "stock_items_share_of_fit_spend": stock.fit_spend.sum() / plan.fit_spend.sum(),
        "buy_to_order_items": int((plan.stock_decision == "Buy to order").sum()),
        "inactive_items": int(plan.stock_decision.str.startswith("Inactive").sum()),
        "stock_items_lead_time_median_days": stock_lt_median,
        "stock_items_lead_time_cv_median": stock.lt_cv.median(),
        "safety_stock_usd_demand_only": ss_usd["demand_only"],
        "safety_stock_usd_demand_and_lead_time": ss_usd["demand_and_lead_time"],
        "safety_stock_usd_empirical": ss_usd["empirical"],
        "lead_time_variability_adds_pct": ss_usd["demand_and_lead_time"] / ss_usd["demand_only"] - 1,
        "largest_item_share_of_test_demand_value": tle_share,
        "largest_item_test_vs_fit_demand": res[res.item == tle].demand_packs.iloc[0] / 12
        / stock.fit_monthly_mean.iloc[0],
        "quote_to_delivery_median_days": pq_lead.median(),
        "booked_share_1_month_ahead": vis.booked_share_usd.iloc[0],
        "booked_share_3_months_ahead": vis.booked_share_usd.iloc[2],
        "booked_share_5_months_ahead": vis.booked_share_usd.iloc[4],
        "booked_share_8_months_ahead": vis.booked_share_usd.iloc[7],
    }
    for row in summ[summ.scope == "All 33 stock items"].itertuples():
        summary[f"fill_rate_{row.method}"] = row.fill_rate_value_weighted
        summary[f"avg_stock_usd_{row.method}"] = row.avg_stock_usd
    print("\nSummary\n", pd.Series(summary).to_string())

    pfep = plan[PFEP_COLUMNS].rename(columns={"s_empirical": "order_up_to_empirical"})
    pfep.to_csv(OUT_DIR / "pfep.csv", index=False)
    res.to_csv(OUT_DIR / "replay_by_item.csv", index=False)
    summ.to_csv(OUT_DIR / "replay_summary.csv", index=False)
    sens.to_csv(OUT_DIR / "replay_lead_time_sensitivity.csv", index=False)
    vis.to_csv(OUT_DIR / "order_visibility.csv", index=False)
    records.to_csv(OUT_DIR / "mrp_records.csv", index=False)
    pd.Series(summary).to_csv(OUT_DIR / "summary.csv", header=["value"])

    charts.make_all(stock, lt_obs, summ, vis, stock_lt_median, records[records.item == tle], tle)
    print("\nOutputs written to outputs and charts")


if __name__ == "__main__":
    main()

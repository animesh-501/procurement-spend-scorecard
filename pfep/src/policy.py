"""Planning half of the PFEP: demand, lead time, stock rule and three ways to size safety stock."""
import numpy as np
import pandas as pd
from scipy.stats import norm

from config import (DAYS_PER_MONTH, FIT_END, FIT_START, MIN_LT_OBS, N_BOOTSTRAP, REVIEW_MONTHS, SEED,
                    SERVICE_TARGET, STOCK_MIN_MONTHS, TEST_START)

METHODS = {
    "demand_only": "Demand variability only",
    "demand_and_lead_time": "Demand + lead-time variability",
    "empirical": "Empirical (bootstrapped lead-time demand)",
}


def month_matrix(md, start, end):
    months = pd.date_range(start, end, freq="MS")
    m = md[(md.month >= months[0]) & (md.month <= months[-1])]
    return m.pivot_table(index="item", columns="month", values="packs", aggfunc="sum").reindex(
        columns=months, fill_value=0).fillna(0)


def abc(spend):
    s = spend.sort_values(ascending=False)
    cum = s.cumsum() / s.sum()
    prev = cum.shift(fill_value=0)
    return pd.Series(np.where(prev < 0.80, "A", np.where(prev < 0.95, "B", "C")), index=s.index)


def lead_times(lt, master):
    """Lead-time observations known at planning time, with a fallback when an item has too few."""
    known = lt[lt.delivered_date < TEST_START]
    by_item = {k: g.lead_time_days.to_numpy() for k, g in known.groupby("item")}
    by_vendor = {k: g.lead_time_days.to_numpy() for k, g in known.groupby("vendor")}
    by_group = {k: g.lead_time_days.to_numpy() for k, g in known.groupby("product_group")}
    rows, obs = [], {}
    for r in master.itertuples():
        for source, pool, key in [("item", by_item, r.item), ("main vendor", by_vendor, r.main_vendor),
                                  ("product group", by_group, r.product_group)]:
            x = pool.get(key)
            if x is not None and len(x) >= MIN_LT_OBS:
                break
        obs[r.item] = x
        rows.append({"item": r.item, "lt_source": source, "lt_obs": len(x),
                     "lt_mean_days": x.mean(), "lt_sd_days": x.std(ddof=1), "lt_p50_days": np.median(x),
                     "lt_p90_days": np.percentile(x, 90), "lt_cv": x.std(ddof=1) / x.mean()})
    return pd.DataFrame(rows), obs


def protection_months(lt_days):
    """Months of demand an order-up-to level must cover: review period + lead time rounded to whole
    months. The replay uses the same rounding, so formula and replay agree on average."""
    return REVIEW_MONTHS + np.rint(np.asarray(lt_days) / DAYS_PER_MONTH)


def build(t):
    lines, md, master = t["lines"], t["monthly_demand"], t["item_master"]
    fit = month_matrix(md, FIT_START, FIT_END)
    fit_lines = lines[(lines.month >= FIT_START) & (lines.month <= FIT_END)]

    plan = master.set_index("item")
    plan["fit_months_with_demand"] = (fit > 0).sum(axis=1)
    plan["fit_monthly_mean"] = fit.mean(axis=1)
    plan["fit_monthly_sd"] = fit.std(axis=1, ddof=1)
    plan["fit_demand_cv"] = plan.fit_monthly_sd / plan.fit_monthly_mean
    plan["fit_spend"] = fit_lines.groupby("item").line_value.sum()
    plan["fit_pack_price"] = fit_lines.groupby("item").pack_price.median()
    plan[["fit_months_with_demand", "fit_monthly_mean", "fit_spend"]] = plan[
        ["fit_months_with_demand", "fit_monthly_mean", "fit_spend"]].fillna(0)
    active = plan.fit_spend > 0
    plan.loc[active, "abc_class"] = abc(plan.loc[active, "fit_spend"])
    plan["stock_decision"] = np.select(
        [~active, plan.fit_months_with_demand >= STOCK_MIN_MONTHS],
        ["Inactive (no demand in fit window)", "Stock: monthly review"], "Buy to order")
    plan = plan.reset_index()

    ltab, lt_obs = lead_times(t["lead_time_obs"], master)
    plan = plan.merge(ltab, on="item", how="left")
    plan["lt_mean_months"] = plan.lt_mean_days / DAYS_PER_MONTH
    plan["lt_sd_months"] = plan.lt_sd_days / DAYS_PER_MONTH

    z = norm.ppf(SERVICE_TARGET)
    rng = np.random.default_rng(SEED)
    stock = plan.stock_decision.str.startswith("Stock")
    for m in METHODS:
        plan[f"ss_{m}"] = np.nan
        plan[f"s_{m}"] = np.nan
    for i in plan.index[stock]:
        r = plan.loc[i]
        d, sd = r.fit_monthly_mean, r.fit_monthly_sd
        p = protection_months(lt_obs[r["item"]])          # per observed lead time
        p_mean, p_var = p.mean(), p.var(ddof=1)
        cycle = d * p_mean
        ss = {
            "demand_only": z * sd * np.sqrt(p_mean),
            "demand_and_lead_time": z * np.sqrt(p_mean * sd ** 2 + d ** 2 * p_var),
        }
        # Empirical: draw a lead time, then that many months of demand from the 24 fit months
        hist = fit.loc[r["item"]].to_numpy()
        draws = rng.choice(p, N_BOOTSTRAP).astype(int)
        total = np.array([rng.choice(hist, k).sum() for k in draws])
        ss["empirical"] = np.quantile(total, SERVICE_TARGET) - cycle
        plan.loc[i, "protection_months"] = p_mean
        plan.loc[i, "cycle_stock_packs"] = d * REVIEW_MONTHS / 2
        for m, v in ss.items():
            plan.loc[i, f"ss_{m}"] = max(v, 0)
            plan.loc[i, f"s_{m}"] = cycle + max(v, 0)
    return plan, lt_obs, fit

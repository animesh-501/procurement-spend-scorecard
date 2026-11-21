"""Replay the monthly order-up-to policy on the demand that actually happened in the test year.

Each month: receive what arrives, ship demand (shortages are back-ordered), then order up to S.
Each order's lead time is drawn from that item's observed supplier lead times, so every run gets a
different arrival pattern. The first 12 months (end of the fit window) only warm the system up;
results are measured on the 12 test months.

The three PFEP methods keep S fixed at the fit-window value. The re-planned variant recomputes S
every month from the trailing months of demand (same demand + lead-time formula), the way a
monthly MRP / S&OP cycle would.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm

from config import (DAYS_PER_MONTH, FIT_START, N_SIMS, REPLAN_WINDOWS, SEED, SERVICE_TARGET, TEST_END,
                    TEST_START, WARMUP_START)
import mrp
from policy import METHODS, month_matrix, protection_months

REPLAN = {f"replan_{w}m": f"Demand + lead time, re-planned monthly on last {w} months" for w in REPLAN_WINDOWS}
BOOKED = {"mrp_booked": "MRP on booked orders + forecast beyond them, buffer for lead-time variability only"}
ALL_METHODS = {**METHODS, **REPLAN, **BOOKED}


def replan_levels(history, lt_days, window, n_hist):
    """Order-up-to level for each simulated month, using only demand known at the end of that month."""
    p = protection_months(lt_days)
    p_mean, p_var = p.mean(), p.var(ddof=1)
    z = norm.ppf(SERVICE_TARGET)
    levels = []
    for t in range(n_hist, len(history)):
        w = history[t - window + 1: t + 1]
        d, sd = w.mean(), w.std(ddof=1)
        levels.append(d * p_mean + z * np.sqrt(p_mean * sd ** 2 + d ** 2 * p_var))
    return np.array(levels)


def simulate(demand, s_level, lt_days, n_test, rng, n_sims=N_SIMS):
    T = len(demand)
    lag = np.rint(np.asarray(lt_days) / DAYS_PER_MONTH).astype(int)
    arrivals = np.zeros((n_sims, T + lag.max() + 2))
    s_level = np.broadcast_to(np.asarray(s_level, dtype=float), (T,))
    on_hand = np.full(n_sims, s_level[0])
    filled = np.zeros((n_sims, T))
    end_stock = np.zeros((n_sims, T))
    idx = np.arange(n_sims)
    for t in range(T):
        on_hand += arrivals[:, t]
        filled[:, t] = np.minimum(np.maximum(on_hand, 0), demand[t])
        on_hand -= demand[t]
        end_stock[:, t] = on_hand
        position = on_hand + arrivals[:, t + 1:].sum(axis=1)
        order = np.maximum(s_level[t] - position, 0)
        k = rng.choice(lag, n_sims)
        arrivals[idx, t + 1 + k] += order
    test = slice(T - n_test, T)
    d = demand[test]
    return {
        "demand_packs": d.sum(),
        "filled_packs": filled[:, test].sum(axis=1).mean(),
        "in_stock_months": (end_stock[:, test] >= 0).mean(),
        "avg_stock_packs": np.maximum(end_stock[:, test], 0).mean(),
        "backorder_month_end_packs": np.maximum(-end_stock[:, test], 0).mean(),
    }


def run(plan, md, lt_obs, lines, lt_override=None):
    """lt_override: optional {item: lead-time array} to draw replay lead times from instead."""
    rng = np.random.default_rng(SEED)
    full = month_matrix(md, FIT_START, TEST_END)
    n_hist = len(pd.date_range(FIT_START, WARMUP_START, freq="MS")) - 1
    n_test = len(pd.date_range(TEST_START, TEST_END, freq="MS"))
    stock = plan[plan.stock_decision.str.startswith("Stock")]
    asof = pd.date_range(WARMUP_START, TEST_END, freq="MS")
    booked = mrp.booked_matrix(lines, stock.item, asof)
    rows = []
    for r in stock.itertuples():
        history = full.loc[r.item].to_numpy()
        demand = history[n_hist:]
        lts = lt_override.get(r.item, lt_obs[r.item]) if lt_override else lt_obs[r.item]
        for m in ALL_METHODS:
            if m in METHODS:
                s_level = getattr(r, f"s_{m}")
            elif m == "mrp_booked":
                b = booked.get(r.item, np.zeros((len(asof), mrp.MAX_HORIZON)))
                s_level = mrp.booked_levels(history, b, lt_obs[r.item], REPLAN_WINDOWS[0], n_hist)
            else:
                s_level = replan_levels(history, lt_obs[r.item], int(m.split("_")[1][:-1]), n_hist)
            res = simulate(demand, s_level, lts, n_test, rng)
            s_test = np.broadcast_to(s_level, demand.shape)[-n_test:].mean()
            rows.append({"item": r.item, "abc_class": r.abc_class, "method": m,
                         "pack_price": r.fit_pack_price,
                         "safety_stock_packs": getattr(r, f"ss_{m}") if m in METHODS else np.nan,
                         "order_up_to_packs": s_test, **res})
    out = pd.DataFrame(rows)
    out["fill_rate"] = out.filled_packs / out.demand_packs
    out["avg_stock_usd"] = out.avg_stock_packs * out.pack_price
    out["safety_stock_usd"] = out.safety_stock_packs * out.pack_price
    return out


def summarise(res):
    res = res.assign(demand_usd=res.demand_packs * res.pack_price, filled_usd=res.filled_packs * res.pack_price)
    g = res.groupby("method", sort=False).agg(
        items=("item", "size"), demand_usd=("demand_usd", "sum"), filled_usd=("filled_usd", "sum"),
        safety_stock_usd=("safety_stock_usd", "sum"), avg_stock_usd=("avg_stock_usd", "sum"),
        median_item_fill_rate=("fill_rate", "median"), in_stock_months=("in_stock_months", "mean"),
        items_below_90pct_fill=("fill_rate", lambda x: int((x < 0.90).sum())))
    g["fill_rate_value_weighted"] = g.filled_usd / g.demand_usd
    g["months_of_supply"] = g.avg_stock_usd / (g.demand_usd / 12)
    return g.reset_index()

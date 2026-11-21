"""MRP-style netting with booked orders.

A purchase line's quote (PQ) goes to the country well before delivery, a median of ~190 days for
the stock items. So at any month-end the planner already knows most of the next few months'
demand. MRP uses that: gross requirement for a future month = the larger of booked orders and
the forecast (forecast consumption). Only demand beyond the booked horizon is forecast.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm

from config import FIT_START, SERVICE_TARGET, TEST_END, WARMUP_START
from policy import protection_months

MAX_HORIZON = 12


def booked_matrix(lines, items, asof_months):
    """packs[item][i, h-1] = packs delivered in month asof_i + h on lines quoted by the end of asof_i."""
    x = lines[lines.item.isin(items) & lines.pq_sent_date.notna()]
    out = {}
    for item, g in x.groupby("item"):
        arr = np.zeros((len(asof_months), MAX_HORIZON))
        for i, a in enumerate(asof_months):
            end = a + pd.offsets.MonthEnd(0)
            known = g[(g.pq_sent_date <= end) & (g.month > a)]
            h = (known.month.dt.year - a.year) * 12 + known.month.dt.month - a.month
            ok = h <= MAX_HORIZON
            np.add.at(arr[i], h[ok].to_numpy() - 1, known.packs[ok].to_numpy())
        out[item] = arr
    return out


def visibility(lines, items, asof_months, horizon=8):
    """Share of each future month's demand (packs and $) already booked at the planning date."""
    x = lines[lines.item.isin(items)]
    last = x.month.max()
    rows = []
    for a in asof_months:
        end = a + pd.offsets.MonthEnd(0)
        for h in range(1, horizon + 1):
            m = a + pd.DateOffset(months=h)
            if m > pd.Timestamp(TEST_END) or m > last:
                continue
            y = x[x.month == m]
            b = y[y.pq_sent_date <= end]
            rows.append({"asof": a, "months_ahead": h, "demand_packs": y.packs.sum(), "booked_packs": b.packs.sum(),
                         "demand_usd": y.line_value.sum(), "booked_usd": b.line_value.sum()})
    r = pd.DataFrame(rows).groupby("months_ahead")[["demand_packs", "booked_packs", "demand_usd", "booked_usd"]].sum()
    r["booked_share_packs"] = r.booked_packs / r.demand_packs
    r["booked_share_usd"] = r.booked_usd / r.demand_usd
    r["planning_dates"] = len(asof_months)
    return r.reset_index()


def booked_levels(history, booked, lt_days, window, n_hist):
    """Order-up-to level per simulated month: booked-or-forecast requirement over the protection
    period, plus a buffer for lead-time variability only."""
    p = protection_months(lt_days)
    p_mean, p_sd = p.mean(), p.std(ddof=1)
    n_full, frac = int(np.floor(p_mean)), p_mean - np.floor(p_mean)
    z = norm.ppf(SERVICE_TARGET)
    levels = []
    for i, t in enumerate(range(n_hist, len(history))):
        f = history[t - window + 1: t + 1].mean()
        req = np.maximum(booked[i], f)
        need = req[:n_full].sum() + frac * req[n_full]
        levels.append(need + z * p_sd * f)
    return np.array(levels)


def record(item, history_months, history, booked_row, plan_row, asof, horizon=9):
    """Time-phased MRP record at one planning date (packs). Starting stock and open orders are
    assumptions, stated in the README: on hand = safety stock, and open orders cover the booked-or-
    forecast requirement for each month inside the lead time."""
    lt_months = int(np.rint(plan_row.lt_mean_months))
    f = history[-12:].mean()
    booked = booked_row[:horizon]
    gross = np.maximum(booked, f)
    ss = norm.ppf(SERVICE_TARGET) * plan_row.lt_sd_months * f
    on_hand = ss
    rows = []
    for h in range(1, horizon + 1):
        sched = gross[h - 1] if h <= lt_months else 0.0
        net = max(round(gross[h - 1] + ss - on_hand - sched, 6), 0.0)     # lot-for-lot
        on_hand = on_hand + sched + net - gross[h - 1]
        rows.append({"item": item, "planning_date": asof.date(), "month": (asof + pd.DateOffset(months=h)).date(),
                     "booked_orders": booked[h - 1], "forecast": f, "gross_requirement": gross[h - 1],
                     "scheduled_receipts": sched, "net_requirement": net, "planned_order_receipt": net,
                     "projected_on_hand": on_hand, "safety_stock": ss})
    r = pd.DataFrame(rows)
    # Planned order release = receipt offset by the mean lead time; releases before the planning
    # date would be late and are flagged for expediting.
    r["planned_order_release_month"] = [(asof + pd.DateOffset(months=h - lt_months)).date() for h in range(1, horizon + 1)]
    r["release_status"] = np.where(r.planned_order_receipt < 0.5, "",
                                   np.where(np.arange(1, horizon + 1) - lt_months < 1, "Past due: expedite", "Release"))
    return r

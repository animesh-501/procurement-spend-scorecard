"""Turn the SQL scorecard into tiers a category manager can act on.

Thresholds are explicit rather than a weighted composite score, so each tier says what's wrong:
  price issue    = price index above 1.05 (paying 5%+ over the item benchmark)
  delivery issue = fewer than 95% of lines delivered on or before the scheduled date
"""
import numpy as np
import pandas as pd

PRICE_LIMIT = 1.05
ON_TIME_TARGET = 0.95


def tiers(card):
    c = card.copy()
    price_bad = c.price_index > PRICE_LIMIT
    late_bad = c.on_time_rate < ON_TIME_TARGET
    c["tier"] = np.select(
        [price_bad & late_bad, price_bad, late_bad],
        ["Review: price and delivery", "Fix price", "Fix delivery"],
        default="Preferred",
    )
    return c


def tier_summary(card):
    t = card.groupby("tier").agg(vendors=("vendor", "size"), spend=("spend", "sum"),
                                 excess_usd=("excess_usd", "sum"))
    t["spend_share"] = t.spend / card.spend.sum()
    order = ["Preferred", "Fix delivery", "Fix price", "Review: price and delivery"]
    return t.reindex([o for o in order if o in t.index]).reset_index()


def short_name(v):
    """Vendor names are long legal names; trim for charts."""
    v = v.split(" (")[0]
    for s in [" LIMITED", " Limited", " LTD.", " LTD", ", Ltd", ", Inc.", ", Plc", " Inc.", " CO.,LTD.", " GmbH & Co. KG"]:
        v = v.replace(s, "")
    return v.strip().title() if v.isupper() else v.strip()

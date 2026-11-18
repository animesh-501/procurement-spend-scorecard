"""Landed cost view: re-score suppliers on goods + freight + insurance, and compare benchmarks."""
import pandas as pd

import scorecard


def vendor_table(card, vendor_landed):
    """Scorecard vendors with price index (goods only) next to landed index, and the tier each gives."""
    v = card.merge(vendor_landed, on="vendor", how="left")
    v["landed_tier"] = scorecard.tiers(v.assign(price_index=v.landed_index))["tier"]
    cols = ["vendor", "spend", "main_inco_term", "seller_pays_share", "freight_insurance_pct_of_goods",
            "freight_estimated_share", "on_time_rate", "price_index", "landed_index", "landed_index_term_rule",
            "excess_usd", "landed_excess_usd", "landed_excess_usd_term_rule", "tier", "landed_tier"]
    return v[cols]


def benchmarks(pv, lv):
    """The three ways of measuring 'paid above benchmark', on the same benchmarked lines."""
    rows = [
        ("Item median price, same year", pv.excess_usd.sum(), pv.line_value.sum()),
        ("Item median price, same year and same delivery terms", pv.excess_usd_same_terms.sum(),
         pv.line_value.sum()),
        ("Item median landed cost, same year", lv.landed_excess_usd.sum(), lv.landed_value.sum()),
        ("Item median landed cost, same year (no freight on seller-paid terms)",
         lv.landed_excess_usd_term_rule.sum(), lv.landed_value_term_rule.sum()),
    ]
    b = pd.DataFrame(rows, columns=["benchmark", "excess_usd", "spend_compared"])
    b["excess_pct"] = b.excess_usd / b.spend_compared
    return b


def same_terms_gap(pv):
    """Why the same-delivery-terms benchmark comes out lower than the plain item benchmark."""
    g = (pv.groupby(["item", "year", "inco_term"])
           .agg(term_lines=("line_id", "size"), term_vendors=("vendor", "nunique")).reset_index())
    x = pv.merge(g, on=["item", "year", "inco_term"])
    x["reason"] = "2+ suppliers on the same terms"
    x.loc[x.term_vendors == 1, "reason"] = "only one supplier on those terms (it sets its own benchmark)"
    x.loc[x.term_lines < 5, "reason"] = "under 5 purchases on those terms (no benchmark, counted as zero)"
    x["gap_usd"] = x.excess_usd - x.excess_usd_same_terms.fillna(0)
    out = x.groupby("reason").agg(lines=("line_id", "size"), excess_usd=("excess_usd", "sum"),
                                  excess_usd_same_terms=("excess_usd_same_terms", "sum"),
                                  gap_usd=("gap_usd", "sum"))
    out["share_of_gap"] = out.gap_usd / out.gap_usd.sum()
    return out.sort_values("gap_usd", ascending=False).reset_index()

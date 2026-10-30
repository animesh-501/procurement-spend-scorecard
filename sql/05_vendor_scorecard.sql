-- Supplier scorecard for vendors that deliver directly, with enough lines to judge.
--   price_index  = what the vendor charged / what the same items' benchmark would have cost.
--                  1.00 = at the median, 1.10 = 10% above it.
--   on_time_rate = share of lines delivered on or before the scheduled date.

CREATE OR REPLACE TABLE vendor_scorecard AS
WITH direct AS (
    SELECT * FROM lines WHERE channel = 'Direct from vendor'
),
base AS (
    SELECT
        vendor,
        COUNT(*)                                                  AS lines,
        COUNT(DISTINCT item)                                      AS items,
        SUM(line_value)                                           AS spend,
        AVG(on_time::INT)                                         AS on_time_rate,
        AVG(days_late) FILTER (WHERE days_late > 0)               AS avg_days_late_when_late,
        MEDIAN(lead_time_days) FILTER (WHERE lead_time_days >= 0) AS median_lead_time_days,
        SUM(freight_usd) FILTER (WHERE freight_usd IS NOT NULL)
          / NULLIF(SUM(line_value) FILTER (WHERE freight_usd IS NOT NULL), 0) AS freight_pct_of_value
    FROM direct
    GROUP BY vendor
    HAVING COUNT(*) >= {MIN_LINES_FOR_SCORECARD}
),
price AS (
    SELECT vendor,
           SUM(pack_price * packs) / SUM(benchmark_price * packs) AS price_index,
           SUM(line_value)                                        AS benchmarked_spend,
           SUM(excess_usd)                                        AS excess_usd
    FROM price_variance
    WHERE channel = 'Direct from vendor'
    GROUP BY vendor
)
SELECT
    b.*,
    p.price_index,
    p.benchmarked_spend / b.spend AS share_of_spend_benchmarked,
    p.excess_usd
FROM base b
LEFT JOIN price p USING (vendor)
ORDER BY spend DESC;

CREATE OR REPLACE TABLE freight_by_mode AS
SELECT
    shipment_mode,
    COUNT(*)                                                                   AS lines,
    SUM(line_value)                                                            AS spend,
    COUNT(freight_usd)                                                         AS lines_with_freight,
    SUM(freight_usd) / NULLIF(SUM(line_value) FILTER (WHERE freight_usd IS NOT NULL), 0) AS freight_pct_of_value,
    SUM(freight_usd) / NULLIF(SUM(weight_kg) FILTER (WHERE freight_usd IS NOT NULL AND weight_kg > 0), 0) AS freight_usd_per_kg,
    AVG(on_time::INT)                                                          AS on_time_rate
FROM lines
GROUP BY shipment_mode
ORDER BY spend DESC;

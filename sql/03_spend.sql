-- Spend cube.

CREATE OR REPLACE TABLE spend_by_year AS
SELECT year, channel, COUNT(*) AS lines, SUM(line_value) AS spend
FROM lines
GROUP BY 1, 2
ORDER BY 1, 2;

-- Vendor concentration for direct purchases (warehouse lines are internal transfers, not a vendor)
CREATE OR REPLACE TABLE vendor_pareto AS
WITH v AS (
    SELECT vendor, COUNT(*) AS lines, SUM(line_value) AS spend
    FROM lines
    WHERE channel = 'Direct from vendor'
    GROUP BY vendor
)
SELECT
    ROW_NUMBER() OVER (ORDER BY spend DESC)                          AS rank,
    vendor,
    lines,
    spend,
    spend / SUM(spend) OVER ()                                       AS spend_share,
    SUM(spend) OVER (ORDER BY spend DESC) / SUM(spend) OVER ()       AS cumulative_share
FROM v
ORDER BY rank;

-- Packs delivered to countries per item per month, by any route (direct or from a warehouse).
-- This is the demand a central planner has to cover.

CREATE OR REPLACE TABLE monthly_demand AS
SELECT item, month, SUM(packs) AS packs, COUNT(*) AS lines
FROM lines
GROUP BY item, month;

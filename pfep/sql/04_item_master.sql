-- Descriptive half of the Plan for Every Part: one row per item, full history.

CREATE OR REPLACE TABLE item_vendor AS
SELECT item, vendor, SUM(line_value) AS spend,
       ROW_NUMBER() OVER (PARTITION BY item ORDER BY SUM(line_value) DESC, vendor) AS rnk
FROM lines
WHERE channel = 'Direct from vendor'
GROUP BY item, vendor;

CREATE OR REPLACE TABLE item_master AS
WITH base AS (
    SELECT
        item,
        MODE(product_group)                                    AS product_group,
        MODE(sub_class)                                            AS sub_class,
        MODE(dosage_form)                                           AS dosage_form,
        MODE(units_per_pack)                                        AS units_per_pack,
        COUNT(*)                                                    AS lines,
        SUM(packs)                                                  AS packs,
        SUM(line_value)                                             AS spend,
        MIN(delivered_date)                                         AS first_delivery,
        MAX(delivered_date)                                         AS last_delivery,
        AVG(CASE WHEN channel = 'Direct from vendor' THEN 1 ELSE 0 END) AS direct_share_of_lines,
        COUNT(DISTINCT CASE WHEN channel = 'Direct from vendor' THEN vendor END) AS direct_vendors,
        COUNT(DISTINCT manufacturing_site)                          AS manufacturing_sites,
        MODE(shipment_mode)                                         AS main_shipment_mode,
        MODE(CASE WHEN channel = 'Direct from vendor' THEN inco_term END) AS main_inco_term,
        -- weight is only numeric on some lines; kg per pack from those lines
        SUM(CASE WHEN weight_kg > 0 THEN weight_kg END)
          / NULLIF(SUM(CASE WHEN weight_kg > 0 THEN packs END), 0)  AS kg_per_pack,
        AVG(CASE WHEN channel = 'Direct from vendor' THEN on_time::INT END) AS direct_on_time_rate,
        AVG(packs)                                                  AS avg_line_packs
    FROM lines
    GROUP BY item
)
SELECT b.*,
       v.vendor                                                     AS main_vendor,
       v.spend / NULLIF(t.direct_spend, 0)                          AS main_vendor_share
FROM base b
LEFT JOIN item_vendor v ON v.item = b.item AND v.rnk = 1
LEFT JOIN (SELECT item, SUM(spend) AS direct_spend FROM item_vendor GROUP BY item) t ON t.item = b.item;

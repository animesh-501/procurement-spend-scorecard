-- Landed cost: goods + freight + insurance for every purchase line.
--
-- Freight is recorded four ways in the source file:
--   a number                        -> freight paid on this line
--   "Freight Included in Commodity" -> already in the goods price, so zero extra
--   "See ASN-... (ID#:n)"           -> the shipment's freight sits on line n; it is shared across
--                                      line n and every line pointing to it, by line value
--                                      (evenly if the whole shipment has zero value)
--   "Invoiced Separately"           -> paid but not recorded; estimated at the freight rate
--                                      (% of goods value) of lines with the same mode and INCO term
-- Insurance is a number on 97% of lines; the rest get that year's median insurance rate.
-- Seller-paid terms (DDP, DAP, DDU, CIP, CIF) are also tested with freight forced to zero,
-- in case recorded freight on those lines was the vendor's cost passed through in the price.

CREATE OR REPLACE TABLE landed_lines AS
WITH f AS (
    SELECT
        l.line_id, l.vendor, l.item, l.year, l.channel, l.inco_term, l.shipment_mode,
        l.packs, l.pack_price, l.line_value,
        TRY_CAST(r.freight_raw AS DOUBLE)                                   AS freight_num,
        CASE WHEN TRY_CAST(r.freight_raw AS DOUBLE) IS NOT NULL THEN 'Recorded'
             WHEN r.freight_raw LIKE 'Freight Included%'        THEN 'In goods price'
             WHEN r.freight_raw LIKE 'Invoiced Separately%'     THEN 'Invoiced separately'
             WHEN r.freight_raw LIKE 'See %'                    THEN 'On another line'
        END                                                                 AS freight_note,
        TRY_CAST(REGEXP_EXTRACT(r.freight_raw, 'ID#:(\d+)', 1) AS INTEGER)  AS ref_id,
        TRY_CAST(r.insurance_raw AS DOUBLE)                                 AS insurance_num
    FROM lines l
    JOIN raw_lines r USING (line_id)
),
shipment AS (
    -- a shipment = the line holding the freight entry plus every line that points to it
    SELECT COALESCE(ref_id, line_id) AS ship_id, SUM(line_value) AS ship_value, COUNT(*) AS ship_lines
    FROM f GROUP BY 1
),
assigned AS (
    SELECT
        f.*,
        h.freight_note                                               AS ship_note,
        CASE
            WHEN f.freight_note = 'In goods price' THEN 0
            WHEN h.freight_note = 'Recorded'
                THEN h.freight_num * CASE WHEN s.ship_value > 0 THEN f.line_value / s.ship_value
                                           ELSE 1.0 / s.ship_lines END
        END                                                          AS freight_known
    FROM f
    LEFT JOIN shipment s ON s.ship_id = COALESCE(f.ref_id, f.line_id)
    LEFT JOIN f h   ON h.line_id = COALESCE(f.ref_id, f.line_id)
),
mode_term_rate AS (
    SELECT shipment_mode, inco_term,
           SUM(freight_known) / NULLIF(SUM(line_value), 0) AS rate
    FROM assigned WHERE freight_known IS NOT NULL AND line_value > 0
    GROUP BY 1, 2
),
mode_rate AS (
    SELECT shipment_mode, SUM(freight_known) / NULLIF(SUM(line_value), 0) AS rate
    FROM assigned WHERE freight_known IS NOT NULL AND line_value > 0
    GROUP BY 1
),
ins_rate AS (
    SELECT year, MEDIAN(insurance_num / line_value) AS rate
    FROM f WHERE insurance_num IS NOT NULL AND line_value > 0
    GROUP BY 1
)
SELECT
    a.line_id, a.vendor, a.item, a.year, a.channel, a.inco_term, a.shipment_mode,
    a.packs, a.pack_price, a.line_value,
    CASE WHEN a.freight_note = 'On another line' AND a.ship_note = 'Recorded' THEN 'Shared from another line'
         WHEN a.freight_note = 'On another line'                               THEN 'Invoiced separately'
         ELSE a.freight_note END                                              AS freight_source,
    COALESCE(a.freight_known,
             a.line_value * COALESCE(mt.rate, mr.rate,
                                     (SELECT SUM(freight_known) / SUM(line_value) FROM assigned
                                      WHERE freight_known IS NOT NULL)))      AS freight_usd,
    a.freight_known IS NULL                                                   AS freight_estimated,
    COALESCE(a.insurance_num,
             a.line_value * COALESCE(ir.rate,
                                     (SELECT MEDIAN(insurance_num / line_value) FROM f
                                      WHERE insurance_num IS NOT NULL AND line_value > 0)))
                                                                              AS insurance_usd,
    a.insurance_num IS NULL                                                   AS insurance_estimated,
    a.inco_term IN ('DDP', 'DAP', 'DDU', 'CIP', 'CIF')                        AS seller_pays_carriage
FROM assigned a
LEFT JOIN mode_term_rate mt ON mt.shipment_mode IS NOT DISTINCT FROM a.shipment_mode
                           AND mt.inco_term = a.inco_term
LEFT JOIN mode_rate mr      ON mr.shipment_mode IS NOT DISTINCT FROM a.shipment_mode
LEFT JOIN ins_rate ir       ON ir.year = a.year;

ALTER TABLE landed_lines ADD COLUMN landed_value DOUBLE;
ALTER TABLE landed_lines ADD COLUMN landed_value_term_rule DOUBLE;
UPDATE landed_lines SET
    landed_value           = line_value + freight_usd + insurance_usd,
    landed_value_term_rule = line_value + CASE WHEN seller_pays_carriage THEN 0 ELSE freight_usd END
                             + insurance_usd;

-- Same benchmark as the price variance (item median, same year, 5+ purchases),
-- run on landed cost per pack.
CREATE OR REPLACE TABLE landed_variance AS
WITH priced AS (
    SELECT *,
           landed_value / packs           AS landed_per_pack,
           landed_value_term_rule / packs AS landed_per_pack_term_rule
    FROM landed_lines WHERE pack_price > 0 AND packs > 0
),
bench AS (
    SELECT item, year,
           MEDIAN(landed_per_pack)           AS landed_benchmark,
           MEDIAN(landed_per_pack_term_rule) AS landed_benchmark_term_rule
    FROM priced GROUP BY item, year
    HAVING COUNT(*) >= {MIN_LINES_FOR_BENCHMARK}
)
SELECT
    p.*,
    b.landed_benchmark,
    GREATEST(p.landed_per_pack - b.landed_benchmark, 0) * p.packs                     AS landed_excess_usd,
    b.landed_benchmark_term_rule,
    GREATEST(p.landed_per_pack_term_rule - b.landed_benchmark_term_rule, 0) * p.packs AS landed_excess_usd_term_rule
FROM priced p
JOIN bench b USING (item, year);

-- Per direct vendor: price index (goods only) next to landed index (goods + freight + insurance).
CREATE OR REPLACE TABLE vendor_landed AS
WITH v AS (
    SELECT
        vendor,
        SUM(line_value)                                                     AS spend,
        SUM(freight_usd)                                                    AS freight_usd,
        SUM(insurance_usd)                                                  AS insurance_usd,
        SUM(freight_usd) FILTER (WHERE freight_estimated) / NULLIF(SUM(freight_usd), 0)
                                                                            AS freight_estimated_share,
        COALESCE(SUM(line_value) FILTER (WHERE seller_pays_carriage), 0) / SUM(line_value) AS seller_pays_share,
        MODE(inco_term)                                                     AS main_inco_term
    FROM landed_lines
    WHERE channel = 'Direct from vendor'
    GROUP BY vendor
),
idx AS (
    SELECT vendor,
           SUM(landed_value) / SUM(landed_benchmark * packs)                     AS landed_index,
           SUM(landed_value_term_rule) / SUM(landed_benchmark_term_rule * packs) AS landed_index_term_rule,
           SUM(landed_excess_usd)                                                AS landed_excess_usd,
           SUM(landed_excess_usd_term_rule)                                      AS landed_excess_usd_term_rule
    FROM landed_variance
    WHERE channel = 'Direct from vendor'
    GROUP BY vendor
)
SELECT
    v.vendor, v.main_inco_term, v.seller_pays_share,
    (v.freight_usd + v.insurance_usd) / v.spend AS freight_insurance_pct_of_goods,
    v.freight_estimated_share,
    i.landed_index, i.landed_excess_usd,
    i.landed_index_term_rule, i.landed_excess_usd_term_rule
FROM v JOIN idx i USING (vendor);

-- One clean row per purchase line: parsed dates, numeric freight, delivery outcome.

CREATE OR REPLACE TABLE lines AS
SELECT
    line_id,
    vendor,
    item,
    product_group,
    sub_class,
    country,
    inco_term,
    shipment_mode,
    CASE WHEN fulfill_via = 'Direct Drop' THEN 'Direct from vendor'
         ELSE 'From regional warehouse' END                         AS channel,
    packs,
    line_value,
    pack_price,
    TRY_CAST(freight_raw AS DOUBLE)                                 AS freight_usd,
    TRY_CAST(weight_raw AS DOUBLE)                                  AS weight_kg,
    TRY_STRPTIME(po_sent_raw, '%m/%d/%Y')::DATE                     AS po_sent_date,
    STRPTIME(scheduled_raw, '%d-%b-%y')::DATE                       AS scheduled_date,
    STRPTIME(delivered_raw, '%d-%b-%y')::DATE                       AS delivered_date
FROM raw_lines;

ALTER TABLE lines ADD COLUMN days_late INTEGER;
ALTER TABLE lines ADD COLUMN on_time BOOLEAN;
ALTER TABLE lines ADD COLUMN lead_time_days INTEGER;
ALTER TABLE lines ADD COLUMN year INTEGER;
UPDATE lines SET
    days_late      = DATE_DIFF('day', scheduled_date, delivered_date),
    on_time        = delivered_date <= scheduled_date,
    lead_time_days = DATE_DIFF('day', po_sent_date, delivered_date),
    year           = YEAR(scheduled_date);

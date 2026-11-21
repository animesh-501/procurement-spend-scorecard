-- One clean row per purchase line: parsed dates, delivery month, supplier lead time.

CREATE OR REPLACE TABLE lines AS
SELECT
    line_id,
    item,
    product_group,
    sub_class,
    dosage_form,
    units_per_pack,
    vendor,
    manufacturing_site,
    inco_term,
    shipment_mode,
    CASE WHEN fulfill_via = 'Direct Drop' THEN 'Direct from vendor'
         ELSE 'From regional warehouse' END                         AS channel,
    packs,
    line_value,
    pack_price,
    TRY_CAST(weight_raw AS DOUBLE)                                  AS weight_kg,
    TRY_STRPTIME(pq_sent_raw, '%m/%d/%Y')::DATE                     AS pq_sent_date,
    TRY_STRPTIME(po_sent_raw, '%m/%d/%Y')::DATE                     AS po_sent_date,
    STRPTIME(scheduled_raw, '%d-%b-%y')::DATE                       AS scheduled_date,
    STRPTIME(delivered_raw, '%d-%b-%y')::DATE                       AS delivered_date
FROM raw_lines;

ALTER TABLE lines ADD COLUMN month DATE;
ALTER TABLE lines ADD COLUMN on_time BOOLEAN;
ALTER TABLE lines ADD COLUMN lead_time_days INTEGER;
UPDATE lines SET
    month          = DATE_TRUNC('month', delivered_date),
    on_time        = delivered_date <= scheduled_date,
    lead_time_days = DATE_DIFF('day', po_sent_date, delivered_date);

-- Supplier lead time = PO sent to vendor -> delivered to client, direct lines only.
-- Warehouse lines ship from stock and have no PO date. Negative values are date errors.
CREATE OR REPLACE TABLE lead_time_obs AS
SELECT line_id, item, vendor, product_group, po_sent_date, delivered_date, lead_time_days
FROM lines
WHERE channel = 'Direct from vendor'
  AND po_sent_date IS NOT NULL
  AND lead_time_days >= 0;

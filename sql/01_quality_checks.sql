-- Data quality checks on the raw purchase-line file.

-- 1. Coverage
SELECT COUNT(*) AS lines, COUNT(DISTINCT vendor) AS vendors, COUNT(DISTINCT item) AS items,
       ROUND(SUM(line_value) / 1e6, 1) AS spend_musd
FROM raw_lines;

-- 2. Duplicate line IDs
SELECT COUNT(*) - COUNT(DISTINCT line_id) AS duplicate_ids FROM raw_lines;

-- 3. Does line value = packs x pack price? (within 1%)
SELECT COUNT(*) AS value_mismatches
FROM raw_lines
WHERE packs > 0 AND ABS(line_value - packs * pack_price) > 0.01 * line_value + 1;

-- 4. Zero-value lines (excluded from price analysis)
SELECT COUNT(*) AS zero_value_lines FROM raw_lines WHERE line_value = 0 OR pack_price = 0;

-- 5. Freight recorded as text instead of a number (included in price, invoiced separately, see another line)
SELECT COUNT(*) AS freight_not_numeric FROM raw_lines WHERE TRY_CAST(freight_raw AS DOUBLE) IS NULL;

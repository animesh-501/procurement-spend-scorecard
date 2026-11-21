-- Checks that matter for planning parameters (run after 01_clean_lines.sql).

SELECT COUNT(*) AS lines, COUNT(DISTINCT item) AS items FROM raw_lines;
SELECT COUNT(*) AS direct_lines_with_po_date,
       SUM(CASE WHEN lead_time_days < 0 THEN 1 ELSE 0 END) AS negative_lead_time_dropped
FROM lines WHERE channel = 'Direct from vendor' AND po_sent_date IS NOT NULL;
SELECT SUM(CASE WHEN pq_sent_date IS NULL THEN 1 ELSE 0 END) AS lines_without_pq_date,
       SUM(CASE WHEN units_per_pack IS NULL THEN 1 ELSE 0 END) AS lines_without_pack_size
FROM lines;

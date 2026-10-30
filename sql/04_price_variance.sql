-- Price variance against a benchmark.
-- Benchmark = the item's median pack price in the same year, across all purchases of it.
-- "Excess" = what was paid above that median. It's the saving if every purchase above the
-- median had been bought at the median price, the usual price-harmonisation target.
-- A stricter second benchmark compares only purchases made under the same delivery (INCO) term,
-- since a delivered-duty-paid price includes freight that an ex-works price doesn't.

CREATE OR REPLACE TABLE price_variance AS
WITH priced AS (
    SELECT * FROM lines WHERE pack_price > 0 AND packs > 0
),
bench AS (
    SELECT item, year, MEDIAN(pack_price) AS benchmark_price, COUNT(*) AS bench_lines
    FROM priced GROUP BY item, year
    HAVING COUNT(*) >= {MIN_LINES_FOR_BENCHMARK}
),
bench_terms AS (
    SELECT item, year, inco_term, MEDIAN(pack_price) AS benchmark_price_same_terms
    FROM priced GROUP BY item, year, inco_term
    HAVING COUNT(*) >= {MIN_LINES_FOR_BENCHMARK}
)
SELECT
    p.line_id, p.vendor, p.item, p.year, p.channel, p.inco_term, p.packs, p.pack_price, p.line_value,
    b.benchmark_price,
    p.pack_price / b.benchmark_price - 1                                   AS variance_pct,
    GREATEST(p.pack_price - b.benchmark_price, 0) * p.packs                AS excess_usd,
    t.benchmark_price_same_terms,
    GREATEST(p.pack_price - t.benchmark_price_same_terms, 0) * p.packs     AS excess_usd_same_terms
FROM priced p
JOIN bench b USING (item, year)
LEFT JOIN bench_terms t USING (item, year, inco_term);

CREATE OR REPLACE TABLE item_opportunity AS
SELECT
    item,
    COUNT(*)                         AS lines,
    COUNT(DISTINCT vendor)           AS vendors,
    SUM(line_value)                  AS benchmarked_spend,
    SUM(excess_usd)                  AS excess_usd,
    SUM(excess_usd) / SUM(line_value) AS excess_share,
    SUM(excess_usd_same_terms)       AS excess_usd_same_terms
FROM price_variance
GROUP BY item
ORDER BY excess_usd DESC;

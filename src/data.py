"""Load the raw purchase lines, then run the SQL layer in DuckDB."""
import duckdb
import pandas as pd

from config import COLUMNS, MIN_LINES_FOR_BENCHMARK, MIN_LINES_FOR_SCORECARD, RAW_FILE, SQL_DIR

TABLES = ["lines", "spend_by_year", "vendor_pareto", "price_variance", "item_opportunity",
          "vendor_scorecard", "freight_by_mode"]


def _statements(path):
    lines = [ln for ln in path.read_text().splitlines() if not ln.strip().startswith("--")]
    sql = "\n".join(lines)
    sql = sql.replace("{MIN_LINES_FOR_BENCHMARK}", str(MIN_LINES_FOR_BENCHMARK))
    sql = sql.replace("{MIN_LINES_FOR_SCORECARD}", str(MIN_LINES_FOR_SCORECARD))
    return [s.strip() for s in sql.split(";") if s.strip()]


def build():
    raw = pd.read_csv(RAW_FILE, encoding="latin-1", usecols=list(COLUMNS), dtype=str).rename(columns=COLUMNS)
    for c in ["line_id", "packs", "line_value", "pack_price"]:
        raw[c] = pd.to_numeric(raw[c])

    con = duckdb.connect()
    con.register("raw_df", raw)
    con.execute("CREATE TABLE raw_lines AS SELECT * FROM raw_df")

    print("Data quality checks")
    for stmt in _statements(SQL_DIR / "01_quality_checks.sql"):
        print("  ", con.execute(stmt).df().to_dict("records")[0])

    for name in ["02_clean_lines.sql", "03_spend.sql", "04_price_variance.sql", "05_vendor_scorecard.sql"]:
        for stmt in _statements(SQL_DIR / name):
            con.execute(stmt)
    return {t: con.execute(f"SELECT * FROM {t}").df() for t in TABLES}

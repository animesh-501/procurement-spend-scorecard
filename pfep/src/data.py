"""Load the raw purchase lines into DuckDB and run the SQL layer."""
import duckdb
import pandas as pd

from config import COLUMNS, RAW_FILE, SQL_DIR

TABLES = ["lines", "lead_time_obs", "monthly_demand", "item_master"]


def _statements(path):
    sql = "\n".join(ln for ln in path.read_text().splitlines() if not ln.strip().startswith("--"))
    return [s.strip() for s in sql.split(";") if s.strip()]


def build():
    raw = pd.read_csv(RAW_FILE, encoding="latin-1", usecols=list(COLUMNS), dtype=str).rename(columns=COLUMNS)
    for c in ["line_id", "packs", "line_value", "pack_price", "units_per_pack"]:
        raw[c] = pd.to_numeric(raw[c])

    con = duckdb.connect()
    con.register("raw_df", raw)
    con.execute("CREATE TABLE raw_lines AS SELECT * FROM raw_df")

    for stmt in _statements(SQL_DIR / "01_clean_lines.sql"):
        con.execute(stmt)
    print("Data quality checks")
    for stmt in _statements(SQL_DIR / "02_quality_checks.sql"):
        print("  ", con.execute(stmt).df().to_dict("records")[0])
    for name in ["03_monthly_demand.sql", "04_item_master.sql"]:
        for stmt in _statements(SQL_DIR / name):
            con.execute(stmt)

    # DuckDB doesn't guarantee row order; sort so random draws are reproducible run to run
    keys = {"lines": ["line_id"], "lead_time_obs": ["line_id"], "monthly_demand": ["item", "month"],
            "item_master": ["item"]}
    out = {t: con.execute(f"SELECT * FROM {t}").df().sort_values(keys[t], ignore_index=True) for t in TABLES}
    for t in ["lines", "lead_time_obs"]:
        for c in [c for c in out[t].columns if c.endswith("_date")]:
            out[t][c] = pd.to_datetime(out[t][c])
    out["lines"]["month"] = pd.to_datetime(out["lines"]["month"])
    out["monthly_demand"]["month"] = pd.to_datetime(out["monthly_demand"]["month"])
    return out

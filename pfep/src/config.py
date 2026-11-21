"""Paths and planning settings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # pfep/
RAW_FILE = ROOT.parent / "data" / "raw" / "SCMS_Delivery_History_Dataset_20150929.csv"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"
CHART_DIR = ROOT / "charts"

# Planning windows (by delivery month). Parameters are set on the fit window only;
# the test year is replayed with the actual demand that followed.
FIT_START, FIT_END = "2012-09-01", "2014-08-01"      # 24 months
WARMUP_START = "2013-09-01"                           # last 12 fit months warm up the replay
TEST_START, TEST_END = "2014-09-01", "2015-08-01"     # 12 months (data ends mid-Sep 2015)

# Stock / non-stock rule: stock an item if it had demand in at least this many of the 24 fit months.
STOCK_MIN_MONTHS = 12

# Lead time: item-level if it has this many observations, else main vendor, else product group.
MIN_LT_OBS = 10
DAYS_PER_MONTH = 30.4

# Replenishment policy: monthly review, order up to S. Target = chance of no stock-out per cycle.
REVIEW_MONTHS = 1
SERVICE_TARGET = 0.95

# Replay. Re-planned variants recompute S each month from this many trailing months of demand.
REPLAN_WINDOWS = [12, 6]
N_SIMS = 500
N_BOOTSTRAP = 20000
SEED = 42

COLUMNS = {
    "ID": "line_id",
    "Fulfill Via": "fulfill_via",
    "Vendor INCO Term": "inco_term",
    "Shipment Mode": "shipment_mode",
    "PQ First Sent to Client Date": "pq_sent_raw",
    "PO Sent to Vendor Date": "po_sent_raw",
    "Scheduled Delivery Date": "scheduled_raw",
    "Delivered to Client Date": "delivered_raw",
    "Product Group": "product_group",
    "Sub Classification": "sub_class",
    "Vendor": "vendor",
    "Item Description": "item",
    "Dosage Form": "dosage_form",
    "Unit of Measure (Per Pack)": "units_per_pack",
    "Line Item Quantity": "packs",
    "Line Item Value": "line_value",
    "Pack Price": "pack_price",
    "Manufacturing Site": "manufacturing_site",
    "Weight (Kilograms)": "weight_raw",
}

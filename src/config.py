"""Paths and analysis settings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "SCMS_Delivery_History_Dataset_20150929.csv"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"
CHART_DIR = ROOT / "charts"

# Price benchmark: an item's median pack price in the same year, from at least this many purchases
MIN_LINES_FOR_BENCHMARK = 5
# Vendors need this many direct-delivery lines to get a scorecard
MIN_LINES_FOR_SCORECARD = 20

COLUMNS = {
    "ID": "line_id",
    "Country": "country",
    "Managed By": "managed_by",
    "Fulfill Via": "fulfill_via",
    "Vendor INCO Term": "inco_term",
    "Shipment Mode": "shipment_mode",
    "PO Sent to Vendor Date": "po_sent_raw",
    "Scheduled Delivery Date": "scheduled_raw",
    "Delivered to Client Date": "delivered_raw",
    "Product Group": "product_group",
    "Sub Classification": "sub_class",
    "Vendor": "vendor",
    "Item Description": "item",
    "Line Item Quantity": "packs",
    "Line Item Value": "line_value",
    "Pack Price": "pack_price",
    "Weight (Kilograms)": "weight_raw",
    "Freight Cost (USD)": "freight_raw",
}

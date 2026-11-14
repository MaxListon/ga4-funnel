from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_BQ = ROOT / "sql" / "bigquery"
SQL_LOCAL = ROOT / "sql" / "duckdb"
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "outputs"

# The four extracts, in the shape BigQuery returns them (synthetic data matches this).
RAW_TABLES = ("sessions", "session_events", "transactions", "items")

FUNNEL_STEPS = (
    ("session_start", "Session"),
    ("view_item", "Viewed product"),
    ("add_to_cart", "Added to cart"),
    ("begin_checkout", "Began checkout"),
    ("add_shipping_info", "Shipping info"),
    ("add_payment_info", "Payment info"),
    ("purchase", "Purchased"),
)
STEP_LABELS = dict(FUNNEL_STEPS)

SEGMENTS = ("device_category", "channel", "week")

# Segments smaller than this are excluded from "best/worst" comparisons in findings.
MIN_SEGMENT_SESSIONS = 1_000

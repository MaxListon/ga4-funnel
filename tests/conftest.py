import pandas as pd
import pytest

from ga4funnel import synth
from ga4funnel.pipeline import analyse, connect_frames

S = 1_000_000  # one second in GA4 microseconds


def make_frames(sessions, events, transactions=(), items=()):
    """Build the four raw frames from compact tuples (for hand-checked tests)."""
    sess = pd.DataFrame(
        [dict(user_pseudo_id=u, session_id=sid, session_start_ts=ts, device_category=dev,
              operating_system="x", country="US", source=src, medium=med, campaign=None,
              first_user_source=fsrc, first_user_medium=fmed, n_events=1)
         for (u, sid, ts, dev, src, med, fsrc, fmed) in sessions])
    ev = pd.DataFrame(list(events), columns=["user_pseudo_id", "session_id", "event_name", "first_ts", "n_events"])
    tx = pd.DataFrame(list(transactions), columns=["transaction_id", "user_pseudo_id", "session_id", "event_ts", "revenue_usd"])
    it = pd.DataFrame(list(items), columns=["event_name", "item_name", "item_category", "n_item_events", "quantity", "item_revenue_usd"])
    # Typed empties so DuckDB can bind columns
    if tx.empty:
        tx = tx.astype({"transaction_id": str, "user_pseudo_id": str, "session_id": "int64", "event_ts": "int64", "revenue_usd": float})
    if it.empty:
        it = it.astype({"event_name": str, "item_name": str, "item_category": str, "n_item_events": "int64", "quantity": "int64", "item_revenue_usd": float})
    return {"sessions": sess, "session_events": ev, "transactions": tx, "items": it}


@pytest.fixture(scope="session")
def demo():
    frames = synth.generate(n_sessions=6_000, seed=11)
    con = connect_frames(frames)
    tables = analyse(con)
    return frames, con, tables

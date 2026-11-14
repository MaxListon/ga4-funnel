"""Synthetic data in the exact shape of the four BigQuery extracts.

FOR TESTS AND DEMO ONLY. The numbers it produces mean nothing about the real
Google Merchandise Store. The pipeline stamps every output it builds from this
data with a DEMO DATA banner.

Usage:  python -m ga4funnel.synth   (writes data/raw/*.parquet, SOURCE=synthetic)
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import RAW_DIR

START = int(datetime(2020, 11, 1, tzinfo=timezone.utc).timestamp() * 1_000_000)
WINDOW_US = 92 * 24 * 3600 * 1_000_000

SOURCES = [  # (source, medium, probability)
    ("google", "organic", 0.34),
    ("(direct)", "(none)", 0.24),
    ("google", "cpc", 0.08),
    ("shop.example.com", "referral", 0.12),
    ("newsletter", "email", 0.04),
    ("<Other>", "<Other>", 0.10),
    ("(data deleted)", "(data deleted)", 0.08),
]
DEVICES = [("desktop", 0.58), ("mobile", 0.40), ("tablet", 0.02)]
COUNTRIES = [("United States", 0.45), ("India", 0.1), ("Canada", 0.08), ("United Kingdom", 0.07), ("Other", 0.30)]

# Base step-through probabilities (conditional on reaching the previous step).
P_STEP = {"view_item": 0.42, "add_to_cart": 0.24, "begin_checkout": 0.50,
          "add_shipping_info": 0.82, "add_payment_info": 0.78, "purchase": 0.72}
MOBILE_PENALTY = {"add_to_cart": 0.85, "begin_checkout": 0.80}
STEPS = list(P_STEP)


def _pick(rng, options, n):
    vals = [o[:-1] if len(o) > 2 else o[0] for o in options]
    p = np.array([o[-1] for o in options], dtype=float)
    idx = rng.choice(len(options), size=n, p=p / p.sum())
    return [vals[i] for i in idx]


def generate(n_sessions: int = 20_000, seed: int = 7) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    n_users = int(n_sessions * 0.72)
    user_ids = [f"demo_user_{i:06d}" for i in range(n_users)]
    users = rng.integers(0, n_users, n_sessions)
    user_first = {u: s for u, s in zip(range(n_users), _pick(rng, SOURCES, n_users))}
    user_device = dict(zip(range(n_users), _pick(rng, DEVICES, n_users)))
    user_country = dict(zip(range(n_users), _pick(rng, COUNTRIES, n_users)))

    session_src = _pick(rng, SOURCES, n_sessions)
    starts = START + rng.integers(0, WINDOW_US, n_sessions)
    session_ids = rng.choice(10**9, size=n_sessions, replace=False) + 10**9

    sess_rows, ev_rows, tx_rows = [], [], []
    tx_counter = 0
    for i in range(n_sessions):
        u = int(users[i])
        uid, sid, t0 = user_ids[u], int(session_ids[i]), int(starts[i])
        device = user_device[u]
        src, med = session_src[i]
        fsrc, fmed = user_first[u]
        n_events = 1
        if rng.random() > 0.02:  # ~2% of sessions lose their session_start event
            ev_rows.append((uid, sid, "session_start", t0, 1))
        t = t0
        reached = {}
        for step in STEPS:
            p = P_STEP[step] * (MOBILE_PENALTY.get(step, 1.0) if device == "mobile" else 1.0)
            if rng.random() >= p:
                break
            t += int(rng.integers(5, 300)) * 1_000_000
            reached[step] = t
        # ~3% of carting sessions add to cart from a list page before ever viewing an item
        if "add_to_cart" in reached and rng.random() < 0.03:
            reached["add_to_cart"] = reached["view_item"] - 120_000_000
        for step, ts in reached.items():
            cnt = int(rng.integers(1, 4))
            n_events += cnt
            ev_rows.append((uid, sid, step, ts, cnt))
        if "purchase" in reached:
            tx_counter += 1
            rev = round(float(rng.lognormal(3.9, 0.6)), 2)
            tx_rows.append((f"T{tx_counter:06d}", uid, sid, reached["purchase"], rev))
        sess_rows.append((uid, sid, t0, device, "Windows" if device == "desktop" else "Android",
                          user_country[u], src, med, "(organic)", fsrc, fmed, n_events + int(rng.integers(0, 20))))

    # Inject a few duplicate purchase events (same transaction id) for the quality audit.
    for row in tx_rows[:5]:
        tx_rows.append((row[0], row[1], row[2], row[3] + 2_000_000, row[4]))

    sessions = pd.DataFrame(sess_rows, columns=[
        "user_pseudo_id", "session_id", "session_start_ts", "device_category", "operating_system",
        "country", "source", "medium", "campaign", "first_user_source", "first_user_medium", "n_events"])
    session_events = pd.DataFrame(ev_rows, columns=["user_pseudo_id", "session_id", "event_name", "first_ts", "n_events"])
    transactions = pd.DataFrame(tx_rows, columns=["transaction_id", "user_pseudo_id", "session_id", "event_ts", "revenue_usd"])

    item_rows = []
    for j in range(40):
        name, cat = f"Demo Item {j:02d}", ["Apparel", "Drinkware", "Bags", "Office"][j % 4]
        views = int(rng.integers(300, 4000))
        carts = int(views * rng.uniform(0.05, 0.35))
        units = int(carts * rng.uniform(0.2, 0.6))
        price = float(rng.uniform(5, 60))
        item_rows += [("view_item", name, cat, views, views, 0.0),
                      ("add_to_cart", name, cat, carts, carts, 0.0),
                      ("purchase", name, cat, max(units, 0), units, round(units * price, 2))]
    items = pd.DataFrame(item_rows, columns=["event_name", "item_name", "item_category", "n_item_events", "quantity", "item_revenue_usd"])

    return {"sessions": sessions, "session_events": session_events, "transactions": transactions, "items": items}


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in generate().items():
        df.to_parquet(RAW_DIR / f"{name}.parquet", index=False)
        print(f"[{name}] {len(df):,} synthetic rows")
    (RAW_DIR / "SOURCE").write_text("synthetic\n")
    print("Synthetic DEMO data written. Next: python -m ga4funnel.run")


if __name__ == "__main__":
    main()

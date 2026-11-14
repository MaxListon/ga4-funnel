"""Build the local DuckDB models and the analysis tables from the raw extracts."""
from pathlib import Path

import duckdb
import pandas as pd

from .config import FUNNEL_STEPS, RAW_TABLES, SQL_LOCAL, STEP_LABELS
from .stats import wilson


def connect_frames(frames: dict[str, pd.DataFrame]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for name in RAW_TABLES:
        con.register(f"_df_{name}", frames[name])
        con.execute(f"CREATE VIEW raw_{name} AS SELECT * FROM _df_{name}")
    return con


def connect_parquet(raw_dir: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for name in RAW_TABLES:
        path = raw_dir / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing - run ga4funnel.extract (or ga4funnel.synth for demo data)")
        con.read_parquet(str(path)).create_view(f"raw_{name}")
    return con


def build_models(con: duckdb.DuckDBPyConnection) -> None:
    for sql_file in sorted(SQL_LOCAL.glob("*.sql")):
        con.execute(sql_file.read_text())


def funnel(con: duckdb.DuckDBPyConnection, by: str | None = None) -> pd.DataFrame:
    """Funnel counts per step with Wilson CIs.

    open_rate   = sessions that fired the step / all sessions   (headline conversion; always a valid proportion)
    step_rate   = closed sessions at step k / closed at step k-1 (where the in-order path leaks)
    closed_rate = closed sessions at step k / all sessions
    """
    seg = by if by else "'All sessions'"
    df = con.execute(f"""
        SELECT CAST({seg} AS VARCHAR) AS segment, step_order, step,
               count(*) FILTER (WHERE reached_open)   AS sessions_open,
               count(*) FILTER (WHERE reached_closed) AS sessions_closed
        FROM session_steps
        GROUP BY ALL
        ORDER BY segment, step_order
    """).df()
    df.insert(0, "segment_type", by or "overall")
    df["step_label"] = df["step"].map(STEP_LABELS)

    prev = df.groupby("segment")["sessions_closed"].shift(1)
    first = df.groupby("segment")["sessions_closed"].transform("first")
    df["open_rate"] = df["sessions_open"] / first
    df["step_rate"] = df["sessions_closed"] / prev
    df["closed_rate"] = df["sessions_closed"] / first
    df["lost_sessions"] = prev - df["sessions_closed"]

    ci = [wilson(int(k), int(n)) for k, n in zip(df["sessions_open"], first)]
    df["open_rate_lo"], df["open_rate_hi"] = zip(*ci)
    ci = [wilson(int(k), int(n)) if pd.notna(n) else (float("nan"),) * 2
          for k, n in zip(df["sessions_closed"], prev)]
    df["step_rate_lo"], df["step_rate_hi"] = zip(*ci)
    ci = [wilson(int(k), int(n)) for k, n in zip(df["sessions_closed"], first)]
    df["closed_rate_lo"], df["closed_rate_hi"] = zip(*ci)
    return df


def quality_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    q = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    sessions = q("SELECT count(*) FROM sessions")
    rows = [
        ("Sessions", sessions, "Distinct (user_pseudo_id, ga_session_id) pairs"),
        ("Users", q("SELECT count(DISTINCT user_pseudo_id) FROM sessions"), ""),
        ("Date range", q("SELECT strftime(min(session_start_at), '%Y-%m-%d') || ' to ' || strftime(max(session_start_at), '%Y-%m-%d') FROM sessions"), ""),
        ("Sessions missing a session_start event", q("SELECT count(*) FROM sessions WHERE ts_session_start IS NULL"),
         "Counted as sessions anyway; GA4 can drop session_start"),
        ("Sessions with obfuscated source/medium", q("SELECT count(*) FROM sessions WHERE channel = 'Obfuscated'"),
         "Sample replaces some values with <Other> / (data deleted)"),
        ("Purchase events", q("SELECT count(*) FROM raw_transactions"), ""),
        ("Duplicate purchase events (same transaction_id)",
         q("SELECT coalesce(sum(c - 1), 0) FROM (SELECT count(*) c FROM raw_transactions WHERE transaction_id NOT IN ('(not set)', '') GROUP BY transaction_id HAVING count(*) > 1)"),
         "Re-fired purchase events; deduplicated before revenue is summed"),
        ("Purchase events with transaction_id '(not set)'",
         q("SELECT count(*) FROM raw_transactions WHERE transaction_id IS NULL OR transaction_id IN ('(not set)', '')"), ""),
        ("Purchase events with no session id", q("SELECT count(*) FROM raw_transactions WHERE session_id IS NULL"),
         "Excluded from session funnel"),
        ("Add-to-cart sessions with no prior view_item",
         q("SELECT count(*) FROM sessions WHERE ts_add_to_cart IS NOT NULL AND NOT c_add_to_cart"),
         "Open funnel counts them; closed funnel does not"),
        ("Purchases that skipped begin_checkout",
         q("SELECT count(*) FROM sessions WHERE ts_purchase IS NOT NULL AND ts_begin_checkout IS NULL"), ""),
        ("Checkout sessions with no add_to_cart in the session",
         q("SELECT count(*) FROM sessions WHERE ts_begin_checkout IS NOT NULL AND ts_add_to_cart IS NULL"),
         f"of {q('SELECT count(*) FROM sessions WHERE ts_begin_checkout IS NOT NULL')} checkout sessions"),
        ("Purchase sessions with no add_to_cart in the session",
         q("SELECT count(*) FROM sessions WHERE ts_purchase IS NOT NULL AND ts_add_to_cart IS NULL"),
         f"of {q('SELECT count(*) FROM sessions WHERE ts_purchase IS NOT NULL')} purchase sessions"),
        ("...of which the user carted in an earlier session",
         q("""WITH c AS (SELECT user_pseudo_id, min(ts_add_to_cart) fc FROM sessions WHERE ts_add_to_cart IS NOT NULL GROUP BY 1)
              SELECT count(*) FROM sessions s JOIN c USING (user_pseudo_id)
              WHERE s.ts_purchase IS NOT NULL AND s.ts_add_to_cart IS NULL AND c.fc < s.session_start_ts"""),
         "Carts that persist across visits; the rest suggests add_to_cart is under-tracked"),
        ("add_shipping_info logged before begin_checkout",
         q("SELECT count(*) FROM sessions WHERE ts_add_shipping_info < ts_begin_checkout"),
         f"median gap {q('SELECT coalesce(median((ts_begin_checkout - ts_add_shipping_info) / 1000.0), 0) FROM sessions WHERE ts_add_shipping_info < ts_begin_checkout'):.1f} ms: same page load; ordering uses a 5 s tolerance"),
    ]
    return pd.DataFrame(rows, columns=["check", "value", "note"]).astype({"value": str})


def analyse(con: duckdb.DuckDBPyConnection, segments=("device_category", "channel", "week")) -> dict[str, pd.DataFrame]:
    build_models(con)
    funnels = [funnel(con)] + [funnel(con, s) for s in segments]
    return {
        "funnel": pd.concat(funnels, ignore_index=True),
        "attribution": con.execute("SELECT * FROM attribution ORDER BY model, revenue_usd DESC").df(),
        "items": con.execute("SELECT * FROM item_performance ORDER BY views DESC NULLS LAST").df(),
        "quality": quality_checks(con),
    }


__all__ = ["connect_frames", "connect_parquet", "build_models", "funnel", "analyse", "FUNNEL_STEPS"]

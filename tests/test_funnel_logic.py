"""Hand-checked cases: small enough to verify every number by eye."""
import duckdb
import pytest

from ga4funnel.config import SQL_LOCAL
from ga4funnel.pipeline import analyse, build_models, connect_frames, funnel

from .conftest import S, make_frames

T0 = 1_604_188_800 * S  # 2020-11-01 UTC
STEPS = ["view_item", "add_to_cart", "begin_checkout", "add_shipping_info", "add_payment_info", "purchase"]


def full_path(u, sid, t0):
    return [(u, sid, "session_start", t0, 1)] + [(u, sid, e, t0 + (i + 1) * S, 1) for i, e in enumerate(STEPS)]


@pytest.fixture
def small():
    sessions = [
        ("a", 1, T0, "desktop", "google", "organic", "google", "organic"),          # buys, in order
        ("b", 2, T0, "mobile", "(direct)", "(none)", "google", "cpc"),             # carts BEFORE viewing
        ("c", 3, T0, "mobile", "google", "cpc", "google", "cpc"),                  # views only
        ("d", 4, T0, "desktop", "<Other>", "<Other>", "(direct)", "(none)"),       # bounces, no session_start
        ("a", 5, T0 + 86400 * S, "desktop", "(direct)", "(none)", "google", "organic"),  # a returns and buys again
    ]
    events = (
        full_path("a", 1, T0)
        + [("b", 2, "session_start", T0, 1), ("b", 2, "add_to_cart", T0 + S, 1), ("b", 2, "view_item", T0 + 60 * S, 1)]
        + [("c", 3, "session_start", T0, 1), ("c", 3, "view_item", T0 + S, 3)]
        + full_path("a", 5, T0 + 86400 * S)
    )
    tx = [("T1", "a", 1, T0 + 6 * S, 100.0),
          ("T1", "a", 1, T0 + 9 * S, 100.0),        # duplicate re-fire of T1
          ("T2", "a", 5, T0 + 86400 * S + 6 * S, 40.0)]
    con = connect_frames(make_frames(sessions, events, tx))
    build_models(con)
    return con


def counts(con, col):
    return dict(con.execute(f"SELECT step, count(*) FILTER (WHERE {col}) FROM session_steps GROUP BY step").fetchall())


def test_open_vs_closed_counts(small):
    open_, closed = counts(small, "reached_open"), counts(small, "reached_closed")
    assert open_["session_start"] == closed["session_start"] == 5   # every session counts, even without the event
    assert open_["view_item"] == closed["view_item"] == 4           # a(1), b, c, a(5); d never views
    assert open_["add_to_cart"] == 3                                # a, b, a
    assert closed["add_to_cart"] == 2                               # b carted before viewing -> excluded
    assert closed["purchase"] == 2


def test_funnel_rates(small):
    f = funnel(small)
    assert list(f.sessions_closed) == [5, 4, 2, 2, 2, 2, 2]
    assert f.loc[f.step == "add_to_cart", "step_rate"].item() == pytest.approx(2 / 4)
    assert f.loc[f.step == "purchase", "closed_rate"].item() == pytest.approx(2 / 5)
    assert f.loc[f.step == "purchase", "open_rate"].item() == pytest.approx(2 / 5)


def test_same_page_load_reversal_counts_as_in_order():
    # shipping logged 0.2 ms before checkout (as in the real data) must not break the in-order funnel
    t = T0
    ev = [("u", 9, "session_start", t, 1), ("u", 9, "view_item", t + S, 1), ("u", 9, "add_to_cart", t + 2 * S, 1),
          ("u", 9, "add_shipping_info", t + 3 * S, 1), ("u", 9, "begin_checkout", t + 3 * S + 200, 1),
          ("u", 9, "add_payment_info", t + 4 * S, 1), ("u", 9, "purchase", t + 5 * S, 1)]
    con = connect_frames(make_frames([("u", 9, t, "desktop", "google", "organic", "google", "organic")], ev))
    build_models(con)
    assert con.execute("SELECT c_purchase FROM sessions").fetchone()[0] is True


def test_duplicate_purchase_not_double_counted(small):
    assert small.execute("SELECT sum(revenue_usd) FROM sessions").fetchone()[0] == pytest.approx(140.0)
    assert small.execute("SELECT revenue_usd FROM sessions WHERE session_id = 1").fetchone()[0] == pytest.approx(100.0)


def test_attribution_models(small):
    a = small.execute("SELECT model, channel, purchase_sessions, revenue_usd FROM attribution ORDER BY ALL").fetchall()
    by = {(m, c): (n, r) for m, c, n, r in a}
    assert by[("last_touch", "Organic Search")] == (1, 100.0)
    assert by[("last_touch", "Direct")] == (1, 40.0)
    assert by[("first_touch_window", "Organic Search")] == (2, 140.0)   # both buys trace back to a's first session
    assert by[("first_user_ga4", "Organic Search")] == (2, 140.0)


def test_quality_checks_flag_problems(small):
    q = analyse(small)["quality"].set_index("check")["value"]
    assert q["Sessions missing a session_start event"] == "1"
    assert q["Duplicate purchase events (same transaction_id)"] == "1"
    assert q["Add-to-cart sessions with no prior view_item"] == "1"
    assert q["Sessions with obfuscated source/medium"] == "1"


@pytest.mark.parametrize("src,med,expected", [
    ("google", "organic", "Organic Search"),
    ("google", "cpc", "Paid Search"),
    ("(direct)", "(none)", "Direct"),
    ("(direct)", None, "Direct"),
    ("site.com", "referral", "Referral"),
    ("news", "Email", "Email"),
    ("<Other>", "<Other>", "Obfuscated"),
    ("(data deleted)", "(data deleted)", "Obfuscated"),
    (None, None, "Unassigned"),
    ("x", "something_new", "Other"),
])
def test_channel_grouping(src, med, expected):
    con = duckdb.connect()
    con.execute((SQL_LOCAL / "00_macros.sql").read_text())
    assert con.execute("SELECT channel_group(?, ?)", [src, med]).fetchone()[0] == expected

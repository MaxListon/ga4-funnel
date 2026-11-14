"""Properties that must hold on any dataset (checked here on synthetic data)."""
import pytest

from ga4funnel import findings


def test_closed_funnel_never_increases(demo):
    _, _, t = demo
    for _, g in t["funnel"].groupby(["segment_type", "segment"]):
        closed = g.sort_values("step_order").sessions_closed.tolist()
        assert closed == sorted(closed, reverse=True)


def test_closed_never_exceeds_open(demo):
    f = demo[2]["funnel"]
    assert (f.sessions_closed <= f.sessions_open).all()


@pytest.mark.parametrize("segment", ["device_category", "channel", "week"])
def test_segments_sum_to_overall(demo, segment):
    f = demo[2]["funnel"]
    overall = f[f.segment_type == "overall"].set_index("step").sessions_closed
    seg = f[f.segment_type == segment].groupby("step").sessions_closed.sum()
    assert seg.sort_index().tolist() == overall.sort_index().tolist()


def test_session_count_matches_raw(demo):
    frames, con, _ = demo
    assert con.execute("SELECT count(*) FROM sessions").fetchone()[0] == len(frames["sessions"])


def test_revenue_reconciles_with_deduplicated_transactions(demo):
    frames, con, _ = demo
    tx = frames["transactions"].sort_values("event_ts").drop_duplicates("transaction_id")
    assert con.execute("SELECT sum(revenue_usd) FROM sessions").fetchone()[0] == pytest.approx(tx.revenue_usd.sum())


def test_attribution_totals_match_across_models(demo):
    a = demo[2]["attribution"].groupby("model")[["purchase_sessions", "revenue_usd"]].sum()
    assert a.purchase_sessions.nunique() == 1
    assert a.revenue_usd.max() - a.revenue_usd.min() < 1e-6


def test_confidence_intervals_bracket_rates(demo):
    f = demo[2]["funnel"].dropna(subset=["step_rate"])
    assert ((f.step_rate_lo <= f.step_rate) & (f.step_rate <= f.step_rate_hi)).all()


def test_findings_flag_demo_data(demo):
    text = findings.build(demo[2], "synthetic")
    assert text.startswith("> **DEMO DATA.**")
    assert "DEMO DATA" not in findings.build(demo[2], "bigquery")

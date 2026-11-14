"""Smoke test: the dashboard renders every tab without errors (needs outputs/, so builds demo outputs if missing)."""
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app.py"
OUT = APP.parent / "outputs"


@pytest.mark.skipif(not (OUT / "funnel.parquet").exists(), reason="run `python -m ga4funnel.run` first")
def test_dashboard_renders():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 5
    assert at.metric[0].value  # sessions KPI populated
    # Switch segment selector to every option and rerun
    for option in ["channel", "week", "device_category"]:
        at.selectbox[0].set_value(option).run()
        assert not at.exception, at.exception

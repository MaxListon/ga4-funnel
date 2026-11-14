# GA4 Checkout Funnel Analysis: Google Merchandise Store

**Question:** Where does the Google Merchandise Store lose buyers between landing and purchase? Does that differ by device and channel? And how much does the attribution model change which channel gets credit for revenue?

**Data:** Google's public [GA4 obfuscated e-commerce sample](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset) in BigQuery: real GA4 event exports from the Google Merchandise Store, Nov 1 2020 to Jan 31 2021.

**Stack:** BigQuery SQL (extract) · DuckDB SQL (models) · Python/pandas · Streamlit + Plotly (dashboard) · CSV exports for Tableau Public · pytest

> **Findings:** see [`outputs/findings.md`](outputs/findings.md). It is generated from the data, and every number in it is computed by the pipeline rather than typed by hand.

---

## What it does

| Stage | Where | What |
|---|---|---|
| Extract | `sql/bigquery/*.sql` | Flattens nested GA4 `event_params` and pulls four compact tables: sessions, session × funnel event, purchase events, item activity |
| Model | `sql/duckdb/*.sql` | Builds sessions with a simplified GA4 channel grouping, then **open and closed funnels** (closed = steps reached in order) |
| Analyse | `ga4funnel/pipeline.py` | Funnel by device, channel and week, with **Wilson 95% CIs** on every step rate |
| Compare | `ga4funnel/stats.py` | Desktop vs mobile gap with a **Newcombe** CI on the difference |
| Attribute | `sql/duckdb/02_attribution.sql` | Revenue credit under last-touch, first-session-in-window and GA4 first-user models |
| Audit | `pipeline.quality_checks` | Duplicate transaction IDs (deduplicated before revenue is summed), missing `session_start`, out-of-order steps, obfuscated sources |
| Report | `ga4funnel/findings.py`, `app.py` | Auto-written brief + 5-tab dashboard |

### Funnel steps
Session → Viewed product → Added to cart → Began checkout → Shipping info → Payment info → Purchased

**Open vs closed.** Headline conversion is open: sessions that fired the step, divided by all sessions. Step-to-step drop-off uses the closed funnel, where steps must happen in order with a 5-second tolerance. The tolerance exists because this store logs `add_shipping_info` about 1 ms *before* `begin_checkout` on the same page load, and a strict rule would throw those sessions away.

## Headline results (real data, Nov 2020 – Jan 2021)
- **1.35%** of 360,129 sessions include a purchase (95% CI 1.31% to 1.38%). **78.6%** of sessions never open a product page.
- **Tracking gap:** 46% of checkout sessions (5,145 of 11,106) have no `add_to_cart` event. Only 252 of the 2,000 cartless buyers had carted on an earlier visit, so cart-based KPIs are understated.
- **Attribution moves revenue:** Referral gets 33.5% of revenue under last-touch but 13.1% under GA4 first-user. Direct goes from 6.7% to 22.0%.
- **Channels:** Referral converts at 2.38% and Paid Search at 0.61%. 42% of sessions have no usable source, which the brief reports rather than hides.

Full brief: [`outputs/findings.md`](outputs/findings.md).

---

## Run it

Use a virtual environment **outside OneDrive**, so OneDrive doesn't sync thousands of package files:

```bash
python3 -m venv ~/.venvs/ga4-funnel && source ~/.venvs/ga4-funnel/bin/activate
pip install -r requirements.txt
```

### 1. Pull the real data (one time, free)
1. Create a Google Cloud project at <https://console.cloud.google.com>. The **BigQuery sandbox** is free and needs no credit card.
2. Install the gcloud CLI, then run `gcloud auth application-default login`.
3. Run:
   ```bash
   python -m ga4funnel.extract --project YOUR_PROJECT_ID
   ```
   Each query is dry-run first and prints the GB it will scan. The sandbox gives 1 TB free per month, and every query has a 30 GB billing cap built in.

### 2. Build everything
```bash
python -m ga4funnel.run          # -> outputs/*.csv, *.parquet, findings.md
streamlit run app.py             # dashboard
pytest                           # 31 tests
```

**No Google Cloud account yet?** Run `python -m ga4funnel.synth` to generate **synthetic** data in the same shape. Every output built from it carries a DEMO DATA banner. Use it to explore the code, never for findings.

### Tableau Public
`outputs/funnel.csv`, `attribution.csv` and `items.csv` are tidy (long-format) files ready for Tableau. A good layout is a funnel bar chart filtered by `segment_type`, a weekly conversion line, and an attribution slope chart.

---

## Tests (31)
- **Hand-checked cases:** a five-session fixture where every count can be verified by eye. It covers out-of-order carting, a missing `session_start`, a re-fired purchase and a returning buyer.
- **Invariants** on any data: the closed funnel never increases; closed ≤ open; segments sum to the overall total; revenue reconciles with deduplicated transactions; every attribution model credits the same total.
- **Stats:** Wilson values and the published Newcombe (1998) example, 56/70 vs 48/80 → [0.0524, 0.3339].
- **Channel grouping** for 10 source/medium cases, plus a dashboard smoke test that renders every tab.

## Caveats
- The dataset is **obfuscated**: some source/medium values are `<Other>` or `(data deleted)`. These get their own "Obfuscated" channel instead of being dropped, and the brief reports their share.
- Session source/medium is the first event-level `source`/`medium` param in the session, which approximates GA4's session-scoped traffic source.
- First-session-in-window attribution is truncated at Nov 1, 2020. The GA4 first-user model is not truncated, because GA4 stores the user's original acquisition source.
- Three months that include the holiday season. Weekly trends should be read with that in mind.

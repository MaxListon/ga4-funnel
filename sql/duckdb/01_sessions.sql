-- sessions: one row per session with attributes, step timestamps and
-- open/closed funnel flags.
--   open   = the session fired the event at any point
--   closed = the session reached every earlier step first, in order
--            (first occurrence of step k is at or after first occurrence of step k-1, +/- 5 s)
CREATE OR REPLACE TABLE sessions AS
WITH steps AS (
  SELECT
    user_pseudo_id,
    session_id,
    min(first_ts) FILTER (WHERE event_name = 'session_start')     AS ts_session_start,
    min(first_ts) FILTER (WHERE event_name = 'view_item')         AS ts_view_item,
    min(first_ts) FILTER (WHERE event_name = 'add_to_cart')       AS ts_add_to_cart,
    min(first_ts) FILTER (WHERE event_name = 'begin_checkout')    AS ts_begin_checkout,
    min(first_ts) FILTER (WHERE event_name = 'add_shipping_info') AS ts_add_shipping_info,
    min(first_ts) FILTER (WHERE event_name = 'add_payment_info')  AS ts_add_payment_info,
    min(first_ts) FILTER (WHERE event_name = 'purchase')          AS ts_purchase
  FROM raw_session_events
  GROUP BY ALL
),
-- Deduplicate re-fired purchase events: keep the first event per real transaction_id.
-- Events with a missing/'(not set)' id can't be deduplicated, so each one is kept.
tx_dedup AS (
  SELECT *
  FROM raw_transactions
  WHERE session_id IS NOT NULL
  QUALIFY transaction_id IS NULL
       OR transaction_id IN ('(not set)', '')
       OR row_number() OVER (PARTITION BY transaction_id ORDER BY event_ts) = 1
),
rev AS (
  SELECT user_pseudo_id, session_id,
         count(*)                        AS n_transactions,
         coalesce(sum(revenue_usd), 0)   AS revenue_usd
  FROM tx_dedup
  GROUP BY ALL
),
base AS (
  SELECT
    s.user_pseudo_id,
    s.session_id,
    s.session_start_ts,
    make_timestamp(s.session_start_ts)                                  AS session_start_at,
    CAST(date_trunc('week', make_timestamp(s.session_start_ts)) AS DATE) AS week,
    coalesce(s.device_category, '(not set)')                            AS device_category,
    coalesce(s.country, '(not set)')                                    AS country,
    s.source, s.medium, s.campaign,
    channel_group(s.source, s.medium)                                   AS channel,
    channel_group(s.first_user_source, s.first_user_medium)             AS first_user_channel,
    s.n_events,
    st.* EXCLUDE (user_pseudo_id, session_id),
    coalesce(r.n_transactions, 0)    AS n_transactions,
    coalesce(r.revenue_usd, 0)       AS revenue_usd
  FROM raw_sessions s
  LEFT JOIN steps st USING (user_pseudo_id, session_id)
  LEFT JOIN rev   r  USING (user_pseudo_id, session_id)
),
-- "In order" allows a 5-second tolerance (5,000,000 us): in this store, add_shipping_info
-- is logged ~0.2 ms BEFORE begin_checkout on the same page load, which is noise, not a reversal.
c1 AS (SELECT *, ts_view_item IS NOT NULL AS c_view_item FROM base),
c2 AS (SELECT *, c_view_item AND coalesce(ts_add_to_cart       >= ts_view_item - 5000000,       false) AS c_add_to_cart       FROM c1),
c3 AS (SELECT *, c_add_to_cart AND coalesce(ts_begin_checkout  >= ts_add_to_cart - 5000000,     false) AS c_begin_checkout    FROM c2),
c4 AS (SELECT *, c_begin_checkout AND coalesce(ts_add_shipping_info >= ts_begin_checkout - 5000000, false) AS c_add_shipping_info FROM c3),
c5 AS (SELECT *, c_add_shipping_info AND coalesce(ts_add_payment_info >= ts_add_shipping_info - 5000000, false) AS c_add_payment_info FROM c4),
c6 AS (SELECT *, c_add_payment_info AND coalesce(ts_purchase   >= ts_add_payment_info - 5000000, false) AS c_purchase          FROM c5)
SELECT * FROM c6;

-- Long format: one row per session x funnel step (feeds every funnel cut).
CREATE OR REPLACE TABLE session_steps AS
SELECT user_pseudo_id, session_id, device_category, channel, country, week,
       1 AS step_order, 'session_start' AS step, true AS reached_open, true AS reached_closed FROM sessions
UNION ALL SELECT user_pseudo_id, session_id, device_category, channel, country, week,
       2, 'view_item',         ts_view_item         IS NOT NULL, c_view_item         FROM sessions
UNION ALL SELECT user_pseudo_id, session_id, device_category, channel, country, week,
       3, 'add_to_cart',       ts_add_to_cart       IS NOT NULL, c_add_to_cart       FROM sessions
UNION ALL SELECT user_pseudo_id, session_id, device_category, channel, country, week,
       4, 'begin_checkout',    ts_begin_checkout    IS NOT NULL, c_begin_checkout    FROM sessions
UNION ALL SELECT user_pseudo_id, session_id, device_category, channel, country, week,
       5, 'add_shipping_info', ts_add_shipping_info IS NOT NULL, c_add_shipping_info FROM sessions
UNION ALL SELECT user_pseudo_id, session_id, device_category, channel, country, week,
       6, 'add_payment_info',  ts_add_payment_info  IS NOT NULL, c_add_payment_info  FROM sessions
UNION ALL SELECT user_pseudo_id, session_id, device_category, channel, country, week,
       7, 'purchase',          ts_purchase          IS NOT NULL, c_purchase          FROM sessions;

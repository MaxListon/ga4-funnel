-- Shared CTE: one row per GA4 event, flattened to the fields this project needs.
-- Source: Google Merchandise Store GA4 obfuscated sample (Nov 2020 - Jan 2021).
-- Prepended to sessions.sql / session_events.sql / transactions.sql by extract.py.
WITH ev AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id,
    event_timestamp,
    event_name,
    device.category          AS device_category,
    device.operating_system  AS operating_system,
    geo.country              AS country,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source')   AS ev_source,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium')   AS ev_medium,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'campaign') AS ev_campaign,
    traffic_source.source    AS first_user_source,
    traffic_source.medium    AS first_user_medium,
    ecommerce.purchase_revenue_in_usd AS revenue_usd,
    ecommerce.transaction_id AS transaction_id
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
)

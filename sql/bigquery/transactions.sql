{{events_cte}}
-- One row per purchase event (kept raw so duplicates can be audited locally).
SELECT
  transaction_id,
  user_pseudo_id,
  session_id,
  event_timestamp AS event_ts,
  revenue_usd
FROM ev
WHERE event_name = 'purchase'

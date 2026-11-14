{{events_cte}}
-- One row per (session, funnel event): when it first happened and how often.
SELECT
  user_pseudo_id,
  session_id,
  event_name,
  MIN(event_timestamp) AS first_ts,
  COUNT(*)             AS n_events
FROM ev
WHERE session_id IS NOT NULL
  AND event_name IN ('session_start', 'view_item', 'add_to_cart', 'begin_checkout',
                     'add_shipping_info', 'add_payment_info', 'purchase')
GROUP BY user_pseudo_id, session_id, event_name

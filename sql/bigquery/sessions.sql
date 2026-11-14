{{events_cte}}
-- One row per session. A GA4 session = (user_pseudo_id, ga_session_id).
-- Session source/medium = first non-null event-level source/medium in the session.
SELECT
  user_pseudo_id,
  session_id,
  MIN(event_timestamp)                                                         AS session_start_ts,
  ANY_VALUE(device_category)                                                   AS device_category,
  ANY_VALUE(operating_system)                                                  AS operating_system,
  ANY_VALUE(country)                                                           AS country,
  ARRAY_AGG(ev_source   IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS source,
  ARRAY_AGG(ev_medium   IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS medium,
  ARRAY_AGG(ev_campaign IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS campaign,
  ANY_VALUE(first_user_source)                                                 AS first_user_source,
  ANY_VALUE(first_user_medium)                                                 AS first_user_medium,
  COUNT(*)                                                                     AS n_events
FROM ev
WHERE session_id IS NOT NULL
GROUP BY user_pseudo_id, session_id

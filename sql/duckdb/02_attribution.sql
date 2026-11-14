-- Revenue credit for purchasing sessions under three single-touch models:
--   last_touch        : channel of the session that purchased
--   first_touch_window: channel of the user's first session inside the data window
--   first_user_ga4    : GA4's user-level first-acquisition source (traffic_source.*)
-- Every model credits the same purchases, so totals must match (tested).
CREATE OR REPLACE TABLE attribution AS
WITH ordered AS (
  SELECT *,
         first_value(channel) OVER (PARTITION BY user_pseudo_id
                                    ORDER BY session_start_ts, session_id) AS first_touch_channel
  FROM sessions
),
buyers AS (SELECT * FROM ordered WHERE ts_purchase IS NOT NULL)
SELECT 'last_touch' AS model, channel AS channel,
       count(*) AS purchase_sessions, sum(revenue_usd) AS revenue_usd
FROM buyers GROUP BY ALL
UNION ALL
SELECT 'first_touch_window', first_touch_channel,
       count(*), sum(revenue_usd)
FROM buyers GROUP BY ALL
UNION ALL
SELECT 'first_user_ga4', first_user_channel,
       count(*), sum(revenue_usd)
FROM buyers GROUP BY ALL;

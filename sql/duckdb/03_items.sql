-- Item performance: how often a viewed product gets carted and bought.
CREATE OR REPLACE TABLE item_performance AS
WITH p AS (
  SELECT
    coalesce(item_name, '(not set)')     AS item_name,
    coalesce(item_category, '(not set)') AS item_category,
    sum(n_item_events) FILTER (WHERE event_name = 'view_item')   AS views,
    sum(n_item_events) FILTER (WHERE event_name = 'add_to_cart') AS add_to_carts,
    sum(quantity)      FILTER (WHERE event_name = 'purchase')    AS units_purchased,
    sum(item_revenue_usd) FILTER (WHERE event_name = 'purchase') AS item_revenue_usd
  FROM raw_items
  GROUP BY ALL
)
SELECT *,
       add_to_carts / nullif(views, 0)            AS view_to_cart_rate,
       units_purchased / nullif(add_to_carts, 0)  AS units_per_cart_event
FROM p;

-- Item-level activity, aggregated in BigQuery (the items array is large).
SELECT
  event_name,
  item.item_name,
  item.item_category,
  COUNT(*)                     AS n_item_events,
  SUM(item.quantity)           AS quantity,
  SUM(item.item_revenue_in_usd) AS item_revenue_usd
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`,
     UNNEST(items) AS item
WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
  AND event_name IN ('view_item', 'add_to_cart', 'begin_checkout', 'purchase')
GROUP BY event_name, item.item_name, item.item_category

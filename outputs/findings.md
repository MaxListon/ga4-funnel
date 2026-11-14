# GA4 checkout funnel: findings

*Data: 2020-11-01 to 2021-01-31, 360,129 sessions, 270,154 users. Source: bigquery.*

## 1. Overall conversion

**1.35%** of sessions include a purchase (4,848 sessions; 95% CI 1.31% to 1.38%). Only 2,749 of them (56.7%) pass through every funnel step in order within the same session; see section 5 for why.

## 2. Where the funnel leaks

- Only 21.4% of sessions ever open a product page. Most traffic leaves before it reaches the funnel.
- Of sessions that view a product, 19.7% add it to the cart (CI 19.4%-19.9%).
- The largest absolute loss after the product page is at **Added to cart**: 61,873 sessions drop there.

| Step | Sessions (any order) | Sessions (in order) | Step conversion, in order |
|---|---:|---:|---:|
| Session | 360,129 | 360,129 | — |
| Viewed product | 77,020 | 77,020 | 21.4% |
| Added to cart | 15,188 | 15,147 | 19.7% |
| Began checkout | 11,106 | 5,293 | 34.9% |
| Shipping info | 11,105 | 5,288 | 99.9% |
| Payment info | 6,815 | 3,719 | 70.3% |
| Purchased | 4,848 | 2,749 | 73.9% |

## 3. Desktop vs mobile

Desktop converts at 1.32% (208,942 sessions) and mobile at 1.39% (143,185). The difference is -0.08 pts (95% CI -0.16 to -0.00 pts): statistically detectable but small in practice (6% relative), so device is not where the conversion problem is.

## 4. Channels

Channels with at least 1,000 sessions, by session conversion:

| Channel | Sessions | Conversion |
|---|---:|---:|
| Referral | 63,399 | 2.38% |
| Obfuscated * | 57,048 | 2.34% |
| Organic Search | 98,144 | 1.65% |
| Direct | 37,786 | 0.81% |
| Paid Search | 7,672 | 0.61% |
| Affiliates | 1,329 | 0.15% |
| Unassigned * | 94,553 | 0.00% |

\* No usable source: 42.1% of sessions are Obfuscated (the sample masks the value) or Unassigned (no source recorded on any event, mostly short visits). Channel comparisons cover only the remainder.

Among identifiable channels, **Referral** converts best and **Affiliates** worst: +2.23 pts (95% CI +1.82 to +2.40).

## 5. Tracking gaps (what I'd raise with the analytics engineers)

- **5,145 of 11,106 checkout sessions (46.3%) have no add_to_cart event.** Among 4,848 purchase sessions, 2,000 have none. Only 252 of those buyers carted in an earlier visit inside the window, so most of the gap looks like add_to_cart going unrecorded (or carts saved before November). Any cart-rate KPI built on this event is understated.
- **add_shipping_info is logged before begin_checkout in 6,862 sessions** (median gap 0.9 ms). The two fire on the same page load. A strict ordering rule would wrongly discard these sessions, so steps within 5 seconds count as in order.
- 335 purchase events are re-fires of an existing transaction ID. They are deduplicated before revenue is summed.

## 6. Attribution: who gets credit for revenue

| Channel | Last-touch share | First-user (GA4) share | Shift |
|---|---:|---:|---:|
| Direct | 6.7% | 22.0% | +15.3 pts |
| Obfuscated | 26.9% | 35.9% | +9.0 pts |
| Paid Search | 0.9% | 2.4% | +1.5 pts |
| Organic Search | 31.4% | 26.6% | -4.8 pts |
| Referral | 33.5% | 13.1% | -20.4 pts |

Moving from last-touch to first-touch credit, **Direct** gains the most share (+15.3 pts) and **Referral** loses the most (-20.4 pts). Channels that gain tend to acquire buyers who purchase on a later visit, so a last-touch report undervalues them.

## 7. Products (at least 500 views)

Highest view-to-cart: Google Tee F/C Black (54.6%); Google Land & Sea Unisex Tee (46.5%); Google Land & Sea Cotton Cap (46.1%).

Lowest view-to-cart: Google Mini Kick Ball (0.7%); Google Campus Bike Tote Navy (0.9%); Google Land & Sea French Terry Sweatshirt (1.0%).

Given the add_to_cart gap in section 5, compare products with each other rather than reading these as absolute rates.

## Data quality

| Check | Value | Note |
|---|---:|---|
| Sessions | 360129 | Distinct (user_pseudo_id, ga_session_id) pairs |
| Users | 270154 |  |
| Date range | 2020-11-01 to 2021-01-31 |  |
| Sessions missing a session_start event | 5272 | Counted as sessions anyway; GA4 can drop session_start |
| Sessions with obfuscated source/medium | 57048 | Sample replaces some values with <Other> / (data deleted) |
| Purchase events | 5692 |  |
| Duplicate purchase events (same transaction_id) | 335 | Re-fired purchase events; deduplicated before revenue is summed |
| Purchase events with transaction_id '(not set)' | 906 |  |
| Purchase events with no session id | 0 | Excluded from session funnel |
| Add-to-cart sessions with no prior view_item | 41 | Open funnel counts them; closed funnel does not |
| Purchases that skipped begin_checkout | 3 |  |
| Checkout sessions with no add_to_cart in the session | 5145 | of 11106 checkout sessions |
| Purchase sessions with no add_to_cart in the session | 2000 | of 4848 purchase sessions |
| ...of which the user carted in an earlier session | 252 | Carts that persist across visits; the rest suggests add_to_cart is under-tracked |
| add_shipping_info logged before begin_checkout | 6862 | median gap 0.9 ms: same page load; ordering uses a 5 s tolerance |

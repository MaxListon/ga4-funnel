"""Turn the analysis tables into a plain-English findings brief (every number computed, none typed)."""
import pandas as pd

from .config import MIN_SEGMENT_SESSIONS, STEP_LABELS
from .stats import newcombe_diff

UNMEASURABLE = {"Obfuscated", "Unassigned"}


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def _rate(f: pd.DataFrame, seg_type: str) -> pd.DataFrame:
    """Per segment: sessions, purchase sessions, open purchase rate."""
    s = f[f.segment_type == seg_type]
    n = s[s.step == "session_start"].set_index("segment").sessions_open
    k = s[s.step == "purchase"].set_index("segment").sessions_open
    return pd.DataFrame({"sessions": n, "buyers": k, "rate": k / n})


def build(tables: dict[str, pd.DataFrame], source: str) -> str:
    f = tables["funnel"]
    overall = f[f.segment_type == "overall"].sort_values("step_order").reset_index(drop=True)
    total = int(overall.loc[0, "sessions_open"])
    buy = overall[overall.step == "purchase"].iloc[0]
    q = tables["quality"].set_index("check")
    qv = q["value"]
    lines = []
    if source != "bigquery":
        lines += ["> **DEMO DATA.** These numbers come from synthetic data generated for testing.",
                  "> They say nothing about the real store. Run `python -m ga4funnel.extract` for real results.", ""]
    lines += ["# GA4 checkout funnel: findings", "",
              f"*Data: {qv['Date range']}, {total:,} sessions, {int(qv['Users']):,} users. Source: {source}.*", "",
              "## 1. Overall conversion", "",
              f"**{pct(buy.open_rate, 2)}** of sessions include a purchase "
              f"({int(buy.sessions_open):,} sessions; 95% CI {pct(buy.open_rate_lo, 2)} to {pct(buy.open_rate_hi, 2)}). "
              f"Only {int(buy.sessions_closed):,} of them ({pct(buy.sessions_closed / buy.sessions_open)}) pass through every funnel step "
              "in order within the same session; see section 5 for why.", ""]

    # Where the in-order path leaks
    steps = overall.iloc[1:]
    browse, later = steps.iloc[0], steps.iloc[1:]
    leak = later.loc[later.lost_sessions.idxmax()]
    lines += ["## 2. Where the funnel leaks", "",
              f"- Only {pct(browse.open_rate)} of sessions ever open a product page. Most traffic leaves before it reaches the funnel.",
              f"- Of sessions that view a product, {pct(later.iloc[0].step_rate)} add it to the cart "
              f"(CI {pct(later.iloc[0].step_rate_lo)}-{pct(later.iloc[0].step_rate_hi)}).",
              f"- The largest absolute loss after the product page is at **{STEP_LABELS[leak.step]}**: "
              f"{int(leak.lost_sessions):,} sessions drop there.", "",
              "| Step | Sessions (any order) | Sessions (in order) | Step conversion, in order |", "|---|---:|---:|---:|"]
    lines += [f"| {r.step_label} | {int(r.sessions_open):,} | {int(r.sessions_closed):,} | "
              + ("—" if pd.isna(r.step_rate) else f"{pct(r.step_rate)}") + " |" for r in overall.itertuples()]
    lines += [""]

    # Device
    dev = _rate(f, "device_category")
    if {"desktop", "mobile"} <= set(dev.index):
        d, lo, hi = newcombe_diff(int(dev.buyers["desktop"]), int(dev.sessions["desktop"]),
                                  int(dev.buyers["mobile"]), int(dev.sessions["mobile"]))
        rel = abs(d) / max(dev.rate["desktop"], dev.rate["mobile"])
        if not (lo > 0 or hi < 0):
            sig = "too small to distinguish from zero"
        elif rel < 0.10:
            sig = (f"statistically detectable but small in practice ({pct(rel, 0)} relative), "
                   "so device is not where the conversion problem is")
        else:
            sig = "a real gap (the CI excludes zero)"
        lines += ["## 3. Desktop vs mobile", "",
                  f"Desktop converts at {pct(dev.rate['desktop'], 2)} ({int(dev.sessions['desktop']):,} sessions) and mobile at "
                  f"{pct(dev.rate['mobile'], 2)} ({int(dev.sessions['mobile']):,}). The difference is {d * 100:+.2f} pts "
                  f"(95% CI {lo * 100:+.2f} to {hi * 100:+.2f} pts): {sig}.", ""]

    # Channels
    ch = _rate(f, "channel")
    big = ch[ch.sessions >= MIN_SEGMENT_SESSIONS].sort_values("rate", ascending=False)
    if len(big):
        lines += ["## 4. Channels", "", f"Channels with at least {MIN_SEGMENT_SESSIONS:,} sessions, by session conversion:", "",
                  "| Channel | Sessions | Conversion |", "|---|---:|---:|"]
        lines += [f"| {c}{' *' if c in UNMEASURABLE else ''} | {int(r.sessions):,} | {pct(r.rate, 2)} |" for c, r in big.iterrows()]
        unk = ch[ch.index.isin(UNMEASURABLE)].sessions.sum()
        lines += ["", f"\\* No usable source: {pct(unk / total)} of sessions are Obfuscated (the sample masks the value) or "
                  "Unassigned (no source recorded on any event, mostly short visits). Channel comparisons cover only the remainder.", ""]
        known = big[~big.index.isin(UNMEASURABLE)]
        if len(known) >= 2:
            a, b = known.index[0], known.index[-1]
            d, lo, hi = newcombe_diff(int(known.buyers[a]), int(known.sessions[a]), int(known.buyers[b]), int(known.sessions[b]))
            lines += [f"Among identifiable channels, **{a}** converts best and **{b}** worst: {d * 100:+.2f} pts "
                      f"(95% CI {lo * 100:+.2f} to {hi * 100:+.2f}).", ""]

    # Tracking gaps
    def num(check):
        return int(qv[check])
    if "Checkout sessions with no add_to_cart in the session" in qv:
        co_total = int(overall.loc[overall.step == "begin_checkout", "sessions_open"].iloc[0])
        nocart, buyers_nocart, earlier = (num("Checkout sessions with no add_to_cart in the session"),
                                          num("Purchase sessions with no add_to_cart in the session"),
                                          num("...of which the user carted in an earlier session"))
        lines += ["## 5. Tracking gaps (what I'd raise with the analytics engineers)", "",
                  f"- **{nocart:,} of {co_total:,} checkout sessions ({pct(nocart / co_total) if co_total else '—'}) have no add_to_cart event.** "
                  f"Among {int(buy.sessions_open):,} purchase sessions, {buyers_nocart:,} have none. Only {earlier:,} of those buyers "
                  "carted in an earlier visit inside the window, so most of the gap looks like add_to_cart going unrecorded "
                  "(or carts saved before November). Any cart-rate KPI built on this event is understated.",
                  f"- **add_shipping_info is logged before begin_checkout in {num('add_shipping_info logged before begin_checkout'):,} sessions** "
                  f"({q.loc['add_shipping_info logged before begin_checkout', 'note'].split(':')[0]}). The two fire on the same page load. "
                  "A strict ordering rule would wrongly discard these sessions, so steps within 5 seconds count as in order.",
                  f"- {num('Duplicate purchase events (same transaction_id)'):,} purchase events are re-fires of an existing transaction ID. "
                  "They are deduplicated before revenue is summed.", ""]

    # Attribution
    a = tables["attribution"].pivot_table(index="channel", columns="model", values="revenue_usd", aggfunc="sum").fillna(0)
    if {"last_touch", "first_user_ga4"} <= set(a.columns) and a["last_touch"].sum() > 0:
        share = a.div(a.sum())
        shift = (share["first_user_ga4"] - share["last_touch"]).sort_values()
        shown = shift[(share.loc[shift.index, ["last_touch", "first_user_ga4"]].max(axis=1) >= 0.005)]
        lines += ["## 6. Attribution: who gets credit for revenue", "",
                  "| Channel | Last-touch share | First-user (GA4) share | Shift |", "|---|---:|---:|---:|"]
        lines += [f"| {c} | {pct(share.loc[c, 'last_touch'])} | {pct(share.loc[c, 'first_user_ga4'])} | {shift[c] * 100:+.1f} pts |"
                  for c in shown.index[::-1]]
        lines += ["", f"Moving from last-touch to first-touch credit, **{shift.index[-1]}** gains the most share "
                  f"({shift.iloc[-1] * 100:+.1f} pts) and **{shift.index[0]}** loses the most ({shift.iloc[0] * 100:+.1f} pts). "
                  f"Channels that gain tend to acquire buyers who purchase on a later visit, so a last-touch report undervalues them.", ""]

    # Items
    it = tables["items"].dropna(subset=["views"])
    it = it[it.views >= 500]
    if len(it):
        top, low = it.nlargest(3, "view_to_cart_rate"), it.nsmallest(3, "view_to_cart_rate")
        lines += ["## 7. Products (at least 500 views)", "",
                  "Highest view-to-cart: " + "; ".join(f"{r.item_name} ({pct(r.view_to_cart_rate)})" for r in top.itertuples()) + ".",
                  "",
                  "Lowest view-to-cart: " + "; ".join(f"{r.item_name} ({pct(r.view_to_cart_rate)})" for r in low.itertuples()) + ".",
                  "", "Given the add_to_cart gap in section 5, compare products with each other rather than reading these as absolute rates.", ""]

    lines += ["## Data quality", "", "| Check | Value | Note |", "|---|---:|---|"]
    lines += [f"| {r.check} | {r.value} | {r.note} |" for r in tables["quality"].itertuples()]
    return "\n".join(lines) + "\n"

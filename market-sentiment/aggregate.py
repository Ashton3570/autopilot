"""Merge raw collector output into per-ticker records + a market-wide 'heating up' list.

Scoring is deliberately simple and transparent (this is a low-confidence signal
layer, not a model): we surface mention spikes and bull/bear tilt, not a black box.
"""
from util import pct_change


def sentiment_label(bull_ratio):
    if bull_ratio is None:
        return ("데이터 부족", "na")
    if bull_ratio >= 70:
        return ("강한 강세", "bull")
    if bull_ratio >= 55:
        return ("강세 우위", "bull")
    if bull_ratio > 45:
        return ("중립/혼조", "neutral")
    if bull_ratio > 30:
        return ("약세 우위", "bear")
    return ("강한 약세", "bear")


def heat_flag(delta_pct, rank, rank_24h_ago):
    """A short human label for how 'hot' the chatter is right now."""
    rank_move = (rank_24h_ago - rank) if (rank and rank_24h_ago) else 0
    if delta_pct is None:
        return ("-", 0)
    score = delta_pct + rank_move * 2  # rank jumps weighted a bit
    if delta_pct >= 150 or rank_move >= 20:
        return ("급등 ▲▲", score)
    if delta_pct >= 50 or rank_move >= 8:
        return ("상승 ▲", score)
    if delta_pct <= -50:
        return ("급랭 ▼", score)
    return ("보합", score)


def build_watchlist_records(watchlist, ape, stwits, reddit):
    records = []
    for t in watchlist:
        a = ape.get(t, {})
        s = stwits.get(t, {})
        r = reddit.get(t, {})
        delta = pct_change(a.get("mentions"), a.get("mentions_24h_ago"))
        flag, score = heat_flag(delta, a.get("rank"), a.get("rank_24h_ago"))
        label, cls = sentiment_label(s.get("bull_ratio"))
        records.append({
            "ticker": t,
            "name": a.get("name") or "",
            "mentions": a.get("mentions"),
            "mentions_24h_ago": a.get("mentions_24h_ago"),
            "mention_delta_pct": delta,
            "rank": a.get("rank"),
            "rank_24h_ago": a.get("rank_24h_ago"),
            "heat_flag": flag,
            "heat_score": round(score, 1),
            "st_messages": s.get("message_count", 0),
            "st_bullish": s.get("bullish", 0),
            "st_bearish": s.get("bearish", 0),
            "st_bull_ratio": s.get("bull_ratio"),
            "sentiment_label": label,
            "sentiment_cls": cls,
            "st_sample": s.get("sample", []),
            "reddit_posts": r.get("post_count", 0),
            "reddit_sample": r.get("sample", []),
        })
    # sort: hottest chatter first
    records.sort(key=lambda x: (x["heat_score"] if x["heat_score"] is not None else -999), reverse=True)
    return records


def build_market_heat(ape, top_n=15, exclude=None, min_mentions=10):
    """Market-wide 'what is heating up across all of Reddit today' from ApeWisdom.

    min_mentions floors out low-base noise (e.g. a 1 -> 7 mention name showing
    '+600%'), so the list surfaces real spikes with meaningful volume.
    """
    exclude = exclude or set()
    rows = []
    for t, a in ape.items():
        if (a.get("mentions") or 0) < min_mentions:
            continue
        delta = pct_change(a.get("mentions"), a.get("mentions_24h_ago"))
        flag, score = heat_flag(delta, a.get("rank"), a.get("rank_24h_ago"))
        rows.append({
            "ticker": t, "name": a.get("name") or "",
            "mentions": a.get("mentions"), "mentions_24h_ago": a.get("mentions_24h_ago"),
            "mention_delta_pct": delta, "rank": a.get("rank"), "rank_24h_ago": a.get("rank_24h_ago"),
            "heat_flag": flag, "heat_score": round(score, 1),
            "on_watchlist": t in exclude,
        })
    rows.sort(key=lambda x: (x["heat_score"] if x["heat_score"] is not None else -999), reverse=True)
    return rows[:top_n]

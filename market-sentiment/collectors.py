"""Data collectors. Each returns plain dicts/lists; each is independently
fail-safe so one dead source never kills the brief.

Keyless (work out of the box):  apewisdom, stocktwits, rss
Needs credentials (optional):   reddit (OAuth app -> REDDIT_CLIENT_ID/SECRET)
"""
import os
import re
import html as _html
import base64
from util import http_get_json, http_get_text


# ----------------------------------------------------------------------------
# ApeWisdom  -- Reddit mention volume / 24h delta / rank per ticker (KEYLESS)
# Covers Reddit indirectly: it aggregates mentions across r/wallstreetbets,
# r/stocks, r/investing, etc.
# ----------------------------------------------------------------------------
def collect_apewisdom(filter_board="all-stocks", pages=1):
    """Return {TICKER: {mentions, mentions_24h_ago, rank, rank_24h_ago, upvotes, name}}."""
    out = {}
    try:
        for page in range(1, pages + 1):
            url = f"https://apewisdom.io/api/v1.0/filter/{filter_board}/page/{page}"
            data = http_get_json(url)
            for r in data.get("results", []):
                t = (r.get("ticker") or "").upper()
                if not t:
                    continue
                out[t] = {
                    "mentions": r.get("mentions"),
                    "mentions_24h_ago": r.get("mentions_24h_ago"),
                    "rank": r.get("rank"),
                    "rank_24h_ago": r.get("rank_24h_ago"),
                    "upvotes": r.get("upvotes"),
                    "name": r.get("name"),
                }
    except Exception as e:
        print(f"[apewisdom] WARN: {e}")
    return out


# ----------------------------------------------------------------------------
# StockTwits  -- per-ticker messages + Bullish/Bearish labels (KEYLESS public)
# ----------------------------------------------------------------------------
def collect_stocktwits(ticker, limit=30):
    """Return {message_count, bullish, bearish, bull_ratio, sample[]} for one ticker."""
    res = {"message_count": 0, "bullish": 0, "bearish": 0, "bull_ratio": None, "sample": [], "error": None}
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        data = http_get_json(url, headers={"User-Agent": "Mozilla/5.0 MarketSentimentBrief/0.1"})
        msgs = data.get("messages", []) or []
        msgs = msgs[:limit]
        res["message_count"] = len(msgs)
        for m in msgs:
            ent = (m.get("entities") or {})
            sent = ((ent.get("sentiment") or {}) or {}).get("basic")
            if sent == "Bullish":
                res["bullish"] += 1
            elif sent == "Bearish":
                res["bearish"] += 1
            if len(res["sample"]) < 5:
                user = (m.get("user") or {})
                res["sample"].append({
                    "body": (m.get("body") or "").strip()[:240],
                    "sentiment": sent,
                    "user": user.get("username"),
                    "followers": user.get("followers"),
                    "created_at": m.get("created_at"),
                })
        labeled = res["bullish"] + res["bearish"]
        if labeled:
            res["bull_ratio"] = round(res["bullish"] / labeled * 100.0, 0)
    except Exception as e:
        res["error"] = str(e)
        print(f"[stocktwits:{ticker}] WARN: {e}")
    return res


# ----------------------------------------------------------------------------
# Reddit  -- official OAuth API (OPTIONAL; needs a free 'script' app)
# ----------------------------------------------------------------------------
def _reddit_token():
    cid = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return None
    try:
        import urllib.request
        auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        body = b"grant_type=client_credentials"
        req = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token", data=body,
            headers={"Authorization": f"Basic {auth}",
                     "User-Agent": "MarketSentimentBrief/0.1 by personal",
                     "Content-Type": "application/x-www-form-urlencoded"})
        import json as _json
        with urllib.request.urlopen(req, timeout=20) as r:
            return _json.loads(r.read().decode()).get("access_token")
    except Exception as e:
        print(f"[reddit] token WARN: {e}")
        return None


def collect_reddit(ticker, subreddits, limit=8):
    """Return {post_count, sample[]} for a ticker across subreddits, or empty if no creds."""
    res = {"post_count": 0, "sample": [], "error": None}
    token = _reddit_token()
    if not token:
        res["error"] = "no REDDIT_CLIENT_ID/SECRET (disabled)"
        return res
    try:
        sr = "+".join(subreddits)
        url = (f"https://oauth.reddit.com/r/{sr}/search?q={ticker}&restrict_sr=1"
               f"&sort=new&limit={limit}&t=day")
        data = http_get_json(url, headers={"Authorization": f"Bearer {token}",
                                            "User-Agent": "MarketSentimentBrief/0.1 by personal"})
        for c in data.get("data", {}).get("children", []):
            d = c.get("data", {})
            res["post_count"] += 1
            if len(res["sample"]) < 5:
                res["sample"].append({
                    "title": (d.get("title") or "")[:160],
                    "subreddit": d.get("subreddit"),
                    "score": d.get("score"),
                    "num_comments": d.get("num_comments"),
                    "url": "https://reddit.com" + (d.get("permalink") or ""),
                })
    except Exception as e:
        res["error"] = str(e)
        print(f"[reddit:{ticker}] WARN: {e}")
    return res


# ----------------------------------------------------------------------------
# RSS  -- generic headline puller (KEYLESS; stdlib XML)
# ----------------------------------------------------------------------------
def collect_rss(feeds, watchlist, max_items=12):
    """Return list of {feed, title, link, tickers[]} for headlines mentioning a watchlist ticker."""
    import xml.etree.ElementTree as ET
    items = []
    wl = {t.upper() for t in watchlist}
    for feed in feeds:
        try:
            txt = http_get_text(feed["url"], headers={"User-Agent": "Mozilla/5.0 MarketSentimentBrief/0.1"})
            txt = re.sub(r"xmlns(:\w+)?=\"[^\"]*\"", "", txt)  # strip namespaces for easy parsing
            root = ET.fromstring(txt)
            entries = root.findall(".//item") or root.findall(".//entry")
            for e in entries[:50]:
                title_el = e.find("title")
                title = "".join(title_el.itertext()).strip() if title_el is not None else ""
                link_el = e.find("link")
                link = (link_el.text or link_el.get("href") or "") if link_el is not None else ""
                title_clean = _html.unescape(title)
                hits = sorted({t for t in wl if re.search(rf"\b{re.escape(t)}\b", title_clean)})
                if hits:
                    items.append({"feed": feed.get("name", feed["url"]),
                                  "title": title_clean[:180], "link": link, "tickers": hits})
                    if len(items) >= max_items:
                        break
        except Exception as ex:
            print(f"[rss:{feed.get('name')}] WARN: {ex}")
    return items

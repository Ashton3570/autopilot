"""Shared helpers: HTTP, dates, small math. Stdlib only (no pip install needed)."""
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

DEFAULT_UA = "MarketSentimentBrief/0.1 (personal research; contact: local)"


def http_get_json(url, headers=None, timeout=20, retries=2, backoff=2.0):
    """GET a URL and parse JSON. Returns parsed object, or raises after retries."""
    hdrs = {"User-Agent": DEFAULT_UA, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
            return json.loads(raw)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"GET failed for {url}: {last_err}")


def http_get_text(url, headers=None, timeout=20, retries=2, backoff=2.0):
    hdrs = {"User-Agent": DEFAULT_UA}
    if headers:
        hdrs.update(headers)
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"GET failed for {url}: {last_err}")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def now_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip()


def pct_change(now, prior):
    """Percentage change; prior<=0 handled gracefully."""
    if prior is None or prior <= 0:
        return None
    return round((now - prior) / prior * 100.0, 1)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))

#!/usr/bin/env python3
"""Economic Calendar fetcher (Python 3, stdlib-only).

A modern rewrite of the old Econoday/Bloomberg-style scraper gist. The original
scraped `us.econoday.com/byday.asp` (now dead / 404). This pulls the same kind
of data -- economic events with actual / consensus / previous -- from a LIVE,
KEYLESS JSON source (Nasdaq's economic-events calendar), then writes:

  - data/<date>.json        raw per-day events (cache / re-processing)
  - out/econ-<from>_<to>.txt  tab-delimited (date, time, country, event, A/C/P)  <- gist parity
  - out/econ-<from>_<to>.html a clean calendar view (open in browser)

USAGE
  python3 econ_calendar.py                       # next 7 days, all countries
  python3 econ_calendar.py --days 14 --country "United States"
  python3 econ_calendar.py --from 2026-07-01 --to 2026-07-07 --high-impact
  python3 econ_calendar.py --days 7 --open       # open the HTML when done (macOS)

NOTE: source has no official "importance" field, so --high-impact flags the
classic market-movers (FOMC, CPI, PCE, NFP, GDP, ISM, retail sales, ...) by
keyword. Times are the source's GMT column (labeled in the output).
"""
import os
import sys
import re
import json
import time
import html
import argparse
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
NASDAQ_URL = "https://api.nasdaq.com/api/calendar/economicevents?date={date}"

# market-moving events flagged when --high-impact is on (US-centric, extendable)
HIGH_IMPACT = re.compile(
    r"\b(FOMC|Fed Interest Rate|Rate Decision|Fed Funds|"
    r"CPI|Core CPI|PCE|Core PCE|PPI|"
    r"Nonfarm|Non-Farm|Payrolls|Employment Situation|Unemployment Rate|ADP|"
    r"GDP|Retail Sales|ISM|PMI|Jobless Claims|"
    r"Consumer Confidence|Consumer Sentiment|Durable Goods|"
    r"Powell|Fed Chair|Treasury)\b", re.I)


def http_json(url, timeout=20, retries=2):
    """Nasdaq needs a browser-ish UA + Accept json; stdlib only."""
    headers = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
    }
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {url}: {last}")


def fetch_day(date_str):
    """date_str = 'YYYY-MM-DD' -> list of normalized event dicts (cached to data/)."""
    cache_dir = os.path.join(HERE, "data")
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, f"{date_str}.json")

    try:
        d = http_json(NASDAQ_URL.format(date=date_str))
    except Exception as e:
        print(f"[{date_str}] WARN: {e}")
        return []
    data = (d or {}).get("data") or {}
    rows = data.get("rows") or []

    def clean(v):
        # source returns literal "&nbsp;" / non-breaking spaces for empty cells
        v = html.unescape(v or "").replace("\xa0", " ").strip()
        return "" if v in ("-", "n/a", "N/A") else v

    events = []
    for r in rows:
        ev = {
            "date": date_str,
            "time_gmt": clean(r.get("gmt")),
            "country": clean(r.get("country")),
            "event": clean(r.get("eventName")),
            "actual": clean(r.get("actual")),
            "consensus": clean(r.get("consensus")),
            "previous": clean(r.get("previous")),
            "description": clean(r.get("description")),
        }
        ev["high_impact"] = bool(HIGH_IMPACT.search(ev["event"]))
        events.append(ev)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump({"date": date_str, "asOf": data.get("asOf"), "events": events},
                  f, ensure_ascii=False, indent=2)
    return events


def date_range(start, end):
    """Inclusive list of 'YYYY-MM-DD' strings (the gist's getDateRanges)."""
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    out, d = [], d0
    while d <= d1:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def collect(start, end, country=None, high_only=False, polite=0.4):
    events = []
    for ds in date_range(start, end):
        day = fetch_day(ds)
        for ev in day:
            if country and ev["country"].lower() != country.lower():
                continue
            if high_only and not ev["high_impact"]:
                continue
            events.append(ev)
        time.sleep(polite)  # be nice to the endpoint
    return events


# ---------------------------------------------------------------- outputs ----
def write_txt(events, path):
    """Tab-delimited (gist parity): date \t time \t country \t event \t A \t C \t P."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("date\ttime_gmt\tcountry\tevent\tactual\tconsensus\tprevious\thigh_impact\n")
        for e in events:
            f.write("\t".join([e["date"], e["time_gmt"], e["country"], e["event"],
                               e["actual"], e["consensus"], e["previous"],
                               "Y" if e["high_impact"] else ""]) + "\n")


CSS = """body{font-family:-apple-system,'Apple SD Gothic Neo',Segoe UI,Roboto,sans-serif;margin:0;background:#f4f6f8;color:#1f2933;font-size:14px}
.wrap{max-width:1040px;margin:0 auto;padding:24px 22px 50px}h1{font-size:24px;margin:0 0 2px}
.sub{color:#64748b;font-size:13px;margin-bottom:18px}h2{font-size:16px;color:#0f5132;border-left:5px solid #157a60;padding-left:10px;margin:22px 0 8px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden}
th{background:#157a60;color:#fff;text-align:left;padding:7px 9px;font-size:12px}
td{padding:6px 9px;border-top:1px solid #eef2f6;font-size:12.5px}
tr:nth-child(even) td{background:#f8fafc}
.hi td{background:#fff7ed!important}.hi .ev{font-weight:700;color:#9a3412}
.c{color:#64748b}.flag{font-size:11px;color:#b45309;font-weight:700}
.num{font-variant-numeric:tabular-nums}"""


def write_html(events, path, title_range, high_only):
    by_date = {}
    for e in events:
        by_date.setdefault(e["date"], []).append(e)
    P = [f"<!doctype html><meta charset='utf-8'><title>Economic Calendar {html.escape(title_range)}</title><style>{CSS}</style><div class='wrap'>"]
    P.append("<h1>Economic Calendar</h1>")
    scope = "high-impact only" if high_only else "all events"
    P.append(f"<div class='sub'>{html.escape(title_range)} - {scope} - times in GMT - source: Nasdaq economic-events (live, keyless)</div>")
    for ds in sorted(by_date):
        dt = datetime.strptime(ds, "%Y-%m-%d")
        P.append(f"<h2>{ds} ({dt.strftime('%a')})</h2>")
        P.append("<table><tr><th>Time</th><th>Country</th><th>Event</th><th>Actual</th><th>Consensus</th><th>Previous</th></tr>")
        for e in sorted(by_date[ds], key=lambda x: x["time_gmt"]):
            cls = " class='hi'" if e["high_impact"] else ""
            flag = " <span class='flag'>HIGH</span>" if e["high_impact"] else ""
            P.append(f"<tr{cls}><td class='num'>{html.escape(e['time_gmt'])}</td>"
                     f"<td>{html.escape(e['country'])}</td>"
                     f"<td class='ev'>{html.escape(e['event'])}{flag}</td>"
                     f"<td class='num'>{html.escape(e['actual'])}</td>"
                     f"<td class='num c'>{html.escape(e['consensus'])}</td>"
                     f"<td class='num c'>{html.escape(e['previous'])}</td></tr>")
        P.append("</table>")
    if not events:
        P.append("<p class='c'>No events for the selected range/filters.</p>")
    P.append("</div>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(P))


def main():
    ap = argparse.ArgumentParser(description="Economic calendar (live, keyless, stdlib-only).")
    ap.add_argument("--from", dest="dfrom", help="start date YYYY-MM-DD (default: today)")
    ap.add_argument("--to", dest="dto", help="end date YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=7, help="N days from --from if --to omitted (default 7)")
    ap.add_argument("--today", help="override 'today' as YYYY-MM-DD (env clock differs from real date)")
    ap.add_argument("--country", help="filter, e.g. \"United States\"")
    ap.add_argument("--high-impact", action="store_true", help="only market-movers (FOMC/CPI/NFP/...)")
    ap.add_argument("--open", action="store_true", help="open the HTML when done (macOS)")
    a = ap.parse_args()

    today = a.today or datetime.now().strftime("%Y-%m-%d")
    start = a.dfrom or today
    if a.dto:
        end = a.dto
    else:
        end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=max(a.days - 1, 0))).strftime("%Y-%m-%d")

    print(f"Fetching economic calendar {start} -> {end}"
          + (f" | country={a.country}" if a.country else "")
          + (" | high-impact only" if a.high_impact else ""))
    events = collect(start, end, country=a.country, high_only=a.high_impact)
    hi = sum(1 for e in events if e["high_impact"])
    print(f"Collected {len(events)} events ({hi} high-impact).")

    out_dir = os.path.join(HERE, "out")
    os.makedirs(out_dir, exist_ok=True)
    base = f"econ-{start}_{end}" + ("-US" if a.country == "United States" else "") + ("-HI" if a.high_impact else "")
    txt = os.path.join(out_dir, base + ".txt")
    htmlp = os.path.join(out_dir, base + ".html")
    write_txt(events, txt)
    write_html(events, htmlp, f"{start} to {end}", a.high_impact)
    print(f"TXT:  {txt}")
    print(f"HTML: {htmlp}")
    if a.open:
        subprocess.run(["open", htmlp], check=False)


if __name__ == "__main__":
    main()

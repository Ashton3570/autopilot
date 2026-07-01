# Economic Calendar (Python 3 port of the Econoday/Bloomberg-style gist)

The gist you shared scraped `us.econoday.com/byday.asp` — that endpoint is **now dead (redirects to a 404)**, and the code was Python 2 (`urllib2` + BeautifulSoup), which won't run on this machine. This is a working rewrite: **Python 3, standard library only (no pip installs), no API key**, pulling the same kind of data (economic events with **actual / consensus / previous**) from a **live keyless JSON source** (Nasdaq's economic-events calendar).

## Run

```bash
cd "Economic Calendar"
python3 econ_calendar.py                              # next 7 days, all countries
python3 econ_calendar.py --days 14 --country "United States"
python3 econ_calendar.py --from 2026-07-01 --to 2026-07-07 --high-impact --open
```

Outputs (in `out/`):
- `econ-<from>_<to>.html` — clean calendar grouped by day; **high-impact rows highlighted** (open in browser / print to PDF)
- `econ-<from>_<to>.txt` — tab-delimited (date, time, country, event, actual, consensus, previous, high_impact) — same idea as the gist's text export
- `data/<date>.json` — raw per-day cache (for re-processing / backtests)

## Options
- `--days N` — N days starting today (default 7); or use `--from`/`--to` for an explicit range
- `--country "United States"` — filter to one country
- `--high-impact` — keep only the market-movers (FOMC, CPI, PCE, Nonfarm/Payrolls, GDP, ISM, PMI, retail sales, jobless claims, Fed speakers, …) — keyword-classified, editable in the `HIGH_IMPACT` regex at the top of the script
- `--today YYYY-MM-DD` — override "today" if the machine clock differs from the date you want
- `--open` — open the HTML when done (macOS)

## Source & caveats
- **Source:** `https://api.nasdaq.com/api/calendar/economicevents?date=YYYY-MM-DD` — keyless JSON; fields: time (GMT), country, event, actual, consensus, previous, description. Covers ~12 major countries (US, Euro Zone, UK, Japan, China, Korea, …).
- **No official "importance" field** in the source, so `--high-impact` is a keyword heuristic — extend the `HIGH_IMPACT` regex for anything you want flagged.
- It's an unofficial endpoint: it needs a browser-like User-Agent + `Accept: json` (already set), and could change without notice. The per-day cache in `data/` means a transient failure doesn't lose prior days.
- Times are the source's **GMT** column (labeled). Add a tz conversion in `fetch_day` if you want local time (the old gist converted ET→CT).

## Where this plugs in
- **EQR pipeline:** feeds the Verdict reports' **Catalyst Calendar (부록 A)** and **§12 Macro & Rate Sensitivity** — e.g. drop the next-30-day FOMC/CPI/PCE/NFP into a ticker's catalyst timeline.
- **Market Sentiment Brief:** could add a "this week's macro" section above the social-sentiment tables (same HTML style).

If you want, I can wire a `--ics` export (so it drops into your calendar app) or merge it into the Market Sentiment Brief as a macro header.

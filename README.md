# 🛰️ Autopilot (Engine A)

Laptop-independent, **zero-Claude-usage** automation for three keyless tools:
Market Sentiment · Intraday TA · Economic Calendar.

Everything runs on **GitHub Actions cron in the cloud** — no MacBook, no Claude
usage consumed. Results are committed back here and rendered on your phone via
GitHub Pages. This is the "deterministic" half of the system; the agentic
Equity Research pipeline is Engine B (separate repo, Claude cloud agent).

## 📱 The phone dashboard

GitHub Pages serves `index.html` as a single newest-first list of every report:

> **https://ashton3570.github.io/autopilot/**

Open it on your phone. First item in each section is the latest. Tap to read the
rendered HTML report (no need to view raw source).

## 🎛️ How you control it from your phone

You never need the laptop. Two levers, both from the **GitHub mobile app / web**:

1. **Change what runs** — edit a config file, commit. The next scheduled run
   (or a manual trigger) picks it up.
   - `intraday-ta/watchlist.txt` — one ticker per line
   - `market-sentiment/config.json` — `watchlist` array
   - Economic calendar needs no config.
2. **Run on demand** — GitHub → Actions tab → pick a workflow → **Run workflow**.
   Fires immediately instead of waiting for the cron.

## ⏰ Schedule (UTC → KST)

| Tool | Cron (UTC) | KST | When / why |
|------|-----------|-----|------------|
| intraday-ta | `45 20 * * 1-5` | 05:45 | after US close, full session |
| market-sentiment | `0 21 * * 1-5` | 06:00 | post-close community mood |
| econ-calendar | `30 21 * * *` | 06:30 | next 7 days of macro events |

Edit the `cron:` line in `.github/workflows/*.yml` to retime. All three share a
`autopilot-push` concurrency group so their commits never collide.

## 🧱 Layout

```
autopilot/
├── index.html                 # phone dashboard (auto-generated)
├── tools/build_index.py       # regenerates the dashboard after each run
├── market-sentiment/          # ApeWisdom + StockTwits digest (rule-based, keyless)
├── intraday-ta/               # Yahoo minute-bar TA snapshot (stdlib, keyless)
├── econ-calendar/             # Nasdaq macro calendar (stdlib, keyless)
└── .github/workflows/         # one cron workflow per tool
```

All three tools are Python-stdlib-only and need no API keys or secrets.

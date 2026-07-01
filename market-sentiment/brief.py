#!/usr/bin/env python3
"""Market Sentiment Brief -- daily digest of US-stock community/social sentiment.

Pipeline:  collect (ApeWisdom + StockTwits [+ Reddit/RSS optional])
        -> aggregate (per-ticker + market-wide 'heating up')
        -> optional Claude summary
        -> render a self-contained HTML brief (print-to-PDF for a PDF copy)

Run:  python3 brief.py                # uses config.json
      python3 brief.py --tickers AVGO,NVDA,WDC
      python3 brief.py --open          # open the HTML when done (macOS)

Out:  briefs/<date>-sentiment-brief.html   and   data/<date>/raw.json
"""
import os
import sys
import json
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from util import today_str, now_stamp
import collectors
import aggregate
import render as render_mod
import llm as llm_mod


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--tickers", help="comma-separated override of the watchlist")
    ap.add_argument("--open", action="store_true", help="open the HTML when done (macOS `open`)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    watchlist = ([t.strip().upper() for t in args.tickers.split(",")]
                 if args.tickers else cfg["watchlist"])
    src = cfg.get("sources", {})
    date = today_str()
    stamp = now_stamp()
    status = []

    # ---- collect ----------------------------------------------------------
    ape = {}
    if src.get("apewisdom", True):
        ape = collectors.collect_apewisdom()
        status.append(f"ApeWisdom({len(ape)})")

    stwits = {}
    if src.get("stocktwits", True):
        ok = 0
        for t in watchlist:
            stwits[t] = collectors.collect_stocktwits(t, cfg.get("stocktwits_per_ticker", 30))
            if not stwits[t].get("error"):
                ok += 1
        status.append(f"StockTwits({ok}/{len(watchlist)})")

    reddit = {}
    if src.get("reddit", False):
        for t in watchlist:
            reddit[t] = collectors.collect_reddit(t, cfg.get("reddit", {}).get("subreddits", []))
        status.append("Reddit(on)")

    rss_items = []
    if src.get("rss", False):
        rss_items = collectors.collect_rss(cfg.get("rss_feeds", []), watchlist)
        status.append(f"RSS({len(rss_items)})")

    # ---- aggregate --------------------------------------------------------
    watchlist_recs = aggregate.build_watchlist_records(watchlist, ape, stwits, reddit)
    market_heat = aggregate.build_market_heat(ape, cfg.get("market_wide_top_n", 15),
                                              exclude=set(watchlist),
                                              min_mentions=cfg.get("market_min_mentions", 10))

    # ---- optional Claude summary -----------------------------------------
    llm_summary = ""
    if cfg.get("llm", {}).get("enabled", False):
        llm_summary = llm_mod.summarize(market_heat, watchlist_recs,
                                        cfg["llm"].get("model", "claude-opus-4-8"))

    # ---- persist raw ------------------------------------------------------
    data_dir = os.path.join(HERE, "data", date)
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "raw.json"), "w", encoding="utf-8") as f:
        json.dump({"date": date, "stamp": stamp, "watchlist": watchlist,
                   "apewisdom": ape, "stocktwits": stwits, "reddit": reddit,
                   "rss": rss_items}, f, ensure_ascii=False, indent=2)

    # ---- render -----------------------------------------------------------
    htmlout = render_mod.render_html(date, stamp, market_heat, watchlist_recs,
                                     rss_items, llm_summary, " · ".join(status))
    briefs_dir = os.path.join(HERE, "briefs")
    os.makedirs(briefs_dir, exist_ok=True)
    out = os.path.join(briefs_dir, f"{date}-sentiment-brief.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(htmlout)

    print(f"Sources: {' · '.join(status)}")
    print(f"Watchlist scored: {len(watchlist_recs)} · market-heat rows: {len(market_heat)}")
    print(f"Brief: {out}")
    if args.open:
        try:
            subprocess.run(["open", out], check=False)
        except Exception:
            pass


if __name__ == "__main__":
    main()

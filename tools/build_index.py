#!/usr/bin/env python3
"""Scan the tool output folders and regenerate index.html at the repo root.

This index is the phone dashboard: served by GitHub Pages, it lists every
generated report newest-first with a tap-through link. Pure stdlib.
Each workflow runs this after its tool so the dashboard stays current.
"""
import os
import html
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (Section title, folder relative to root, file extensions to include)
SECTIONS = [
    ("📊 Market Sentiment", "market-sentiment/briefs", (".html",)),
    ("📈 Intraday TA", "intraday-ta/out", (".html",)),
    ("🗓️ Economic Calendar", "econ-calendar/out", (".html", ".txt")),
]


def scan(folder, exts):
    d = os.path.join(ROOT, folder)
    if not os.path.isdir(d):
        return []
    items = []
    for name in os.listdir(d):
        if name.startswith("."):
            continue
        if not name.lower().endswith(exts):
            continue
        full = os.path.join(d, name)
        try:
            mtime = os.path.getmtime(full)
        except OSError:
            mtime = 0
        items.append((mtime, f"{folder}/{name}", name))
    items.sort(reverse=True)  # newest first
    return items


def main():
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Autopilot Dashboard</title>",
        "<style>",
        "body{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0b1220;color:#e2e8f0;}",
        ".wrap{max-width:760px;margin:0 auto;padding:20px 16px 60px;}",
        "h1{font-size:22px;margin:0 0 4px;}",
        ".sub{color:#94a3b8;font-size:13px;margin-bottom:24px;}",
        "h2{font-size:16px;margin:28px 0 10px;border-bottom:1px solid #1e293b;padding-bottom:6px;}",
        "a.item{display:block;padding:12px 14px;margin:8px 0;background:#111c30;border:1px solid #1e293b;",
        "border-radius:10px;color:#7dd3fc;text-decoration:none;font-size:15px;word-break:break-all;}",
        "a.item:first-of-type{border-color:#3b82f6;background:#132038;}",
        ".tag{display:inline-block;font-size:11px;color:#22c55e;margin-left:6px;}",
        ".empty{color:#64748b;font-size:13px;padding:8px 2px;}",
        "</style></head><body><div class='wrap'>",
        "<h1>🛰️ Autopilot Dashboard</h1>",
        f"<div class='sub'>Rebuilt {html.escape(now)} · newest first · first item = latest</div>",
    ]

    for title, folder, exts in SECTIONS:
        parts.append(f"<h2>{html.escape(title)}</h2>")
        items = scan(folder, exts)
        if not items:
            parts.append("<div class='empty'>No reports yet.</div>")
            continue
        for i, (_mtime, relpath, name) in enumerate(items[:30]):
            tag = "<span class='tag'>LATEST</span>" if i == 0 else ""
            parts.append(
                f"<a class='item' href='{html.escape(relpath)}'>{html.escape(name)}{tag}</a>"
            )

    parts.append("</div></body></html>")
    out = os.path.join(ROOT, "index.html")
    with open(out, "w", encoding="utf-8") as fp:
        fp.write("\n".join(parts))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

"""Render the daily brief as a self-contained HTML file (rich CSS, opens in any
browser; print-to-PDF for a PDF copy). Korean labels, institutional teal style."""
import html


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def _num(v, suffix=""):
    return f"{v}{suffix}" if v is not None else "-"


def _delta_badge(d):
    if d is None:
        return '<span class="mut">-</span>'
    cls = "up" if d > 0 else ("down" if d < 0 else "mut")
    sign = "+" if d > 0 else ""
    return f'<span class="{cls}">{sign}{d}%</span>'


def _bull_bar(ratio):
    if ratio is None:
        return '<div class="mut">데이터 부족</div>'
    bull = int(ratio)
    bear = 100 - bull
    return (f'<div class="gauge"><div class="g-bull" style="width:{bull}%">{bull}%</div>'
            f'<div class="g-bear" style="width:{bear}%">{bear}%</div></div>')


CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, "Apple SD Gothic Neo", "Segoe UI", Roboto, sans-serif;
  margin: 0; background: #f4f6f8; color: #1f2933; font-size: 14px; line-height: 1.5; }
.wrap { max-width: 1040px; margin: 0 auto; padding: 28px 24px 60px; }
h1 { font-size: 26px; margin: 0 0 2px; }
.sub { color: #64748b; font-size: 13px; margin-bottom: 22px; }
h2 { font-size: 18px; margin: 30px 0 12px; padding-left: 10px; border-left: 5px solid #157a60; color: #0f5132; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 18px; margin-bottom: 14px; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; }
th { background: #157a60; color: #fff; text-align: left; padding: 9px 11px; font-weight: 600; font-size: 12.5px; }
td { padding: 8px 11px; border-top: 1px solid #eef2f6; font-size: 13px; }
tr:nth-child(even) td { background: #f8fafc; }
.tkr { font-weight: 700; }
.up { color: #157a60; font-weight: 600; }
.down { color: #b72626; font-weight: 600; }
.mut { color: #94a3b8; }
.flag { font-weight: 700; }
.wl-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.wl { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; }
.wl-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
.wl-head .t { font-size: 17px; font-weight: 700; }
.wl-head .n { color: #64748b; font-size: 12px; }
.pill { display:inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 700; }
.pill.bull { background: #d8f3e6; color: #0f5132; }
.pill.bear { background: #fbe0e0; color: #b72626; }
.pill.neutral { background: #e7edf3; color: #475569; }
.pill.na { background: #eef2f6; color: #94a3b8; }
.metrics { display: flex; gap: 16px; font-size: 12.5px; color: #475569; margin: 6px 0 8px; flex-wrap: wrap; }
.metrics b { color: #1f2933; }
.gauge { display: flex; height: 20px; border-radius: 6px; overflow: hidden; font-size: 11px; font-weight: 700; color: #fff; margin: 6px 0; }
.g-bull { background: #157a60; display:flex; align-items:center; justify-content:center; min-width: 0; }
.g-bear { background: #b72626; display:flex; align-items:center; justify-content:center; min-width: 0; }
.msg { border-top: 1px dashed #e2e8f0; padding: 6px 0; font-size: 12.5px; color: #334155; }
.msg .s-bull { color: #157a60; font-weight: 700; }
.msg .s-bear { color: #b72626; font-weight: 700; }
.msg .meta { color: #94a3b8; font-size: 11px; }
.disclaimer { background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412; border-radius: 10px;
  padding: 12px 16px; font-size: 12.5px; margin-top: 26px; }
.foot { color: #94a3b8; font-size: 11.5px; margin-top: 18px; text-align: center; }
"""


def render_html(date_str, stamp, market_heat, watchlist_recs, rss_items, llm_summary, sources_status):
    P = []
    P.append(f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>")
    P.append(f"<meta name='viewport' content='width=device-width, initial-scale=1'>")
    P.append(f"<title>Market Sentiment Brief — {esc(date_str)}</title><style>{CSS}</style></head><body><div class='wrap'>")
    P.append(f"<h1>Market Sentiment Brief</h1>")
    P.append(f"<div class='sub'>{esc(date_str)} · 생성 {esc(stamp)} · 커뮤니티/소셜 심리 (비공식 · 저신뢰 레인) · 개인용</div>")

    # optional LLM narrative
    if llm_summary:
        P.append("<h2>오늘의 요약 (Claude)</h2>")
        P.append(f"<div class='card'>{llm_summary}</div>")

    # 1) market-wide heating up
    P.append("<h2>오늘 달아오르는 종목 (Reddit 전체)</h2>")
    P.append("<table><tr><th>#</th><th>Ticker</th><th>이름</th><th>언급</th><th>24h 전</th><th>변화</th><th>Rank</th><th>상태</th></tr>")
    for i, r in enumerate(market_heat, 1):
        star = " ★" if r.get("on_watchlist") else ""
        P.append(
            f"<tr><td>{i}</td><td class='tkr'>{esc(r['ticker'])}{star}</td><td>{esc(r['name'])}</td>"
            f"<td>{_num(r['mentions'])}</td><td>{_num(r['mentions_24h_ago'])}</td>"
            f"<td>{_delta_badge(r['mention_delta_pct'])}</td>"
            f"<td>{_num(r['rank'])} <span class='mut'>(was {_num(r['rank_24h_ago'])})</span></td>"
            f"<td class='flag'>{esc(r['heat_flag'])}</td></tr>")
    P.append("</table><div class='sub' style='margin-top:6px'>★ = 워치리스트 종목 · 출처 ApeWisdom (Reddit 언급 집계)</div>")

    # 2) watchlist sentiment cards
    P.append("<h2>워치리스트 심리 스냅샷</h2>")
    P.append("<div class='wl-grid'>")
    for r in watchlist_recs:
        P.append("<div class='wl'>")
        P.append(f"<div class='wl-head'><span class='t'>{esc(r['ticker'])} "
                 f"<span class='n'>{esc(r['name'])}</span></span>"
                 f"<span class='pill {esc(r['sentiment_cls'])}'>{esc(r['sentiment_label'])}</span></div>")
        P.append("<div class='metrics'>"
                 f"<span>언급 <b>{_num(r['mentions'])}</b> {_delta_badge(r['mention_delta_pct'])}</span>"
                 f"<span>StockTwits <b>{_num(r['st_messages'])}</b>건</span>"
                 f"<span class='flag'>{esc(r['heat_flag'])}</span></div>")
        P.append(_bull_bar(r["st_bull_ratio"]))
        if r["st_sample"]:
            P.append(f"<div class='metrics'><span>강세 {r['st_bullish']} · 약세 {r['st_bearish']}</span></div>")
            for m in r["st_sample"][:3]:
                sc = "s-bull" if m.get("sentiment") == "Bullish" else ("s-bear" if m.get("sentiment") == "Bearish" else "mut")
                tag = f"<span class='{sc}'>[{esc(m.get('sentiment') or '–')}]</span> "
                P.append(f"<div class='msg'>{tag}{esc(m.get('body'))}"
                         f"<div class='meta'>@{esc(m.get('user'))} · 팔로워 {_num(m.get('followers'))}</div></div>")
        if r["reddit_sample"]:
            for p in r["reddit_sample"][:2]:
                P.append(f"<div class='msg'>[r/{esc(p.get('subreddit'))}] {esc(p.get('title'))}"
                         f"<div class='meta'>▲{_num(p.get('score'))} · 댓글 {_num(p.get('num_comments'))}</div></div>")
        P.append("</div>")
    P.append("</div>")

    # 3) RSS headlines
    if rss_items:
        P.append("<h2>관련 헤드라인 (RSS)</h2><div class='card'>")
        for it in rss_items:
            P.append(f"<div class='msg'><b>{esc(', '.join(it['tickers']))}</b> — "
                     f"<a href='{esc(it['link'])}'>{esc(it['title'])}</a>"
                     f"<div class='meta'>{esc(it['feed'])}</div></div>")
        P.append("</div>")

    # disclaimer + sources
    P.append("<div class='disclaimer'><b>주의:</b> 본 브리핑은 커뮤니티/소셜의 <b>비공식·저신뢰 심리 데이터</b>입니다. "
             "찌라시·소문은 의도적 작전(펌프&덤프)일 수 있어 사실이 아니라 <b>'분위기/역신호'</b>로만 사용하세요. "
             "1차 자료(공시·실적)로 교차검증 전엔 의사결정 근거로 삼지 마세요.</div>")
    P.append(f"<div class='foot'>Sources: {esc(sources_status)} · Market Sentiment Brief (private)</div>")
    P.append("</div></body></html>")
    return "".join(P)

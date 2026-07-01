#!/usr/bin/env python3
"""Intraday Technical Analysis snapshot (pure stdlib).

Pulls minute bars from Yahoo, computes the standard day-trading indicator suite
(VWAP, EMA 9/20/50, RSI, MACD, Bollinger, ATR), classic pivots from the prior
session, auto support/resistance from swing points, and a trend read; then
writes a self-contained HTML report with an SVG candlestick chart.

USAGE:
    python3 ta.py MU                 # 1-minute, latest session
    python3 ta.py MU --interval 5m   # 5-minute bars
    python3 ta.py MU --open          # open the HTML when done (macOS)

NOT a live signal: Yahoo data is delayed (~15m) and only completed bars are
returned. Use this for structure/levels, not for execution timing.
"""
import os, sys, json, math, argparse, subprocess, urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def yahoo_chart(ticker, interval, rng):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?interval={interval}&range={rng}&includePrePost=false")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 IntradayTA/0.1"})
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode())
    res = d["chart"]["result"][0]
    meta = res["meta"]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c):
            continue
        bars.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v or 0})
    return meta, bars


def latest_session(bars, tzname):
    """Keep only the most recent calendar session's bars (exchange-local date)."""
    if not bars:
        return bars
    # exchange offset approximated from last bar vs UTC date is messy; use UTC day
    # boundaries are fine because US session never crosses UTC midnight intraday.
    last_day = datetime.utcfromtimestamp(bars[-1]["t"]).date()
    return [b for b in bars if datetime.utcfromtimestamp(b["t"]).date() == last_day]


# --------------------------------------------------------------------------- #
# indicators (pure python)
# --------------------------------------------------------------------------- #
def sma(vals, n):
    out = [None] * len(vals)
    s = 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= n:
            s -= vals[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(vals, n):
    out = [None] * len(vals)
    k = 2 / (n + 1)
    e = None
    for i, v in enumerate(vals):
        e = v if e is None else v * k + e * (1 - k)
        out[i] = e
    return out


def rsi(closes, n=14):
    out = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        ch = closes[i] - closes[i - 1]
        gains += max(ch, 0); losses += max(-ch, 0)
    ag, al = gains / n, losses / n
    out[n] = 100 - 100 / (1 + (ag / al if al else 999))
    for i in range(n + 1, len(closes)):
        ch = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(ch, 0)) / n
        al = (al * (n - 1) + max(-ch, 0)) / n
        out[i] = 100 - 100 / (1 + (ag / al if al else 999))
    return out


def macd(closes, fast=12, slow=26, sig=9):
    ef, es = ema(closes, fast), ema(closes, slow)
    line = [(a - b) if (a is not None and b is not None) else None for a, b in zip(ef, es)]
    vals = [x for x in line if x is not None]
    sigfull = ema(vals, sig)
    signal = [None] * len(line); j = 0
    for i, x in enumerate(line):
        if x is not None:
            signal[i] = sigfull[j]; j += 1
    hist = [(l - s) if (l is not None and s is not None) else None for l, s in zip(line, signal)]
    return line, signal, hist


def bollinger(closes, n=20, k=2):
    m = sma(closes, n)
    up = [None] * len(closes); lo = [None] * len(closes)
    for i in range(len(closes)):
        if i >= n - 1:
            window = closes[i - n + 1:i + 1]
            mean = m[i]
            sd = math.sqrt(sum((x - mean) ** 2 for x in window) / n)
            up[i] = mean + k * sd; lo[i] = mean - k * sd
    return up, m, lo


def atr(bars, n=14):
    trs = []
    for i, b in enumerate(bars):
        if i == 0:
            trs.append(b["h"] - b["l"]); continue
        pc = bars[i - 1]["c"]
        trs.append(max(b["h"] - b["l"], abs(b["h"] - pc), abs(b["l"] - pc)))
    out = [None] * len(bars)
    if len(trs) < n:
        return out
    a = sum(trs[:n]) / n; out[n - 1] = a
    for i in range(n, len(trs)):
        a = (a * (n - 1) + trs[i]) / n; out[i] = a
    return out


def vwap(bars):
    out = []; cum_pv = cum_v = 0.0
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3
        cum_pv += tp * b["v"]; cum_v += b["v"]
        out.append(cum_pv / cum_v if cum_v else b["c"])
    return out


def linreg_slope(closes, n=30):
    pts = closes[-n:]
    m = len(pts)
    if m < 3:
        return 0.0
    xs = list(range(m)); xm = sum(xs) / m; ym = sum(pts) / m
    num = sum((x - xm) * (y - ym) for x, y in zip(xs, pts))
    den = sum((x - xm) ** 2 for x in xs) or 1
    slope = num / den
    return slope / ym * 100  # % of price per bar


def swing_levels(bars, left=3, right=3, atr_val=None):
    """Find swing highs/lows; cluster into support/resistance with touch counts."""
    highs, lows = [], []
    n = len(bars)
    for i in range(left, n - right):
        wh = [bars[j]["h"] for j in range(i - left, i + right + 1)]
        wl = [bars[j]["l"] for j in range(i - left, i + right + 1)]
        if bars[i]["h"] == max(wh):
            highs.append(bars[i]["h"])
        if bars[i]["l"] == min(wl):
            lows.append(bars[i]["l"])
    tol = (atr_val or (bars[-1]["c"] * 0.0015)) * 0.6

    def cluster(levels):
        levels = sorted(levels); clusters = []
        for lv in levels:
            if clusters and abs(lv - clusters[-1][0]) <= tol:
                c = clusters[-1]; c[0] = (c[0] * c[1] + lv) / (c[1] + 1); c[1] += 1
            else:
                clusters.append([lv, 1])
        return sorted(clusters, key=lambda x: -x[1])
    return cluster(highs), cluster(lows)


def pivots(prior_h, prior_l, prior_c):
    p = (prior_h + prior_l + prior_c) / 3
    return {"P": p, "R1": 2 * p - prior_l, "S1": 2 * p - prior_h,
            "R2": p + (prior_h - prior_l), "S2": p - (prior_h - prior_l),
            "R3": prior_h + 2 * (p - prior_l), "S3": prior_l - 2 * (prior_h - p)}


# --------------------------------------------------------------------------- #
# analysis text
# --------------------------------------------------------------------------- #
def f(x, d=2):
    return f"{x:,.{d}f}" if isinstance(x, (int, float)) else "-"


def bar_local(ts, meta):
    """Format a UNIX ts in the exchange's local time using Yahoo's gmtoffset."""
    off = meta.get("gmtoffset", 0) or 0
    lt = datetime.utcfromtimestamp(ts + off)
    abbr = meta.get("timezone", "")  # e.g. 'EDT'
    return lt.strftime("%Y-%m-%d %H:%M") + (f" {abbr}" if abbr else "")


def build_read(meta, bars, ind):
    c = bars[-1]["c"]
    e9, e20, e50 = ind["ema9"][-1], ind["ema20"][-1], ind["ema50"][-1]
    vw = ind["vwap"][-1]; r = ind["rsi"][-1]; sl = ind["slope"]
    macd_l, macd_s = ind["macd"][-1], ind["macd_sig"][-1]
    a = ind["atr"][-1] or 0
    notes = []

    # trend via EMA alignment + slope
    if e9 and e20 and e50:
        if e9 > e20 > e50 and sl > 0:
            trend = "상승 추세 (EMA 9>20>50 정배열, 기울기 +)"
        elif e9 < e20 < e50 and sl < 0:
            trend = "하락 추세 (EMA 9<20<50 역배열, 기울기 -)"
        else:
            trend = "혼조/횡보 (EMA 엉킴)"
    else:
        trend = "데이터 부족"
    notes.append(f"추세: {trend}. 30봉 회귀 기울기 {f(sl,3)}%/봉.")

    # VWAP
    if vw:
        side = "위" if c >= vw else "아래"
        notes.append(f"VWAP {f(vw)} 대비 현재가 {f(c)} = VWAP {side}. "
                     f"({'VWAP 위 = 매수세 우위/롱 편향' if c>=vw else 'VWAP 아래 = 매도세 우위/숏 편향'}; "
                     "단타는 보통 VWAP 되돌림에서 방향 잡음.)")
    # RSI
    if r is not None:
        zone = "과매수(>70)" if r > 70 else ("과매도(<30)" if r < 30 else "중립")
        notes.append(f"RSI(14) {f(r,1)} = {zone}.")
    # MACD
    if macd_l is not None and macd_s is not None:
        notes.append(f"MACD {'골든(상승모멘텀)' if macd_l>macd_s else '데드(하락모멘텀)'} "
                     f"(line {f(macd_l,3)} vs signal {f(macd_s,3)}).")
    # ATR / stop sizing
    if a:
        notes.append(f"ATR(14) {f(a)} = 분봉 평균 변동폭. 통상 손절은 1.0~1.5×ATR "
                     f"(≈ {f(a)}~{f(a*1.5)}) 밖에 두고, 1R 대비 1.5~2R 목표가 일반적.")
    return trend, notes


# --------------------------------------------------------------------------- #
# SVG chart
# --------------------------------------------------------------------------- #
def svg_chart(bars, ind, sr_res, sr_sup, piv, width=1000, ph=420, vh=90):
    n = len(bars)
    pad_l, pad_r, pad_t = 8, 66, 10
    plot_w = width - pad_l - pad_r
    his = [b["h"] for b in bars]; los = [b["l"] for b in bars]
    extra = [lv for lv, _ in (sr_res[:3] + sr_sup[:3])] + [v for v in piv.values()]
    hi = max(his + [x for x in extra if x]); lo = min(los + [x for x in extra if x])
    rng = (hi - lo) or 1
    bw = plot_w / max(n, 1)

    def X(i): return pad_l + i * bw + bw / 2
    def Y(p): return pad_t + (hi - p) / rng * ph

    s = [f'<svg viewBox="0 0 {width} {ph+vh+40}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Segoe UI,Roboto,sans-serif" font-size="10">']
    s.append(f'<rect x="0" y="0" width="{width}" height="{ph+vh+40}" fill="#ffffff"/>')

    # gridlines + price axis
    for g in range(5):
        p = lo + rng * g / 4; y = Y(p)
        s.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" stroke="#eef2f6"/>')
        s.append(f'<text x="{pad_l+plot_w+4}" y="{y+3:.1f}" fill="#94a3b8">{p:,.2f}</text>')

    # pivots + S/R lines
    def hline(p, color, label, dash="4 3"):
        if p is None or p > hi or p < lo:
            return
        y = Y(p)
        s.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" '
                 f'stroke="{color}" stroke-width="1" stroke-dasharray="{dash}" opacity="0.8"/>')
        s.append(f'<text x="{pad_l+2}" y="{y-2:.1f}" fill="{color}">{label} {p:,.2f}</text>')
    hline(piv["P"], "#7c3aed", "P")
    for k in ("R1", "R2"):
        hline(piv[k], "#b72626", k)
    for k in ("S1", "S2"):
        hline(piv[k], "#157a60", k)
    for lv, tc in sr_res[:2]:
        hline(lv, "#b7262688", f"R×{tc}", "1 3")
    for lv, tc in sr_sup[:2]:
        hline(lv, "#157a6088", f"S×{tc}", "1 3")

    # candles
    for i, b in enumerate(bars):
        up = b["c"] >= b["o"]; col = "#157a60" if up else "#b72626"
        x = X(i)
        s.append(f'<line x1="{x:.1f}" y1="{Y(b["h"]):.1f}" x2="{x:.1f}" y2="{Y(b["l"]):.1f}" stroke="{col}" stroke-width="0.7"/>')
        yo, yc = Y(b["o"]), Y(b["c"]); top = min(yo, yc); h = max(abs(yo - yc), 0.6)
        s.append(f'<rect x="{x-bw*0.3:.1f}" y="{top:.1f}" width="{max(bw*0.6,0.8):.1f}" height="{h:.1f}" fill="{col}"/>')

    # overlay lines
    def poly(series, color, w=1.3):
        pts = [f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(series) if v is not None]
        if pts:
            s.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{w}"/>')
    poly(ind["vwap"], "#f59e0b", 1.6)   # VWAP amber
    poly(ind["ema9"], "#2563eb")        # blue
    poly(ind["ema20"], "#7c3aed")       # purple
    poly(ind["ema50"], "#64748b")       # gray

    # volume panel
    vy0 = pad_t + ph + 24
    vmax = max((b["v"] for b in bars), default=1) or 1
    s.append(f'<text x="{pad_l}" y="{vy0-6}" fill="#94a3b8">Volume</text>')
    for i, b in enumerate(bars):
        up = b["c"] >= b["o"]; col = "#157a6066" if up else "#b7262666"
        bh = b["v"] / vmax * vh; x = X(i)
        s.append(f'<rect x="{x-bw*0.3:.1f}" y="{vy0+vh-bh:.1f}" width="{max(bw*0.6,0.8):.1f}" height="{bh:.1f}" fill="{col}"/>')

    # legend
    leg = [("VWAP", "#f59e0b"), ("EMA9", "#2563eb"), ("EMA20", "#7c3aed"), ("EMA50", "#64748b")]
    lx = pad_l
    for name, col in leg:
        s.append(f'<rect x="{lx}" y="{ph+vh+30}" width="10" height="10" fill="{col}"/>'
                 f'<text x="{lx+13}" y="{ph+vh+39}" fill="#475569">{name}</text>')
        lx += 70
    s.append("</svg>")
    return "".join(s)


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #
CSS = """body{font-family:-apple-system,'Apple SD Gothic Neo',Segoe UI,Roboto,sans-serif;margin:0;background:#f4f6f8;color:#1f2933}
.wrap{max-width:1040px;margin:0 auto;padding:24px 22px 50px}h1{font-size:24px;margin:0 0 2px}
.sub{color:#64748b;font-size:13px;margin-bottom:18px}h2{font-size:17px;color:#0f5132;border-left:5px solid #157a60;padding-left:10px;margin:24px 0 10px}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;margin-bottom:14px}
table{width:100%;border-collapse:collapse}td,th{padding:6px 9px;border-top:1px solid #eef2f6;font-size:13px;text-align:left}
th{background:#157a60;color:#fff;border:0}.k{color:#64748b}.up{color:#157a60;font-weight:600}.down{color:#b72626;font-weight:600}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.lvl{font-variant-numeric:tabular-nums}
.warn{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;border-radius:10px;padding:11px 15px;font-size:12.5px;margin-top:22px}
ul{margin:6px 0 0;padding-left:18px}li{margin:3px 0;font-size:13px}"""


def render(meta, bars, ind, sr_res, sr_sup, piv, trend, notes, interval):
    import html as H
    c = bars[-1]["c"]; o = bars[0]["o"]; chg = (c - o) / o * 100
    sess = bar_local(bars[-1]["t"], meta).split()[0]
    last_t = bar_local(bars[-1]["t"], meta)
    first_t = bar_local(bars[0]["t"], meta)
    P = [f"<!doctype html><meta charset='utf-8'><style>{CSS}</style><div class='wrap'>"]
    P.append(f"<h1>{meta.get('symbol')} — Intraday TA <span class='k' style='font-size:15px'>({interval})</span></h1>")
    P.append(f"<div class='sub'>세션 {sess} · {len(bars)}봉 ({first_t} ~ <b>{last_t}</b>) · 현재가 <b>{f(c)}</b> "
             f"<span class='{'up' if chg>=0 else 'down'}'>({'+' if chg>=0 else ''}{f(chg)}% vs 시가)</span> · "
             f"최신봉 <b>{last_t}</b> · 데이터 지연(~15m)</div>")
    P.append(f"<div class='card'>{svg_chart(bars, ind, sr_res, sr_sup, piv)}</div>")

    # read
    P.append("<h2>구조 요약</h2><div class='card'><b>" + H.escape(trend) + "</b><ul>")
    for nt in notes:
        P.append("<li>" + H.escape(nt) + "</li>")
    P.append("</ul></div>")

    # indicator dashboard
    e9, e20, e50 = ind["ema9"][-1], ind["ema20"][-1], ind["ema50"][-1]
    bbu, bbm, bbl = ind["bb_up"][-1], ind["bb_mid"][-1], ind["bb_lo"][-1]
    rows = [("VWAP", f(ind["vwap"][-1])), ("EMA 9", f(e9)), ("EMA 20", f(e20)), ("EMA 50", f(e50)),
            ("RSI(14)", f(ind["rsi"][-1], 1)), ("MACD line", f(ind["macd"][-1], 3)),
            ("MACD signal", f(ind["macd_sig"][-1], 3)), ("ATR(14)", f(ind["atr"][-1])),
            ("Boll upper", f(bbu)), ("Boll mid", f(bbm)), ("Boll lower", f(bbl)),
            ("세션 고가", f(max(b["h"] for b in bars))), ("세션 저가", f(min(b["l"] for b in bars)))]
    P.append("<h2>지표 대시보드</h2><div class='grid'><div class='card'><table>")
    for k, v in rows[:7]:
        P.append(f"<tr><td class='k'>{k}</td><td class='lvl'>{v}</td></tr>")
    P.append("</table></div><div class='card'><table>")
    for k, v in rows[7:]:
        P.append(f"<tr><td class='k'>{k}</td><td class='lvl'>{v}</td></tr>")
    P.append("</table></div></div>")

    # levels
    P.append("<h2>주요 레벨 (지지/저항/피봇)</h2><div class='grid'>")
    P.append("<div class='card'><table><tr><th>저항</th><th>값</th></tr>")
    for k in ("R3", "R2", "R1"):
        P.append(f"<tr><td>피봇 {k}</td><td class='lvl down'>{f(piv[k])}</td></tr>")
    for lv, tc in sr_res[:3]:
        P.append(f"<tr><td>스윙 저항 (터치 {tc})</td><td class='lvl down'>{f(lv)}</td></tr>")
    P.append("</table></div><div class='card'><table><tr><th>지지</th><th>값</th></tr>")
    P.append(f"<tr><td>피봇 P</td><td class='lvl'>{f(piv['P'])}</td></tr>")
    for k in ("S1", "S2", "S3"):
        P.append(f"<tr><td>피봇 {k}</td><td class='lvl up'>{f(piv[k])}</td></tr>")
    for lv, tc in sr_sup[:3]:
        P.append(f"<tr><td>스윙 지지 (터치 {tc})</td><td class='lvl up'>{f(lv)}</td></tr>")
    P.append("</table></div></div>")

    P.append("<div class='warn'><b>주의:</b> 본 분석은 지연(~15분) 데이터 기준의 <b>정적 스냅샷</b>입니다. "
             "분 단위 체결 시그널이 아니며, 레벨·추세 구조 파악용입니다. 실제 매매는 실시간 차트/호가로 확인하고, "
             "기술적 분석은 확률이지 보장이 아닙니다. 손절·포지션 사이징을 항상 먼저 정하세요.</div></div>")
    return "".join(P)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--interval", default="1m", help="1m,2m,5m,15m,30m,60m")
    ap.add_argument("--range", default=None, help="override Yahoo range (e.g. 1d,5d)")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()

    rng = a.range or ("1d" if a.interval in ("1m", "2m") else "5d")
    meta, allbars = yahoo_chart(a.ticker, a.interval, rng)
    bars = latest_session(allbars, meta.get("exchangeTimezoneName"))
    if len(bars) < 20:
        bars = allbars[-200:]  # fallback if session split is sparse

    closes = [b["c"] for b in bars]
    atr_v = atr(bars, 14)
    macd_l, macd_s, macd_h = macd(closes)
    bbu, bbm, bbl = bollinger(closes, 20, 2)
    ind = {"ema9": ema(closes, 9), "ema20": ema(closes, 20), "ema50": ema(closes, 50),
           "vwap": vwap(bars), "rsi": rsi(closes, 14), "atr": atr_v,
           "macd": macd_l, "macd_sig": macd_s, "macd_hist": macd_h,
           "bb_up": bbu, "bb_mid": bbm, "bb_lo": bbl,
           "slope": linreg_slope(closes, 30)}

    sr_res, sr_sup = swing_levels(bars, 3, 3, atr_v[-1] if atr_v[-1] else None)

    # prior-session pivots from a daily series
    try:
        _, daily = yahoo_chart(a.ticker, "1d", "10d")
        prior = daily[-2] if len(daily) >= 2 else daily[-1]
        piv = pivots(prior["h"], prior["l"], prior["c"])
    except Exception:
        ph = max(b["h"] for b in bars); pl = min(b["l"] for b in bars)
        piv = pivots(ph, pl, bars[-1]["c"])

    trend, notes = build_read(meta, bars, ind)
    out_html = render(meta, bars, ind, sr_res, sr_sup, piv, trend, notes, a.interval)

    outdir = os.path.join(HERE, "out"); os.makedirs(outdir, exist_ok=True)
    sess = datetime.utcfromtimestamp(bars[-1]["t"]).strftime("%Y%m%d")
    path = os.path.join(outdir, f"{a.ticker}-{a.interval}-{sess}.html")
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(out_html)

    print(f"{a.ticker} {a.interval}: {len(bars)} bars, last close {f(closes[-1])}")
    print(f"latest bar: {bar_local(bars[-1]['t'], meta)}  (oldest: {bar_local(bars[0]['t'], meta)})")
    print(f"trend: {trend}")
    print(f"VWAP {f(ind['vwap'][-1])} | RSI {f(ind['rsi'][-1],1)} | ATR {f(atr_v[-1])}")
    print(f"report: {path}")
    if a.open:
        subprocess.run(["open", path], check=False)


if __name__ == "__main__":
    main()

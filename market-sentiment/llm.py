"""Optional Claude enrichment: turn the raw aggregated signals into a short
Korean narrative ('어제의 종목별 심리 + 주목할 루머'). Falls back to a rule-based
digest when the API key / library is unavailable, so the brief always renders.
"""
import os
import json
import html


def _rule_based(market_heat, watchlist_recs):
    """Deterministic digest, no API needed."""
    hot = [r for r in market_heat if (r.get("mention_delta_pct") or 0) >= 50][:5]
    bull = [r for r in watchlist_recs if r.get("sentiment_cls") == "bull"]
    bear = [r for r in watchlist_recs if r.get("sentiment_cls") == "bear"]
    parts = []
    if hot:
        names = ", ".join(f"{r['ticker']}(+{r['mention_delta_pct']}%)" for r in hot)
        parts.append(f"<b>오늘 언급 급증:</b> {html.escape(names)}.")
    if bull:
        parts.append("<b>강세 우위:</b> " + html.escape(", ".join(r["ticker"] for r in bull[:6])) + ".")
    if bear:
        parts.append("<b>약세 우위:</b> " + html.escape(", ".join(r["ticker"] for r in bear[:6])) + ".")
    if not parts:
        parts.append("워치리스트에서 두드러진 심리 변화는 관찰되지 않음.")
    parts.append("<span style='color:#94a3b8'>(rule-based 요약 — Claude 요약을 켜려면 ANTHROPIC_API_KEY 설정)</span>")
    return " ".join(parts)


def summarize(market_heat, watchlist_recs, model="claude-opus-4-8"):
    """Return an HTML snippet. Uses Claude if available, else rule-based."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _rule_based(market_heat, watchlist_recs)
    try:
        import anthropic
    except ImportError:
        print("[llm] anthropic library not installed; pip install anthropic. Using rule-based.")
        return _rule_based(market_heat, watchlist_recs)

    # compact payload for the model
    payload = {
        "market_heat": [{k: r.get(k) for k in ("ticker", "mentions", "mention_delta_pct", "heat_flag")}
                        for r in market_heat[:15]],
        "watchlist": [{k: r.get(k) for k in ("ticker", "mention_delta_pct", "st_bull_ratio",
                                             "st_messages", "sentiment_label", "heat_flag")}
                      for r in watchlist_recs],
        "samples": {r["ticker"]: [m.get("body") for m in r.get("st_sample", [])[:3]]
                    for r in watchlist_recs if r.get("st_sample")},
    }
    prompt = (
        "너는 헤지펀드의 센티먼트 애널리스트다. 아래는 미국 주식에 대한 커뮤니티/소셜(Reddit 언급량, "
        "StockTwits 강세/약세) 집계다. 한국어로 간결한 '오늘의 심리 브리핑'을 작성하라. 규칙:\n"
        "- 3~5문장. 과장 금지, 숫자 근거 인용.\n"
        "- 언급이 급증했거나 강세/약세 쏠림이 큰 종목을 짚어라.\n"
        "- 이건 비공식·저신뢰 데이터임을 전제로, 사실이 아니라 '분위기/쏠림/역신호'로 해석하라.\n"
        "- 종목명/티커/숫자는 영문·원문 유지. 매수/매도 추천 금지.\n"
        "- HTML 인라인 태그(<b> 등)만 사용, 코드블록·마크다운 금지.\n\n"
        f"데이터:\n{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model, max_tokens=900,
            messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        return text or _rule_based(market_heat, watchlist_recs)
    except Exception as e:
        print(f"[llm] Claude call failed ({e}); using rule-based.")
        return _rule_based(market_heat, watchlist_recs)

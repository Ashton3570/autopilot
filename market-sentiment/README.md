# Market Sentiment Brief (private)

미국주식 **커뮤니티/소셜 심리**를 매일 한 장의 HTML 리포트로 모아주는 개인용 도구.
공시·실적 같은 1차 정보가 아니라, Reddit 언급량·StockTwits 강세/약세 같은 **비공식·저신뢰 심리 레인**을 빠르게 훑기 위한 것.

> ⚠️ 이 데이터는 찌라시·소문 포함. 사실이 아니라 **'분위기/쏠림/역신호'**로만 쓰고, 1차 자료로 교차검증 전엔 매매 근거로 삼지 말 것.

---

## 바로 실행 (API 키 불필요)

```bash
cd "Market Sentiment Brief"
python3 brief.py --open
```

키리스로 작동하는 기본 소스:
- **ApeWisdom** — Reddit 전체의 종목 언급량 / 24h 변화 / rank (→ "오늘 달아오르는 종목")
- **StockTwits** — 종목별 메시지 + Bullish/Bearish 라벨 (→ 강세/약세 게이지 + 샘플 글)

결과물:
- `briefs/<날짜>-sentiment-brief.html` — 브라우저로 열기 / 인쇄→PDF 저장
- `data/<날짜>/raw.json` — 원본 수집 데이터 (재처리/백테스트용)

## 설정 — `config.json`

- `watchlist` — 추적할 티커 (기본: 반도체/AI 중심)
- `market_wide_top_n` — "달아오르는 종목" 표 길이
- `sources` — 각 소스 on/off
- `llm.enabled` — Claude 요약 on/off

## 선택 기능

### 1) Claude 한국어 요약 (`llm.enabled=true`)
```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
# config.json -> "llm": { "enabled": true }
```
켜면 상단에 "오늘의 요약" 문단이 붙음. 끄면 rule-based 요약으로 자동 대체(항상 렌더됨).

### 2) Reddit 직접 수집 (`sources.reddit=true`)
Reddit 무료 'script' 앱 발급 후:
```bash
# https://www.reddit.com/prefs/apps -> create app (type: script)
export REDDIT_CLIENT_ID=...
export REDDIT_CLIENT_SECRET=...
```
(없어도 ApeWisdom이 Reddit 언급을 간접 커버하므로 필수는 아님.)

### 3) RSS 헤드라인 (`sources.rss=true`)
`config.json`의 `rss_feeds`에 피드 추가. 워치리스트 티커가 제목에 있으면 수집.

## 매일 자동 실행 (cron)

```bash
chmod +x run_daily.sh
crontab -e
# 평일 오전 8시(장 시작 전)에 생성:
0 8 * * 1-5  "/Users/ashton/Market Sentiment Brief/run_daily.sh"
```
비밀키는 `.env` 파일(`ANTHROPIC_API_KEY=...`)에 두면 `run_daily.sh`가 자동 로드.

## 구조

```
brief.py        # 메인 오케스트레이터 (collect -> aggregate -> render)
collectors.py   # ApeWisdom / StockTwits / Reddit / RSS
aggregate.py    # 종목별 머지 + heat/sentiment 스코어
render.py       # 자가완결 HTML 리포트
llm.py          # 선택: Claude 요약 (없으면 rule-based)
config.json     # 워치리스트 + 소스 토글
run_daily.sh    # cron 진입점
```

## 로드맵 (Phase 2+)
- 워치리스트 종목별 페이지 + 센티먼트 추세 차트 (날짜별 raw.json 누적 활용)
- 텔레그램 채널 아카이빙 (`Telethon`) — 찌라시 통로
- 급등 시 푸시 알림(준실시간)
- X(트위터) FinTwit — 유료 API 필요
- 한국 커뮤니티 — 스크래핑(유지보수 부담, ToS 유의)

## 주의 (법/신뢰도)
- 받아보는 것은 자유지만 **허위·풍문 유포**나 **미공개 중요정보 이용 매매**는 자본시장법 위반.
- 찌라시 적중률은 낮음 — 작전(펌프&덤프) 가능성을 항상 전제.
- "커뮤니티 고수"는 생존편향 큼 — 트랙레코드를 시계열로 남길 것.

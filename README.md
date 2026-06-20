# AI 신뢰성·안정성 인증 및 평가 — 일일 뉴스 요약기

매일 **AI 신뢰성 / 안정성 / 인증 / 평가**와 관련된 최신 뉴스를 수집해
한국어 브리핑 리포트로 만들어 주는 프로그램입니다.

- 국내(한국어) + 해외(영어) 뉴스를 **Google 뉴스 RSS**에서 수집
- 중복 제거 후 최신순 정렬, 최근 N일 이내 기사만 필터링
- **Claude(claude-opus-4-8)** 로 주제별 한국어 요약 리포트 생성 (API 키 있을 때)
- API 키가 없으면 RSS 설명 기반 **자동 정리**로 폴백
- 결과를 콘솔에 출력하고 `reports/ai-news-YYYY-MM-DD.md` 로 저장

## 요구 사항

- Python 3.10 이상
- 뉴스 수집·폴백 요약: **추가 설치 불필요** (표준 라이브러리만 사용)
- Claude 요약(선택): `pip install anthropic` + 환경변수 `ANTHROPIC_API_KEY`

## 사용법

```bash
# 1) (선택) Claude 요약을 쓰려면
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."

# 2) 실행
python3 ai_news_summary.py

# 옵션
python3 ai_news_summary.py --days 3     # 최근 3일치 수집(기본 2일)
python3 ai_news_summary.py --no-save    # 파일로 저장하지 않고 화면 출력만
```

## 매일 자동 실행 (cron 예시)

매일 오전 8시에 실행하고 로그를 남기려면 `crontab -e` 에 추가하세요.

```cron
0 8 * * * cd /path/to/project && ANTHROPIC_API_KEY=sk-ant-... /usr/bin/python3 ai_news_summary.py >> reports/cron.log 2>&1
```

## 검색 키워드 바꾸기

`ai_news_summary.py` 상단의 `KEYWORDS_KO`, `KEYWORDS_EN` 리스트를 수정하면
원하는 주제로 손쉽게 바꿀 수 있습니다.

## 동작 방식

1. **수집** — 각 키워드별 Google 뉴스 RSS를 받아 기사 제목·링크·출처·날짜·요약을 파싱
2. **정리** — 제목 기준 중복 제거 + 최근 N일 필터 + 최신순 정렬
3. **요약** — Claude로 핵심 요약/주제별 정리/시사점 작성 (키 없으면 자동 정리)
4. **출력** — 콘솔 + `reports/` 폴더에 Markdown 저장

> 참고: 요약 생성에 사용한 기사 출처 전체 목록이 리포트 하단에 항상 링크로 포함됩니다.

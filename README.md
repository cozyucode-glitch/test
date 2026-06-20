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

## 요약 엔진 — API 키 없이도 됩니다

`--engine` 옵션으로 요약 방식을 고를 수 있습니다. 기본값 `auto`는 사용 가능한
것을 자동 감지합니다(Claude API 키 → Codex CLI → 오프라인 폴백 순).

| 엔진 | 키 필요? | 설명 |
|------|:---:|------|
| `none` | ❌ | LLM 없이 RSS 설명만 정리. **완전 무료·완전 자동.** |
| `codex` | ❌ | **OpenAI Codex CLI** 를 호출해 요약. ChatGPT **구독(Plus/Pro)** 로그인으로 동작 → 별도 API 키·과금 없음. |
| `claude` | ✅ | Anthropic API 키(`ANTHROPIC_API_KEY`)로 가장 매끄러운 요약. |
| (반자동) | ❌ | `--chatgpt-prompt` 로 "붙여넣기용 프롬프트" 파일만 생성 → ChatGPT 웹에 붙여넣어 요약. |

### Codex(ChatGPT 구독) 연동 — 키 없이 자동 요약

> ⚠️ ChatGPT Plus 구독에는 호출 가능한 API가 포함돼 있지 않습니다. 하지만
> **Codex CLI는 "Sign in with ChatGPT"(OAuth) 로그인** 을 지원하고, 그 사용량은
> 구독에 포함됩니다. 이 스크립트는 Codex CLI를 서브프로세스로 호출해 요약을 받습니다.

```bash
# 1) Codex CLI 설치 후 ChatGPT 계정으로 로그인 (최초 1회)
npm install -g @openai/codex
codex            # 실행 후 "Sign in with ChatGPT" 선택

# 2) Codex 엔진으로 실행 (API 키 불필요)
python3 ai_news_summary.py --engine codex
```

호출 명령을 바꾸려면 `CODEX_CMD` 환경변수를 쓰세요(기본 `codex exec`):

```bash
export CODEX_CMD="codex exec --skip-git-repo-check"
```

### ChatGPT 웹에 붙여넣기 (반자동)

```bash
python3 ai_news_summary.py --chatgpt-prompt
# → reports/chatgpt-prompt-YYYY-MM-DD.txt 생성. 내용을 복사해 ChatGPT에 붙여넣으세요.
```

### Claude API 사용 (선택)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
python3 ai_news_summary.py --engine claude
```

## 사용법

```bash
python3 ai_news_summary.py                 # auto: 가능한 엔진 자동 선택
python3 ai_news_summary.py --engine none   # 완전 무료·오프라인 정리
python3 ai_news_summary.py --engine codex  # ChatGPT 구독으로 요약
python3 ai_news_summary.py --days 3        # 최근 3일치 수집(기본 2일)
python3 ai_news_summary.py --no-save       # 파일로 저장하지 않고 화면 출력만
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

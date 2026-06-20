#!/usr/bin/env python3
"""AI 신뢰성·안정성 인증 및 평가 관련 뉴스 일일 요약 프로그램.

매일 실행하면 'AI 신뢰성/안정성/인증/평가'와 관련된 최신 뉴스를
구글 뉴스 RSS에서 수집해 중복을 제거하고, 한국어 요약 리포트를
콘솔과 Markdown 파일(reports/)로 만들어 줍니다.

요약 방식:
  * 환경변수 ANTHROPIC_API_KEY 가 설정돼 있으면 Claude(claude-opus-4-8)로
    기사들을 묶어 한국어 요약 리포트를 생성합니다(권장).
  * 키가 없으면 RSS가 제공하는 기사 설명을 그대로 정리해 보여줍니다(폴백).

의존성:
  * 수집/폴백 요약: 표준 라이브러리만 사용(설치 불필요)
  * Claude 요약(선택): pip install anthropic
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import sys
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

# 검색 키워드. 한국어와 영어를 함께 넣어 국내외 뉴스를 모두 수집합니다.
KEYWORDS_KO = [
    "AI 신뢰성 평가",
    "인공지능 안정성 인증",
    "AI 신뢰성 인증",
    "인공지능 신뢰성 평가",
    "AI 안전성 평가",
]
KEYWORDS_EN = [
    "AI reliability certification",
    "AI safety evaluation",
    "trustworthy AI assessment",
    "AI assurance standard",
]

MODEL = "claude-opus-4-8"
USER_AGENT = "Mozilla/5.0 (compatible; AINewsSummary/1.0)"
REPORT_DIR = "reports"


@dataclass
class Article:
    title: str
    link: str
    source: str
    published: dt.datetime | None
    summary: str

    @property
    def published_str(self) -> str:
        return self.published.strftime("%Y-%m-%d %H:%M") if self.published else "날짜 미상"


# ---------------------------------------------------------------------------
# 수집
# ---------------------------------------------------------------------------

def _google_news_rss_url(query: str, lang: str) -> str:
    """구글 뉴스 검색 RSS URL을 만든다."""
    params = urllib.parse.quote(query)
    if lang == "ko":
        return f"https://news.google.com/rss/search?q={params}&hl=ko&gl=KR&ceid=KR:ko"
    return f"https://news.google.com/rss/search?q={params}&hl=en-US&gl=US&ceid=US:en"


def _strip_html(text: str) -> str:
    """RSS 설명에서 HTML 태그를 제거하고 공백을 정리한다."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_pubdate(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            parsed = dt.datetime.strptime(value, fmt)
            # tz 정보가 있으면 UTC 기준 naive 로 변환
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    return None


def fetch_feed(query: str, lang: str, timeout: int = 15) -> list[Article]:
    """하나의 키워드에 대한 RSS를 받아 Article 리스트로 변환한다."""
    url = _google_news_rss_url(query, lang)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    articles: list[Article] = []
    for item in root.iter("item"):
        title = _strip_html(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        description = _strip_html(item.findtext("description") or "")
        published = _parse_pubdate(item.findtext("pubDate"))

        source_el = item.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else ""
        # 구글 뉴스 제목은 보통 "기사 제목 - 언론사" 형태라 source 가 없으면 추출
        if not source and " - " in title:
            source = title.rsplit(" - ", 1)[-1].strip()

        if title and link:
            articles.append(Article(title, link, source, published, description))
    return articles


def collect_articles(days: int) -> list[Article]:
    """모든 키워드에서 기사를 모아 중복을 제거하고 최근 N일로 필터링한다."""
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
    seen_titles: set[str] = set()
    results: list[Article] = []

    for lang, keywords in (("ko", KEYWORDS_KO), ("en", KEYWORDS_EN)):
        for kw in keywords:
            try:
                feed = fetch_feed(kw, lang)
            except Exception as exc:  # 네트워크 등 개별 실패는 건너뛴다
                print(f"  ! '{kw}' 수집 실패: {exc}", file=sys.stderr)
                continue
            for art in feed:
                key = re.sub(r"\s+", "", art.title.lower())[:80]
                if key in seen_titles:
                    continue
                # 날짜를 알 수 있는 기사만 cutoff 적용(날짜 미상은 포함)
                if art.published and art.published < cutoff:
                    continue
                seen_titles.add(key)
                results.append(art)

    # 최신순 정렬(날짜 미상은 뒤로)
    results.sort(key=lambda a: a.published or dt.datetime.min, reverse=True)
    return results


# ---------------------------------------------------------------------------
# 요약
# ---------------------------------------------------------------------------

def summarize_with_claude(articles: list[Article]) -> str | None:
    """Claude로 한국어 요약 리포트를 생성한다. 실패/키 없음이면 None."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        print("  ! anthropic 패키지가 없어 Claude 요약을 건너뜁니다. (pip install anthropic)",
              file=sys.stderr)
        return None

    # 기사 목록을 프롬프트로 구성(토큰 절약을 위해 상위 30건)
    lines = []
    for i, a in enumerate(articles[:30], 1):
        lines.append(f"[{i}] {a.title} ({a.source}, {a.published_str})\n    {a.summary}")
    article_block = "\n".join(lines)

    prompt = textwrap.dedent(f"""\
        아래는 'AI 신뢰성·안정성 인증 및 평가'와 관련해 오늘 수집한 뉴스 기사 목록입니다.
        이 내용을 바탕으로 한국어 일일 브리핑을 작성해 주세요.

        작성 형식:
        1. **오늘의 핵심 요약** — 전체 흐름을 3~5문장으로 정리
        2. **주요 토픽별 정리** — 관련 기사를 2~4개 주제로 묶어 각 주제를 불릿으로 요약
           (각 항목 끝에 참고한 기사 번호를 [n] 형태로 표기)
        3. **주목할 동향/시사점** — 인증·평가·규제 관점에서 눈여겨볼 점 2~3가지

        과장 없이 사실 위주로, 기사에 없는 내용은 추측하지 마세요.

        ===== 기사 목록 =====
        {article_block}
        """)

    client = anthropic.Anthropic()
    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()
    except Exception as exc:
        print(f"  ! Claude 요약 실패, 폴백으로 전환합니다: {exc}", file=sys.stderr)
        return None

    return "".join(b.text for b in message.content if b.type == "text").strip()


def fallback_digest(articles: list[Article]) -> str:
    """Claude 없이 RSS 설명만으로 간단 정리한다."""
    parts = ["## 기사 요약 (자동 정리)\n",
             f"_총 {len(articles)}건의 관련 기사를 수집했습니다._\n"]
    for i, a in enumerate(articles, 1):
        summary = a.summary or "(요약 없음)"
        if len(summary) > 220:
            summary = summary[:220] + "…"
        parts.append(f"**{i}. {a.title}**  \n"
                     f"   - 출처: {a.source or '미상'} · {a.published_str}  \n"
                     f"   - {summary}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 리포트 출력
# ---------------------------------------------------------------------------

def build_report(articles: list[Article], body: str, used_claude: bool) -> str:
    today = dt.date.today().isoformat()
    engine = "Claude 요약" if used_claude else "자동 정리(폴백)"
    header = (
        f"# AI 신뢰성·안정성 인증 및 평가 — 일일 뉴스 브리핑\n\n"
        f"- 생성일: {today}\n"
        f"- 수집 기사 수: {len(articles)}건\n"
        f"- 요약 엔진: {engine}\n"
    )
    sources = "\n".join(
        f"{i}. [{a.title}]({a.link}) — {a.source or '미상'} ({a.published_str})"
        for i, a in enumerate(articles, 1)
    )
    return f"{header}\n---\n\n{body}\n\n---\n\n## 전체 기사 출처\n\n{sources}\n"


def save_report(report: str) -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f"ai-news-{dt.date.today().isoformat()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    return path


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI 신뢰성·안정성 인증/평가 관련 뉴스 일일 요약")
    parser.add_argument("--days", type=int, default=2,
                        help="최근 며칠 이내의 기사만 수집 (기본: 2)")
    parser.add_argument("--no-save", action="store_true",
                        help="Markdown 파일로 저장하지 않음")
    args = parser.parse_args()

    print(f"[1/3] 뉴스 수집 중... (최근 {args.days}일)")
    articles = collect_articles(args.days)
    if not articles:
        print("수집된 기사가 없습니다. 네트워크 상태나 키워드를 확인해 주세요.")
        return 1
    print(f"      → {len(articles)}건 수집 완료")

    print("[2/3] 요약 생성 중...")
    body = summarize_with_claude(articles)
    used_claude = body is not None
    if not used_claude:
        body = fallback_digest(articles)

    print("[3/3] 리포트 작성 중...")
    report = build_report(articles, body, used_claude)

    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)

    if not args.no_save:
        path = save_report(report)
        print(f"\n저장 완료: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

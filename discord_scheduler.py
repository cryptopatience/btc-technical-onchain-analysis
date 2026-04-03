#!/usr/bin/env python3
"""
Discord 자동 발송 스케줄러
매일 KST 08:00 — 5개 모드 뉴스 수집 → 각 Deep Dive → AI 종합분석 → Discord 발송
실행: python discord_scheduler.py
"""

import datetime
import logging
import os
import re
import time

import requests
import schedule
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ── 설정 ──────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1489587323145556089/bU3SPqYHML4R-EWap7BpkEuaLCOA4iJs2KRjMPciqr_TKbvQGaPylathyi9hJyLDD0vb",
)
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# ── 공통 유틸 ──────────────────────────────────────
# ══════════════════════════════════════════════════
def _now_kst():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(text, "html.parser").get_text(separator=" ")).strip()


def _make_item(title, url="", source="", published_at="", description=""):
    return {
        "title":        re.sub(r"\s+", " ", title).strip(),
        "url":          url,
        "source":       source,
        "published_at": published_at,
        "description":  _strip_html(description or ""),
    }


def _dedup(items: list) -> list:
    seen, out = {}, []
    for item in items:
        key = re.sub(r"[^a-z0-9]", "", item["title"].lower())[:60]
        if key not in seen:
            seen[key] = True
            out.append(item)
    return out


def _fetch_rss(url: str, source: str, limit: int = 20) -> list:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "xml")
        results = []
        for item in soup.find_all("item")[:limit]:
            title = item.find("title")
            link  = item.find("link")
            desc  = item.find("description")
            pub   = item.find("pubDate")
            if not title or not title.text.strip():
                continue
            results.append(_make_item(
                title=title.text,
                url=link.text.strip() if link else "",
                source=source,
                published_at=pub.text.strip() if pub else "",
                description=desc.text if desc else "",
            ))
        return results
    except Exception as e:
        log.warning(f"RSS 오류 [{source}]: {e}")
        return []


def _build_text(items: list, limit: int = 40) -> str:
    lines = []
    for item in items[:limit]:
        line = f"- [{item['source']}] {item['title']}"
        if item.get("description"):
            line += f"\n  {item['description'][:120]}"
        lines.append(line)
    return "\n".join(lines)


# ══════════════════════════════════════════════════
# ── 뉴스 수집 함수 ─────────────────────────────────
# ══════════════════════════════════════════════════
def fetch_stock_news() -> list:
    items = []
    items += _fetch_rss("https://finance.yahoo.com/news/rssindex", "Yahoo Finance")
    items += _fetch_rss("https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=120000000", "CNBC")
    items += _fetch_rss("http://feeds.marketwatch.com/marketwatch/topstories/", "MarketWatch")
    if FINNHUB_API_KEY:
        try:
            r = requests.get("https://finnhub.io/api/v1/news",
                params={"category": "general", "token": FINNHUB_API_KEY},
                headers=HEADERS, timeout=15)
            for item in r.json()[:20]:
                items.append(_make_item(
                    title=item.get("headline", ""),
                    url=item.get("url", ""),
                    source=item.get("source", "Finnhub"),
                    published_at=datetime.datetime.utcfromtimestamp(
                        item.get("datetime", 0)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    description=item.get("summary", "")[:200],
                ))
        except Exception as e:
            log.warning(f"Finnhub 오류: {e}")
    return _dedup([x for x in items if x["title"]])


def fetch_coin_news() -> list:
    items = []
    items += _fetch_rss("https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk")
    items += _fetch_rss("https://theblock.co/rss.xml", "The Block")
    items += _fetch_rss("https://decrypt.co/feed", "Decrypt")
    if CRYPTOPANIC_API_KEY:
        try:
            r = requests.get("https://cryptopanic.com/api/v1/posts/",
                params={"auth_token": CRYPTOPANIC_API_KEY, "kind": "news", "currencies": "BTC"},
                headers=HEADERS, timeout=15)
            for post in r.json().get("results", [])[:20]:
                items.append(_make_item(
                    title=post.get("title", ""),
                    url=post.get("url", ""),
                    source="CryptoPanic",
                    published_at=post.get("published_at", ""),
                ))
        except Exception as e:
            log.warning(f"CryptoPanic 오류: {e}")
    return _dedup([x for x in items if x["title"]])


def fetch_btc_ta_news() -> list:
    items = []
    items += _fetch_rss("https://cointelegraph.com/rss/tag/bitcoin", "CoinTelegraph")
    items += _fetch_rss("https://ambcrypto.com/feed/", "AMBCrypto")
    items += _fetch_rss("https://cryptoslate.com/feed/", "CryptoSlate")
    items += _fetch_rss("https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk")
    return _dedup([x for x in items if x["title"]])


def fetch_btc_oc_news() -> list:
    items = []
    items += _fetch_rss("https://insights.glassnode.com/rss/", "Glassnode")
    items += _fetch_rss("https://cointelegraph.com/rss/tag/bitcoin", "CoinTelegraph")
    items += _fetch_rss("https://cryptoslate.com/feed/", "CryptoSlate")
    items += _fetch_rss("https://theblock.co/rss.xml", "The Block")
    return _dedup([x for x in items if x["title"]])


def fetch_m7_news() -> list:
    M7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"]
    items = []
    items += _fetch_rss("https://finance.yahoo.com/news/rssindex", "Yahoo Finance")
    items += _fetch_rss("https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=120000000", "CNBC")
    items += _fetch_rss("http://feeds.marketwatch.com/marketwatch/topstories/", "MarketWatch")
    if FINNHUB_API_KEY:
        for ticker in M7:
            try:
                now_kst = _now_kst()
                today = now_kst.strftime("%Y-%m-%d")
                yesterday = (now_kst - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                r = requests.get("https://finnhub.io/api/v1/company-news",
                    params={"symbol": ticker, "from": yesterday, "to": today, "token": FINNHUB_API_KEY},
                    headers=HEADERS, timeout=15)
                for item in r.json()[:10]:
                    items.append(_make_item(
                        title=item.get("headline", ""),
                        url=item.get("url", ""),
                        source=item.get("source", "Finnhub"),
                        published_at=datetime.datetime.utcfromtimestamp(
                            item.get("datetime", 0)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        description=item.get("summary", "")[:200],
                    ))
            except Exception as e:
                log.warning(f"Finnhub M7 [{ticker}] 오류: {e}")
    # 티커 키워드 필터
    ticker_kw = {t.lower() for t in M7} | {
        "apple", "microsoft", "alphabet", "google", "amazon", "meta", "tesla", "nvidia",
    }
    filtered = [x for x in items if any(kw in x["title"].lower() for kw in ticker_kw)]
    return _dedup([x for x in filtered if x["title"]])


# ══════════════════════════════════════════════════
# ── AI 분석 ────────────────────────────────────────
# ══════════════════════════════════════════════════
PROMPTS_DEEP = {
    "stock": (
        "다음은 {date} (KST) 미국 증시 주요 뉴스입니다.\n{content}\n"
        "위 뉴스만을 바탕으로 한국어 Deep Dive 심층 분석을 작성해주세요.\n"
        "1. **거시 경제 및 연준(Fed) 동향 분석**\n"
        "2. **주요 기업 실적 및 펀더멘털 분석**\n"
        "3. **섹터별 자금 흐름 및 특징**\n"
        "4. **리스크 요인 및 시장의 우려**\n"
        "5. **단기 시장 전망 및 월가 시각**\n"
        "전문적인 금융 리포트 톤으로 작성해주세요."
    ),
    "coin": (
        "다음은 {date} (KST) 기준 코인 뉴스입니다.\n{content}\n"
        "위 뉴스만 바탕으로 한국어 Deep Dive 분석을 작성해주세요.\n"
        "1. **거시 경제 및 규제 환경 분석**\n"
        "2. **주요 코인별/섹터별 테마 분석**\n"
        "3. **기관 투자자 동향**\n"
        "4. **리스크 요인 및 주의 포인트**\n"
        "5. **단기 시장 전망 및 투자 시사점**"
    ),
    "ta": (
        "다음은 {date} (KST) 기준 비트코인 기술적 분석 기사들입니다.\n{content}\n"
        "위 내용만을 바탕으로 한국어 Deep Dive 기술적 분석을 작성해주세요.\n"
        "1. **현재 가격 구조 분석**\n"
        "2. **오실레이터·모멘텀 지표 분석**\n"
        "3. **이동평균선 및 추세 분석**\n"
        "4. **주요 패턴 및 차트 형태**\n"
        "5. **단기/중기 가격 전망 및 핵심 레벨**"
    ),
    "oc": (
        "다음은 {date} (KST) 기준 비트코인 온체인 분석 기사들입니다.\n{content}\n"
        "위 내용만을 바탕으로 한국어 Deep Dive 온체인 분석을 작성해주세요.\n"
        "1. **밸류에이션 지표 분석** (MVRV, SOPR)\n"
        "2. **홀더 행동 분석** (LTH vs STH)\n"
        "3. **거래소 흐름 분석**\n"
        "4. **파생상품·레버리지 현황**\n"
        "5. **매크로 온체인 전망**"
    ),
    "m7": (
        "다음은 {date} (KST) 기준 Magnificent 7 관련 기사들입니다.\n{content}\n"
        "위 내용만을 바탕으로 한국어 Deep Dive 분석을 작성해주세요.\n"
        "1. **기술적 분석 종목별 현황**\n"
        "2. **펀더멘털 분석**\n"
        "3. **애널리스트 의견 종합**\n"
        "4. **섹터 및 매크로 연관성**\n"
        "5. **종목별 리스크 및 기회 요인**"
    ),
}

PROMPT_COMBINED = """다음은 {date} (KST) 기준 각 시장별 AI Deep Dive 분석 결과입니다.

{sections}

위 분석들을 종합하여 한국어로 AI 종합 분석 리포트를 작성해주세요.

1. **매크로 환경 및 주요 리스크 요인**
   - 주식 시장과 비트코인에 공통으로 영향을 미치는 매크로 요인
   - 현재 가장 주목해야 할 리스크

2. **BTC 포지셔닝 전략**
   - 기술적 분석 + 온체인 분석을 종합한 BTC 현재 상황 평가
   - 단기(1주일) / 중기(1개월) 전망

3. **M7 및 미국 주식 전망**
   - 주식 시장과 M7 분석을 종합한 현재 투자 환경
   - 주목해야 할 종목 및 섹터

4. **크립토 vs 전통 자산 상관관계**
   - 비트코인과 주식 시장의 상관관계 분석
   - 자산 배분 관점에서의 시사점

5. **결론: 오늘의 핵심 인사이트 3가지**
   - 가장 중요한 관찰 사항 3가지를 bullet point로 명확히 제시

전문적이고 날카로운 금융 분석 리포트 톤으로 작성해주세요."""


def _call_gemini(prompt_text: str) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        log.error("google-genai 패키지 없음. pip install google-genai")
        return ""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        r = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt_text,
            config=types.GenerateContentConfig(temperature=0.35, max_output_tokens=16000),
        )
        return r.text if r.text is not None else r.candidates[0].content.parts[0].text or ""
    except Exception as e:
        log.error(f"Gemini 오류: {e}")
        return ""


def _call_openai(prompt_text: str, max_tokens: int = 4000) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        log.error("openai 패키지 없음. pip install openai")
        return ""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        return (
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt_text}],
                max_tokens=max_tokens,
                temperature=0.35,
            ).choices[0].message.content or ""
        )
    except Exception as e:
        log.error(f"GPT 오류: {e}")
        return ""


def _ai_deep_dive(mode: str, news_items: list, date_str: str) -> str:
    content = _build_text(news_items, 40)
    if not content:
        return ""
    prompt = PROMPTS_DEEP[mode].format(date=date_str, content=content)
    if GEMINI_API_KEY:
        return _call_gemini(prompt)
    if OPENAI_API_KEY:
        return _call_openai(prompt, max_tokens=3000)
    return ""


# ══════════════════════════════════════════════════
# ── Discord 발송 ────────────────────────────────────
# ══════════════════════════════════════════════════
def send_discord(text: str, webhook_url: str = DISCORD_WEBHOOK_URL) -> bool:
    if not text or not webhook_url:
        return False
    chunks, remaining = [], text
    while remaining:
        chunks.append(remaining[:1900])
        remaining = remaining[1900:]
    total = len(chunks)
    success = True
    for i, chunk in enumerate(chunks):
        header = f"**[{i+1}/{total}]**\n" if total > 1 else ""
        try:
            r = requests.post(webhook_url, json={"content": header + chunk}, timeout=15)
            if r.status_code not in (200, 204):
                log.warning(f"Discord 응답 {r.status_code}: {r.text[:200]}")
                success = False
            if i < total - 1:
                time.sleep(0.5)
        except Exception as e:
            log.error(f"Discord 발송 오류: {e}")
            success = False
    return success


# ══════════════════════════════════════════════════
# ── 메인 잡 ────────────────────────────────────────
# ══════════════════════════════════════════════════
def run_daily_report():
    now_kst = _now_kst()
    date_str = now_kst.strftime("%Y-%m-%d")
    log.info(f"=== 일일 종합분석 시작 [{date_str} KST] ===")

    # 1. 각 모드 뉴스 수집
    fetchers = {
        "stock": fetch_stock_news,
        "coin":  fetch_coin_news,
        "ta":    fetch_btc_ta_news,
        "oc":    fetch_btc_oc_news,
        "m7":    fetch_m7_news,
    }
    labels = {
        "stock": "📈 미국 주식 시장 분석",
        "coin":  "🪙 코인 시장 분석",
        "ta":    "📊 BTC 기술적 분석",
        "oc":    "🔗 BTC 온체인 분석",
        "m7":    "🏆 M7 기술적 분석",
    }

    # 2. 각 모드 Deep Dive 생성
    deep_dives = {}
    for mode, fetch_fn in fetchers.items():
        log.info(f"  수집 중: {labels[mode]}")
        try:
            items = fetch_fn()
            log.info(f"    → {len(items)}건 수집")
            if items:
                log.info(f"  AI Deep Dive 생성 중: {labels[mode]}")
                deep = _ai_deep_dive(mode, items, date_str)
                if deep:
                    deep_dives[mode] = deep
                    log.info(f"    → Deep Dive 완료 ({len(deep)}자)")
                else:
                    log.warning(f"    → Deep Dive 생성 실패 (AI 응답 없음)")
        except Exception as e:
            log.error(f"  오류 [{mode}]: {e}")

    if not deep_dives:
        log.error("모든 모드에서 Deep Dive 생성 실패. Discord 발송 취소.")
        return

    # 3. 종합분석 생성
    log.info("AI 종합분석 생성 중...")
    sections = "\n\n".join(
        f"=== {labels[m]} ===\n{deep_dives[m][:3000]}"
        for m in labels if m in deep_dives
    )
    combined_prompt = PROMPT_COMBINED.format(date=date_str, sections=sections)

    combined = ""
    if GEMINI_API_KEY:
        log.info("  Gemini 2.5 Pro 종합분석 중...")
        combined = _call_gemini(combined_prompt)
    elif OPENAI_API_KEY:
        log.info("  GPT-4o-mini 종합분석 중...")
        combined = _call_openai(combined_prompt, max_tokens=4000)

    if not combined:
        log.error("종합분석 생성 실패. Discord 발송 취소.")
        return

    # 4. Discord 발송
    log.info("Discord 발송 중...")
    header = (
        f"📊 **AI 종합분석 리포트** | {date_str} KST\n"
        f"{'─'*40}\n\n"
    )
    ok = send_discord(header + combined)
    if ok:
        log.info("✅ Discord 발송 완료!")
        # 발송 시각 캐시에 기록 (Streamlit UI에서 표시)
        try:
            import json as _json
            _cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis_cache.json")
            _cache = {}
            if os.path.exists(_cache_file):
                with open(_cache_file, "r", encoding="utf-8") as _f:
                    _cache = _json.load(_f)
            _cache["discord_last_sent"] = now_kst.strftime("%Y-%m-%d %H:%M KST")
            with open(_cache_file, "w", encoding="utf-8") as _f:
                _json.dump(_cache, _f, ensure_ascii=False, indent=2)
        except Exception as _e:
            log.warning(f"캐시 기록 실패: {_e}")
    else:
        log.error("❌ Discord 발송 실패.")

    log.info("=== 일일 종합분석 완료 ===")


# ══════════════════════════════════════════════════
# ── 스케줄러 ───────────────────────────────────────
# ══════════════════════════════════════════════════
def _is_kst_08():
    """현재 시각이 KST 08:00~08:01 인지 확인"""
    now = _now_kst()
    return now.hour == 8 and now.minute == 0


def _schedule_loop():
    """매분 KST 시간을 확인해 08:00에 실행"""
    _fired_today = {"date": None}

    def _check():
        today = _now_kst().date()
        if _is_kst_08() and _fired_today["date"] != today:
            _fired_today["date"] = today
            run_daily_report()

    schedule.every(1).minutes.do(_check)
    log.info("스케줄러 시작 — 매일 KST 08:00 Discord 자동 발송")
    log.info(f"현재 KST 시각: {_now_kst().strftime('%Y-%m-%d %H:%M:%S')}")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        # 즉시 실행 테스트용: python discord_scheduler.py --now
        log.info("즉시 실행 모드 (--now)")
        run_daily_report()
    else:
        _schedule_loop()

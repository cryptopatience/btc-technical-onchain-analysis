"""
BTC 기술적 분석 + 온체인 분석 뉴스 리포트
- 사이드바에서 '기술적 분석' / '온체인 분석' 선택 후 각각 수집·AI 요약·목록 표시
- 소스: CoinTelegraph, AMBCrypto, Glassnode Insights, CryptoSlate, Coinglass, The Block, Reddit
"""

import datetime
import os
import re
import time as _time
from email.utils import parsedate_to_datetime

import requests
import streamlit as st
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="BTC 기술적, 온체인분석",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_secret(key: str) -> str:
    try:
        return st.secrets.get(key, "") or os.getenv(key, "")
    except Exception:
        return os.getenv(key, "")


# ── API 키 ─────────────────────────────────────
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
APP_PASSWORD = get_secret("APP_PASSWORD") or "btc1234"  # ← 기본 비밀번호 (변경 가능)

# ── 비밀번호 인증 ─────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if APP_PASSWORD and not st.session_state.authenticated:
    st.markdown("""
    <style>
    #MainMenu, header, footer { visibility: hidden; }
    .lock-wrap {
        max-width: 380px; margin: 10vh auto 0;
        background: #161b22; border: 1px solid #30363d;
        border-radius: 20px; padding: 48px 40px;
        text-align: center; box-shadow: 0 24px 64px rgba(0,0,0,.6);
    }
    .lock-wrap h2 { font-size: 1.4rem; font-weight: 700; color: #f0f6fc; margin-bottom: 6px; }
    .lock-wrap p { color: #8b949e; font-size: .88rem; margin-bottom: 28px; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(
        '<div class="lock-wrap"><div style="font-size:2.6rem">🔐</div><h2>BTC 기술적, 온체인분석</h2><p>접근하려면 비밀번호를 입력하세요</p></div>',
        unsafe_allow_html=True,
    )
    pw = st.text_input("비밀번호", type="password", placeholder="••••", label_visibility="collapsed")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("잠금 해제", type="primary", use_container_width=True):
            if pw == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    st.stop()

# ── 공통 상수 ──────────────────────────────────
NOW_UTC = datetime.datetime.utcnow()
NOW_KST = NOW_UTC + datetime.timedelta(hours=9)
TODAY_STR = NOW_KST.strftime("%Y-%m-%d")
YESTERDAY_STR = (NOW_KST - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

# ── 소스 색상 ──────────────────────────────────
SOURCE_COLORS = {
    "cointelegraph": "#00d4aa",
    "ambcrypto": "#f59e0b",
    "glassnode": "#3b82f6",
    "cryptoslate": "#8b5cf6",
    "coinglass": "#ef4444",
    "the block": "#f97316",
    "reddit": "#ff4500",
    "coindesk": "#1a73e8",
    "decrypt": "#00d4aa",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── 기술적 분석 키워드 필터 ────────────────────
TA_KEYWORDS = [
    "technical analysis", "price analysis", "chart analysis", "price prediction",
    "rsi", "macd", "moving average", "ema", "sma", "bollinger",
    "support", "resistance", "breakout", "breakdown", "trend",
    "fibonacci", "fib", "elliott wave", "pattern", "wedge", "triangle",
    "bullish", "bearish", "rally", "correction", "reversal",
    "all-time high", "ath", "price target", "key level",
    "overbought", "oversold", "momentum", "volume", "candlestick",
    "head and shoulders", "reverse head and shoulders", "double top", "double bottom", "flag", "pennant",
    "bitcoin price", "btc price", "btc/usd", "price outlook", "market structure",
    "higher high", "lower low", "higher low", "lower high",
]

# ── 온체인 분석 키워드 필터 ────────────────────
ONCHAIN_KEYWORDS = [
    "on-chain", "onchain", "on chain",
    "mvrv", "sopr", "nupl", "nvt", "realized price",
    "exchange flow", "exchange balance", "exchange inflow", "exchange outflow",
    "funding rate", "open interest", "liquidation", "long/short",
    "whale", "large holder", "accumulation", "distribution",
    "hash rate", "hashrate", "miner", "mining",
    "stablecoin", "usdt", "usdc supply",
    "etf flow", "etf inflow", "etf outflow", "spot etf",
    "netflow", "urpd", "arpd", "cost basis",
    "hodl", "lth", "sth", "long-term holder", "short-term holder",
    "glassnode", "intotheblock", "santiment", "coinglass",
    "network value", "active address", "transaction volume",
    "unrealized profit", "unrealized loss",
    "dormancy", "coin days destroyed", "cdd",
    "perpetual", "derivatives", "basis",
    "funding", "liquidity",
]

# ── CSS ────────────────────────────────────────
st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #0a0f1e 0%, #0d1b2a 50%, #1a1228 100%);
    border: 1px solid #1e3a5f; border-radius: 16px;
    padding: 32px 28px 24px; text-align: center; margin-bottom: 24px;
}
.main-header h1 {
    font-size: 2rem; font-weight: 800;
    background: linear-gradient(90deg, #f7931a, #00d4aa, #3b82f6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 8px;
}
.main-header .sub { color: #8892b0; font-size: .9rem; }
.news-card {
    background: #161b22; border: 1px solid #21262d;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 8px;
}
.news-card:hover { border-color: #f7931a; }
.news-title { font-size: .93rem; font-weight: 500; color: #e6edf3; line-height: 1.5; margin-bottom: 5px; }
.news-title a { color: #e6edf3; text-decoration: none; }
.news-title a:hover { color: #f7931a; }
.news-desc { font-size: .8rem; color: #8b949e; line-height: 1.5; margin-bottom: 7px; }
.news-meta { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
.src-badge { font-size: .7rem; border: 1px solid; border-radius: 4px; padding: 1px 7px; font-weight: 600; }
.tag-badge {
    font-size: .68rem; border-radius: 4px; padding: 1px 6px; font-weight: 700;
    background: rgba(247,147,26,0.15); color: #f7931a; border: 1px solid rgba(247,147,26,0.3);
}
.tag-onchain {
    background: rgba(59,130,246,0.15); color: #3b82f6; border: 1px solid rgba(59,130,246,0.3);
}
.time-tag { font-size: .72rem; color: #6e7681; }
.sec-title {
    font-size: 1rem; font-weight: 700; color: #f0f6fc;
    margin: 24px 0 12px; padding-left: 10px;
    border-left: 4px solid #f7931a;
}
.keyword-chip {
    display: inline-block; font-size: .65rem; padding: 1px 5px;
    background: rgba(0,212,170,0.12); color: #00d4aa;
    border: 1px solid rgba(0,212,170,0.25); border-radius: 3px;
    margin: 1px 2px;
}
</style>
""", unsafe_allow_html=True)


# ── 공통 유틸 ──────────────────────────────────
def src_color(source: str) -> str:
    low = source.lower()
    for k, v in SOURCE_COLORS.items():
        if k in low:
            return v
    return "#8b949e"


def _strip_html(text: str) -> str:
    if not text:
        return ""
    cleaned = BeautifulSoup(text, "html.parser").get_text(separator=" ")
    return re.sub(r"\s+", " ", cleaned).strip()


def make_item(title, url="", source="", published_at="", description="", matched_keywords=None):
    desc = _strip_html(description or "")
    return {
        "title": re.sub(r"\s+", " ", title).strip(),
        "url": url,
        "source": source,
        "published_at": published_at,
        "description": desc,
        "matched_keywords": matched_keywords or [],
    }


def is_recent(pub: str, days: int = 3) -> bool:
    """최근 N일 이내인지 확인 (기본 3일)"""
    if not pub:
        return True
    cutoff = (NOW_KST - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    return pub[:10] >= cutoff


def dedup(news_list: list) -> list:
    seen, result = {}, []
    for item in news_list:
        key = re.sub(r"[^a-z0-9]", "", item["title"].lower())[:60]
        if key not in seen:
            seen[key] = True
            result.append(item)
    return result


def utc_to_kst(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (dt + datetime.timedelta(hours=9)).strftime("%m/%d %H:%M")
    except Exception:
        return iso_str[:16]


def build_news_text(news_list: list, limit: int = 60) -> str:
    lines = []
    for item in news_list[:limit]:
        line = f"- [{item['source']}] {item['title']}"
        if item.get("description"):
            line += f"\n  {item['description'][:150]}"
        if item.get("matched_keywords"):
            line += f"\n  키워드: {', '.join(item['matched_keywords'][:5])}"
        lines.append(line)
    return "\n".join(lines)


def match_keywords(text: str, keywords: list) -> list:
    """텍스트에서 매칭된 키워드 반환"""
    text_lower = text.lower()
    return [kw for kw in keywords if kw in text_lower]


def is_ta_article(item: dict) -> bool:
    combined = (item["title"] + " " + item.get("description", "")).lower()
    return any(kw in combined for kw in TA_KEYWORDS)


def is_onchain_article(item: dict) -> bool:
    combined = (item["title"] + " " + item.get("description", "")).lower()
    return any(kw in combined for kw in ONCHAIN_KEYWORDS)


def tag_item(item: dict) -> dict:
    """아이템에 TA/온체인 태그 및 매칭 키워드 추가"""
    combined = (item["title"] + " " + item.get("description", "")).lower()
    ta_matched = [kw for kw in TA_KEYWORDS if kw in combined]
    oc_matched = [kw for kw in ONCHAIN_KEYWORDS if kw in combined]
    item["is_ta"] = len(ta_matched) > 0
    item["is_onchain"] = len(oc_matched) > 0
    item["matched_keywords"] = (ta_matched + oc_matched)[:8]
    return item


def render_news_card(item: dict, idx: int) -> None:
    import html as _html

    title = _html.escape(item.get("title", "") or "")
    url = item.get("url", "")
    source = item.get("source", "")
    pub = item.get("published_at", "")
    desc = _html.escape((item.get("description", "") or "").strip())
    color = src_color(source)
    kst = utc_to_kst(pub)
    is_ta = item.get("is_ta", False)
    is_oc = item.get("is_onchain", False)
    matched = item.get("matched_keywords", [])

    title_html = f'<a href="{url}" target="_blank">{title}</a>' if url else title
    desc_html = f'<div class="news-desc">{desc[:200]}</div>' if desc and desc != title else ""
    time_html = f'<span class="time-tag">🕐 KST {kst}</span>' if kst else ""

    # 분석 유형 뱃지
    type_badges = ""
    if is_ta:
        type_badges += '<span class="tag-badge">📊 TA</span> '
    if is_oc:
        type_badges += '<span class="tag-badge tag-onchain">🔗 온체인</span> '

    # 매칭 키워드 칩 (최대 4개)
    kw_chips = ""
    for kw in matched[:4]:
        kw_chips += f'<span class="keyword-chip">{_html.escape(kw)}</span>'

    st.markdown(f"""
    <div class="news-card">
      <div style="display:flex;gap:10px;align-items:flex-start">
        <div style="flex-shrink:0;width:24px;height:24px;background:#21262d;border-radius:5px;
                    display:flex;align-items:center;justify-content:center;
                    font-size:.7rem;color:#8b949e;font-weight:600;margin-top:2px">{idx}</div>
        <div style="flex:1;min-width:0">
          <div class="news-title">{title_html}</div>
          {desc_html}
          <div class="news-meta">
            <span class="src-badge" style="background:{color}22;color:{color};border-color:{color}55">{source}</span>
            {type_badges}
            {time_html}
          </div>
          {f'<div style="margin-top:5px">{kw_chips}</div>' if kw_chips else ""}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── AI 요약 ───────────────────────────────────
PROMPT_TA_QUICK = """다음은 {date} (KST) 기준 비트코인 기술적 분석 기사들입니다.

{content}

위 내용만을 바탕으로 한국어 Quick Summary를 작성해주세요.
1. **현재 BTC 차트 핵심 구조** (주요 지지/저항 레벨, 현재 포지션)
2. **주요 기술적 지표 현황** (RSI, MACD, 이평선 상태 등 언급된 것 위주)
3. **단기 시나리오** (강세/약세 시나리오 각 1~2문장)
4. **한줄 차트 요약**
간결하고 트레이더 관점에서 실용적으로 작성해주세요."""

PROMPT_TA_DEEP = """다음은 {date} (KST) 기준 비트코인 기술적 분석 기사들입니다.

{content}

위 내용만을 바탕으로 한국어 Deep Dive 기술적 분석을 작성해주세요.
1. **현재 가격 구조 분석** (주요 지지·저항, 시장 구조 상세)
2. **오실레이터·모멘텀 지표 분석** (RSI, MACD, 스토캐스틱 등)
3. **이동평균선 및 추세 분석** (EMA, SMA, 골든/데드 크로스)
4. **주요 패턴 및 차트 형태** (삼각수렴, 플래그, 웨지 등)
5. **단기/중기 가격 전망 및 핵심 레벨**
전문 트레이더를 위한 상세 분석으로 작성해주세요."""

PROMPT_OC_QUICK = """다음은 {date} (KST) 기준 비트코인 온체인 분석 기사들입니다.

{content}

위 내용만을 바탕으로 한국어 Quick Summary를 작성해주세요.
1. **핵심 온체인 시그널** (3~5개, 각 1~2문장)
2. **투자자 행동 분석** (매집/분산, 고래 움직임 등)
3. **파생상품 시장 현황** (펀딩비, OI, 청산 등)
4. **한줄 온체인 요약**
데이터 중심으로 간결하게 작성해주세요."""

PROMPT_OC_DEEP = """다음은 {date} (KST) 기준 비트코인 온체인 분석 기사들입니다.

{content}

위 내용만을 바탕으로 한국어 Deep Dive 온체인 분석을 작성해주세요.
1. **밸류에이션 지표 분석** (MVRV, SOPR, Realized Price, NVT 등)
2. **홀더 행동 분석** (LTH vs STH, HODL 패턴, 코인 이동)
3. **거래소 흐름 분석** (거래소 입출금, 잔고 변화)
4. **파생상품·레버리지 현황** (펀딩비, 미결제약정, 청산 데이터)
5. **매크로 온체인 전망** (시장 사이클 위치, 투자 시사점)
각 지표의 의미와 현재 시사점을 충분히 설명해주세요."""


def summarize_gemini(news_list, api_key, prompt_quick, prompt_deep):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        st.error("google-genai 패키지가 없습니다.")
        return "", ""

    client = genai.Client(api_key=api_key)
    content = build_news_text(news_list, 60)

    def _extract(resp):
        if resp.text is not None:
            return resp.text
        try:
            return resp.candidates[0].content.parts[0].text or ""
        except Exception:
            return ""

    quick, deep = "", ""
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt_quick.format(date=TODAY_STR, content=content),
            config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=8000),
        )
        quick = _extract(resp)
    except Exception as e:
        st.warning(f"Gemini Quick Summary 오류: {e}")
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt_deep.format(date=TODAY_STR, content=content),
            config=types.GenerateContentConfig(temperature=0.35, max_output_tokens=16000),
        )
        deep = _extract(resp)
    except Exception as e:
        st.warning(f"Gemini Deep Dive 오류: {e}")
    return quick, deep


def summarize_openai(news_list, api_key, prompt_quick, prompt_deep):
    try:
        from openai import OpenAI
    except ImportError:
        st.error("openai 패키지가 없습니다.")
        return "", ""

    client = OpenAI(api_key=api_key)
    content = build_news_text(news_list, 60)
    quick, deep = "", ""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_quick.format(date=TODAY_STR, content=content)}],
            max_tokens=1500,
            temperature=0.4,
        )
        quick = resp.choices[0].message.content or ""
    except Exception as e:
        st.warning(f"GPT Quick Summary 오류: {e}")
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_deep.format(date=TODAY_STR, content=content)}],
            max_tokens=3000,
            temperature=0.35,
        )
        deep = resp.choices[0].message.content or ""
    except Exception as e:
        st.warning(f"GPT Deep Dive 오류: {e}")
    return quick, deep


# ─────────────────────────────────────────────
# ── 스크래퍼 함수들 ───────────────────────────
# ─────────────────────────────────────────────

def parse_rss_datetime(raw: str) -> str:
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return raw[:19]


def fetch_cointelegraph_ta() -> list:
    """CoinTelegraph BTC 기술적 분석 태그 페이지 스크래핑"""
    results = []
    urls_to_try = [
        "https://cointelegraph.com/rss/tag/bitcoin-price",
        "https://cointelegraph.com/rss/tag/technical-analysis",
        "https://cointelegraph.com/rss/tag/bitcoin",
    ]
    seen = set()
    for rss_url in urls_to_try:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "xml")
        except Exception:
            continue
        for item in soup.find_all("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            desc_el = item.find("description")
            title = title_el.get_text(strip=True) if title_el else ""
            link = link_el.get_text(strip=True) if link_el else ""
            pub_raw = pub_el.get_text(strip=True) if pub_el else ""
            desc = BeautifulSoup(desc_el.get_text(strip=True) if desc_el else "", "html.parser").get_text()[:200]
            if not title or link in seen:
                continue
            pub_iso = parse_rss_datetime(pub_raw)
            if not is_recent(pub_iso, days=5):
                continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source="CoinTelegraph", published_at=pub_iso, description=desc))
    return results


def fetch_ambcrypto() -> list:
    """AMBCrypto RSS 수집 + TA/온체인 관련 기사 필터링"""
    results = []
    rss_urls = [
        "https://ambcrypto.com/feed/",
        "https://ambcrypto.com/category/bitcoin/feed/",
    ]
    seen = set()
    for rss_url in rss_urls:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "xml")
        except Exception:
            continue
        for item in soup.find_all("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            desc_el = item.find("description")
            title = title_el.get_text(strip=True) if title_el else ""
            link = link_el.get_text(strip=True) if link_el else ""
            pub_raw = pub_el.get_text(strip=True) if pub_el else ""
            desc = BeautifulSoup(desc_el.get_text(strip=True) if desc_el else "", "html.parser").get_text()[:200]
            if not title or link in seen:
                continue
            pub_iso = parse_rss_datetime(pub_raw)
            if not is_recent(pub_iso, days=5):
                continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source="AMBCrypto", published_at=pub_iso, description=desc))
    return results


def fetch_glassnode_insights() -> list:
    """Glassnode Insights RSS/블로그 수집"""
    results = []
    seen = set()
    # RSS 시도
    rss_attempts = [
        "https://insights.glassnode.com/rss/",
        "https://insights.glassnode.com/feed/",
        "https://insights.glassnode.com/rss.xml",
    ]
    for rss_url in rss_attempts:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "xml")
            items = soup.find_all("item") or soup.find_all("entry")
            if not items:
                continue
            for item in items:
                title_el = item.find("title")
                link_el = item.find("link")
                pub_el = item.find("pubDate") or item.find("published")
                desc_el = item.find("description") or item.find("summary")
                title = title_el.get_text(strip=True) if title_el else ""
                link = (link_el.get("href") or link_el.get_text(strip=True)) if link_el else ""
                pub_raw = pub_el.get_text(strip=True) if pub_el else ""
                desc = BeautifulSoup(desc_el.get_text(strip=True) if desc_el else "", "html.parser").get_text()[:200]
                if not title or link in seen:
                    continue
                pub_iso = parse_rss_datetime(pub_raw)
                seen.add(link)
                results.append(make_item(title=title, url=link, source="Glassnode", published_at=pub_iso, description=desc))
            if results:
                break
        except Exception:
            continue

    # RSS 실패 시 HTML 스크래핑 시도
    if not results:
        try:
            r = requests.get("https://insights.glassnode.com/", headers=HEADERS, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if not ("glassnode.com" in href or href.startswith("/")):
                        continue
                    full_url = href if href.startswith("http") else f"https://insights.glassnode.com{href}"
                    if full_url in seen or "insights.glassnode.com" not in full_url:
                        continue
                    title = a.get_text(strip=True)
                    if not title or len(title) < 15:
                        continue
                    seen.add(full_url)
                    results.append(make_item(title=title, url=full_url, source="Glassnode", published_at=""))
        except Exception:
            pass

    return results


def fetch_cryptoslate_research() -> list:
    """CryptoSlate Research/분석 기사 RSS 수집"""
    results = []
    seen = set()
    rss_urls = [
        "https://cryptoslate.com/feed/",
        "https://cryptoslate.com/category/research/feed/",
        "https://cryptoslate.com/category/bitcoin/feed/",
    ]
    for rss_url in rss_urls:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "xml")
        except Exception:
            continue
        for item in soup.find_all("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            desc_el = item.find("description")
            title = title_el.get_text(strip=True) if title_el else ""
            link = link_el.get_text(strip=True) if link_el else ""
            pub_raw = pub_el.get_text(strip=True) if pub_el else ""
            desc = BeautifulSoup(desc_el.get_text(strip=True) if desc_el else "", "html.parser").get_text()[:200]
            if not title or link in seen:
                continue
            pub_iso = parse_rss_datetime(pub_raw)
            if not is_recent(pub_iso, days=5):
                continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source="CryptoSlate", published_at=pub_iso, description=desc))
    return results


def fetch_coinglass_news() -> list:
    """Coinglass 뉴스/분석 페이지 스크래핑"""
    results = []
    seen = set()
    try:
        # Coinglass 블로그/뉴스 RSS
        r = requests.get("https://www.coinglass.com/blog", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/blog/" not in href and "/news/" not in href and "/analysis/" not in href:
                    continue
                full_url = href if href.startswith("http") else f"https://www.coinglass.com{href}"
                if full_url in seen:
                    continue
                title = a.get_text(strip=True)
                if not title or len(title) < 15:
                    continue
                seen.add(full_url)
                results.append(make_item(title=title, url=full_url, source="Coinglass", published_at=""))
    except Exception:
        pass
    return results


def fetch_theblock_research() -> list:
    """The Block RSS 수집 (리서치/온체인 데이터 중심)"""
    results = []
    seen = set()
    rss_attempts = [
        "https://www.theblock.co/rss.xml",
        "https://www.theblock.co/feeds/rss.xml",
    ]
    for rss_url in rss_attempts:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "xml")
        except Exception:
            continue
        for item in soup.find_all("item") or soup.find_all("entry"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate") or item.find("published")
            desc_el = item.find("description") or item.find("summary")
            title = title_el.get_text(strip=True) if title_el else ""
            link = link_el.get_text(strip=True) if link_el else ""
            pub_raw = pub_el.get_text(strip=True) if pub_el else ""
            desc = BeautifulSoup(desc_el.get_text(strip=True) if desc_el else "", "html.parser").get_text()[:200]
            if not title or link in seen:
                continue
            pub_iso = parse_rss_datetime(pub_raw)
            if not is_recent(pub_iso, days=5):
                continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source="The Block", published_at=pub_iso, description=desc))
        if results:
            break
    return results


def fetch_reddit_btcmarkets() -> list:
    """Reddit r/BitcoinMarkets 핫 포스트 수집"""
    results = []
    seen = set()
    reddit_headers = {**HEADERS, "Accept": "application/json"}
    for subreddit in ["BitcoinMarkets", "CryptoCurrency"]:
        for sort in ["hot", "top"]:
            try:
                r = requests.get(
                    f"https://www.reddit.com/r/{subreddit}/{sort}.json",
                    headers=reddit_headers,
                    params={"limit": 25, "t": "day"},
                    timeout=15,
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                posts = data.get("data", {}).get("children", [])
                for post in posts:
                    p = post.get("data", {})
                    title = p.get("title", "")
                    url = p.get("url", "")
                    permalink = "https://www.reddit.com" + p.get("permalink", "")
                    created_utc = p.get("created_utc", 0)
                    selftext = p.get("selftext", "")[:200]
                    flair = p.get("link_flair_text", "")
                    score = p.get("score", 0)

                    if not title or permalink in seen:
                        continue
                    if score < 5:  # 너무 낮은 점수 제외
                        continue

                    pub = datetime.datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%dT%H:%M:%SZ") if created_utc else ""
                    if pub and not is_recent(pub, days=3):
                        continue

                    seen.add(permalink)
                    display_url = permalink
                    full_title = f"[r/{subreddit}] {title}"
                    if flair:
                        full_title = f"[{flair}] {title}"

                    results.append(make_item(
                        title=full_title,
                        url=display_url,
                        source=f"Reddit r/{subreddit}",
                        published_at=pub,
                        description=selftext,
                    ))
            except Exception:
                continue
    return results


def fetch_coindesk_analysis() -> list:
    """CoinDesk 마켓/분석 RSS"""
    results = []
    seen = set()
    rss_urls = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
        "https://www.coindesk.com/feed",
    ]
    for rss_url in rss_urls:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "xml")
        except Exception:
            continue
        for item in soup.find_all("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            desc_el = item.find("description")
            title = title_el.get_text(strip=True) if title_el else ""
            link = link_el.get_text(strip=True) if link_el else ""
            pub_raw = pub_el.get_text(strip=True) if pub_el else ""
            desc = BeautifulSoup(desc_el.get_text(strip=True) if desc_el else "", "html.parser").get_text()[:200]
            if not title or link in seen:
                continue
            pub_iso = parse_rss_datetime(pub_raw)
            if not is_recent(pub_iso, days=5):
                continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source="CoinDesk", published_at=pub_iso, description=desc))
        if results:
            break
    return results


# ── 필터링 함수 ──────────────────────────────
def filter_ta_news(news_list: list) -> list:
    """기술적 분석 관련 기사만 필터링"""
    filtered = []
    for item in news_list:
        combined = (item["title"] + " " + item.get("description", "")).lower()
        ta_hits = [kw for kw in TA_KEYWORDS if kw in combined]
        if ta_hits:
            item = dict(item)
            item["is_ta"] = True
            item["is_onchain"] = any(kw in combined for kw in ONCHAIN_KEYWORDS)
            oc_hits = [kw for kw in ONCHAIN_KEYWORDS if kw in combined]
            item["matched_keywords"] = (ta_hits + oc_hits)[:8]
            filtered.append(item)
    return filtered


def filter_onchain_news(news_list: list) -> list:
    """온체인 분석 관련 기사만 필터링"""
    filtered = []
    for item in news_list:
        combined = (item["title"] + " " + item.get("description", "")).lower()
        oc_hits = [kw for kw in ONCHAIN_KEYWORDS if kw in combined]
        if oc_hits:
            item = dict(item)
            item["is_onchain"] = True
            item["is_ta"] = any(kw in combined for kw in TA_KEYWORDS)
            ta_hits = [kw for kw in TA_KEYWORDS if kw in combined]
            item["matched_keywords"] = (oc_hits + ta_hits)[:8]
            filtered.append(item)
    return filtered


def filter_all_analysis(news_list: list) -> list:
    """TA 또는 온체인 관련 기사 모두 필터링"""
    filtered = []
    for item in news_list:
        combined = (item["title"] + " " + item.get("description", "")).lower()
        ta_hits = [kw for kw in TA_KEYWORDS if kw in combined]
        oc_hits = [kw for kw in ONCHAIN_KEYWORDS if kw in combined]
        if ta_hits or oc_hits:
            item = dict(item)
            item["is_ta"] = len(ta_hits) > 0
            item["is_onchain"] = len(oc_hits) > 0
            item["matched_keywords"] = (ta_hits + oc_hits)[:8]
            filtered.append(item)
    return filtered


# ── 세션 상태 초기화 ──────────────────────────
def init_session():
    for prefix in ("ta_", "oc_"):
        for key in ("news_data", "source_stats", "summary_quick", "summary_deep", "provider"):
            full_key = f"{prefix}{key}"
            if full_key not in st.session_state:
                st.session_state[full_key] = [] if key in ("news_data",) else ({} if key == "source_stats" else "")


init_session()


# ── 사이드바 ──────────────────────────────────
with st.sidebar:
    st.markdown("### ₿ 메뉴")
    mode = st.radio("선택", ["📊 기술적 분석 (TA)", "🔗 온체인 분석"], label_visibility="collapsed")
    is_ta_mode = mode == "📊 기술적 분석 (TA)"
    st.markdown("---")
    st.markdown("### ⚙️ 설정")

    use_ai = st.toggle("AI 요약 생성", value=True)
    if use_ai:
        ai_provider = st.selectbox("AI 제공자", ["Gemini 2.5 Pro", "GPT-4o-mini"])
    else:
        ai_provider = ""

    st.markdown("---")
    st.markdown("**수집 소스**")
    src_ct = st.checkbox("CoinTelegraph", value=True)
    src_amb = st.checkbox("AMBCrypto", value=True)
    src_glass = st.checkbox("Glassnode Insights", value=True)
    src_slate = st.checkbox("CryptoSlate Research", value=True)
    src_coinglass = st.checkbox("Coinglass", value=True)
    src_theblock = st.checkbox("The Block", value=True)
    src_coindesk = st.checkbox("CoinDesk", value=True)
    src_reddit = st.checkbox("Reddit (r/BitcoinMarkets)", value=True)

    st.markdown("---")
    label = "📊 기술적 분석 수집" if is_ta_mode else "🔗 온체인 분석 수집"
    run_btn = st.button(f"🚀 {label} 시작", type="primary", use_container_width=True)
    st.markdown("---")
    st.caption(f"KST {NOW_KST.strftime('%Y-%m-%d %H:%M')}")


# ── 수집 실행 ─────────────────────────────────
if run_btn:
    all_raw = []
    source_map = {}

    tasks = []
    if src_ct:
        tasks.append(("CoinTelegraph", fetch_cointelegraph_ta, []))
    if src_amb:
        tasks.append(("AMBCrypto", fetch_ambcrypto, []))
    if src_glass:
        tasks.append(("Glassnode", fetch_glassnode_insights, []))
    if src_slate:
        tasks.append(("CryptoSlate", fetch_cryptoslate_research, []))
    if src_coinglass:
        tasks.append(("Coinglass", fetch_coinglass_news, []))
    if src_theblock:
        tasks.append(("The Block", fetch_theblock_research, []))
    if src_coindesk:
        tasks.append(("CoinDesk", fetch_coindesk_analysis, []))
    if src_reddit:
        tasks.append(("Reddit", fetch_reddit_btcmarkets, []))

    prefix = "ta_" if is_ta_mode else "oc_"
    prompt_quick = PROMPT_TA_QUICK if is_ta_mode else PROMPT_OC_QUICK
    prompt_deep = PROMPT_TA_DEEP if is_ta_mode else PROMPT_OC_DEEP

    with st.status("뉴스 수집 중...", expanded=True) as status:
        for name, fn, args in tasks:
            st.write(f"📡 {name} 수집 중...")
            try:
                items = fn(*args)
                all_raw += items
                source_map[name] = len(items)
                st.write(f"  ✅ {name}: {len(items)}건 (원시)")
            except Exception as e:
                source_map[name] = 0
                st.write(f"  ⚠️ {name}: {e}")

        # 중복 제거 후 분석 유형 필터링
        all_raw = dedup(all_raw)

        if is_ta_mode:
            filtered_news = filter_ta_news(all_raw)
        else:
            filtered_news = filter_onchain_news(all_raw)

        # 필터링 후 소스별 통계 재집계
        filtered_source_map = {}
        for item in filtered_news:
            src = item["source"]
            filtered_source_map[src] = filtered_source_map.get(src, 0) + 1

        filtered_news.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        st.write(f"\n🔍 전체 수집: {len(all_raw)}건 → 필터링 후: **{len(filtered_news)}건**")

        st.session_state[f"{prefix}news_data"] = filtered_news
        st.session_state[f"{prefix}source_stats"] = filtered_source_map
        st.session_state[f"{prefix}summary_quick"] = ""
        st.session_state[f"{prefix}summary_deep"] = ""
        st.session_state[f"{prefix}provider"] = ""

        if use_ai and filtered_news:
            if ai_provider == "Gemini 2.5 Pro" and GEMINI_API_KEY:
                st.write("🤖 Gemini 2.5 Pro로 분석 생성 중...")
                q, d = summarize_gemini(filtered_news, GEMINI_API_KEY, prompt_quick, prompt_deep)
                st.session_state[f"{prefix}summary_quick"] = q
                st.session_state[f"{prefix}summary_deep"] = d
                st.session_state[f"{prefix}provider"] = "Gemini 2.5 Pro"
            elif ai_provider == "GPT-4o-mini" and OPENAI_API_KEY:
                st.write("🤖 GPT-4o-mini로 분석 생성 중...")
                q, d = summarize_openai(filtered_news, OPENAI_API_KEY, prompt_quick, prompt_deep)
                st.session_state[f"{prefix}summary_quick"] = q
                st.session_state[f"{prefix}summary_deep"] = d
                st.session_state[f"{prefix}provider"] = "GPT-4o-mini"
            else:
                st.write("⚠️ AI API 키가 없어 요약을 건너뜁니다.")
        elif use_ai and not filtered_news:
            st.write("⚠️ 필터링 후 기사가 없어 AI 요약을 건너뜁니다.")

        status.update(
            label=f"✅ 수집 완료 — 분석 기사 {len(filtered_news)}건 (전체 {len(all_raw)}건 중 필터링)",
            state="complete"
        )


# ── 현재 모드 데이터 ──────────────────────────
prefix = "ta_" if is_ta_mode else "oc_"
news_data = st.session_state[f"{prefix}news_data"]
source_stats = st.session_state[f"{prefix}source_stats"]
summary_quick = st.session_state[f"{prefix}summary_quick"]
summary_deep = st.session_state[f"{prefix}summary_deep"]
provider = st.session_state[f"{prefix}provider"]

# ── 헤더 ──────────────────────────────────────
if is_ta_mode:
    st.markdown(f"""
    <div class="main-header">
      <h1>₿ BTC 기술적 분석 리포트</h1>
      <div class="sub">차트 분석 · RSI · MACD · 지지/저항 · 패턴 분석 통합 수집 | {TODAY_STR} (KST)</div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class="main-header">
      <h1>₿ BTC 온체인 분석 리포트</h1>
      <div class="sub">MVRV · SOPR · 거래소 흐름 · 펀딩비 · 고래 동향 통합 수집 | {TODAY_STR} (KST)</div>
    </div>
    """, unsafe_allow_html=True)


# ── 결과 표시 ─────────────────────────────────
if not news_data:
    mode_name = "기술적 분석" if is_ta_mode else "온체인 분석"
    st.info(f"👈 사이드바에서 **{mode_name} 수집 시작** 버튼을 눌러주세요.")

    # 키워드 미리보기
    st.markdown("---")
    col_ta, col_oc = st.columns(2)
    with col_ta:
        st.markdown("**📊 기술적 분석 키워드 (예시)**")
        for kw in TA_KEYWORDS[:20]:
            st.markdown(f'<span class="keyword-chip">{kw}</span>', unsafe_allow_html=True)
    with col_oc:
        st.markdown("**🔗 온체인 분석 키워드 (예시)**")
        for kw in ONCHAIN_KEYWORDS[:20]:
            st.markdown(f'<span class="keyword-chip" style="color:#3b82f6;border-color:rgba(59,130,246,0.35);background:rgba(59,130,246,0.12)">{kw}</span>', unsafe_allow_html=True)
    st.stop()


# ── 소스별 통계 ───────────────────────────────
accent = "#f7931a" if is_ta_mode else "#3b82f6"
st.markdown('<div class="sec-title">📊 소스별 수집 현황</div>', unsafe_allow_html=True)

total_col, *src_cols = st.columns([1] + [1] * min(len(source_stats), 6))
with total_col:
    st.markdown(f"""
    <div style="background:#161b22;border:1px solid #21262d;border-top:3px solid {accent};
                border-radius:10px;padding:14px 10px;text-align:center">
      <div style="font-size:1.5rem;font-weight:700;color:{accent}">{len(news_data)}</div>
      <div style="font-size:.75rem;color:#8b949e;margin-top:4px">분석 기사</div>
    </div>""", unsafe_allow_html=True)

for col, (src, cnt) in zip(src_cols, list(source_stats.items())[:6]):
    color = src_color(src)
    with col:
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #21262d;border-top:3px solid {color};
                    border-radius:10px;padding:14px 10px;text-align:center">
          <div style="font-size:1.5rem;font-weight:700;color:{color}">{cnt}</div>
          <div style="font-size:.72rem;color:#8b949e;margin-top:4px;word-break:break-all">{src}</div>
        </div>""", unsafe_allow_html=True)

# TA vs 온체인 비율
n_ta = sum(1 for x in news_data if x.get("is_ta"))
n_oc = sum(1 for x in news_data if x.get("is_onchain"))
st.markdown(f"""
<div style="margin:12px 0 4px;padding:10px 14px;background:#161b22;border:1px solid #21262d;border-radius:8px;font-size:.82rem;color:#8b949e">
  📊 기술적 분석: <span style="color:#f7931a;font-weight:700">{n_ta}건</span>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  🔗 온체인 분석: <span style="color:#3b82f6;font-weight:700">{n_oc}건</span>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  중복 포함 (한 기사가 두 분류 해당 가능)
</div>
""", unsafe_allow_html=True)


# ── AI 요약 ───────────────────────────────────
if summary_quick or summary_deep:
    provider_label = f" <span style='font-size:.8rem;color:#8b949e'>by {provider}</span>" if provider else ""
    st.markdown(f'<div class="sec-title">🤖 AI 분석{provider_label}</div>', unsafe_allow_html=True)
    tab_quick, tab_deep = st.tabs(["⚡ Quick Summary", "🔬 Deep Dive"])
    with tab_quick:
        st.markdown(summary_quick or "_요약 없음_")
    with tab_deep:
        st.markdown(summary_deep or "_분석 없음_")


# ── 뉴스 목록 ─────────────────────────────────
st.markdown(f'<div class="sec-title">📋 분석 기사 목록 ({len(news_data)}건)</div>', unsafe_allow_html=True)

col_search, col_type, col_src = st.columns([3, 1, 1])
with col_search:
    search_q = st.text_input(
        "🔍 검색",
        placeholder="RSI, MACD, MVRV, support, funding rate...",
        label_visibility="collapsed",
    )
with col_type:
    type_filter = st.selectbox(
        "분석 유형",
        ["전체", "📊 TA만", "🔗 온체인만", "📊+🔗 둘 다"],
        label_visibility="collapsed",
    )
with col_src:
    all_sources = sorted(set(item["source"] for item in news_data))
    filter_src = st.selectbox("소스 필터", ["전체"] + all_sources, label_visibility="collapsed")

filtered = news_data

if search_q:
    q = search_q.lower()
    filtered = [n for n in filtered if q in n["title"].lower() or q in (n.get("description") or "").lower()]

if type_filter == "📊 TA만":
    filtered = [n for n in filtered if n.get("is_ta") and not n.get("is_onchain")]
elif type_filter == "🔗 온체인만":
    filtered = [n for n in filtered if n.get("is_onchain") and not n.get("is_ta")]
elif type_filter == "📊+🔗 둘 다":
    filtered = [n for n in filtered if n.get("is_ta") and n.get("is_onchain")]

if filter_src != "전체":
    filtered = [n for n in filtered if n["source"] == filter_src]

st.caption(f"{len(filtered)}건 표시 중")

for i, item in enumerate(filtered, 1):
    render_news_card(item, i)


# ── 푸터 ─────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;padding:24px 16px;color:#6e7681;font-size:.8rem;
            border-top:1px solid #21262d;margin-top:32px">
  데이터 출처: CoinTelegraph · AMBCrypto · Glassnode · CryptoSlate · Coinglass · The Block · CoinDesk · Reddit
  &nbsp;|&nbsp; 생성: {NOW_KST.strftime('%Y-%m-%d %H:%M')} KST
  <br>⚠️ 본 리포트는 정보 제공 목적이며 투자 조언이 아닙니다.
</div>
""", unsafe_allow_html=True)

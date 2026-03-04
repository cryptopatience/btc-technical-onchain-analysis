"""
BTC 기술적/온체인 분석 + Magnificent 7 주식 분석 리포트
모드: 📊 기술적 분석(TA) | 🔗 온체인 분석 | 🏆 M7 주식 분석
"""

import datetime
import os
import re
from email.utils import parsedate_to_datetime

import requests
import streamlit as st
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="BTC 분석 + M7 주식 리포트",
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
OPENAI_API_KEY  = get_secret("OPENAI_API_KEY")
GEMINI_API_KEY  = get_secret("GEMINI_API_KEY")
FINNHUB_API_KEY = get_secret("FINNHUB_API_KEY")
APP_PASSWORD    = get_secret("APP_PASSWORD") or "1234"

# ── 비밀번호 인증 ──────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if APP_PASSWORD and not st.session_state.authenticated:
    st.markdown("""
    <style>
    #MainMenu,header,footer{visibility:hidden}
    .lock-wrap{max-width:380px;margin:10vh auto 0;background:#161b22;border:1px solid #30363d;
               border-radius:20px;padding:48px 40px;text-align:center;box-shadow:0 24px 64px rgba(0,0,0,.6)}
    .lock-wrap h2{font-size:1.4rem;font-weight:700;color:#f0f6fc;margin-bottom:6px}
    .lock-wrap p{color:#8b949e;font-size:.88rem;margin-bottom:28px}
    </style>""", unsafe_allow_html=True)
    st.markdown(
        '<div class="lock-wrap"><div style="font-size:2.6rem">🔐</div>'
        '<h2>BTC 분석 + M7 주식 리포트</h2><p>접근하려면 비밀번호를 입력하세요</p></div>',
        unsafe_allow_html=True)
    pw = st.text_input("비밀번호", type="password", placeholder="••••", label_visibility="collapsed")
    _, c2, _ = st.columns([1, 2, 1])
    with c2:
        if st.button("잠금 해제", type="primary", use_container_width=True):
            if pw == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    st.stop()

# ── 공통 상수 ──────────────────────────────────
NOW_UTC      = datetime.datetime.utcnow()
NOW_KST      = NOW_UTC + datetime.timedelta(hours=9)
TODAY_STR    = NOW_KST.strftime("%Y-%m-%d")
YESTERDAY_STR = (NOW_KST - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

# ── M7 종목 정의 ────────────────────────────────
M7_STOCKS = {
    "AAPL":  {"name": "Apple",     "emoji": "🍎", "color": "#A8B0B8"},
    "MSFT":  {"name": "Microsoft", "emoji": "🪟", "color": "#00A4EF"},
    "GOOGL": {"name": "Alphabet",  "emoji": "🔍", "color": "#4285F4"},
    "AMZN":  {"name": "Amazon",    "emoji": "📦", "color": "#FF9900"},
    "META":  {"name": "Meta",      "emoji": "👥", "color": "#1877F2"},
    "TSLA":  {"name": "Tesla",     "emoji": "⚡", "color": "#CC0000"},
    "NVDA":  {"name": "Nvidia",    "emoji": "🎮", "color": "#76B900"},
}

# ── 소스 색상 ──────────────────────────────────
SOURCE_COLORS = {
    # BTC
    "cointelegraph": "#00d4aa", "ambcrypto": "#f59e0b",
    "glassnode": "#3b82f6", "cryptoslate": "#8b5cf6",
    "coinglass": "#ef4444", "the block": "#f97316",
    "reddit": "#ff4500", "coindesk": "#1a73e8",
    # M7
    "yahoo finance": "#720e9e", "seekingalpha": "#1DB954",
    "benzinga": "#0070f3", "marketwatch": "#40a829",
    "reuters": "#ff8000", "cnbc": "#005594",
    "barrons": "#c0392b", "finviz": "#2ecc71",
    "thestreet": "#e67e22", "investopedia": "#e74c3c",
    "motley fool": "#f39c12", "zacks": "#8e44ad",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── 키워드 ─────────────────────────────────────
TA_KEYWORDS = [
    "technical analysis","price analysis","chart analysis","price prediction",
    "rsi","macd","moving average","ema","sma","bollinger",
    "support","resistance","breakout","breakdown","trend",
    "fibonacci","fib","elliott wave","pattern","wedge","triangle",
    "bullish","bearish","rally","correction","reversal",
    "all-time high","ath","price target","key level",
    "overbought","oversold","momentum","volume","candlestick",
    "head and shoulders","double top","double bottom","flag","pennant",
    "bitcoin price","btc price","btc/usd","price outlook","market structure",
    "higher high","lower low","higher low","lower high",
]

ONCHAIN_KEYWORDS = [
    "on-chain","onchain","on chain",
    "mvrv","sopr","nupl","nvt","realized price",
    "exchange flow","exchange balance","exchange inflow","exchange outflow",
    "funding rate","open interest","liquidation","long/short",
    "whale","large holder","accumulation","distribution",
    "hash rate","hashrate","miner","mining",
    "stablecoin","usdt","usdc supply",
    "etf flow","etf inflow","etf outflow","spot etf",
    "netflow","urpd","arpd","cost basis",
    "hodl","lth","sth","long-term holder","short-term holder",
    "glassnode","intotheblock","santiment","coinglass",
    "network value","active address","transaction volume",
    "unrealized profit","unrealized loss",
    "dormancy","coin days destroyed","cdd",
    "perpetual","derivatives","basis","funding","liquidity",
]

M7_TA_KEYWORDS = [
    "technical analysis","price analysis","chart analysis","price target",
    "rsi","macd","moving average","ema","sma","bollinger",
    "support","resistance","breakout","breakdown","trend",
    "fibonacci","bullish","bearish","rally","correction","reversal",
    "overbought","oversold","momentum","volume","candlestick",
    "head and shoulders","double top","double bottom","flag","wedge",
    "buy signal","sell signal","outperform","underperform","upgrade","downgrade",
    "all-time high","52-week high","52-week low","key level","trading range",
    "cup and handle","ascending triangle","descending triangle",
]

M7_FUND_KEYWORDS = [
    "earnings","revenue","eps","profit","margin","guidance","forecast",
    "pe ratio","price-to-earnings","valuation","market cap","forward pe",
    "analyst","rating","target price","consensus","wall street",
    "beat","miss","surprise","estimate","outlook","full year",
    "cloud","ai","artificial intelligence","data center","advertising",
    "iphone","mac","services","azure","aws","gcp",
    "autonomous","ev","electric vehicle","fsd","cybertruck",
    "metaverse","vr","ar","quest","threads","instagram",
    "gpu","chip","semiconductor","h100","blackwell","cuda",
    "buyback","dividend","share repurchase","capex","free cash flow",
    "subscription","user growth","dau","mau","monthly active",
]

# ── CSS ────────────────────────────────────────
st.markdown("""
<style>
.main-header{background:linear-gradient(135deg,#0a0f1e 0%,#0d1b2a 50%,#1a1228 100%);
    border:1px solid #1e3a5f;border-radius:16px;padding:32px 28px 24px;
    text-align:center;margin-bottom:24px}
.main-header h1{font-size:2rem;font-weight:800;
    background:linear-gradient(90deg,#f7931a,#00d4aa,#3b82f6,#76B900);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;margin-bottom:8px}
.main-header .sub{color:#8892b0;font-size:.9rem}
.news-card{background:#161b22;border:1px solid #21262d;
    border-radius:10px;padding:14px 16px;margin-bottom:8px}
.news-card:hover{border-color:#f7931a}
.news-title{font-size:.93rem;font-weight:500;color:#e6edf3;line-height:1.5;margin-bottom:5px}
.news-title a{color:#e6edf3;text-decoration:none}
.news-title a:hover{color:#f7931a}
.news-desc{font-size:.8rem;color:#8b949e;line-height:1.5;margin-bottom:7px}
.news-meta{display:flex;flex-wrap:wrap;gap:5px;align-items:center}
.src-badge{font-size:.7rem;border:1px solid;border-radius:4px;padding:1px 7px;font-weight:600}
.tag-badge{font-size:.68rem;border-radius:4px;padding:1px 6px;font-weight:700;
    background:rgba(247,147,26,.15);color:#f7931a;border:1px solid rgba(247,147,26,.3)}
.tag-onchain{background:rgba(59,130,246,.15);color:#3b82f6;border:1px solid rgba(59,130,246,.3)}
.tag-fund{background:rgba(118,185,0,.15);color:#76B900;border:1px solid rgba(118,185,0,.3)}
.ticker-badge{font-size:.7rem;border-radius:4px;padding:1px 7px;font-weight:800;border:1px solid}
.time-tag{font-size:.72rem;color:#6e7681}
.sec-title{font-size:1rem;font-weight:700;color:#f0f6fc;
    margin:24px 0 12px;padding-left:10px;border-left:4px solid #f7931a}
.keyword-chip{display:inline-block;font-size:.65rem;padding:1px 5px;
    background:rgba(0,212,170,.12);color:#00d4aa;
    border:1px solid rgba(0,212,170,.25);border-radius:3px;margin:1px 2px}
.m7-card{background:#0d1117;border:1px solid #21262d;border-radius:8px;
    padding:10px 14px;margin-bottom:6px;display:flex;align-items:center;gap:8px}
[data-baseweb="tag"]{background:transparent !important;border:none !important;padding:0 4px 0 0 !important}
[data-baseweb="tag"] span[role="presentation"]{display:none !important}
[data-baseweb="tag"] svg{display:none !important}
[data-baseweb="tag"] button{display:none !important}
[data-baseweb="tag"] span:first-child{color:#000000 !important;font-size:.85rem !important}
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
    return re.sub(r"\s+", " ", BeautifulSoup(text, "html.parser").get_text(separator=" ")).strip()

def make_item(title, url="", source="", published_at="", description="", ticker=""):
    return {
        "title": re.sub(r"\s+", " ", title).strip(),
        "url": url, "source": source,
        "published_at": published_at,
        "description": _strip_html(description or ""),
        "ticker": ticker,
        "matched_keywords": [],
        "is_ta": False, "is_onchain": False, "is_fund": False,
    }

def is_recent(pub: str, days: int = 3) -> bool:
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

def parse_rss_dt(raw: str) -> str:
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return raw[:19]

def build_news_text(news_list: list, limit: int = 60) -> str:
    lines = []
    for item in news_list[:limit]:
        ticker = f"[{item['ticker']}] " if item.get("ticker") else ""
        line = f"- {ticker}[{item['source']}] {item['title']}"
        if item.get("description"):
            line += f"\n  {item['description'][:150]}"
        lines.append(line)
    return "\n".join(lines)


# ── 뉴스 카드 렌더링 ───────────────────────────
def render_news_card(item: dict, idx: int) -> None:
    import html as _html
    title   = _html.escape(item.get("title","") or "")
    url     = item.get("url","")
    source  = item.get("source","")
    pub     = item.get("published_at","")
    desc    = _html.escape((item.get("description","") or "").strip())
    color   = src_color(source)
    kst     = utc_to_kst(pub)
    ticker  = item.get("ticker","")
    matched = item.get("matched_keywords",[])

    title_html = f'<a href="{url}" target="_blank">{title}</a>' if url else title
    desc_html  = f'<div class="news-desc">{desc[:200]}</div>' if desc and desc != title else ""
    time_html  = f'<span class="time-tag">🕐 KST {kst}</span>' if kst else ""

    type_badges = ""
    if item.get("is_ta"):
        type_badges += '<span class="tag-badge">📊 TA</span> '
    if item.get("is_onchain"):
        type_badges += '<span class="tag-badge tag-onchain">🔗 온체인</span> '
    if item.get("is_fund"):
        type_badges += '<span class="tag-badge tag-fund">💹 펀더멘털</span> '

    ticker_html = ""
    if ticker and ticker in M7_STOCKS:
        tc = M7_STOCKS[ticker]["color"]
        em = M7_STOCKS[ticker]["emoji"]
        ticker_html = f'<span class="ticker-badge" style="background:{tc}22;color:{tc};border-color:{tc}55">{em} {ticker}</span> '

    kw_chips = "".join(f'<span class="keyword-chip">{_html.escape(kw)}</span>' for kw in matched[:4])

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
            {ticker_html}
            <span class="src-badge" style="background:{color}22;color:{color};border-color:{color}55">{source}</span>
            {type_badges}{time_html}
          </div>
          {f'<div style="margin-top:5px">{kw_chips}</div>' if kw_chips else ""}
        </div>
      </div>
    </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════
# ── AI 요약 ────────────────────────────────────
# ═══════════════════════════════════════════════
PROMPT_TA_QUICK = """다음은 {date} (KST) 기준 비트코인 기술적 분석 기사들입니다.
{content}
위 내용만을 바탕으로 한국어 Quick Summary를 작성해주세요.
1. **현재 BTC 차트 핵심 구조** (주요 지지/저항 레벨)
2. **주요 기술적 지표 현황** (RSI, MACD, 이평선 등)
3. **단기 시나리오** (강세/약세 각 1~2문장)
4. **한줄 차트 요약**"""

PROMPT_TA_DEEP = """다음은 {date} (KST) 기준 비트코인 기술적 분석 기사들입니다.
{content}
위 내용만을 바탕으로 한국어 Deep Dive 기술적 분석을 작성해주세요.
1. **현재 가격 구조 분석** (지지·저항 상세)
2. **오실레이터·모멘텀 지표 분석** (RSI, MACD 등)
3. **이동평균선 및 추세 분석**
4. **주요 패턴 및 차트 형태**
5. **단기/중기 가격 전망 및 핵심 레벨**"""

PROMPT_OC_QUICK = """다음은 {date} (KST) 기준 비트코인 온체인 분석 기사들입니다.
{content}
위 내용만을 바탕으로 한국어 Quick Summary를 작성해주세요.
1. **핵심 온체인 시그널** (3~5개)
2. **투자자 행동 분석** (매집/분산, 고래 움직임)
3. **파생상품 시장 현황** (펀딩비, OI, 청산)
4. **한줄 온체인 요약**"""

PROMPT_OC_DEEP = """다음은 {date} (KST) 기준 비트코인 온체인 분석 기사들입니다.
{content}
위 내용만을 바탕으로 한국어 Deep Dive 온체인 분석을 작성해주세요.
1. **밸류에이션 지표 분석** (MVRV, SOPR, Realized Price 등)
2. **홀더 행동 분석** (LTH vs STH)
3. **거래소 흐름 분석**
4. **파생상품·레버리지 현황**
5. **매크로 온체인 전망**"""

PROMPT_M7_QUICK = """다음은 {date} (KST) 기준 Magnificent 7 (AAPL·MSFT·GOOGL·AMZN·META·TSLA·NVDA) 관련 기사들입니다.
{content}
위 내용만을 바탕으로 한국어 Quick Summary를 작성해주세요.
1. **M7 전체 시장 분위기** (기술주 섹터 흐름 1~2문장)
2. **종목별 핵심 이슈** (언급된 종목 각 1문장, 티커 명시)
3. **기술적 주목 레벨** (주요 지지/저항, 돌파 여부)
4. **단기 투자 시사점** (매수·매도 심리, 섹터 로테이션)
5. **한줄 M7 요약**
트레이더·투자자 관점에서 실용적으로 작성해주세요."""

PROMPT_M7_DEEP = """다음은 {date} (KST) 기준 Magnificent 7 관련 기사들입니다.
{content}
위 내용만을 바탕으로 한국어 Deep Dive 분석을 작성해주세요.
1. **기술적 분석 종목별 현황**
   - 각 종목(AAPL·MSFT·GOOGL·AMZN·META·TSLA·NVDA) 차트 구조, 지지/저항, 모멘텀
2. **펀더멘털 분석**
   - 실적, 가이던스, AI·클라우드·EV 사업 동향
3. **애널리스트 의견 종합**
   - 목표주가, 등급 변경, 월가 컨센서스
4. **섹터 및 매크로 연관성**
   - 금리·달러·나스닥 상관관계
5. **종목별 리스크 및 기회 요인**
전문 리서치 리포트 수준으로 상세히 작성해주세요."""


def summarize_gemini(news_list, api_key, prompt_quick, prompt_deep):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        st.error("google-genai 패키지가 없습니다.")
        return "", ""
    client = genai.Client(api_key=api_key)
    content = build_news_text(news_list, 60)
    def _ex(r):
        if r.text is not None: return r.text
        try: return r.candidates[0].content.parts[0].text or ""
        except: return ""
    q, d = "", ""
    try:
        q = _ex(client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt_quick.format(date=TODAY_STR, content=content),
            config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=8000)))
    except Exception as e:
        st.warning(f"Gemini Quick 오류: {e}")
    try:
        d = _ex(client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt_deep.format(date=TODAY_STR, content=content),
            config=types.GenerateContentConfig(temperature=0.35, max_output_tokens=16000)))
    except Exception as e:
        st.warning(f"Gemini Deep 오류: {e}")
    return q, d


def summarize_openai(news_list, api_key, prompt_quick, prompt_deep):
    try:
        from openai import OpenAI
    except ImportError:
        st.error("openai 패키지가 없습니다.")
        return "", ""
    client = OpenAI(api_key=api_key)
    content = build_news_text(news_list, 60)
    q, d = "", ""
    try:
        q = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt_quick.format(date=TODAY_STR,content=content)}],
            max_tokens=1500, temperature=0.4).choices[0].message.content or ""
    except Exception as e:
        st.warning(f"GPT Quick 오류: {e}")
    try:
        d = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt_deep.format(date=TODAY_STR,content=content)}],
            max_tokens=3000, temperature=0.35).choices[0].message.content or ""
    except Exception as e:
        st.warning(f"GPT Deep 오류: {e}")
    return q, d


# ═══════════════════════════════════════════════
# ── BTC 스크래퍼 ───────────────────────────────
# ═══════════════════════════════════════════════
def fetch_cointelegraph_ta() -> list:
    results, seen = [], set()
    for rss_url in [
        "https://cointelegraph.com/rss/tag/bitcoin-price",
        "https://cointelegraph.com/rss/tag/technical-analysis",
        "https://cointelegraph.com/rss/tag/bitcoin",
    ]:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
        except: continue
        for item in soup.find_all("item"):
            te = item.find("title"); le = item.find("link")
            pe = item.find("pubDate"); de = item.find("description")
            title = te.get_text(strip=True) if te else ""
            link  = le.get_text(strip=True) if le else ""
            pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
            desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
            if not title or link in seen: continue
            if not is_recent(pub, 5): continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source="CoinTelegraph", published_at=pub, description=desc))
    return results

def fetch_ambcrypto() -> list:
    results, seen = [], set()
    for rss_url in ["https://ambcrypto.com/feed/", "https://ambcrypto.com/category/bitcoin/feed/"]:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
        except: continue
        for item in soup.find_all("item"):
            te = item.find("title"); le = item.find("link")
            pe = item.find("pubDate"); de = item.find("description")
            title = te.get_text(strip=True) if te else ""
            link  = le.get_text(strip=True) if le else ""
            pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
            desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
            if not title or link in seen: continue
            if not is_recent(pub, 5): continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source="AMBCrypto", published_at=pub, description=desc))
    return results

def fetch_glassnode_insights() -> list:
    results, seen = [], set()
    for rss_url in ["https://insights.glassnode.com/rss/", "https://insights.glassnode.com/feed/"]:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            items = soup.find_all("item") or soup.find_all("entry")
            if not items: continue
            for item in items:
                te = item.find("title"); le = item.find("link")
                pe = item.find("pubDate") or item.find("published")
                de = item.find("description") or item.find("summary")
                title = te.get_text(strip=True) if te else ""
                link  = (le.get("href") or le.get_text(strip=True)) if le else ""
                pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
                desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
                if not title or link in seen: continue
                seen.add(link)
                results.append(make_item(title=title, url=link, source="Glassnode", published_at=pub, description=desc))
            if results: break
        except: continue
    if not results:
        try:
            r = requests.get("https://insights.glassnode.com/", headers=HEADERS, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    full_url = href if href.startswith("http") else f"https://insights.glassnode.com{href}"
                    if full_url in seen or "insights.glassnode.com" not in full_url: continue
                    title = a.get_text(strip=True)
                    if not title or len(title) < 15: continue
                    seen.add(full_url)
                    results.append(make_item(title=title, url=full_url, source="Glassnode", published_at=""))
        except: pass
    return results

def fetch_cryptoslate_research() -> list:
    results, seen = [], set()
    for rss_url in [
        "https://cryptoslate.com/feed/",
        "https://cryptoslate.com/category/research/feed/",
        "https://cryptoslate.com/category/bitcoin/feed/",
    ]:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
        except: continue
        for item in soup.find_all("item"):
            te = item.find("title"); le = item.find("link")
            pe = item.find("pubDate"); de = item.find("description")
            title = te.get_text(strip=True) if te else ""
            link  = le.get_text(strip=True) if le else ""
            pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
            desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
            if not title or link in seen: continue
            if not is_recent(pub, 5): continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source="CryptoSlate", published_at=pub, description=desc))
    return results

def fetch_coinglass_news() -> list:
    results, seen = [], set()
    try:
        r = requests.get("https://www.coinglass.com/blog", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not any(x in href for x in ["/blog/", "/news/", "/analysis/"]): continue
                full_url = href if href.startswith("http") else f"https://www.coinglass.com{href}"
                if full_url in seen: continue
                title = a.get_text(strip=True)
                if not title or len(title) < 15: continue
                seen.add(full_url)
                results.append(make_item(title=title, url=full_url, source="Coinglass", published_at=""))
    except: pass
    return results

def fetch_theblock_research() -> list:
    results, seen = [], set()
    for rss_url in ["https://www.theblock.co/rss.xml", "https://www.theblock.co/feeds/rss.xml"]:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
        except: continue
        for item in soup.find_all("item") or soup.find_all("entry"):
            te = item.find("title"); le = item.find("link")
            pe = item.find("pubDate") or item.find("published")
            de = item.find("description") or item.find("summary")
            title = te.get_text(strip=True) if te else ""
            link  = le.get_text(strip=True) if le else ""
            pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
            desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
            if not title or link in seen: continue
            if not is_recent(pub, 5): continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source="The Block", published_at=pub, description=desc))
        if results: break
    return results

def fetch_reddit_btcmarkets() -> list:
    results, seen = [], set()
    rh = {**HEADERS, "Accept": "application/json"}
    for sub in ["BitcoinMarkets", "CryptoCurrency"]:
        for sort in ["hot", "top"]:
            try:
                r = requests.get(f"https://www.reddit.com/r/{sub}/{sort}.json",
                    headers=rh, params={"limit": 25, "t": "day"}, timeout=15)
                if r.status_code != 200: continue
                for post in r.json().get("data",{}).get("children",[]):
                    p = post.get("data",{})
                    title = p.get("title","")
                    permalink = "https://www.reddit.com" + p.get("permalink","")
                    created_utc = p.get("created_utc", 0)
                    selftext = p.get("selftext","")[:200]
                    flair = p.get("link_flair_text","")
                    score = p.get("score",0)
                    if not title or permalink in seen or score < 5: continue
                    pub = datetime.datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%dT%H:%M:%SZ") if created_utc else ""
                    if pub and not is_recent(pub, 3): continue
                    seen.add(permalink)
                    full_title = f"[{flair}] {title}" if flair else f"[r/{sub}] {title}"
                    results.append(make_item(title=full_title, url=permalink,
                        source=f"Reddit r/{sub}", published_at=pub, description=selftext))
            except: continue
    return results

def fetch_coindesk_analysis() -> list:
    results, seen = [], set()
    for rss_url in [
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
        "https://www.coindesk.com/feed",
    ]:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
        except: continue
        for item in soup.find_all("item"):
            te = item.find("title"); le = item.find("link")
            pe = item.find("pubDate"); de = item.find("description")
            title = te.get_text(strip=True) if te else ""
            link  = le.get_text(strip=True) if le else ""
            pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
            desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
            if not title or link in seen: continue
            if not is_recent(pub, 5): continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source="CoinDesk", published_at=pub, description=desc))
        if results: break
    return results


# ═══════════════════════════════════════════════
# ── M7 스크래퍼 ────────────────────────────────
# ═══════════════════════════════════════════════
def _detect_ticker(text: str) -> str:
    """텍스트에서 M7 티커 감지"""
    t = text.upper()
    for ticker, info in M7_STOCKS.items():
        if ticker in t or info["name"].upper() in t:
            return ticker
    return ""

def fetch_yahoo_finance_m7(tickers: list) -> list:
    """Yahoo Finance RSS - 종목별 뉴스"""
    results, seen = [], set()
    for ticker in tickers:
        try:
            r = requests.get(
                f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
                headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            for item in soup.find_all("item"):
                te = item.find("title"); le = item.find("link")
                pe = item.find("pubDate"); de = item.find("description")
                title = te.get_text(strip=True) if te else ""
                link  = le.get_text(strip=True) if le else ""
                pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
                desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
                if not title or link in seen: continue
                if not is_recent(pub, 5): continue
                seen.add(link)
                results.append(make_item(title=title, url=link, source="Yahoo Finance",
                    published_at=pub, description=desc, ticker=ticker))
        except: continue
    return results

def fetch_benzinga_m7(tickers: list) -> list:
    """Benzinga RSS - M7 종목 뉴스"""
    results, seen = [], set()
    for ticker in tickers:
        try:
            r = requests.get(
                f"https://www.benzinga.com/stock/{ticker.lower()}/feed",
                headers=HEADERS, timeout=15)
            if r.status_code != 200:
                r = requests.get(
                    f"https://feeds.benzinga.com/benzinga/{ticker.lower()}",
                    headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            for item in soup.find_all("item"):
                te = item.find("title"); le = item.find("link")
                pe = item.find("pubDate"); de = item.find("description")
                title = te.get_text(strip=True) if te else ""
                link  = le.get_text(strip=True) if le else ""
                pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
                desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
                if not title or link in seen: continue
                if not is_recent(pub, 5): continue
                seen.add(link)
                results.append(make_item(title=title, url=link, source="Benzinga",
                    published_at=pub, description=desc, ticker=ticker))
        except: continue
    return results

def fetch_marketwatch_m7() -> list:
    """MarketWatch RSS - 기술주 섹터 뉴스"""
    results, seen = [], set()
    rss_urls = [
        "http://feeds.marketwatch.com/marketwatch/topstories/",
        "http://feeds.marketwatch.com/marketwatch/technology/",
        "http://feeds.marketwatch.com/marketwatch/marketpulse/",
    ]
    for rss_url in rss_urls:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            for item in soup.find_all("item"):
                te = item.find("title"); le = item.find("link")
                pe = item.find("pubDate"); de = item.find("description")
                title = te.get_text(strip=True) if te else ""
                link  = le.get_text(strip=True) if le else ""
                pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
                desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
                if not title or link in seen: continue
                if not is_recent(pub, 5): continue
                # M7 관련 기사만
                combined = (title + " " + desc).upper()
                ticker = _detect_ticker(combined)
                if not ticker: continue
                seen.add(link)
                results.append(make_item(title=title, url=link, source="MarketWatch",
                    published_at=pub, description=desc, ticker=ticker))
        except: continue
    return results

def fetch_cnbc_m7() -> list:
    """CNBC RSS - M7 관련 뉴스"""
    results, seen = [], set()
    rss_urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=120000000",
        "https://www.cnbc.com/id/15839135/device/rss/rss.html",  # tech
    ]
    for rss_url in rss_urls:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            for item in soup.find_all("item"):
                te = item.find("title"); le = item.find("link")
                pe = item.find("pubDate"); de = item.find("description")
                title = te.get_text(strip=True) if te else ""
                link  = le.get_text(strip=True) if le else ""
                pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
                desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
                if not title or link in seen: continue
                if not is_recent(pub, 5): continue
                combined = (title + " " + desc).upper()
                ticker = _detect_ticker(combined)
                if not ticker: continue
                seen.add(link)
                results.append(make_item(title=title, url=link, source="CNBC",
                    published_at=pub, description=desc, ticker=ticker))
        except: continue
    return results

def fetch_seekingalpha_m7(tickers: list) -> list:
    """Seeking Alpha RSS - 종목 분석 기사"""
    results, seen = [], set()
    for ticker in tickers:
        try:
            r = requests.get(
                f"https://seekingalpha.com/api/sa/combined/{ticker}.xml",
                headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            for item in soup.find_all("item"):
                te = item.find("title"); le = item.find("link")
                pe = item.find("pubDate"); de = item.find("description")
                title = te.get_text(strip=True) if te else ""
                link  = le.get_text(strip=True) if le else ""
                pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
                desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
                if not title or link in seen: continue
                if not is_recent(pub, 5): continue
                seen.add(link)
                results.append(make_item(title=title, url=link, source="SeekingAlpha",
                    published_at=pub, description=desc, ticker=ticker))
        except: continue
    return results

def fetch_reddit_stocks_m7() -> list:
    """Reddit r/stocks r/investing - M7 관련 포스트"""
    results, seen = [], set()
    rh = {**HEADERS, "Accept": "application/json"}
    for sub in ["stocks", "investing", "wallstreetbets"]:
        try:
            r = requests.get(f"https://www.reddit.com/r/{sub}/hot.json",
                headers=rh, params={"limit": 30}, timeout=15)
            if r.status_code != 200: continue
            for post in r.json().get("data",{}).get("children",[]):
                p = post.get("data",{})
                title = p.get("title","")
                permalink = "https://www.reddit.com" + p.get("permalink","")
                created_utc = p.get("created_utc",0)
                selftext = p.get("selftext","")[:200]
                score = p.get("score",0)
                if not title or permalink in seen or score < 20: continue
                combined = (title + " " + selftext).upper()
                ticker = _detect_ticker(combined)
                if not ticker: continue
                pub = datetime.datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%dT%H:%M:%SZ") if created_utc else ""
                if pub and not is_recent(pub, 3): continue
                seen.add(permalink)
                results.append(make_item(title=f"[r/{sub}] {title}", url=permalink,
                    source=f"Reddit r/{sub}", published_at=pub, description=selftext, ticker=ticker))
        except: continue
    return results

def fetch_finnhub_m7(api_key: str, tickers: list) -> list:
    """Finnhub API - M7 종목 뉴스"""
    if not api_key:
        return []
    results, seen = [], set()
    for ticker in tickers:
        try:
            r = requests.get("https://finnhub.io/api/v1/company-news",
                params={"symbol": ticker, "from": YESTERDAY_STR, "to": TODAY_STR, "token": api_key},
                headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            for item in r.json()[:15]:
                try:
                    dt  = datetime.datetime.utcfromtimestamp(item.get("datetime",0))
                    pub = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    url = item.get("url","")
                    title = item.get("headline","")
                    if not title or url in seen: continue
                    seen.add(url)
                    results.append(make_item(title=title, url=url,
                        source=item.get("source","Finnhub"), published_at=pub,
                        description=item.get("summary","")[:200], ticker=ticker))
                except: continue
        except: continue
    return results


# ═══════════════════════════════════════════════
# ── 필터링 ─────────────────────────────────────
# ═══════════════════════════════════════════════
def _tag(item, kws_list):
    combined = (item["title"] + " " + item.get("description","")).lower()
    hits = [kw for kw in kws_list if kw in combined]
    return hits

def filter_ta_news(news_list):
    out = []
    for item in news_list:
        hits = _tag(item, TA_KEYWORDS)
        if hits:
            item = dict(item); oc = _tag(item, ONCHAIN_KEYWORDS)
            item["is_ta"]=True; item["is_onchain"]=bool(oc)
            item["matched_keywords"]=(hits+oc)[:8]; out.append(item)
    return out

def filter_onchain_news(news_list):
    out = []
    for item in news_list:
        hits = _tag(item, ONCHAIN_KEYWORDS)
        if hits:
            item = dict(item); ta = _tag(item, TA_KEYWORDS)
            item["is_onchain"]=True; item["is_ta"]=bool(ta)
            item["matched_keywords"]=(hits+ta)[:8]; out.append(item)
    return out

def filter_m7_news(news_list, selected_tickers):
    """M7 뉴스 필터링 - TA 또는 펀더멘털 키워드 포함"""
    out = []
    for item in news_list:
        # 선택된 티커만
        if item.get("ticker") and item["ticker"] not in selected_tickers:
            continue
        # 티커 없는 건 제목/설명에서 감지
        if not item.get("ticker"):
            combined_upper = (item["title"] + " " + item.get("description","")).upper()
            ticker = _detect_ticker(combined_upper)
            if not ticker or ticker not in selected_tickers:
                continue
            item = dict(item); item["ticker"] = ticker

        ta_hits   = _tag(item, M7_TA_KEYWORDS)
        fund_hits = _tag(item, M7_FUND_KEYWORDS)
        if ta_hits or fund_hits:
            item = dict(item)
            item["is_ta"]   = bool(ta_hits)
            item["is_fund"] = bool(fund_hits)
            item["matched_keywords"] = (ta_hits + fund_hits)[:8]
            out.append(item)
    return out


# ── 세션 상태 초기화 ───────────────────────────
def init_session():
    for prefix in ("ta_", "oc_", "m7_"):
        for key in ("news_data","source_stats","summary_quick","summary_deep","provider"):
            fk = f"{prefix}{key}"
            if fk not in st.session_state:
                st.session_state[fk] = ([] if key=="news_data" else ({} if key=="source_stats" else ""))

init_session()

for _k, _v in [("nav_mode", "ta"), ("btc_ver", 0), ("m7_ver", 0)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _on_btc():
    key = f"btc_{st.session_state.btc_ver}"
    val = st.session_state.get(key)
    st.session_state.nav_mode = "ta" if val == "기술적 분석" else "oc"
    st.session_state.m7_ver += 1   # m7 라디오 강제 초기화


def _on_m7():
    st.session_state.nav_mode = "m7"
    st.session_state.btc_ver += 1  # btc 라디오 강제 초기화


# ═══════════════════════════════════════════════
# ── 사이드바 ────────────────────────────────────
# ═══════════════════════════════════════════════
with st.sidebar:
    _ls = "font-size:.72rem;font-weight:700;color:#6e7681;letter-spacing:.08em;text-transform:uppercase;"
    st.markdown(f'<div style="{_ls}padding:4px 0 2px">BTC</div>', unsafe_allow_html=True)

    _btc_key = f"btc_{st.session_state.btc_ver}"
    _btc_idx = {"ta": 0, "oc": 1}.get(st.session_state.nav_mode, None)
    st.radio("btc_nav", ["기술적 분석", "온체인 분석"],
             index=_btc_idx, label_visibility="collapsed",
             key=_btc_key, on_change=_on_btc)

    st.markdown(f'<div style="{_ls}padding:12px 0 2px;border-top:1px solid #30363d;margin-top:6px">미국주식</div>', unsafe_allow_html=True)

    _m7_key = f"m7_{st.session_state.m7_ver}"
    _m7_idx = 0 if st.session_state.nav_mode == "m7" else None
    st.radio("m7_nav", ["기술적 분석"],
             index=_m7_idx, label_visibility="collapsed",
             key=_m7_key, on_change=_on_m7)

    is_ta = st.session_state.nav_mode == "ta"
    is_oc = st.session_state.nav_mode == "oc"
    is_m7 = st.session_state.nav_mode == "m7"
    st.markdown("---")
    st.markdown("### ⚙️ 설정")

    use_ai = st.toggle("AI 요약 생성", value=True)
    if use_ai:
        ai_opts = ["Gemini 2.5 Pro", "GPT-4o-mini"]
        ai_providers = st.multiselect("AI 제공자", ai_opts, default=ai_opts)
    else:
        ai_providers = []

    st.markdown("---")

    # ── BTC 소스 (TA / 온체인 공통) ──────────────
    if is_ta or is_oc:
        st.markdown("**수집 소스 (BTC)**")
        src_ct      = st.checkbox("CoinTelegraph",      value=True)
        src_amb     = st.checkbox("AMBCrypto",          value=True)
        src_glass   = st.checkbox("Glassnode Insights", value=True)
        src_slate   = st.checkbox("CryptoSlate",        value=True)
        src_cg      = st.checkbox("Coinglass",          value=True)
        src_tb      = st.checkbox("The Block",          value=True)
        src_cd      = st.checkbox("CoinDesk",           value=True)
        src_reddit  = st.checkbox("Reddit r/BitcoinMarkets", value=True)
        label = "📊 기술적 분석 수집" if is_ta else "🔗 온체인 분석 수집"

    # ── M7 전용 설정 ─────────────────────────────
    if is_m7:
        st.markdown("**종목 선택**")
        selected_tickers = []
        cols = st.columns(2)
        for i, (ticker, info) in enumerate(M7_STOCKS.items()):
            with cols[i % 2]:
                if st.checkbox(f"{info['emoji']} {ticker}", value=True, key=f"m7_{ticker}"):
                    selected_tickers.append(ticker)

        st.markdown("---")
        st.markdown("**수집 소스 (M7)**")
        src_yahoo    = st.checkbox("Yahoo Finance",   value=True)
        src_benzinga = st.checkbox("Benzinga",        value=True)
        src_mw       = st.checkbox("MarketWatch",     value=True)
        src_cnbc_m7  = st.checkbox("CNBC",            value=True)
        src_sa       = st.checkbox("Seeking Alpha",   value=True)
        src_fh_m7    = st.checkbox("Finnhub API",     value=bool(FINNHUB_API_KEY))
        src_reddit_s = st.checkbox("Reddit r/stocks", value=True)
        label = "🏆 M7 주식 뉴스 수집"

    st.markdown("---")
    run_btn = st.button(f"🚀 {label} 시작", type="primary", use_container_width=True)
    st.markdown("---")
    st.caption(f"KST {NOW_KST.strftime('%Y-%m-%d %H:%M')}")


# ═══════════════════════════════════════════════
# ── 수집 실행 ───────────────────────────────────
# ═══════════════════════════════════════════════
if run_btn:
    all_raw, source_map = [], {}

    if is_ta or is_oc:
        tasks = []
        if src_ct:    tasks.append(("CoinTelegraph",      fetch_cointelegraph_ta,    []))
        if src_amb:   tasks.append(("AMBCrypto",           fetch_ambcrypto,           []))
        if src_glass: tasks.append(("Glassnode",           fetch_glassnode_insights,  []))
        if src_slate: tasks.append(("CryptoSlate",         fetch_cryptoslate_research,[]))
        if src_cg:    tasks.append(("Coinglass",           fetch_coinglass_news,      []))
        if src_tb:    tasks.append(("The Block",           fetch_theblock_research,   []))
        if src_cd:    tasks.append(("CoinDesk",            fetch_coindesk_analysis,   []))
        if src_reddit:tasks.append(("Reddit",              fetch_reddit_btcmarkets,   []))
        prefix = "ta_" if is_ta else "oc_"
        pq = PROMPT_TA_QUICK if is_ta else PROMPT_OC_QUICK
        pd_ = PROMPT_TA_DEEP  if is_ta else PROMPT_OC_DEEP

    else:  # M7
        tasks = []
        if src_yahoo:    tasks.append(("Yahoo Finance",  fetch_yahoo_finance_m7,  [selected_tickers]))
        if src_benzinga: tasks.append(("Benzinga",       fetch_benzinga_m7,       [selected_tickers]))
        if src_mw:       tasks.append(("MarketWatch",    fetch_marketwatch_m7,    []))
        if src_cnbc_m7:  tasks.append(("CNBC",           fetch_cnbc_m7,           []))
        if src_sa:       tasks.append(("SeekingAlpha",   fetch_seekingalpha_m7,   [selected_tickers]))
        if src_fh_m7 and FINNHUB_API_KEY:
                         tasks.append(("Finnhub",        fetch_finnhub_m7,        [FINNHUB_API_KEY, selected_tickers]))
        if src_reddit_s: tasks.append(("Reddit r/stocks",fetch_reddit_stocks_m7,  []))
        prefix = "m7_"
        pq  = PROMPT_M7_QUICK
        pd_ = PROMPT_M7_DEEP

    with st.status("뉴스 수집 중...", expanded=True) as status:
        for name, fn, args in tasks:
            st.write(f"📡 {name} 수집 중...")
            try:
                items = fn(*args)
                all_raw += items
                source_map[name] = len(items)
                st.write(f"  ✅ {name}: {len(items)}건")
            except Exception as e:
                source_map[name] = 0
                st.write(f"  ⚠️ {name}: {e}")

        all_raw = dedup(all_raw)

        if is_ta:
            filtered = filter_ta_news(all_raw)
        elif is_oc:
            filtered = filter_onchain_news(all_raw)
        else:
            filtered = filter_m7_news(all_raw, selected_tickers)

        fsrc = {}
        for item in filtered:
            s = item["source"]; fsrc[s] = fsrc.get(s,0)+1
        filtered.sort(key=lambda x: x.get("published_at",""), reverse=True)

        st.write(f"\n🔍 전체: {len(all_raw)}건 → 필터링 후: **{len(filtered)}건**")

        st.session_state[f"{prefix}news_data"]     = filtered
        st.session_state[f"{prefix}source_stats"]  = fsrc
        st.session_state[f"{prefix}summary_quick"] = ""
        st.session_state[f"{prefix}summary_deep"]  = ""
        st.session_state[f"{prefix}provider"]      = ""

        if use_ai and filtered and ai_providers:
            all_quick, all_deep, used = [], [], []
            if "Gemini 2.5 Pro" in ai_providers and GEMINI_API_KEY:
                st.write("🤖 Gemini 2.5 Pro 분석 중...")
                q, d = summarize_gemini(filtered, GEMINI_API_KEY, pq, pd_)
                if q: all_quick.append(f"### 🔵 Gemini 2.5 Pro\n{q}")
                if d: all_deep.append(f"### 🔵 Gemini 2.5 Pro\n{d}")
                used.append("Gemini 2.5 Pro")
            if "GPT-4o-mini" in ai_providers and OPENAI_API_KEY:
                st.write("🤖 GPT-4o-mini 분석 중...")
                q, d = summarize_openai(filtered, OPENAI_API_KEY, pq, pd_)
                if q: all_quick.append(f"### 🟢 GPT-4o-mini\n{q}")
                if d: all_deep.append(f"### 🟢 GPT-4o-mini\n{d}")
                used.append("GPT-4o-mini")
            if not used:
                st.write("⚠️ AI API 키 없음 — 요약 건너뜀")
            st.session_state[f"{prefix}summary_quick"] = "\n\n---\n\n".join(all_quick)
            st.session_state[f"{prefix}summary_deep"]  = "\n\n---\n\n".join(all_deep)
            st.session_state[f"{prefix}provider"] = " + ".join(used)
        elif use_ai and filtered:
            st.write("⚠️ AI 제공자를 선택해주세요")

        status.update(label=f"✅ 완료 — {len(filtered)}건 (전체 {len(all_raw)}건 중)", state="complete")


# ═══════════════════════════════════════════════
# ── 현재 모드 데이터 로드 ───────────────────────
# ═══════════════════════════════════════════════
prefix        = "ta_" if is_ta else ("oc_" if is_oc else "m7_")
news_data     = st.session_state[f"{prefix}news_data"]
source_stats  = st.session_state[f"{prefix}source_stats"]
summary_quick = st.session_state[f"{prefix}summary_quick"]
summary_deep  = st.session_state[f"{prefix}summary_deep"]
provider      = st.session_state[f"{prefix}provider"]

# ── 헤더 ──────────────────────────────────────
if is_ta:
    st.markdown(f"""<div class="main-header">
      <h1>₿ BTC 기술적 분석 리포트</h1>
      <div class="sub">차트 분석 · RSI · MACD · 지지/저항 · 패턴 분석 | {TODAY_STR} (KST)</div>
    </div>""", unsafe_allow_html=True)
elif is_oc:
    st.markdown(f"""<div class="main-header">
      <h1>₿ BTC 온체인 분석 리포트</h1>
      <div class="sub">MVRV · SOPR · 거래소 흐름 · 펀딩비 · 고래 동향 | {TODAY_STR} (KST)</div>
    </div>""", unsafe_allow_html=True)
else:
    tickers_str = " · ".join(f"{M7_STOCKS[t]['emoji']}{t}" for t in M7_STOCKS)
    st.markdown(f"""<div class="main-header">
      <h1>🏆 Magnificent 7 분석 리포트</h1>
      <div class="sub">{tickers_str}</div>
      <div class="sub">차트 분석 · 실적 · 애널리스트 · 섹터 동향 | {TODAY_STR} (KST)</div>
    </div>""", unsafe_allow_html=True)


# ── 빈 상태 ───────────────────────────────────
if not news_data:
    if is_ta:   st.info("👈 사이드바에서 **기술적 분석 수집 시작** 버튼을 눌러주세요.")
    elif is_oc: st.info("👈 사이드바에서 **온체인 분석 수집 시작** 버튼을 눌러주세요.")
    else:
        st.info("👈 사이드바에서 종목을 선택하고 **M7 주식 뉴스 수집** 버튼을 눌러주세요.")
        # M7 종목 카드 미리보기
        st.markdown('<div class="sec-title">🏆 Magnificent 7 종목</div>', unsafe_allow_html=True)
        cols = st.columns(7)
        for col, (ticker, info) in zip(cols, M7_STOCKS.items()):
            with col:
                tc = info["color"]
                st.markdown(f"""
                <div style="background:#161b22;border:1px solid #21262d;border-top:3px solid {tc};
                            border-radius:10px;padding:12px 8px;text-align:center">
                  <div style="font-size:1.5rem">{info['emoji']}</div>
                  <div style="font-size:.85rem;font-weight:700;color:{tc};margin-top:4px">{ticker}</div>
                  <div style="font-size:.7rem;color:#8b949e;margin-top:2px">{info['name']}</div>
                </div>""", unsafe_allow_html=True)
    st.stop()


# ── 소스별 통계 ───────────────────────────────
accent = "#f7931a" if is_ta else ("#3b82f6" if is_oc else "#76B900")
st.markdown('<div class="sec-title">📊 소스별 수집 현황</div>', unsafe_allow_html=True)

total_col, *src_cols = st.columns([1] + [1] * min(len(source_stats), 7))
with total_col:
    st.markdown(f"""
    <div style="background:#161b22;border:1px solid #21262d;border-top:3px solid {accent};
                border-radius:10px;padding:14px 10px;text-align:center">
      <div style="font-size:1.5rem;font-weight:700;color:{accent}">{len(news_data)}</div>
      <div style="font-size:.75rem;color:#8b949e;margin-top:4px">분석 기사</div>
    </div>""", unsafe_allow_html=True)
for col, (src, cnt) in zip(src_cols, list(source_stats.items())[:7]):
    color = src_color(src)
    with col:
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #21262d;border-top:3px solid {color};
                    border-radius:10px;padding:14px 10px;text-align:center">
          <div style="font-size:1.5rem;font-weight:700;color:{color}">{cnt}</div>
          <div style="font-size:.72rem;color:#8b949e;margin-top:4px;word-break:break-all">{src}</div>
        </div>""", unsafe_allow_html=True)


# ── M7 전용: 종목별 집계 바 ────────────────────
if is_m7:
    st.markdown('<div class="sec-title">📈 종목별 기사 수</div>', unsafe_allow_html=True)
    ticker_counts = {}
    for item in news_data:
        t = item.get("ticker","기타")
        ticker_counts[t] = ticker_counts.get(t,0)+1
    t_cols = st.columns(len(M7_STOCKS))
    for col, (ticker, info) in zip(t_cols, M7_STOCKS.items()):
        cnt = ticker_counts.get(ticker, 0)
        tc  = info["color"]
        with col:
            st.markdown(f"""
            <div style="background:#161b22;border:1px solid #21262d;border-top:3px solid {tc};
                        border-radius:10px;padding:12px 8px;text-align:center">
              <div style="font-size:1.2rem">{info['emoji']}</div>
              <div style="font-size:1.1rem;font-weight:700;color:{tc}">{cnt}</div>
              <div style="font-size:.68rem;color:#8b949e;margin-top:2px">{ticker}</div>
            </div>""", unsafe_allow_html=True)

    n_ta_m7   = sum(1 for x in news_data if x.get("is_ta"))
    n_fund_m7 = sum(1 for x in news_data if x.get("is_fund"))
    st.markdown(f"""
    <div style="margin:12px 0 4px;padding:10px 14px;background:#161b22;border:1px solid #21262d;
                border-radius:8px;font-size:.82rem;color:#8b949e">
      📊 기술적 분석: <span style="color:#f7931a;font-weight:700">{n_ta_m7}건</span>
      &nbsp;&nbsp;|&nbsp;&nbsp;
      💹 펀더멘털: <span style="color:#76B900;font-weight:700">{n_fund_m7}건</span>
    </div>""", unsafe_allow_html=True)

elif is_ta or is_oc:
    n_ta = sum(1 for x in news_data if x.get("is_ta"))
    n_oc_cnt = sum(1 for x in news_data if x.get("is_onchain"))
    st.markdown(f"""
    <div style="margin:12px 0 4px;padding:10px 14px;background:#161b22;border:1px solid #21262d;
                border-radius:8px;font-size:.82rem;color:#8b949e">
      📊 기술적 분석: <span style="color:#f7931a;font-weight:700">{n_ta}건</span>
      &nbsp;&nbsp;|&nbsp;&nbsp;
      🔗 온체인 분석: <span style="color:#3b82f6;font-weight:700">{n_oc_cnt}건</span>
    </div>""", unsafe_allow_html=True)


# ── AI 요약 ───────────────────────────────────
if summary_quick or summary_deep:
    pl = f" <span style='font-size:.8rem;color:#8b949e'>by {provider}</span>" if provider else ""
    st.markdown(f'<div class="sec-title">🤖 AI 분석{pl}</div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["⚡ Quick Summary", "🔬 Deep Dive"])
    with t1: st.markdown(summary_quick or "_요약 없음_")
    with t2: st.markdown(summary_deep  or "_분석 없음_")


# ── 뉴스 목록 ─────────────────────────────────
st.markdown(f'<div class="sec-title">📋 기사 목록 ({len(news_data)}건)</div>', unsafe_allow_html=True)

if is_m7:
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        search_q = st.text_input("🔍", placeholder="earnings, price target, RSI, buyback...",
                                  label_visibility="collapsed")
    with c2:
        ticker_opts = ["전체"] + [t for t in M7_STOCKS if any(x.get("ticker")==t for x in news_data)]
        filter_ticker = st.selectbox("종목", ticker_opts, label_visibility="collapsed")
    with c3:
        type_filter = st.selectbox("유형", ["전체","📊 TA","💹 펀더멘털","📊+💹 둘다"],
                                    label_visibility="collapsed")
    with c4:
        all_srcs = sorted(set(x["source"] for x in news_data))
        filter_src = st.selectbox("소스", ["전체"]+all_srcs, label_visibility="collapsed")
else:
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        search_q = st.text_input("🔍", placeholder="RSI, MACD, MVRV, funding rate...",
                                  label_visibility="collapsed")
    with c2:
        type_filter = st.selectbox("유형", ["전체","📊 TA만","🔗 온체인만","📊+🔗 둘다"],
                                    label_visibility="collapsed")
    with c3:
        all_srcs = sorted(set(x["source"] for x in news_data))
        filter_src = st.selectbox("소스", ["전체"]+all_srcs, label_visibility="collapsed")
    filter_ticker = "전체"

filtered = news_data

if search_q:
    q = search_q.lower()
    filtered = [n for n in filtered if q in n["title"].lower() or q in (n.get("description") or "").lower()]

if is_m7:
    if filter_ticker != "전체":
        filtered = [n for n in filtered if n.get("ticker") == filter_ticker]
    if type_filter == "📊 TA":
        filtered = [n for n in filtered if n.get("is_ta")]
    elif type_filter == "💹 펀더멘털":
        filtered = [n for n in filtered if n.get("is_fund")]
    elif type_filter == "📊+💹 둘다":
        filtered = [n for n in filtered if n.get("is_ta") and n.get("is_fund")]
else:
    if type_filter == "📊 TA만":
        filtered = [n for n in filtered if n.get("is_ta") and not n.get("is_onchain")]
    elif type_filter == "🔗 온체인만":
        filtered = [n for n in filtered if n.get("is_onchain") and not n.get("is_ta")]
    elif type_filter == "📊+🔗 둘다":
        filtered = [n for n in filtered if n.get("is_ta") and n.get("is_onchain")]

if filter_src != "전체":
    filtered = [n for n in filtered if n["source"] == filter_src]

st.caption(f"{len(filtered)}건 표시 중")
for i, item in enumerate(filtered, 1):
    render_news_card(item, i)


# ── 푸터 ─────────────────────────────────────
if is_m7:
    footer_src = "Yahoo Finance · Benzinga · MarketWatch · CNBC · Seeking Alpha · Finnhub · Reddit"
else:
    footer_src = "CoinTelegraph · AMBCrypto · Glassnode · CryptoSlate · Coinglass · The Block · CoinDesk · Reddit"

st.markdown(f"""
<div style="text-align:center;padding:24px 16px;color:#6e7681;font-size:.8rem;
            border-top:1px solid #21262d;margin-top:32px">
  데이터 출처: {footer_src}<br>
  생성: {NOW_KST.strftime('%Y-%m-%d %H:%M')} KST
  &nbsp;|&nbsp; ⚠️ 본 리포트는 정보 제공 목적이며 투자 조언이 아닙니다.
</div>""", unsafe_allow_html=True)

"""
통합 분석 대시보드 — CryptoQuant 스타일 UI
모드: 📈 주식 뉴스 | 🪙 코인 뉴스 | 📊 BTC 기술적 분석 | 🔗 BTC 온체인 분석 | 🏆 미국주식 기술적 분석
"""

import datetime
import json
import os
import re
import time
from email.utils import parsedate_to_datetime

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="통합 분석 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_secret(key: str) -> str:
    try:
        return st.secrets.get(key, "") or os.getenv(key, "")
    except Exception:
        return os.getenv(key, "")


# ── API 키 ─────────────────────────────────────────
FINNHUB_API_KEY     = get_secret("FINNHUB_API_KEY")
CRYPTOPANIC_API_KEY = get_secret("CRYPTOPANIC_API_KEY")
OPENAI_API_KEY      = get_secret("OPENAI_API_KEY")
GEMINI_API_KEY      = get_secret("GEMINI_API_KEY")
APP_PASSWORD        = get_secret("APP_PASSWORD") or "1234"

# ── 비밀번호 인증 ──────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if APP_PASSWORD and not st.session_state.authenticated:
    st.markdown("""
    <style>
    html, body, .stApp { background: #F4F6F9 !important; }
    #MainMenu, header, footer { visibility: hidden; }
    .lock-card {
        max-width: 400px; margin: 12vh auto 0;
        background: #FFFFFF; border: 1px solid #E5E7EB;
        border-radius: 16px; padding: 48px 40px;
        text-align: center; box-shadow: 0 4px 24px rgba(0,0,0,.08);
    }
    .lock-card .icon { font-size: 2.8rem; margin-bottom: 12px; }
    .lock-card h2 { font-size: 1.3rem; font-weight: 700; color: #111827; margin-bottom: 6px; }
    .lock-card p  { color: #6B7280; font-size: .88rem; margin-bottom: 0; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(
        '<div class="lock-card">'
        '<div class="icon">📊</div>'
        '<h2>통합 분석 대시보드</h2>'
        '<p>접근하려면 비밀번호를 입력하세요</p></div>',
        unsafe_allow_html=True)
    pw = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력", label_visibility="collapsed")
    _, c2, _ = st.columns([1, 2, 1])
    with c2:
        if st.button("로그인", type="primary", use_container_width=True):
            if pw == APP_PASSWORD:
                st.session_state.authenticated = True
                st.session_state["auto_run_combined_on_login"] = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    st.stop()

# ── 공통 상수 ──────────────────────────────────────
NOW_UTC       = datetime.datetime.utcnow()
NOW_KST       = NOW_UTC + datetime.timedelta(hours=9)
TODAY_STR     = NOW_KST.strftime("%Y-%m-%d")
YESTERDAY_STR = (NOW_KST - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

# ── M7 종목 정의 ───────────────────────────────────
M7_STOCKS = {
    "AAPL":  {"name": "Apple",     "emoji": "🍎", "color": "#6B7280"},
    "MSFT":  {"name": "Microsoft", "emoji": "🪟", "color": "#00A4EF"},
    "GOOGL": {"name": "Alphabet",  "emoji": "🔍", "color": "#4285F4"},
    "AMZN":  {"name": "Amazon",    "emoji": "📦", "color": "#FF9900"},
    "META":  {"name": "Meta",      "emoji": "👥", "color": "#1877F2"},
    "TSLA":  {"name": "Tesla",     "emoji": "⚡", "color": "#CC0000"},
    "NVDA":  {"name": "Nvidia",    "emoji": "🎮", "color": "#76B900"},
}

# ── 소스 색상 ──────────────────────────────────────
SOURCE_COLORS = {
    "finnhub": "#3B82F6", "yahoo finance": "#7C3AED", "cnbc": "#1D4ED8",
    "marketwatch": "#16A34A", "reuters": "#EA580C", "mni markets": "#DC2626",
    "mkt news": "#D97706", "cryptopanic": "#F7931A", "coindesk": "#2563EB",
    "cryptonews.net": "#15803D", "coincarp": "#7C3AED", "crypto.news": "#0891B2",
    "cryptonews.com": "#DC2626", "the block": "#D97706", "decrypt": "#059669",
    "cointelegraph": "#0D9488", "ambcrypto": "#B45309", "glassnode": "#2563EB",
    "cryptoslate": "#7C3AED", "coinglass": "#DC2626", "reddit": "#EA580C",
    "seekingalpha": "#15803D", "benzinga": "#1D4ED8", "barrons": "#9F1239",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── 키워드 ─────────────────────────────────────────
TA_KEYWORDS = [
    "technical analysis", "price analysis", "chart analysis", "price prediction",
    "rsi", "macd", "moving average", "ema", "sma", "bollinger",
    "support", "resistance", "breakout", "breakdown", "trend",
    "fibonacci", "fib", "elliott wave", "pattern", "wedge", "triangle",
    "bullish", "bearish", "rally", "correction", "reversal",
    "all-time high", "ath", "price target", "key level",
    "overbought", "oversold", "momentum", "volume", "candlestick",
    "head and shoulders", "double top", "double bottom", "flag", "pennant",
    "bitcoin price", "btc price", "btc/usd", "price outlook", "market structure",
    "higher high", "lower low", "higher low", "lower high",
]
ONCHAIN_KEYWORDS = [
    "on-chain", "onchain", "on chain", "mvrv", "sopr", "nupl", "nvt", "realized price",
    "exchange flow", "exchange balance", "exchange inflow", "exchange outflow",
    "funding rate", "open interest", "liquidation", "long/short",
    "whale", "large holder", "accumulation", "distribution",
    "hash rate", "hashrate", "miner", "mining", "stablecoin", "usdt", "usdc supply",
    "etf flow", "etf inflow", "etf outflow", "spot etf", "netflow", "cost basis",
    "hodl", "lth", "sth", "long-term holder", "short-term holder",
    "glassnode", "intotheblock", "santiment", "coinglass",
    "network value", "active address", "transaction volume",
    "unrealized profit", "unrealized loss", "dormancy", "coin days destroyed", "cdd",
    "perpetual", "derivatives", "basis", "funding", "liquidity",
]
M7_TA_KEYWORDS = [
    "technical analysis", "price analysis", "chart analysis", "price target",
    "rsi", "macd", "moving average", "ema", "sma", "bollinger",
    "support", "resistance", "breakout", "breakdown", "trend",
    "fibonacci", "bullish", "bearish", "rally", "correction", "reversal",
    "overbought", "oversold", "momentum", "volume", "candlestick",
    "buy signal", "sell signal", "outperform", "underperform", "upgrade", "downgrade",
    "all-time high", "52-week high", "52-week low", "key level", "trading range",
]
M7_FUND_KEYWORDS = [
    "earnings", "revenue", "eps", "profit", "margin", "guidance", "forecast",
    "pe ratio", "price-to-earnings", "valuation", "market cap", "forward pe",
    "analyst", "rating", "target price", "consensus", "wall street",
    "beat", "miss", "surprise", "estimate", "outlook", "full year",
    "cloud", "ai", "artificial intelligence", "data center", "advertising",
    "iphone", "mac", "services", "azure", "aws", "gcp",
    "autonomous", "ev", "electric vehicle", "fsd", "cybertruck",
    "gpu", "chip", "semiconductor", "h100", "blackwell", "cuda",
    "buyback", "dividend", "share repurchase", "capex", "free cash flow",
]

# ══════════════════════════════════════════════════
# ── CryptoQuant 스타일 CSS ─────────────────────────
# ══════════════════════════════════════════════════
st.markdown("""
<style>
/* ── 전역 라이트 테마 ── */
html, body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important; }
.stApp { background: #F4F6F9 !important; }
.main .block-container { padding: 0 !important; max-width: 100% !important; background: transparent; }

/* ── 사이드바 ── */
section[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #E5E7EB !important;
}
section[data-testid="stSidebar"] > div { padding: 0 !important; }

/* 사이드바 내부 마진 */
section[data-testid="stSidebar"] .stMarkdown { padding: 0 4px; }
section[data-testid="stSidebar"] .stButton button { margin: 2px 12px; }

/* ── 헤더 숨김 ── */
header[data-testid="stHeader"] { background: #FFFFFF !important; border-bottom: 1px solid #E5E7EB !important; }
#MainMenu, footer { visibility: hidden; }

/* ── 라디오 버튼 → 사이드바 nav 스타일 ── */
[data-testid="stRadio"] { margin: 0 !important; }
[data-testid="stRadio"] > label { display: none !important; }
[data-testid="stRadio"] div[role="radiogroup"] { gap: 1px !important; flex-direction: column; }
[data-testid="stRadio"] label {
    display: flex !important; align-items: center !important;
    padding: 9px 16px !important; margin: 0 !important;
    border-radius: 0 !important; cursor: pointer !important;
    font-size: .875rem !important; color: #374151 !important;
    font-weight: 400 !important; transition: background .1s !important;
    border-left: 3px solid transparent !important;
    background: transparent !important;
}
[data-testid="stRadio"] label:hover { background: #F9FAFB !important; color: #111827 !important; }
[data-testid="stRadio"] label[data-checked="true"] {
    background: #FFF7ED !important; color: #C2410C !important;
    font-weight: 600 !important; border-left: 3px solid #F7931A !important;
}
/* radio circle 숨김 */
[data-testid="stRadio"] input[type="radio"] { display: none !important; }
[data-testid="stRadio"] div[data-testid="stMarkdownContainer"] p { margin: 0 !important; font-size: .875rem !important; }

/* ── 토글 & 멀티셀렉트 ── */
.stToggle label { font-size: .875rem !important; color: #374151 !important; }
.stMultiSelect > div { font-size: .875rem !important; }

/* ── 버튼 ── */
.stButton button[kind="primary"] {
    background: #F7931A !important; border: none !important;
    border-radius: 8px !important; font-weight: 600 !important;
    font-size: .875rem !important; padding: 10px 20px !important;
    color: #FFFFFF !important; transition: background .15s !important;
}
.stButton button[kind="primary"]:hover { background: #E8820A !important; }

/* ── 상단 앱 바 ── */
.cq-topbar {
    background: #FFFFFF; border-bottom: 1px solid #E5E7EB;
    padding: 0 24px; height: 56px;
    display: flex; align-items: center; gap: 24px;
    position: sticky; top: 0; z-index: 100;
}
.cq-topbar .logo {
    font-size: 1rem; font-weight: 800; color: #111827;
    display: flex; align-items: center; gap: 8px; white-space: nowrap;
}
.cq-topbar .logo span { color: #F7931A; }
.cq-mode-tabs { display: flex; gap: 2px; flex: 1; }
.cq-mode-tab {
    padding: 6px 14px; border-radius: 6px; font-size: .82rem;
    font-weight: 500; color: #6B7280; cursor: default;
    background: transparent; border: 1px solid transparent;
    white-space: nowrap;
}
.cq-mode-tab.active {
    background: #FFF7ED; color: #C2410C;
    border-color: #FED7AA; font-weight: 700;
}
.cq-topbar .time-info { font-size: .78rem; color: #9CA3AF; white-space: nowrap; margin-left: auto; }

/* ── 컨텐츠 래퍼 ── */
.cq-content { padding: 20px 24px; }

/* ── 섹션 타이틀 ── */
.cq-section-title {
    font-size: .68rem; font-weight: 700; color: #9CA3AF;
    letter-spacing: .1em; text-transform: uppercase;
    padding: 16px 16px 6px; margin: 0;
}

/* ── 사이드바 구분선 ── */
.cq-divider { height: 1px; background: #F3F4F6; margin: 8px 0; }

/* ── 사이드바 로고 ── */
.cq-sidebar-logo {
    padding: 16px 16px 12px;
    font-size: .95rem; font-weight: 800; color: #111827;
    border-bottom: 1px solid #F3F4F6;
    display: flex; align-items: center; gap: 8px;
}
.cq-sidebar-logo .dot { color: #F7931A; }

/* ── 통계 카드 행 ── */
.cq-stats-row {
    display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;
}
.cq-stat-card {
    background: #FFFFFF; border: 1px solid #E5E7EB;
    border-radius: 10px; padding: 14px 20px;
    display: flex; flex-direction: column; gap: 4px;
    min-width: 120px;
}
.cq-stat-card .s-label { font-size: .72rem; color: #9CA3AF; font-weight: 500; text-transform: uppercase; letter-spacing: .05em; }
.cq-stat-card .s-value { font-size: 1.4rem; font-weight: 700; color: #111827; line-height: 1; }
.cq-stat-card .s-sub { font-size: .75rem; color: #6B7280; }

/* ── 뉴스 테이블 ── */
.cq-table-wrap {
    background: #FFFFFF; border: 1px solid #E5E7EB;
    border-radius: 12px; overflow: hidden;
}
.cq-table-header {
    display: grid; grid-template-columns: 40px 1fr 160px 100px;
    padding: 10px 16px; background: #F9FAFB;
    border-bottom: 1px solid #E5E7EB;
    font-size: .72rem; font-weight: 700; color: #9CA3AF;
    text-transform: uppercase; letter-spacing: .06em;
    gap: 12px;
}
.cq-news-row {
    display: grid; grid-template-columns: 40px 1fr 160px 100px;
    padding: 12px 16px; border-bottom: 1px solid #F3F4F6;
    gap: 12px; align-items: start; transition: background .1s;
}
.cq-news-row:last-child { border-bottom: none; }
.cq-news-row:hover { background: #FAFAFA; }
.cq-row-num {
    font-size: .75rem; color: #D1D5DB; font-weight: 600;
    padding-top: 3px; text-align: center;
}
.cq-row-title {
    font-size: .875rem; font-weight: 500; color: #111827; line-height: 1.45;
    margin-bottom: 4px; word-break: break-word;
}
.cq-row-title a { color: #111827; text-decoration: none; }
.cq-row-title a:hover { color: #F7931A; }
.cq-row-desc { font-size: .78rem; color: #9CA3AF; line-height: 1.4; }
.cq-row-badges { display: flex; flex-wrap: wrap; gap: 5px; align-items: flex-start; padding-top: 2px; }
.cq-src-badge {
    font-size: .7rem; font-weight: 600; padding: 3px 8px;
    border-radius: 5px; border: 1px solid; white-space: nowrap;
}
.cq-type-badge {
    font-size: .68rem; font-weight: 700; padding: 3px 8px;
    border-radius: 5px; white-space: nowrap;
}
.cq-type-ta    { background: #FFF7ED; color: #C2410C; border: 1px solid #FED7AA; }
.cq-type-oc    { background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; }
.cq-type-fund  { background: #F0FDF4; color: #15803D; border: 1px solid #BBF7D0; }
.cq-ticker-badge {
    font-size: .7rem; font-weight: 800; padding: 3px 8px;
    border-radius: 5px; border: 1px solid;
}
.cq-kw-chip {
    display: inline-block; font-size: .65rem; padding: 2px 6px;
    background: #F3F4F6; color: #6B7280;
    border-radius: 4px; margin: 1px 1px 0 0;
}
.cq-row-time { font-size: .75rem; color: #9CA3AF; padding-top: 3px; white-space: nowrap; }

/* ── 검색 & 필터 바 ── */
.cq-filter-bar {
    background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 10px;
    padding: 12px 16px; margin-bottom: 14px;
    display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
}

/* ── AI 분석 카드 ── */
.cq-ai-card {
    background: #FFFFFF; border: 1px solid #E5E7EB;
    border-radius: 12px; padding: 20px 24px; margin-bottom: 20px;
}
.cq-ai-header {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 16px; padding-bottom: 12px;
    border-bottom: 1px solid #F3F4F6;
}
.cq-ai-dot { width: 10px; height: 10px; border-radius: 50%; background: #F7931A; }
.cq-ai-title { font-size: .9rem; font-weight: 700; color: #111827; }
.cq-ai-provider { font-size: .78rem; color: #9CA3AF; margin-left: 4px; }

/* ── M7 종목 카드 ── */
.cq-ticker-grid { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
.cq-ticker-card {
    background: #FFFFFF; border: 1px solid #E5E7EB;
    border-radius: 10px; padding: 14px 16px; min-width: 120px;
    text-align: center; border-top: 3px solid var(--tc);
}
.cq-ticker-card .tc-emoji { font-size: 1.4rem; }
.cq-ticker-card .tc-name { font-size: .85rem; font-weight: 700; color: var(--tc); margin-top: 6px; }
.cq-ticker-card .tc-full { font-size: .72rem; color: #9CA3AF; margin-top: 2px; }
.cq-ticker-card .tc-count { font-size: 1.1rem; font-weight: 800; color: #111827; margin-top: 4px; }

/* ── 현황 바 ── */
.cq-status-bar {
    background: #F9FAFB; border: 1px solid #E5E7EB;
    border-radius: 8px; padding: 10px 16px; margin-bottom: 16px;
    font-size: .82rem; color: #6B7280; display: flex; gap: 20px;
}
.cq-status-bar .item { display: flex; align-items: center; gap: 6px; }
.cq-status-bar .count { font-weight: 700; font-size: .9rem; }

/* ── 소스별 수집현황 ── */
.cq-source-grid { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
.cq-source-card {
    background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px;
    padding: 12px 16px; min-width: 100px; border-top: 3px solid var(--sc);
}
.cq-source-card .sc-count { font-size: 1.2rem; font-weight: 700; color: var(--sc); }
.cq-source-card .sc-name { font-size: .72rem; color: #6B7280; margin-top: 2px; word-break: break-all; }

/* ── 빈 상태 ── */
.cq-empty {
    background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px;
    padding: 60px 24px; text-align: center;
}
.cq-empty .empty-icon { font-size: 2.5rem; margin-bottom: 12px; }
.cq-empty h3 { font-size: 1rem; font-weight: 600; color: #374151; margin-bottom: 8px; }
.cq-empty p { font-size: .875rem; color: #9CA3AF; }

/* ── 푸터 ── */
.cq-footer {
    text-align: center; padding: 20px 16px;
    color: #D1D5DB; font-size: .76rem;
    border-top: 1px solid #E5E7EB; margin-top: 32px;
}

/* ── 체크박스 (수집 소스) ── */
section[data-testid="stSidebar"] .stCheckbox label {
    font-size: .83rem !important; color: #374151 !important;
}
section[data-testid="stSidebar"] .stCheckbox { margin: 1px 0 !important; }

/* ── 사이드바 caption ── */
section[data-testid="stSidebar"] .stCaption { color: #9CA3AF !important; font-size: .75rem !important; padding: 0 16px; }

/* ── 설정 마크다운 ── */
section[data-testid="stSidebar"] h3 { font-size: .75rem !important; color: #9CA3AF !important; font-weight: 700 !important; letter-spacing: .08em !important; text-transform: uppercase !important; padding: 12px 16px 4px !important; margin: 0 !important; }
section[data-testid="stSidebar"] strong { font-size: .75rem !important; color: #9CA3AF !important; font-weight: 700 !important; text-transform: uppercase !important; letter-spacing: .06em !important; }
section[data-testid="stSidebar"] hr { border-color: #F3F4F6 !important; margin: 8px 0 !important; }

/* Streamlit status box */
[data-testid="stStatusWidget"] { border-radius: 8px !important; border-color: #E5E7EB !important; }

/* info box */
.stAlert { border-radius: 8px !important; border-left: 4px solid #F7931A !important; background: #FFF7ED !important; color: #374151 !important; }
</style>
""", unsafe_allow_html=True)


# ── 공통 유틸 ──────────────────────────────────────
def src_color(source: str) -> str:
    low = source.lower()
    for k, v in SOURCE_COLORS.items():
        if k in low:
            return v
    return "#9CA3AF"


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(text, "html.parser").get_text(separator=" ")).strip()


def make_item(title, url="", source="", published_at="", description="", ticker=""):
    return {
        "title":            re.sub(r"\s+", " ", title).strip(),
        "url":              url,
        "source":           source,
        "published_at":     published_at,
        "description":      _strip_html(description or ""),
        "ticker":           ticker,
        "matched_keywords": [],
        "is_ta":            False,
        "is_onchain":       False,
        "is_fund":          False,
    }


def is_recent(pub: str, days: int = 1) -> bool:
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


def find_time_in_parents(element) -> str:
    current = element
    for _ in range(6):
        if not current:
            break
        current = getattr(current, "parent", None)
        if not current:
            break
        time_tag = current.find("time")
        if time_tag:
            return time_tag.get("datetime", "")
    return ""


# ── 뉴스 행 렌더링 (CryptoQuant 테이블 스타일) ──────
def render_news_row(item: dict, idx: int = 0) -> str:  # noqa: ARG001
    """Notion 스타일 링크 프리뷰 카드로 기사 한 건 렌더링."""
    import html as _html, re as _re
    title  = _html.escape(item.get("title", "") or "(제목 없음)")
    url    = item.get("url", "")
    source = item.get("source", "")
    pub    = item.get("published_at", "")
    desc   = _html.escape((item.get("description", "") or "").strip())
    kst    = utc_to_kst(pub)
    ticker = item.get("ticker", "")

    # 도메인 & 파비콘
    domain = ""
    if url:
        m = _re.search(r"https?://([^/]+)", url)
        if m:
            domain = m.group(1).lstrip("www.")
    favicon_html = (
        f'<img src="https://www.google.com/s2/favicons?domain={domain}&sz=16" '
        f'width="14" height="14" '
        f'style="vertical-align:middle;border-radius:2px;margin-right:4px" '
        f'onerror="this.style.display=\'none\'">'
    ) if domain else ""

    # 하단 메타 줄
    meta_parts = [f'{favicon_html}<span style="color:#6b7280">{_html.escape(domain or source)}</span>']
    if ticker and ticker in M7_STOCKS:
        tc = M7_STOCKS[ticker]["color"]
        em = M7_STOCKS[ticker]["emoji"]
        meta_parts.append(f'<span style="color:{tc}">{em} {ticker}</span>')
    if item.get("is_ta"):      meta_parts.append('<span style="color:#5dade2">📊 TA</span>')
    if item.get("is_onchain"): meta_parts.append('<span style="color:#a569bd">🔗 온체인</span>')
    if kst: meta_parts.append(f'<span style="color:#4b5563">{kst}</span>')
    meta_html = ' · '.join(meta_parts)

    # 설명 (제목과 다를 때, 2줄 clamp)
    desc_html = ""
    if desc and desc.lower()[:60] != title.lower()[:60]:
        desc_html = (
            f'<div style="font-size:.76rem;color:#94a3b8;margin-top:4px;'
            f'overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;'
            f'-webkit-box-orient:vertical;line-height:1.45">'
            f'{desc[:220]}</div>'
        )

    inner = f"""<div style="border:1px solid #2a2f45;border-radius:8px;
                     background:#111827;margin:4px 0;cursor:pointer;
                     transition:border-color .15s,background .15s"
                onmouseover="this.style.borderColor='#4f5a78';this.style.background='#161d30'"
                onmouseout="this.style.borderColor='#2a2f45';this.style.background='#111827'">
  <div style="padding:11px 15px">
    <div style="font-size:.88rem;font-weight:700;color:#e2e8f0;
                overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;
                -webkit-box-orient:vertical;line-height:1.45">
      {title}
    </div>
    {desc_html}
    <div style="font-size:.72rem;margin-top:7px;display:flex;align-items:center;gap:0;flex-wrap:wrap;gap:4px">
      {meta_html}
    </div>
  </div>
</div>"""

    if url:
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;display:block">{inner}</a>'
    return inner


# ══════════════════════════════════════════════════
# ── AI 프롬프트 ────────────────────────────────────
# ══════════════════════════════════════════════════
PROMPT_STOCK_QUICK = """다음은 {date} (KST) 미국 주식 및 금융 시장 뉴스입니다.\n{content}\n위 뉴스만을 바탕으로 한국어 Quick Summary를 작성해주세요.\n1. **오늘의 증시 핵심 테마** (거시경제, S&P500 흐름 등 3~5가지, 각 1~2문장)\n2. **주요 기업/섹터별 이슈** (특징주 중심, 각 1문장)\n3. **한줄 시장 요약**\n가독성 좋고 간결하게 작성해주세요."""
PROMPT_STOCK_DEEP  = """다음은 {date} (KST) 미국 증시 주요 뉴스입니다.\n{content}\n위 뉴스만을 바탕으로 한국어 Deep Dive 심층 분석을 작성해주세요.\n1. **거시 경제 및 연준(Fed) 동향 분석**\n2. **주요 기업 실적 및 펀더멘털 분석**\n3. **섹터별 자금 흐름 및 특징**\n4. **리스크 요인 및 시장의 우려**\n5. **단기 시장 전망 및 월가 시각**\n전문적인 금융 리포트 톤으로 작성해주세요."""
PROMPT_COIN_QUICK  = """다음은 {date} (KST) 기준 코인 뉴스입니다.\n{content}\n위 뉴스만 바탕으로 한국어 Quick Summary를 작성해주세요.\n1. **오늘의 핵심 이슈** (3~5개, 각 1~2문장)\n2. **코인/프로젝트별 주요 이슈**\n3. **시장 한줄 요약**"""
PROMPT_COIN_DEEP   = """다음은 {date} (KST) 기준 코인 뉴스입니다.\n{content}\n위 뉴스만 바탕으로 한국어 Deep Dive 분석을 작성해주세요.\n1. **거시 경제 및 규제 환경 분석**\n2. **주요 코인별/섹터별 테마 분석**\n3. **기관 투자자 동향**\n4. **리스크 요인 및 주의 포인트**\n5. **단기 시장 전망 및 투자 시사점**"""
PROMPT_TA_QUICK    = """다음은 {date} (KST) 기준 비트코인 기술적 분석 기사들입니다.\n{content}\n위 내용만을 바탕으로 한국어 Quick Summary를 작성해주세요.\n1. **현재 BTC 차트 핵심 구조**\n2. **주요 기술적 지표 현황** (RSI, MACD, 이평선)\n3. **단기 시나리오** (강세/약세)\n4. **한줄 차트 요약**"""
PROMPT_TA_DEEP     = """다음은 {date} (KST) 기준 비트코인 기술적 분석 기사들입니다.\n{content}\n위 내용만을 바탕으로 한국어 Deep Dive 기술적 분석을 작성해주세요.\n1. **현재 가격 구조 분석**\n2. **오실레이터·모멘텀 지표 분석**\n3. **이동평균선 및 추세 분석**\n4. **주요 패턴 및 차트 형태**\n5. **단기/중기 가격 전망 및 핵심 레벨**"""
PROMPT_OC_QUICK    = """다음은 {date} (KST) 기준 비트코인 온체인 분석 기사들입니다.\n{content}\n위 내용만을 바탕으로 한국어 Quick Summary를 작성해주세요.\n1. **핵심 온체인 시그널**\n2. **투자자 행동 분석**\n3. **파생상품 시장 현황**\n4. **한줄 온체인 요약**"""
PROMPT_OC_DEEP     = """다음은 {date} (KST) 기준 비트코인 온체인 분석 기사들입니다.\n{content}\n위 내용만을 바탕으로 한국어 Deep Dive 온체인 분석을 작성해주세요.\n1. **밸류에이션 지표 분석** (MVRV, SOPR)\n2. **홀더 행동 분석** (LTH vs STH)\n3. **거래소 흐름 분석**\n4. **파생상품·레버리지 현황**\n5. **매크로 온체인 전망**"""
PROMPT_M7_QUICK    = """다음은 {date} (KST) 기준 Magnificent 7 관련 기사들입니다.\n{content}\n위 내용만을 바탕으로 한국어 Quick Summary를 작성해주세요.\n1. **M7 전체 시장 분위기**\n2. **종목별 핵심 이슈** (티커 명시)\n3. **기술적 주목 레벨**\n4. **단기 투자 시사점**\n5. **한줄 M7 요약**"""
PROMPT_M7_DEEP     = """다음은 {date} (KST) 기준 Magnificent 7 관련 기사들입니다.\n{content}\n위 내용만을 바탕으로 한국어 Deep Dive 분석을 작성해주세요.\n1. **기술적 분석 종목별 현황**\n2. **펀더멘털 분석**\n3. **애널리스트 의견 종합**\n4. **섹터 및 매크로 연관성**\n5. **종목별 리스크 및 기회 요인**"""

def _get_discord_webhook() -> str:
    return (get_secret("DISCORD_WEBHOOK_URL") or "").strip()

DISCORD_WEBHOOK_URL = _get_discord_webhook()

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

5. **기관 BTC 채택 및 DeFi 수익률 환경**
   - BTC 기업 보유 현황과 기관 채택 최신 동향
   - USDT DeFi APY 수준이 시사하는 시장 유동성 및 리스크 선호도
   - DeFi APY ↔ BTC 가격 상관관계에서 읽히는 신호

6. **결론: 오늘의 핵심 인사이트 3가지**
   - 가장 중요한 관찰 사항 3가지를 bullet point로 명확히 제시

전문적이고 날카로운 금융 분석 리포트 톤으로 작성해주세요.

리포트 본문 맨 마지막 줄에 반드시 아래 형식 한 줄을 추가하세요 (다른 설명 없이):
SENTIMENT_BTC=극단적공포|공포|중립|탐욕|극단적탐욕 SENTIMENT_STOCK=극단적공포|공포|중립|탐욕|극단적탐욕"""


# ── AI 요약 ────────────────────────────────────────
def _gemini_generate(client, types, contents, **kw) -> str:
    """503 재시도 포함 Gemini 단일 호출. 공통 retry 헬퍼."""
    def _ex(r):
        if r.text is not None: return r.text
        try: return r.candidates[0].content.parts[0].text or ""
        except Exception: return ""
    for attempt, delay in enumerate([10, 20, 40, None], 1):
        try:
            return _ex(client.models.generate_content(
                model="gemini-2.5-pro",
                contents=contents,
                config=types.GenerateContentConfig(**kw)))
        except Exception as e:
            if delay is None or ("503" not in str(e) and "UNAVAILABLE" not in str(e)):
                raise
            st.info(f"Gemini 503 — {delay}초 후 재시도 ({attempt}/3)...")
            time.sleep(delay)
    return ""


def summarize_gemini(news_list, api_key, prompt_quick, prompt_deep):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        st.error("google-genai 패키지가 없습니다.")
        return "", ""
    client = genai.Client(api_key=api_key)
    content = build_news_text(news_list, 60)
    q, d = "", ""
    try:
        q = _gemini_generate(client, types,
                             prompt_quick.format(date=TODAY_STR, content=content),
                             temperature=0.4, max_output_tokens=8000)
    except Exception as e:
        st.warning(f"Gemini Quick 오류: {e}")
    try:
        d = _gemini_generate(client, types,
                             prompt_deep.format(date=TODAY_STR, content=content),
                             temperature=0.35, max_output_tokens=16000)
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
            messages=[{"role": "user", "content": prompt_quick.format(date=TODAY_STR, content=content)}],
            max_tokens=1500, temperature=0.4).choices[0].message.content or ""
    except Exception as e:
        st.warning(f"GPT Quick 오류: {e}")
    try:
        d = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_deep.format(date=TODAY_STR, content=content)}],
            max_tokens=3000, temperature=0.35).choices[0].message.content or ""
    except Exception as e:
        st.warning(f"GPT Deep 오류: {e}")
    return q, d


def send_discord(text: str, webhook_url: str = DISCORD_WEBHOOK_URL) -> bool:
    """Discord 웹훅으로 메시지 전송 (2000자 초과 시 청크 분할)"""
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
                success = False
            if i < total - 1:
                import time as _time; _time.sleep(0.5)
        except Exception:
            success = False
    return success


def summarize_combined_gemini(deep_dives: dict, api_key: str) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return ""
    _labels = {
        "stock_":        "📈 미국 주식 시장 분석",
        "coin_":         "🪙 코인 시장 분석",
        "ta_":           "📊 BTC 기술적 분석",
        "oc_":           "🔗 BTC 온체인 분석",
        "m7_":           "🏆 M7 기술적 분석",
        "btc_treasury_": "🏦 BTC Treasury (기업 보유 현황)",
        "usdt_apy_":     "💵 USDT APY (DeFi 수익률 환경)",
    }
    sections = "\n\n".join(
        f"=== {_labels[p]} ===\n{deep_dives[p][:3000]}"
        for p in _labels if p in deep_dives and deep_dives[p]
    )
    if not sections:
        return ""
    client = genai.Client(api_key=api_key)
    try:
        return _gemini_generate(client, types,
                                PROMPT_COMBINED.format(date=TODAY_STR, sections=sections),
                                temperature=0.35, max_output_tokens=16000)
    except Exception as e:
        return f"[Gemini 오류: {e}]"


def summarize_combined_openai(deep_dives: dict, api_key: str) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        return ""
    _labels = {
        "stock_":        "📈 미국 주식 시장 분석",
        "coin_":         "🪙 코인 시장 분석",
        "ta_":           "📊 BTC 기술적 분석",
        "oc_":           "🔗 BTC 온체인 분석",
        "m7_":           "🏆 M7 기술적 분석",
        "btc_treasury_": "🏦 BTC Treasury (기업 보유 현황)",
        "usdt_apy_":     "💵 USDT APY (DeFi 수익률 환경)",
    }
    sections = "\n\n".join(
        f"=== {_labels[p]} ===\n{deep_dives[p][:2000]}"
        for p in _labels if p in deep_dives and deep_dives[p]
    )
    if not sections:
        return ""
    client = OpenAI(api_key=api_key)
    try:
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": PROMPT_COMBINED.format(date=TODAY_STR, sections=sections)}],
            max_tokens=4000, temperature=0.35).choices[0].message.content or ""
    except Exception as e:
        return f"[GPT 오류: {e}]"


_SENTIMENT_LABELS = ["극단적공포", "공포", "중립", "탐욕", "극단적탐욕"]

def _parse_sentiment(text: str) -> tuple[str, str]:
    """종합분석 텍스트에서 BTC·미국주식 투자심리를 추출한다."""
    import re
    m = re.search(r"SENTIMENT_BTC=(\S+)\s+SENTIMENT_STOCK=(\S+)", text)
    if m:
        btc = m.group(1).strip()
        stock = m.group(2).strip()
        btc   = btc   if btc   in _SENTIMENT_LABELS else "중립"
        stock = stock if stock in _SENTIMENT_LABELS else "중립"
        return btc, stock
    return "", ""


def _render_dual_gauge(btc_sentiment: str, stock_sentiment: str) -> str:
    """BTC·미국주식 공포탐욕 게이지를 SVG 문자열로 반환 (브라우저 렌더링 → 한국어 완벽 지원)."""
    import math

    _val_map  = {"극단적공포": 10, "공포": 30, "중립": 50, "탐욕": 70, "극단적탐욕": 90}
    _disp_map = {"극단적공포": "극단적 공포", "공포": "공포", "중립": "중립",
                 "탐욕": "탐욕", "극단적탐욕": "극단적 탐욕"}
    _sections = [
        (180, 144, "#c0392b", 162, ["극단적", "공포"]),
        (144, 108, "#e67e22", 126, ["공포"]),
        (108,  72, "#95a5a6",  90, ["중립"]),
        ( 72,  36, "#2ecc71",  54, ["탐욕"]),
        ( 36,   0, "#16a085",  18, ["극단적", "탐욕"]),
    ]
    RO, RI = 110, 64   # outer / inner radius

    def pt(cx, cy, r, deg):
        rad = math.radians(deg)
        return cx + r * math.cos(rad), cy - r * math.sin(rad)

    def sector_path(cx, cy, t1, t2):
        x1o, y1o = pt(cx, cy, RO, t1);  x2o, y2o = pt(cx, cy, RO, t2)
        x1i, y1i = pt(cx, cy, RI, t1);  x2i, y2i = pt(cx, cy, RI, t2)
        lg = 1 if (t1 - t2) > 180 else 0
        return (f"M {x1o:.1f},{y1o:.1f} A {RO},{RO} 0 {lg},0 {x2o:.1f},{y2o:.1f} "
                f"L {x2i:.1f},{y2i:.1f} A {RI},{RI} 0 {lg},1 {x1i:.1f},{y1i:.1f} Z")

    def one_gauge(cx, cy, sentiment, title):
        value = _val_map.get(sentiment, 50) if sentiment else 50
        parts = []

        # 섹션 호
        for t1, t2, color, mid, lines in _sections:
            d = sector_path(cx, cy, t1, t2)
            parts.append(f'<path d="{d}" fill="{color}"/>')
            # 구분선
            for bdeg in (t1, t2):
                xi, yi = pt(cx, cy, RI,      bdeg)
                xo, yo = pt(cx, cy, RO + 1,  bdeg)
                parts.append(f'<line x1="{xi:.1f}" y1="{yi:.1f}" x2="{xo:.1f}" y2="{yo:.1f}" '
                              f'stroke="#0E1117" stroke-width="2.5"/>')
            # 라벨 (호 중앙)
            rm = (RO + RI) / 2
            lx, ly = pt(cx, cy, rm, mid)
            rot = mid - 90
            if len(lines) == 1:
                parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="white" '
                              f'font-size="11" font-weight="bold" text-anchor="middle" '
                              f'dominant-baseline="middle" '
                              f'transform="rotate({rot},{lx:.1f},{ly:.1f})">{lines[0]}</text>')
            else:
                dy = 7
                for i, ln in enumerate(lines):
                    offset = (i - (len(lines) - 1) / 2) * dy * 2
                    bx = lx + offset * math.cos(math.radians(rot + 90))
                    by = ly + offset * math.sin(math.radians(rot + 90))
                    parts.append(f'<text x="{bx:.1f}" y="{by:.1f}" fill="white" '
                                  f'font-size="10" font-weight="bold" text-anchor="middle" '
                                  f'dominant-baseline="middle" '
                                  f'transform="rotate({rot},{bx:.1f},{by:.1f})">{ln}</text>')

        # 바늘
        needle_deg = 180 - value * 1.8
        nx, ny = pt(cx, cy, RI - 8, needle_deg)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" '
                     f'stroke="white" stroke-width="3" stroke-linecap="round" '
                     f'marker-end="url(#arrowW)"/>')
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="white"/>')

        # 점수
        parts.append(f'<text x="{cx}" y="{cy - 14}" fill="white" font-size="22" '
                     f'font-weight="bold" text-anchor="middle" dominant-baseline="middle">'
                     f'{value}</text>')

        # 심리 텍스트
        sent_lbl = _disp_map.get(sentiment, "—") if sentiment else "—"
        parts.append(f'<text x="{cx}" y="{cy + 28}" fill="white" font-size="13" '
                     f'font-weight="bold" text-anchor="middle">{sent_lbl}</text>')

        # 제목
        parts.append(f'<text x="{cx}" y="{cy - RO - 14}" fill="#cccccc" font-size="15" '
                     f'font-weight="bold" text-anchor="middle">{title}</text>')

        # 눈금
        for val, lbl, anchor in ((0, "0", "middle"), (50, "50", "middle"), (100, "100", "middle")):
            gx, gy = pt(cx, cy, RO + 16, 180 - val * 1.8)
            parts.append(f'<text x="{gx:.1f}" y="{gy + 4:.1f}" fill="#666" '
                         f'font-size="10" text-anchor="{anchor}">{lbl}</text>')

        return "\n".join(parts)

    W, H = 580, 210
    g1 = one_gauge(145, 165, btc_sentiment,   "BTC")
    g2 = one_gauge(435, 165, stock_sentiment, "미국주식")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"
     style="width:100%;background:#0E1117;border-radius:10px;display:block">
  <defs>
    <marker id="arrowW" markerWidth="8" markerHeight="6"
            refX="8" refY="3" orient="auto">
      <polygon points="0 0,8 3,0 6" fill="white"/>
    </marker>
  </defs>
  {g1}
  {g2}
</svg>"""


# ══════════════════════════════════════════════════
# ── 주식 뉴스 스크래퍼 ────────────────────────────
# ══════════════════════════════════════════════════
def _now_kst_dynamic() -> datetime.datetime:
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def _auto_send_combined_to_discord(combined_text: str, trigger_source: str = "manual") -> str:
    webhook_url = _get_discord_webhook()
    if not webhook_url:
        st.warning("DISCORD_WEBHOOK_URL이 설정되지 않아 Discord 자동 발송을 건너뜁니다.")
        return "success_skipped_missing_webhook"

    now_kst = _now_kst_dynamic()
    today_str = now_kst.strftime("%Y-%m-%d")
    if st.session_state.get("discord_last_sent_date", "") == today_str:
        st.info("오늘은 이미 Discord 발송을 완료하여 자동 발송을 건너뜁니다.")
        return "success_skipped_daily_limit"

    trigger_text = " (login auto-run)" if trigger_source == "login" else ""
    header = (
        f"🤖 **AI 종합분석 리포트**{trigger_text} | {today_str} KST\n"
        f"{'-' * 40}\n\n"
    )

    if send_discord(header + combined_text, webhook_url=webhook_url):
        st.session_state["discord_last_sent"] = now_kst.strftime("%Y-%m-%d %H:%M KST")
        st.session_state["discord_last_sent_date"] = today_str
        st.success("Discord 자동 발송 완료")
        return "success_sent"

    st.warning("Discord 자동 발송에 실패했습니다.")
    return "success_send_failed"


def run_combined_analysis_pipeline(use_ai: bool, ai_providers: list, trigger_source: str = "manual") -> bool:
    run_started = _now_kst_dynamic()
    st.session_state["combined_last_run_at"] = run_started.strftime("%Y-%m-%d %H:%M KST")
    st.session_state["combined_last_run_status"] = "running"
    save_cache()

    _all_m7 = list(M7_STOCKS.keys())
    _auto_tasks = {
        "stock_": {
            "label": "📈 주식 뉴스",
            "tasks": [
                ("Yahoo Finance", fetch_rss_feed, ["https://finance.yahoo.com/news/rssindex", "Yahoo Finance"]),
                ("CNBC",          fetch_rss_feed, ["https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=120000000", "CNBC"]),
                ("MarketWatch",   fetch_rss_feed, ["http://feeds.marketwatch.com/marketwatch/topstories/", "MarketWatch"]),
                ("MNI Markets",   fetch_mni_markets, []),
                ("MKT News",      fetch_mktnews, []),
            ] + ([("Finnhub API", fetch_finnhub, [FINNHUB_API_KEY])] if FINNHUB_API_KEY else []),
            "pq": PROMPT_STOCK_QUICK, "pd": PROMPT_STOCK_DEEP, "filter": None,
        },
        "coin_": {
            "label": "🪙 코인 뉴스",
            "tasks": [
                ("CoinDesk",      fetch_coindesk, []),
                ("cryptonews.net",fetch_cryptonews_net, []),
                ("coincarp.com",  fetch_coincarp, []),
                ("The Block",     fetch_theblock_rss, []),
                ("cryptonews.com",fetch_cryptonews_com, []),
                ("Decrypt",       fetch_decrypt, []),
            ] + ([("CryptoPanic", fetch_cryptopanic, [CRYPTOPANIC_API_KEY])] if CRYPTOPANIC_API_KEY else []),
            "pq": PROMPT_COIN_QUICK, "pd": PROMPT_COIN_DEEP, "filter": None,
        },
        "ta_": {
            "label": "📊 BTC 기술적 분석",
            "tasks": [
                ("CoinTelegraph", fetch_cointelegraph_ta, []),
                ("AMBCrypto",     fetch_ambcrypto, []),
                ("Glassnode",     fetch_glassnode_insights, []),
                ("CryptoSlate",   fetch_cryptoslate_research, []),
                ("Coinglass",     fetch_coinglass_news, []),
                ("The Block",     fetch_theblock_research, []),
                ("CoinDesk",      fetch_coindesk_analysis, []),
                ("Reddit",        fetch_reddit_btcmarkets, []),
            ],
            "pq": PROMPT_TA_QUICK, "pd": PROMPT_TA_DEEP, "filter": filter_ta_news,
        },
        "oc_": {
            "label": "🔗 BTC 온체인 분석",
            "tasks": [
                ("CoinTelegraph", fetch_cointelegraph_ta, []),
                ("AMBCrypto",     fetch_ambcrypto, []),
                ("Glassnode",     fetch_glassnode_insights, []),
                ("CryptoSlate",   fetch_cryptoslate_research, []),
                ("Coinglass",     fetch_coinglass_news, []),
                ("The Block",     fetch_theblock_research, []),
                ("CoinDesk",      fetch_coindesk_analysis, []),
                ("Reddit",        fetch_reddit_btcmarkets, []),
            ],
            "pq": PROMPT_OC_QUICK, "pd": PROMPT_OC_DEEP, "filter": filter_onchain_news,
        },
        "m7_": {
            "label": "🏆 M7 기술적 분석",
            "tasks": [
                ("Yahoo Finance", fetch_yahoo_finance_m7, [_all_m7]),
                ("Benzinga",      fetch_benzinga_m7, [_all_m7]),
                ("MarketWatch",   fetch_marketwatch_m7, []),
                ("CNBC",          fetch_cnbc_m7, []),
                ("SeekingAlpha",  fetch_seekingalpha_m7, [_all_m7]),
                ("Reddit r/stocks", fetch_reddit_stocks_m7, []),
            ] + ([("Finnhub", fetch_finnhub_m7, [FINNHUB_API_KEY, _all_m7])] if FINNHUB_API_KEY else []),
            "pq": PROMPT_M7_QUICK, "pd": PROMPT_M7_DEEP,
            "filter": lambda nl: filter_m7_news(nl, _all_m7),
        },
    }

    with st.status("🤖 AI 종합분석 실행 중...", expanded=True) as _cstatus:
        _deep_dives = {}

        for _cp, _cfg in _auto_tasks.items():
            _cl = _cfg["label"]
            st.write(f"→ {_cl} 수집 중...")
            _raw = []
            for _, _tfn, _targs in _cfg["tasks"]:
                try:
                    _raw += _tfn(*_targs)
                except Exception:
                    pass
            _raw = dedup(_raw)
            if _cfg["filter"]:
                _raw = _cfg["filter"](_raw)
            _raw.sort(key=lambda x: x.get("published_at", ""), reverse=True)

            if not _raw:
                st.write(f"  - {_cl}: 수집된 뉴스 없음")
                continue

            st.write(f"  - {_cl}: {len(_raw)}건 수집, AI 분석 중...")
            _q, _d = "", ""
            if use_ai and ai_providers:
                if "Gemini 2.5 Pro" in ai_providers and GEMINI_API_KEY:
                    _q, _d = summarize_gemini(_raw, GEMINI_API_KEY, _cfg["pq"], _cfg["pd"])
                elif "GPT-4o-mini" in ai_providers and OPENAI_API_KEY:
                    _q, _d = summarize_openai(_raw, OPENAI_API_KEY, _cfg["pq"], _cfg["pd"])

            st.session_state[f"{_cp}news_data"] = _raw
            st.session_state[f"{_cp}summary_quick"] = _q
            st.session_state[f"{_cp}summary_deep"] = _d
            if _d:
                _deep_dives[_cp] = _d
                st.write(f"  - {_cl}: 분석 완료")
            else:
                st.write(f"  - {_cl}: 분석 결과 없음 (API 키 확인)")

        # ── BTC Treasury 수집 및 분석
        st.write("→ 🏦 BTC Treasury 수집 중...")
        _td = fetch_btc_treasuries()
        st.session_state["btc_treasury_data"] = _td
        _tnews = []
        try:
            _tnews = fetch_btc_treasury_news()
            st.session_state["btc_treasury_news_data"] = _tnews
        except Exception:
            pass
        if use_ai and "Gemini 2.5 Pro" in ai_providers and GEMINI_API_KEY:
            if not any(r.get("_error") for r in _td):
                st.write("  - 🏦 BTC Treasury: AI 분석 중...")
                _ta = summarize_btc_treasury_gemini(_td, _tnews, GEMINI_API_KEY)
                st.session_state["btc_treasury_ai_summary"] = _ta
                if _ta:
                    _deep_dives["btc_treasury_"] = _ta
                    st.write("  - 🏦 BTC Treasury: 분석 완료")

        # ── USDT APY 수집 및 분석
        st.write("→ 💵 USDT APY 수집 중...")
        _usdt_data, _aave_pid = fetch_usdt_apy()
        st.session_state["usdt_apy_data"] = _usdt_data
        _hist = {}
        if _aave_pid:
            try:
                _hist = fetch_aave_v3_usdt_history(_aave_pid)
                st.session_state["usdt_apy_aave_history"] = _hist
            except Exception:
                pass
        _unews = []
        try:
            _unews = fetch_usdt_apy_news()
            st.session_state["usdt_apy_news_data"] = _unews
        except Exception:
            pass
        if use_ai and "Gemini 2.5 Pro" in ai_providers and GEMINI_API_KEY:
            if not any(r.get("_error") for r in _usdt_data):
                st.write("  - 💵 USDT APY: AI 분석 중...")
                _ua = summarize_usdt_apy_gemini(
                    _usdt_data, _hist.get("history", []), GEMINI_API_KEY, _unews)
                st.session_state["usdt_apy_ai_summary"] = _ua
                if _ua:
                    _deep_dives["usdt_apy_"] = _ua
                    st.write("  - 💵 USDT APY: 분석 완료")

        if not _deep_dives:
            st.session_state["combined_last_run_status"] = "failed_no_analysis"
            st.session_state["combined_summary_deep"] = ""
            st.session_state["combined_provider"] = ""
            st.error("모든 모드에서 분석 생성에 실패했습니다. API 키를 확인하세요.")
            _cstatus.update(label="❌ 종합분석 실패", state="error")
            save_cache()
            return False

        _combined_result, _used_prov = "", ""
        if use_ai and ai_providers:
            if "Gemini 2.5 Pro" in ai_providers and GEMINI_API_KEY:
                st.write("🤖 Gemini 2.5 Pro 종합분석 생성 중...")
                _combined_result = summarize_combined_gemini(_deep_dives, GEMINI_API_KEY)
                _used_prov = "Gemini 2.5 Pro"
            elif "GPT-4o-mini" in ai_providers and OPENAI_API_KEY:
                st.write("🤖 GPT-4o-mini 종합분석 생성 중...")
                _combined_result = summarize_combined_openai(_deep_dives, OPENAI_API_KEY)
                _used_prov = "GPT-4o-mini"
            else:
                st.write("⚠️ AI API key is not configured.")

        st.session_state["combined_summary_deep"] = _combined_result
        st.session_state["combined_provider"] = _used_prov
        _btc_s, _stock_s = _parse_sentiment(_combined_result)
        st.session_state["btc_sentiment"] = _btc_s
        st.session_state["stock_sentiment"] = _stock_s

        if not _combined_result:
            st.session_state["combined_last_run_status"] = "failed_combined_generation"
            st.error("종합분석 생성에 실패했습니다.")
            _cstatus.update(label="❌ 종합분석 실패", state="error")
            save_cache()
            return False

        send_status = _auto_send_combined_to_discord(_combined_result, trigger_source=trigger_source)
        st.session_state["combined_last_run_status"] = send_status
        st.session_state["combined_last_run_at"] = _now_kst_dynamic().strftime("%Y-%m-%d %H:%M KST")
        _cstatus.update(label="✅ 종합분석 완료!", state="complete")
        save_cache()
        return True


def fetch_finnhub(api_key: str) -> list:
    if not api_key: return []
    try:
        r = requests.get("https://finnhub.io/api/v1/news",
            params={"category": "general", "token": api_key}, headers=HEADERS, timeout=15)
        r.raise_for_status(); data = r.json()
    except Exception: return []
    results = []
    for item in data[:30]:
        try:
            dt = datetime.datetime.utcfromtimestamp(item.get("datetime", 0))
            pub = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            if not is_recent(pub, 1): continue
            results.append(make_item(title=item.get("headline",""), url=item.get("url",""),
                source=item.get("source","Finnhub"), published_at=pub, description=item.get("summary","")))
        except Exception: continue
    return results


def fetch_mktnews() -> list:
    results = []
    try:
        import time as _time
        t = int(_time.time() * 1000)
        r = requests.get(f"https://static.mktnews.net/json/flash/en.json?t={t}", headers=HEADERS, timeout=15)
        if r.status_code != 200: return []
        for item in r.json()[:50]:
            try:
                content     = (item.get("data") or {}).get("content","").strip()
                title_field = (item.get("data") or {}).get("title","").strip()
                title = title_field if title_field else content[:120]
                if not title: continue
                pub = item.get("time","")
                if pub and not is_recent(pub, 1): continue
                item_id = item.get("id","")
                url  = f"https://mktnews.com/flashDetail.html?id={item_id}" if item_id else ""
                desc = content if title_field and content != title else ""
                results.append(make_item(title=title, url=url, source="MKT News", published_at=pub, description=desc))
            except Exception: continue
    except Exception: pass
    return results


def fetch_mni_markets() -> list:
    results = []
    try:
        r = requests.get("https://www.mnimarkets.com/articles", headers=HEADERS, timeout=15)
        if r.status_code != 200:
            r = requests.get("https://www.mnimarkets.com/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser"); seen_urls = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/articles/" not in href: continue
            url = href if href.startswith("http") else "https://www.mnimarkets.com" + href
            if url in seen_urls: continue
            seen_urls.add(url)
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                parent = a.find_parent()
                if parent: title = parent.get_text(separator=" ", strip=True)[:200]
            if not title or len(title) < 10: continue
            results.append(make_item(title=title[:200], url=url, source="MNI Markets"))
            if len(results) >= 30: break
    except Exception: pass
    return results


def fetch_rss_feed(rss_url: str, source_name: str) -> list:
    results = []
    try:
        r = requests.get(rss_url, headers=HEADERS, timeout=15)
        if r.status_code != 200: return []
        soup = BeautifulSoup(r.text, "xml")
        for item in soup.find_all("item") or soup.find_all("entry"):
            te = item.find("title"); le = item.find("link")
            pe = item.find("pubDate") or item.find("published"); de = item.find("description") or item.find("summary")
            title = te.get_text(strip=True) if te else ""
            link  = le.get_text(strip=True) if le else ""
            pub_raw = pe.get_text(strip=True) if pe else ""
            desc = (BeautifulSoup(de.get_text(strip=True), "html.parser").get_text(strip=True)[:200] if de else "")
            if not title: continue
            pub_iso = parse_rss_dt(pub_raw)
            if pub_iso and not is_recent(pub_iso, 1): continue
            results.append(make_item(title=title, url=link, source=source_name, published_at=pub_iso, description=desc))
    except Exception: pass
    return results


# ══════════════════════════════════════════════════
# ── 코인 뉴스 스크래퍼 ────────────────────────────
# ══════════════════════════════════════════════════
def fetch_cryptopanic(api_key: str) -> list:
    if not api_key: return []
    try:
        response = requests.get("https://cryptopanic.com/api/developer/v2/posts/",
            params={"auth_token": api_key, "public":"true","kind":"news","regions":"en"},
            headers=HEADERS, timeout=15)
        if response.status_code in (403,429): return []
        response.raise_for_status(); data = response.json()
    except Exception: return []
    results = []
    for item in data.get("results",[]):
        pub = item.get("published_at","")
        if not is_recent(pub, 1): continue
        results.append(make_item(title=item.get("title",""), source="CryptoPanic",
            published_at=pub, description=item.get("description","") or ""))
    return results


def fetch_coindesk() -> list:
    try:
        response = requests.get("https://www.coindesk.com/latest-crypto-news", headers=HEADERS, timeout=15)
        response.raise_for_status(); soup = BeautifulSoup(response.text, "html.parser")
    except Exception: return []
    results = []; seen = set()
    for selector in ["a[href*='/markets/']","a[href*='/business/']","a[href*='/tech/']","a[href*='/policy/']"]:
        for link in soup.select(selector):
            href = link.get("href",""); title = link.get_text(strip=True)
            if not title or len(title) < 15 or href in seen: continue
            seen.add(href)
            full_url = f"https://www.coindesk.com{href}" if href.startswith("/") else href
            pub = find_time_in_parents(link)
            if pub and not is_recent(pub, 1): continue
            results.append(make_item(title=title, url=full_url, source="CoinDesk", published_at=pub))
    return results


def fetch_cryptonews_net() -> list:
    results = []; seen = set()
    for url in ["https://cryptonews.net/news/bitcoin/","https://cryptonews.net/news/ethereum/","https://cryptonews.net/"]:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status(); soup = BeautifulSoup(response.text, "html.parser")
        except Exception: continue
        for item in soup.select(".news-item"):
            link = item.find("a", href=True)
            if not link: continue
            href = link["href"]; full_url = f"https://cryptonews.net{href}" if href.startswith("/") else href
            if full_url in seen: continue
            seen.add(full_url)
            title_el = item.select_one(".news-item__title, h2, h3, h4, .title")
            title = title_el.get_text(strip=True) if title_el else item.get_text(separator=" ",strip=True)[:120]
            time_el = item.find("time"); pub = time_el.get("datetime","") if time_el else ""
            if pub and not is_recent(pub, 1): continue
            source_el = item.select_one(".news-item__source, .source")
            source = source_el.get_text(strip=True) if source_el else "cryptonews.net"
            results.append(make_item(title=title, url=full_url, source=source or "cryptonews.net", published_at=pub))
    return results


def fetch_coincarp() -> list:
    results = []; seen = set()
    for url in ["https://www.coincarp.com/news/bitcoin/","https://www.coincarp.com/news/ethereum/","https://www.coincarp.com/news/"]:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status(); soup = BeautifulSoup(response.text, "html.parser")
        except Exception: continue
        for link in soup.find_all("a", href=True):
            href = link.get("href","")
            if not href.startswith("http") or "coincarp.com" in href: continue
            raw = link.get_text(strip=True)
            title = re.sub(r"^\d+\s*(min|mins|hour|hours|sec|secs|day|days)\s*(Ago|ago)\s*","",raw).strip()
            if not title or len(title) < 15 or href in seen: continue
            seen.add(href)
            match = re.search(r"(\d+)\s*(min|mins|hour|hours)", raw); pub = ""
            if match:
                value = int(match.group(1))
                delta = datetime.timedelta(minutes=value) if "min" in match.group(2) else datetime.timedelta(hours=value)
                pub = (NOW_UTC - delta).strftime("%Y-%m-%dT%H:%M:%SZ")
            domain = re.search(r"https?://(?:www\.)?([^/]+)", href)
            source = domain.group(1) if domain else "coincarp"
            results.append(make_item(title=title, url=href, source=source, published_at=pub))
    return results


def fetch_theblock_rss() -> list:
    results = []
    for rss_url in ["https://www.theblock.co/rss.xml","https://www.theblock.co/feeds/rss.xml"]:
        try:
            response = requests.get(rss_url, headers=HEADERS, timeout=15)
            if response.status_code != 200: continue
            soup = BeautifulSoup(response.text, "xml")
        except Exception: continue
        for item in soup.find_all("item") or soup.find_all("entry"):
            te = item.find("title"); le = item.find("link")
            pe = item.find("pubDate") or item.find("published") or item.find("updated")
            de = item.find("description") or item.find("summary")
            title = te.get_text(strip=True) if te else ""
            link  = le.get_text(strip=True) if le else ""
            pub_iso = parse_rss_dt(pe.get_text(strip=True) if pe else "")
            desc = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
            if not title: continue
            if pub_iso and not is_recent(pub_iso, 1): continue
            results.append(make_item(title=title, url=link, source="The Block", published_at=pub_iso, description=desc))
        if results: break
    return results


def fetch_cryptonews_com() -> list:
    results = []; seen = set()
    for url in ["https://cryptonews.com/news/","https://cryptonews.com/news/bitcoin-news/","https://cryptonews.com/news/ethereum-news/"]:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status(); soup = BeautifulSoup(response.text, "html.parser")
        except Exception: continue
        for link in soup.find_all("a", href=True):
            href = link.get("href","")
            full_url = f"https://cryptonews.com{href}" if href.startswith("/") else href
            if not re.search(r"cryptonews\.com/news/[a-z]", full_url): continue
            title = link.get_text(strip=True)
            if not title or len(title) < 15 or full_url in seen: continue
            seen.add(full_url)
            pub = find_time_in_parents(link)
            if pub and not is_recent(pub, 1): continue
            results.append(make_item(title=title, url=full_url, source="cryptonews.com", published_at=pub))
    return results


def fetch_decrypt() -> list:
    try:
        response = requests.get("https://decrypt.co/feed", headers=HEADERS, timeout=15)
        if response.status_code != 200: return []
        soup = BeautifulSoup(response.text, "xml")
    except Exception: return []
    results = []
    for item in soup.find_all("item"):
        te = item.find("title"); le = item.find("link")
        pe = item.find("pubDate"); de = item.find("description")
        title = te.get_text(strip=True) if te else ""
        link  = le.get_text(strip=True) if le else ""
        pub_iso = parse_rss_dt(pe.get_text(strip=True) if pe else "")
        desc = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
        if not title: continue
        if pub_iso and not is_recent(pub_iso, 1): continue
        results.append(make_item(title=title, url=link, source="Decrypt", published_at=pub_iso, description=desc))
    return results


# ══════════════════════════════════════════════════
# ── BTC 분석 스크래퍼 ─────────────────────────────
# ══════════════════════════════════════════════════
def _btc_rss(rss_urls, source_name, days=5) -> list:
    """공통 BTC RSS 수집 헬퍼"""
    results, seen = [], set()
    for rss_url in rss_urls:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
        except Exception: continue
        for item in soup.find_all("item") or soup.find_all("entry"):
            te = item.find("title"); le = item.find("link")
            pe = item.find("pubDate") or item.find("published")
            de = item.find("description") or item.find("summary")
            title = te.get_text(strip=True) if te else ""
            link  = (le.get("href") or le.get_text(strip=True)) if le else ""
            pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
            desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
            if not title or link in seen or not is_recent(pub, days): continue
            seen.add(link)
            results.append(make_item(title=title, url=link, source=source_name, published_at=pub, description=desc))
        if results: break
    return results


def fetch_cointelegraph_ta() -> list:
    return _btc_rss([
        "https://cointelegraph.com/rss/tag/bitcoin-price",
        "https://cointelegraph.com/rss/tag/technical-analysis",
        "https://cointelegraph.com/rss/tag/bitcoin",
    ], "CoinTelegraph")


def fetch_ambcrypto() -> list:
    return _btc_rss(["https://ambcrypto.com/feed/","https://ambcrypto.com/category/bitcoin/feed/"], "AMBCrypto")


def fetch_glassnode_insights() -> list:
    results, seen = [], set()
    for rss_url in ["https://insights.glassnode.com/rss/","https://insights.glassnode.com/feed/"]:
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
        except Exception: continue
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
                    results.append(make_item(title=title, url=full_url, source="Glassnode"))
        except Exception: pass
    return results


def fetch_cryptoslate_research() -> list:
    return _btc_rss([
        "https://cryptoslate.com/feed/",
        "https://cryptoslate.com/category/research/feed/",
        "https://cryptoslate.com/category/bitcoin/feed/",
    ], "CryptoSlate")


def fetch_coinglass_news() -> list:
    results, seen = [], set()
    try:
        r = requests.get("https://www.coinglass.com/blog", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not any(x in href for x in ["/blog/","/news/","/analysis/"]): continue
                full_url = href if href.startswith("http") else f"https://www.coinglass.com{href}"
                if full_url in seen: continue
                title = a.get_text(strip=True)
                if not title or len(title) < 15: continue
                seen.add(full_url)
                results.append(make_item(title=title, url=full_url, source="Coinglass"))
    except Exception: pass
    return results


def fetch_theblock_research() -> list:
    return _btc_rss(["https://www.theblock.co/rss.xml","https://www.theblock.co/feeds/rss.xml"], "The Block")


def fetch_reddit_btcmarkets() -> list:
    results, seen = [], set()
    rh = {**HEADERS, "Accept":"application/json"}
    for sub in ["BitcoinMarkets","CryptoCurrency"]:
        for sort in ["hot","top"]:
            try:
                r = requests.get(f"https://www.reddit.com/r/{sub}/{sort}.json",
                    headers=rh, params={"limit":25,"t":"day"}, timeout=15)
                if r.status_code != 200: continue
                for post in r.json().get("data",{}).get("children",[]):
                    p = post.get("data",{}); title = p.get("title","")
                    permalink = "https://www.reddit.com" + p.get("permalink","")
                    created_utc = p.get("created_utc",0); selftext = p.get("selftext","")[:200]
                    flair = p.get("link_flair_text",""); score = p.get("score",0)
                    if not title or permalink in seen or score < 5: continue
                    pub = datetime.datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%dT%H:%M:%SZ") if created_utc else ""
                    if pub and not is_recent(pub, 3): continue
                    seen.add(permalink)
                    full_title = f"[{flair}] {title}" if flair else f"[r/{sub}] {title}"
                    results.append(make_item(title=full_title, url=permalink,
                        source=f"Reddit r/{sub}", published_at=pub, description=selftext))
            except Exception: continue
    return results


def fetch_coindesk_analysis() -> list:
    return _btc_rss([
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
        "https://www.coindesk.com/feed",
    ], "CoinDesk")


# ══════════════════════════════════════════════════
# ── M7 스크래퍼 ───────────────────────────────────
# ══════════════════════════════════════════════════
def _detect_ticker(text: str) -> str:
    t = text.upper()
    for ticker, info in M7_STOCKS.items():
        if ticker in t or info["name"].upper() in t:
            return ticker
    return ""


def _m7_rss_parse(soup, ticker="", detect=False, days=5) -> list:
    results, seen = [], set()
    for item in soup.find_all("item"):
        te = item.find("title"); le = item.find("link")
        pe = item.find("pubDate"); de = item.find("description")
        title = te.get_text(strip=True) if te else ""
        link  = le.get_text(strip=True) if le else ""
        pub   = parse_rss_dt(pe.get_text(strip=True) if pe else "")
        desc  = BeautifulSoup(de.get_text(strip=True) if de else "", "html.parser").get_text()[:200]
        if not title or link in seen or not is_recent(pub, days): continue
        if detect:
            ticker = _detect_ticker((title + " " + desc).upper())
            if not ticker: continue
        seen.add(link)
        results.append(make_item(title=title, url=link, source="", published_at=pub, description=desc, ticker=ticker))
    return results


def fetch_yahoo_finance_m7(tickers: list) -> list:
    results, seen = [], set()
    for ticker in tickers:
        try:
            r = requests.get(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
                headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            items = _m7_rss_parse(soup, ticker=ticker)
            for it in items: it["source"] = "Yahoo Finance"
            results.extend(it for it in items if it["url"] not in seen and not seen.add(it["url"]))
        except Exception: continue
    return results


def fetch_benzinga_m7(tickers: list) -> list:
    results, seen = [], set()
    for ticker in tickers:
        try:
            r = requests.get(f"https://www.benzinga.com/stock/{ticker.lower()}/feed", headers=HEADERS, timeout=15)
            if r.status_code != 200:
                r = requests.get(f"https://feeds.benzinga.com/benzinga/{ticker.lower()}", headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            items = _m7_rss_parse(soup, ticker=ticker)
            for it in items: it["source"] = "Benzinga"
            results.extend(it for it in items if it["url"] not in seen and not seen.add(it["url"]))
        except Exception: continue
    return results


def fetch_marketwatch_m7() -> list:
    results, seen = [], set()
    for rss_url in ["http://feeds.marketwatch.com/marketwatch/topstories/",
                    "http://feeds.marketwatch.com/marketwatch/technology/"]:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            items = _m7_rss_parse(soup, detect=True)
            for it in items:
                it["source"] = "MarketWatch"
                if it["url"] not in seen:
                    seen.add(it["url"]); results.append(it)
        except Exception: continue
    return results


def fetch_cnbc_m7() -> list:
    results, seen = [], set()
    for rss_url in ["https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=120000000",
                    "https://www.cnbc.com/id/15839135/device/rss/rss.html"]:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            items = _m7_rss_parse(soup, detect=True)
            for it in items:
                it["source"] = "CNBC"
                if it["url"] not in seen:
                    seen.add(it["url"]); results.append(it)
        except Exception: continue
    return results


def fetch_seekingalpha_m7(tickers: list) -> list:
    results, seen = [], set()
    for ticker in tickers:
        try:
            r = requests.get(f"https://seekingalpha.com/api/sa/combined/{ticker}.xml", headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "xml")
            items = _m7_rss_parse(soup, ticker=ticker)
            for it in items:
                it["source"] = "SeekingAlpha"
                if it["url"] not in seen:
                    seen.add(it["url"]); results.append(it)
        except Exception: continue
    return results


def fetch_reddit_stocks_m7() -> list:
    results, seen = [], set()
    rh = {**HEADERS, "Accept":"application/json"}
    for sub in ["stocks","investing","wallstreetbets"]:
        try:
            r = requests.get(f"https://www.reddit.com/r/{sub}/hot.json",
                headers=rh, params={"limit":30}, timeout=15)
            if r.status_code != 200: continue
            for post in r.json().get("data",{}).get("children",[]):
                p = post.get("data",{}); title = p.get("title","")
                permalink = "https://www.reddit.com" + p.get("permalink","")
                created_utc = p.get("created_utc",0); selftext = p.get("selftext","")[:200]
                score = p.get("score",0)
                if not title or permalink in seen or score < 20: continue
                ticker = _detect_ticker((title + " " + selftext).upper())
                if not ticker: continue
                pub = datetime.datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%dT%H:%M:%SZ") if created_utc else ""
                if pub and not is_recent(pub, 3): continue
                seen.add(permalink)
                results.append(make_item(title=f"[r/{sub}] {title}", url=permalink,
                    source=f"Reddit r/{sub}", published_at=pub, description=selftext, ticker=ticker))
        except Exception: continue
    return results


def fetch_finnhub_m7(api_key: str, tickers: list) -> list:
    if not api_key: return []
    results, seen = [], set()
    for ticker in tickers:
        try:
            r = requests.get("https://finnhub.io/api/v1/company-news",
                params={"symbol":ticker,"from":YESTERDAY_STR,"to":TODAY_STR,"token":api_key},
                headers=HEADERS, timeout=15)
            if r.status_code != 200: continue
            for item in r.json()[:15]:
                try:
                    dt = datetime.datetime.utcfromtimestamp(item.get("datetime",0))
                    pub = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    url = item.get("url",""); title = item.get("headline","")
                    if not title or url in seen: continue
                    seen.add(url)
                    results.append(make_item(title=title, url=url,
                        source=item.get("source","Finnhub"), published_at=pub,
                        description=item.get("summary","")[:200], ticker=ticker))
                except Exception: continue
        except Exception: continue
    return results


# ══════════════════════════════════════════════════
# ── 필터링 ────────────────────────────────────────
# ══════════════════════════════════════════════════
def _tag(item, kws_list):
    combined = (item["title"] + " " + item.get("description","")).lower()
    return [kw for kw in kws_list if kw in combined]


def filter_ta_news(news_list):
    out = []
    for item in news_list:
        hits = _tag(item, TA_KEYWORDS)
        if hits:
            item = dict(item); oc = _tag(item, ONCHAIN_KEYWORDS)
            item["is_ta"] = True; item["is_onchain"] = bool(oc)
            item["matched_keywords"] = (hits+oc)[:8]; out.append(item)
    return out


def filter_onchain_news(news_list):
    out = []
    for item in news_list:
        hits = _tag(item, ONCHAIN_KEYWORDS)
        if hits:
            item = dict(item); ta = _tag(item, TA_KEYWORDS)
            item["is_onchain"] = True; item["is_ta"] = bool(ta)
            item["matched_keywords"] = (hits+ta)[:8]; out.append(item)
    return out


def filter_m7_news(news_list, selected_tickers):
    out = []
    for item in news_list:
        if item.get("ticker") and item["ticker"] not in selected_tickers: continue
        if not item.get("ticker"):
            ticker = _detect_ticker((item["title"] + " " + item.get("description","")).upper())
            if not ticker or ticker not in selected_tickers: continue
            item = dict(item); item["ticker"] = ticker
        ta_hits = _tag(item, M7_TA_KEYWORDS); fund_hits = _tag(item, M7_FUND_KEYWORDS)
        if ta_hits or fund_hits:
            item = dict(item)
            item["is_ta"] = bool(ta_hits); item["is_fund"] = bool(fund_hits)
            item["matched_keywords"] = (ta_hits+fund_hits)[:8]; out.append(item)
    return out


# ══════════════════════════════════════════════════
# ── BTC Treasury & USDT APY 수집 ─────────────────
# ══════════════════════════════════════════════════
DEFILLAMA_POOLS_URL = "https://yields.llama.fi/pools"
BTC_TREASURIES_URL  = "https://bitbo.io/treasuries/"

_SCRAPE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}
_API_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _fmt_usd(n):
    if n is None or n != n: return "N/A"
    if abs(n) >= 1e12: return f"${n/1e12:,.2f}T"
    if abs(n) >= 1e9:  return f"${n/1e9:,.2f}B"
    if abs(n) >= 1e6:  return f"${n/1e6:,.2f}M"
    if abs(n) >= 1e3:  return f"${n/1e3:,.1f}K"
    return f"${n:,.0f}"



_SVG_COPY = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>'
    '</svg>'
)


def _copy_btn(text: str) -> None:
    js_str = json.dumps(text)
    components.html(f"""
<div style="text-align:right;margin:0;padding:0">
  <button id="copybtn" style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:6px;
    padding:4px 10px;cursor:pointer;color:#6B7280;font-size:13px;font-family:sans-serif;
    display:inline-flex;align-items:center;gap:5px">
    {_SVG_COPY}&nbsp;복사
  </button>
</div>
<script>
document.getElementById('copybtn').addEventListener('click', function() {{
  var btn = this;
  var txt = {js_str};
  function done() {{
    btn.innerHTML = '&#10003;&nbsp;복사됨';
    btn.style.color = '#10B981'; btn.style.borderColor = '#10B981';
    setTimeout(function() {{
      btn.innerHTML = '{_SVG_COPY}&nbsp;복사';
      btn.style.color = '#6B7280'; btn.style.borderColor = '#E5E7EB';
    }}, 1500);
  }}
  var cb = (window.parent && window.parent.navigator && window.parent.navigator.clipboard)
    ? window.parent.navigator.clipboard : (navigator.clipboard || null);
  if (cb && cb.writeText) {{
    cb.writeText(txt).then(done).catch(function() {{ fallback(txt); }});
  }} else {{ fallback(txt); }}
  function fallback(t) {{
    var doc = (window.parent && window.parent.document) ? window.parent.document : document;
    var ta = doc.createElement('textarea');
    ta.value = t; ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0';
    doc.body.appendChild(ta); ta.focus(); ta.select();
    try {{ doc.execCommand('copy'); done(); }} catch(e) {{ alert('복사 실패'); }}
    doc.body.removeChild(ta);
  }}
}});
</script>
""", height=38)


def fetch_btc_treasuries() -> list:
    """bitbo.io/treasuries/ 스크래핑 → list of dicts
    컬럼: Rank | Entity | Country | # of BTC | Value Today | % of 21m
    페이지에 table이 10개 있으므로 가장 행이 많은 tbody(253행)를 대상으로 파싱.
    """
    try:
        resp = requests.get(BTC_TREASURIES_URL, headers=_SCRAPE_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return [{"_error": str(e)}]

    soup = BeautifulSoup(resp.text, "html.parser")

    # 가장 많은 행을 가진 tbody = 메인 253행 테이블
    all_tbodies = soup.find_all("tbody")
    if not all_tbodies:
        return [{"_error": "테이블 미검출"}]
    main_tbody = max(all_tbodies, key=lambda tb: len(tb.find_all("tr")))

    # 부모 table 에서 thead 헤더 추출
    parent_table = main_tbody.find_parent("table")
    thead = parent_table.find("thead") if parent_table else None
    if thead:
        hdrs = [th.get_text(strip=True) for th in thead.find_all("th")]
    else:
        hdrs = ["Rank", "Entity", "Country", "# of BTC", "Value Today", "% of 21m"]

    def _td_value(td) -> str:
        # 국기 이미지 → data-tooltip 속성(국가 코드)으로 대체
        img = td.find("img")
        if img and img.get("data-tooltip"):
            return img["data-tooltip"]
        return td.get_text(strip=True)

    result = []
    for tr in main_tbody.find_all("tr"):
        cells = [_td_value(td) for td in tr.find_all("td")]
        if len(cells) < 2:
            continue
        result.append({hdrs[i] if i < len(hdrs) else f"col_{i}": v
                        for i, v in enumerate(cells)})
    return result if result else [{"_error": "파싱된 행 없음"}]


_TREASURY_KEYWORDS = frozenset({
    "microstrategy", "mstr", "saylor", "strategy",
    "bitcoin treasury", "btc treasury", "corporate bitcoin",
    "institutional bitcoin", "bitcoin reserve", "btc reserve",
    "metaplanet", "semler", "twenty one", "nakamoto",
    "bitcoin holding", "corporate btc", "bitcoin balance sheet",
})


def _filter_treasury(news_list: list) -> list:
    return [
        i for i in news_list
        if any(k in (i.get("title", "") + " " + i.get("description", "")).lower()
               for k in _TREASURY_KEYWORDS)
    ]


def fetch_btc_treasury_news() -> list:
    """BTC Treasury 관련 뉴스 수집 (7일)"""
    collected = []

    # Google News RSS
    for q in ["bitcoin treasury corporate", "microstrategy bitcoin"]:
        try:
            url = f"https://news.google.com/rss/search?q={q.replace(' ', '+')}&hl=en&gl=US&ceid=US:en"
            collected.extend(_btc_rss([url], "Google News", days=7))
        except Exception:
            pass

    # Yahoo Finance MSTR
    try:
        collected.extend(fetch_rss_feed(
            "https://finance.yahoo.com/rss/headline?s=MSTR", "Yahoo Finance"))
    except Exception:
        pass

    # CoinTelegraph — keyword filter
    try:
        items = _btc_rss([
            "https://cointelegraph.com/rss/tag/bitcoin",
            "https://cointelegraph.com/rss",
        ], "CoinTelegraph", days=7)
        collected.extend(_filter_treasury(items))
    except Exception:
        pass

    # CoinDesk — keyword filter
    try:
        collected.extend(_filter_treasury(fetch_coindesk()))
    except Exception:
        pass

    # The Block
    try:
        items = _btc_rss(["https://www.theblock.co/rss/all.xml"], "The Block", days=7)
        collected.extend(_filter_treasury(items))
    except Exception:
        pass

    result = dedup(collected)
    result.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return result[:30]


def summarize_btc_treasury_gemini(holdings: list, news: list, api_key: str) -> str:
    """BTC Treasury 보유량 + 뉴스 AI 분석"""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return ""

    valid = [r for r in holdings if not r.get("_error")][:20]
    holdings_text = "\n".join(
        f"{i + 1}. " + " | ".join(f"{k}: {v}" for k, v in r.items() if not k.startswith("_") and v)
        for i, r in enumerate(valid)
    ) if valid else "보유 데이터 없음"

    news_text = "\n".join(
        f"- [{item.get('source', '')}] {item.get('title', '')}"
        + (f" — {item.get('description', '')[:120]}" if item.get("description") else "")
        for item in news[:20]
    ) if news else "관련 뉴스 없음"

    prompt = (
        "당신은 비트코인 기관 투자 및 기업 재무 전문 애널리스트입니다.\n"
        "아래 데이터를 바탕으로 BTC 기업 보유 현황과 최근 동향을 분석해 주세요.\n\n"
        f"## 상위 BTC 보유 기업 현황\n{holdings_text}\n\n"
        f"## 최근 관련 뉴스 (7일)\n{news_text}\n\n"
        "다음 항목을 포함해 한국어로 분석하세요:\n"
        "1. 📊 전체 현황 요약 (총 보유량 추정, 기업 수, 시장 의미)\n"
        "2. 🏆 주요 보유 기업 분석 (투자 배경, 전략)\n"
        "3. 📰 최근 뉴스 핵심 동향\n"
        "4. 📈 기관 채택 트렌드 및 향후 전망\n"
        "5. ⚠️ 리스크 및 주의사항\n\n"
        "각 섹션은 명확히 구분하고, 객관적 사실에 근거해 분석하세요."
    )

    client = genai.Client(api_key=api_key)
    try:
        return _gemini_generate(client, types, prompt, temperature=0.3, max_output_tokens=8000)
    except Exception as e:
        return f"AI 분석 오류: {e}"


def fetch_usdt_apy(min_tvl: float = 1_000_000, max_apy: float = 50, top_n: int = 50) -> tuple:
    """DefiLlama 무료 API → (USDT 상위 풀 list, aave_v3_eth_pool_id str)"""
    _h = _API_HEADERS
    try:
        resp = requests.get(DEFILLAMA_POOLS_URL, headers=_h, timeout=30)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        return [{"_error": str(e)}], ""

    pools = raw.get("data", raw) if isinstance(raw, dict) else raw
    result = []
    aave_pool_id = ""
    for p in pools:
        sym = (p.get("symbol") or "").upper()
        if sym != "USDT" or "-" in sym:
            continue
        # Aave V3 Ethereum USDT pool_id 기록
        if (not aave_pool_id
                and (p.get("project") or "").lower() == "aave-v3"
                and (p.get("chain") or "").lower() == "ethereum"):
            aave_pool_id = p.get("pool") or ""
        tvl = p.get("tvlUsd") or 0
        apy = p.get("apy") or 0
        if tvl < min_tvl or apy <= 0 or apy > max_apy:
            continue
        apr = 365 * ((1 + apy / 100) ** (1 / 365) - 1) * 100
        result.append({
            "프로토콜":       (p.get("project") or "").replace("-", " ").title(),
            "체인":           p.get("chain") or "",
            "풀메타":         p.get("poolMeta") or "",
            "TVL($)":         round(tvl),
            "APY(%)":         round(apy, 2),
            "APR(%)":         round(apr, 2),
            "Base APY(%)":    round(p.get("apyBase") or 0, 2),
            "Reward APY(%)":  round(p.get("apyReward") or 0, 2),
        })
    result.sort(key=lambda x: x["APY(%)"], reverse=True)
    return (result[:top_n] if result else [{"_error": "조건에 맞는 풀 없음"}]), aave_pool_id


def fetch_aave_v3_usdt_history(pool_id: str) -> dict:
    """DefiLlama chart API → Aave V3 Ethereum USDT 1년 APY/TVL 히스토리"""
    if not pool_id:
        return {"error": "pool_id 없음"}
    _h = _API_HEADERS
    try:
        resp = requests.get(f"https://yields.llama.fi/chart/{pool_id}", headers=_h, timeout=30)
        resp.raise_for_status()
        raw_data = resp.json().get("data", [])
    except Exception as e:
        return {"error": str(e)}

    cutoff = datetime.datetime(2023, 1, 1)
    history = []
    for item in raw_data:
        try:
            ts_str = item.get("timestamp", "")
            ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
            if ts < cutoff:
                continue
            history.append({
                "date":    ts.strftime("%Y-%m-%d"),
                "apy":     round(item.get("apy") or 0, 4),
                "apyBase": round(item.get("apyBase") or 0, 4),
                "tvlUsd":  round(item.get("tvlUsd") or 0),
            })
        except Exception:
            continue
    return {"pool_id": pool_id, "history": history}


_USDT_APY_KEYWORDS = frozenset({
    "usdt", "tether", "stablecoin yield", "stablecoin apy", "defi yield",
    "aave", "compound", "curve finance", "lending rate", "stable apy",
    "defi lending", "usdt apy", "usdt yield", "stable yield",
    "yield farming", "liquidity pool usdt",
})


def fetch_usdt_apy_news() -> list:
    """USDT/DeFi 수익률 관련 뉴스 수집 (7일)"""
    def _kw_filter(items):
        return [
            i for i in items
            if any(k in (i.get("title", "") + " " + i.get("description", "")).lower()
                   for k in _USDT_APY_KEYWORDS)
        ]

    collected = []

    # Google News RSS
    for q in ["USDT DeFi yield APY", "stablecoin lending rate DeFi"]:
        try:
            url = f"https://news.google.com/rss/search?q={q.replace(' ', '+')}&hl=en&gl=US&ceid=US:en"
            collected.extend(_btc_rss([url], "Google News", days=7))
        except Exception:
            pass

    # Yahoo Finance — stablecoin/DeFi keyword filter
    try:
        collected.extend(_kw_filter(
            fetch_rss_feed("https://finance.yahoo.com/news/rssindex", "Yahoo Finance")))
    except Exception:
        pass

    # CoinTelegraph
    try:
        items = _btc_rss([
            "https://cointelegraph.com/rss/tag/defi",
            "https://cointelegraph.com/rss",
        ], "CoinTelegraph", days=7)
        collected.extend(_kw_filter(items))
    except Exception:
        pass

    # CoinDesk
    try:
        collected.extend(_kw_filter(fetch_coindesk()))
    except Exception:
        pass

    result = dedup(collected)
    result.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return result[:25]


def summarize_usdt_apy_gemini(pools: list, history: list, api_key: str,
                              news: list | None = None) -> str:
    """USDT APY 데이터 + Aave V3 히스토리 + 뉴스를 Gemini로 분석."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return ""
    top_pools_text = "\n".join(
        f"{i+1}. {p['프로토콜']} ({p['체인']}) — APY: {p['APY(%)']}%, TVL: {_fmt_usd(p['TVL($)'])}"
        for i, p in enumerate(pools[:20])
    )
    aave_text = ""
    if history:
        cur, old = history[-1], history[0]
        apy_chg  = cur["apy"] - old["apy"]
        tvl_chg  = (cur["tvlUsd"] - old["tvlUsd"]) / old["tvlUsd"] * 100 if old["tvlUsd"] else 0
        recent90 = history[-90:]
        avg90    = sum(h["apy"] for h in recent90) / len(recent90) if recent90 else 0
        aave_text = (
            f"Aave V3 Ethereum USDT (2023.01~현재):\n"
            f"- 현재 APY: {cur['apy']:.2f}%  /  TVL: {_fmt_usd(cur['tvlUsd'])}\n"
            f"- 시작 APY: {old['apy']:.2f}%  /  TVL: {_fmt_usd(old['tvlUsd'])}\n"
            f"- APY 변화: {apy_chg:+.2f}%p  /  TVL 변화: {tvl_chg:+.1f}%\n"
            f"- 최근 90일 평균 APY: {avg90:.2f}%"
        )
    news_text = ""
    if news:
        news_text = "\n## 최근 관련 뉴스 (7일)\n" + "\n".join(
            f"- [{item.get('source', '')}] {item.get('title', '')}"
            + (f" — {item.get('description', '')[:100]}" if item.get("description") else "")
            for item in news[:15]
        )
    prompt = (
        f"당신은 DeFi 수익률 및 암호화폐 시장 상관관계 전문 애널리스트입니다.\n"
        f"분석 기준일: {TODAY_STR}\n\n"
        f"## USDT 상위 풀 (APY 순)\n{top_pools_text}\n\n"
        f"## Aave V3 Ethereum USDT 추세 (2023.01~현재)\n{aave_text}\n"
        f"{news_text}\n\n"
        "위 데이터를 바탕으로 아래 항목을 한국어로 심층 분석해주세요.\n\n"
        "1. 📊 현재 USDT DeFi 수익률 환경\n"
        "   - 전체 수준·분포 평가, 전통금융(MMF·국채) 대비 매력도\n\n"
        "2. 📈 Aave V3 APY/TVL 장기 추세 해석\n"
        "   - 주요 변곡점과 배경 요인, 현재 국면 진단\n\n"
        "3. 🔗 USDT APY와 BTC 가격의 상관관계 심층분석\n"
        "   - BTC 강세장/약세장 국면별 USDT DeFi 수익률 패턴\n"
        "   - APY 급등·급락이 BTC 가격에 선행·동행·후행하는 메커니즘\n"
        "     (예: 강세장 → 레버리지 수요 증가 → USDT 차입 수요 상승 → APY↑)\n"
        "   - Aave TVL 변화와 BTC 시장 심리의 연관성\n"
        "   - 현재 APY 수준이 BTC 시장 방향에 시사하는 신호\n\n"
        "4. 🎯 주목할 고수익 풀과 프로토콜별 리스크\n\n"
        "5. 📰 최근 뉴스 핵심 동향\n\n"
        "6. 💡 투자자 전략적 시사점\n"
        "   - USDT APY 수준별 최적 자산배분 전략\n"
        "   - BTC 가격 국면에 따른 DeFi 수익률 활용법"
    )
    client = genai.Client(api_key=api_key)
    try:
        return _gemini_generate(client, types, prompt, temperature=0.35, max_output_tokens=8000)
    except Exception as e:
        return f"[Gemini 오류: {e}]"


# ══════════════════════════════════════════════════
# ── 세션 초기화 ───────────────────────────────────
# ══════════════════════════════════════════════════
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis_cache.json")


def load_cache():
    """파일 캐시 → 세션 스테이트로 복원 (앱 시작 시 1회)"""
    if st.session_state.get("_cache_loaded"):
        return
    try:
        import json
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k not in st.session_state:
                st.session_state[k] = v
    except FileNotFoundError:
        pass
    except Exception:
        pass
    st.session_state["_cache_loaded"] = True


def save_cache():
    """세션 스테이트 → 파일 캐시로 저장"""
    try:
        import json
        keys_to_save = []
        for pfx in ("stock_","coin_","ta_","oc_","m7_","combined_"):
            for k in ("news_data","source_stats","summary_quick","summary_deep","provider"):
                keys_to_save.append(f"{pfx}{k}")
        keys_to_save += [
            "combined_summary_deep",
            "combined_provider",
            "discord_last_sent",
            "discord_last_sent_date",
            "combined_last_run_at",
            "combined_last_run_status",
            "btc_sentiment",
            "stock_sentiment",
            "btc_treasury_snapshot",   # {date, data} 이전 보유량 스냅샷
            "btc_treasury_history",    # [{date, btc_map}] 최대 90일 히스토리
        ]
        data = {k: st.session_state[k] for k in keys_to_save if k in st.session_state}
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def init_session():
    for prefix in ("stock_","coin_","ta_","oc_","m7_","combined_","btc_treasury_","usdt_apy_"):
        for key in ("news_data","source_stats","summary_quick","summary_deep","provider"):
            fk = f"{prefix}{key}"
            if fk not in st.session_state:
                st.session_state[fk] = [] if key=="news_data" else ({} if key=="source_stats" else "")
    _str_keys = ("discord_last_sent","discord_last_sent_date","combined_last_run_at",
                 "combined_last_run_status","btc_sentiment","stock_sentiment",
                 "usdt_apy_ai_summary","btc_treasury_ai_summary")
    for k in _str_keys:
        if k not in st.session_state:
            st.session_state[k] = ""
    for k in ("btc_treasury_data", "btc_treasury_news_data", "usdt_apy_data", "usdt_apy_news_data"):
        if k not in st.session_state:
            st.session_state[k] = []
    if "usdt_apy_aave_history" not in st.session_state:
        st.session_state["usdt_apy_aave_history"] = {}
    if "btc_treasury_snapshot" not in st.session_state:
        st.session_state["btc_treasury_snapshot"] = {}
    if "btc_treasury_history" not in st.session_state:
        st.session_state["btc_treasury_history"] = []  # [{"date":str,"btc_map":{entity:float}}]

init_session()
load_cache()
# 캐시에서 복원된 종합분석 텍스트가 있으면 심리를 재파싱
if not st.session_state.get("btc_sentiment") and st.session_state.get("combined_summary_deep"):
    _r_btc, _r_stock = _parse_sentiment(st.session_state["combined_summary_deep"])
    st.session_state["btc_sentiment"]   = _r_btc
    st.session_state["stock_sentiment"] = _r_stock


# ══════════════════════════════════════════════════
# ── 사이드바 ──────────────────────────────────────
# ══════════════════════════════════════════════════
with st.sidebar:
    # 로고
    st.markdown("""
    <div class="cq-sidebar-logo">
      <span style="font-size:1.2rem">📊</span>
      통합 분석 <span class="dot">•</span>
    </div>
    """, unsafe_allow_html=True)

    # ── 뉴스 섹션
    mode_label = st.radio("모드 선택", [
        "📈  주식 뉴스",
        "🪙  코인 뉴스",
        "📊  BTC 기술적 분석",
        "🔗  BTC 온체인 분석",
        "🏆  미국주식 기술적 분석",
        "🏦  BTC Treasury",
        "💵  USDT APY",
        "🤖  AI 종합분석",
    ], label_visibility="collapsed")

    nav_mode = {
        "📈  주식 뉴스":          "stock",
        "🪙  코인 뉴스":          "coin",
        "📊  BTC 기술적 분석":     "ta",
        "🔗  BTC 온체인 분석":     "oc",
        "🏆  미국주식 기술적 분석": "m7",
        "🏦  BTC Treasury":        "btc_treasury",
        "💵  USDT APY":            "usdt_apy",
        "🤖  AI 종합분석":         "combined",
    }[mode_label]

    is_stock       = nav_mode == "stock"
    is_coin        = nav_mode == "coin"
    is_ta          = nav_mode == "ta"
    is_oc          = nav_mode == "oc"
    is_m7          = nav_mode == "m7"
    is_treasury    = nav_mode == "btc_treasury"
    is_usdt_apy    = nav_mode == "usdt_apy"
    is_combined    = nav_mode == "combined"

    st.markdown('<div class="cq-divider"></div>', unsafe_allow_html=True)

    # ── AI 설정
    st.markdown("### AI 설정")
    use_ai = st.toggle("AI 요약 생성", value=True)
    if use_ai:
        ai_opts = ["Gemini 2.5 Pro", "GPT-4o-mini"]
        ai_provider = st.selectbox("AI 제공자", ai_opts)
        ai_providers = [ai_provider]
    else:
        ai_providers = []

    st.markdown('<div class="cq-divider"></div>', unsafe_allow_html=True)

    # ── 수집 소스
    if is_stock:
        st.markdown("**수집 소스**")
        src_finnhub     = st.checkbox("Finnhub API",           value=True)
        src_yahoo       = st.checkbox("Yahoo Finance (RSS)",   value=True)
        src_cnbc        = st.checkbox("CNBC (RSS)",            value=True)
        src_marketwatch = st.checkbox("MarketWatch (RSS)",     value=True)
        src_mni         = st.checkbox("MNI Markets",           value=True)
        src_mktnews     = st.checkbox("MKT News",              value=True)
        run_label = "주식 뉴스 수집"

    elif is_coin:
        st.markdown("**수집 소스**")
        src_cryptopanic  = st.checkbox("CryptoPanic API",   value=bool(CRYPTOPANIC_API_KEY))
        src_coindesk     = st.checkbox("CoinDesk",          value=True)
        src_cryptonews_n = st.checkbox("cryptonews.net",    value=True)
        src_coincarp     = st.checkbox("coincarp.com",      value=True)
        src_theblock     = st.checkbox("The Block (RSS)",   value=True)
        src_cryptonews_c = st.checkbox("cryptonews.com",    value=True)
        src_decrypt      = st.checkbox("Decrypt (RSS)",     value=True)
        run_label = "코인 뉴스 수집"

    elif is_ta or is_oc:
        st.markdown("**수집 소스 (BTC)**")
        src_ct     = st.checkbox("CoinTelegraph",           value=True)
        src_amb    = st.checkbox("AMBCrypto",               value=True)
        src_glass  = st.checkbox("Glassnode Insights",      value=True)
        src_slate  = st.checkbox("CryptoSlate",             value=True)
        src_cg     = st.checkbox("Coinglass",               value=True)
        src_tb     = st.checkbox("The Block",               value=True)
        src_cd     = st.checkbox("CoinDesk",                value=True)
        src_reddit = st.checkbox("Reddit BitcoinMarkets",   value=True)
        run_label = "BTC 기술적 분석 수집" if is_ta else "BTC 온체인 분석 수집"

    elif is_treasury:
        st.markdown("**데이터 소스**")
        st.caption("bitbo.io/treasuries")
        _trs_news = st.checkbox("관련 뉴스 수집", value=True,
                                help="Google News · CoinTelegraph · CoinDesk · The Block")
        run_label = "BTC Treasury 조회"

    elif is_usdt_apy:
        st.markdown("**데이터 소스**")
        st.caption("DefiLlama API (무료)")
        _min_tvl_m = st.slider("최소 TVL (백만$)", 0, 50, 1)
        _max_apy_v = st.slider("최대 APY (%)", 10, 200, 50)
        _top_n_v   = st.slider("상위 N개", 10, 100, 50)
        run_label = "USDT APY 조회"

    elif is_combined:
        st.markdown("**수집 대상 (자동)**")
        for _cl in ["📈 주식 뉴스", "🪙 코인 뉴스", "📊 BTC 기술적 분석",
                    "🔗 BTC 온체인 분석", "🏆 M7 기술적 분석",
                    "🏦 BTC Treasury", "💵 USDT APY"]:
            st.checkbox(_cl, value=True, disabled=True, key=f"_combined_chk_{_cl}")
        run_label = "AI 종합분석 실행"

    else:
        st.markdown("**종목 선택**")
        selected_tickers = []
        cols = st.columns(2)
        for i, (ticker, info) in enumerate(M7_STOCKS.items()):
            with cols[i % 2]:
                if st.checkbox(f"{info['emoji']} {ticker}", value=True, key=f"m7_{ticker}"):
                    selected_tickers.append(ticker)
        st.markdown('<div class="cq-divider"></div>', unsafe_allow_html=True)
        st.markdown("**수집 소스**")
        src_yahoo_m7 = st.checkbox("Yahoo Finance",  value=True)
        src_benzinga = st.checkbox("Benzinga",       value=True)
        src_mw_m7    = st.checkbox("MarketWatch",    value=True)
        src_cnbc_m7  = st.checkbox("CNBC",           value=True)
        src_sa       = st.checkbox("Seeking Alpha",  value=True)
        src_fh_m7    = st.checkbox("Finnhub API",    value=bool(FINNHUB_API_KEY))
        src_reddit_s = st.checkbox("Reddit r/stocks", value=True)
        run_label = "미국주식 기술적 분석 수집"

    st.markdown('<div class="cq-divider"></div>', unsafe_allow_html=True)

    # ── 투자심리 게이지
    _btc_sent = st.session_state.get("btc_sentiment", "")
    _stk_sent = st.session_state.get("stock_sentiment", "")
    if _btc_sent or _stk_sent:
        st.markdown("**📡 현재 투자심리**")
        st.markdown(_render_dual_gauge(_btc_sent, _stk_sent), unsafe_allow_html=True)
        # 텍스트 표시
        _clr_map = {
            "극단적공포": "#c0392b", "공포": "#e67e22", "중립": "#95a5a6",
            "탐욕": "#2ecc71",       "극단적탐욕": "#16a085",
        }
        _disp_map2 = {"극단적공포": "극단적 공포", "공포": "공포", "중립": "중립",
                      "탐욕": "탐욕", "극단적탐욕": "극단적 탐욕"}
        def _badge_html(label, sentiment):
            if not sentiment:
                return f"<div style='text-align:center;font-size:.75rem;color:#888'>{label}<br>—</div>"
            c = _clr_map.get(sentiment, "#888")
            t = _disp_map2.get(sentiment, sentiment)
            return (f"<div style='text-align:center'>"
                    f"<span style='font-size:.7rem;color:#aaa'>{label}</span><br>"
                    f"<span style='background:{c};color:#fff;padding:2px 8px;"
                    f"border-radius:10px;font-size:.78rem;font-weight:700'>{t}</span></div>")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(_badge_html("BTC", _btc_sent), unsafe_allow_html=True)
        with col2:
            st.markdown(_badge_html("미국주식", _stk_sent), unsafe_allow_html=True)
        st.markdown('<div class="cq-divider"></div>', unsafe_allow_html=True)

    run_btn = st.button(f"🚀 {run_label}", type="primary", use_container_width=True)
    st.caption(f"🕐 KST {NOW_KST.strftime('%Y-%m-%d %H:%M')}")


# ══════════════════════════════════════════════════
# ── 수집 실행 ──────────────────────────────────────
# ══════════════════════════════════════════════════
auto_run_combined = bool(st.session_state.pop("auto_run_combined_on_login", False))
if auto_run_combined:
    st.info("로그인 후 AI 종합분석 자동 실행 중입니다.")
    run_combined_analysis_pipeline(use_ai, ai_providers, trigger_source="login")
    st.rerun()

if run_btn:
    all_raw, source_map = [], {}

    if is_stock:
        tasks = []
        if src_finnhub and FINNHUB_API_KEY: tasks.append(("Finnhub API", fetch_finnhub, [FINNHUB_API_KEY]))
        if src_yahoo:       tasks.append(("Yahoo Finance", fetch_rss_feed, ["https://finance.yahoo.com/news/rssindex","Yahoo Finance"]))
        if src_cnbc:        tasks.append(("CNBC",          fetch_rss_feed, ["https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=120000000","CNBC"]))
        if src_marketwatch: tasks.append(("MarketWatch",   fetch_rss_feed, ["http://feeds.marketwatch.com/marketwatch/topstories/","MarketWatch"]))
        if src_mni:         tasks.append(("MNI Markets",   fetch_mni_markets, []))
        if src_mktnews:     tasks.append(("MKT News",      fetch_mktnews, []))
        prefix = "stock_"; pq, pd_ = PROMPT_STOCK_QUICK, PROMPT_STOCK_DEEP; post_filter = None

    elif is_coin:
        tasks = []
        if src_cryptopanic and CRYPTOPANIC_API_KEY: tasks.append(("CryptoPanic", fetch_cryptopanic, [CRYPTOPANIC_API_KEY]))
        if src_coindesk:     tasks.append(("CoinDesk",      fetch_coindesk, []))
        if src_cryptonews_n: tasks.append(("cryptonews.net",fetch_cryptonews_net, []))
        if src_coincarp:     tasks.append(("coincarp.com",  fetch_coincarp, []))
        if src_theblock:     tasks.append(("The Block",     fetch_theblock_rss, []))
        if src_cryptonews_c: tasks.append(("cryptonews.com",fetch_cryptonews_com, []))
        if src_decrypt:      tasks.append(("Decrypt",       fetch_decrypt, []))
        prefix = "coin_"; pq, pd_ = PROMPT_COIN_QUICK, PROMPT_COIN_DEEP; post_filter = None

    elif is_ta or is_oc:
        tasks = []
        if src_ct:     tasks.append(("CoinTelegraph", fetch_cointelegraph_ta, []))
        if src_amb:    tasks.append(("AMBCrypto",     fetch_ambcrypto, []))
        if src_glass:  tasks.append(("Glassnode",     fetch_glassnode_insights, []))
        if src_slate:  tasks.append(("CryptoSlate",   fetch_cryptoslate_research, []))
        if src_cg:     tasks.append(("Coinglass",     fetch_coinglass_news, []))
        if src_tb:     tasks.append(("The Block",     fetch_theblock_research, []))
        if src_cd:     tasks.append(("CoinDesk",      fetch_coindesk_analysis, []))
        if src_reddit: tasks.append(("Reddit",        fetch_reddit_btcmarkets, []))
        prefix = "ta_" if is_ta else "oc_"
        pq = PROMPT_TA_QUICK if is_ta else PROMPT_OC_QUICK
        pd_ = PROMPT_TA_DEEP if is_ta else PROMPT_OC_DEEP
        post_filter = filter_ta_news if is_ta else filter_onchain_news

    elif is_treasury:
        with st.spinner("🏦 bitbo.io 수집 중..."):
            _td = fetch_btc_treasuries()

        # ── 히스토리 기반 비교
        def _parse_btc(s):
            try: return float(str(s).replace(",", "").strip())
            except: return None

        # 현재 btc_map 생성
        _cur_map = {}
        for row in _td:
            if row.get("_error"): continue
            v = _parse_btc(row.get("# of BTC", ""))
            if v is not None:
                _cur_map[row.get("Entity", "")] = v

        # 히스토리 로드
        _history = st.session_state.get("btc_treasury_history", [])

        # ── 비교 기준 스냅샷 선택
        import datetime as _dt
        _today_d  = _dt.date.today()
        _30d_ago  = (_today_d - _dt.timedelta(days=30)).isoformat()
        _90d_ago  = (_today_d - _dt.timedelta(days=90)).isoformat()

        # 전회 (오늘 제외 가장 최근)
        _prev_snap = next((h for h in reversed(_history) if h["date"] != TODAY_STR), None)
        # 1개월 전 (30일 이내 가장 오래된 것)
        _1m_snap = next((h for h in _history if h["date"] >= _30d_ago), None) or \
                   (_history[0] if _history else None)
        # 3개월 전 (90일 이내 가장 오래된 것)
        _3m_snap = next((h for h in _history if h["date"] >= _90d_ago), None) or \
                   (_history[0] if _history else None)

        def _delta_str(cur, snap, entity):
            if not snap or snap["date"] == TODAY_STR:
                return "-"
            old = snap["btc_map"].get(entity)
            if cur is None or old is None:
                return "신규"
            d = cur - old
            return f"{d:+,.1f}" if d != 0 else "변동없음"

        for row in _td:
            if row.get("_error"): continue
            entity  = row.get("Entity", "")
            cur_val = _cur_map.get(entity)
            row["전회 대비"]  = _delta_str(cur_val, _prev_snap, entity)
            row["1개월 변화"] = _delta_str(cur_val, _1m_snap,   entity)
            row["3개월 변화"] = _delta_str(cur_val, _3m_snap,   entity)

        # 오늘 날짜 스냅샷이 없으면 추가 (하루 1회), 최대 90개 유지
        if not _history or _history[-1]["date"] != TODAY_STR:
            _history.append({"date": TODAY_STR, "btc_map": _cur_map})
            if len(_history) > 90:
                _history = _history[-90:]
            st.session_state["btc_treasury_history"] = _history

        save_cache()

        st.session_state["btc_treasury_data"] = _td
        st.session_state["btc_treasury_ai_summary"] = ""
        st.session_state["btc_treasury_news_data"] = []
        if _trs_news:
            with st.spinner("📰 BTC Treasury 뉴스 수집 중..."):
                _tnews = fetch_btc_treasury_news()
            st.session_state["btc_treasury_news_data"] = _tnews
        if use_ai and GEMINI_API_KEY and "Gemini 2.5 Pro" in ai_providers:
            with st.spinner("🤖 AI 분석 중..."):
                st.session_state["btc_treasury_ai_summary"] = summarize_btc_treasury_gemini(
                    _td, st.session_state["btc_treasury_news_data"], GEMINI_API_KEY)
        st.rerun()

    elif is_usdt_apy:
        with st.spinner("💵 DefiLlama USDT APY 수집 중..."):
            _data, _aave_pid = fetch_usdt_apy(
                min_tvl=_min_tvl_m * 1_000_000,
                max_apy=_max_apy_v,
                top_n=_top_n_v,
            )
        st.session_state["usdt_apy_data"] = _data
        st.session_state["usdt_apy_ai_summary"] = ""
        st.session_state["usdt_apy_news_data"] = []
        if _aave_pid:
            with st.spinner("📈 Aave V3 히스토리 수집 중..."):
                _hist = fetch_aave_v3_usdt_history(_aave_pid)
            st.session_state["usdt_apy_aave_history"] = _hist
        with st.spinner("📰 USDT/DeFi 뉴스 수집 중..."):
            _usdt_news = fetch_usdt_apy_news()
        st.session_state["usdt_apy_news_data"] = _usdt_news
        if use_ai and GEMINI_API_KEY and "Gemini 2.5 Pro" in ai_providers:
            _hist_list = st.session_state["usdt_apy_aave_history"].get("history", [])
            with st.spinner("🤖 AI 분석 중..."):
                st.session_state["usdt_apy_ai_summary"] = summarize_usdt_apy_gemini(
                    _data, _hist_list, GEMINI_API_KEY,
                    st.session_state["usdt_apy_news_data"])
        st.rerun()

    elif is_combined:
        run_combined_analysis_pipeline(use_ai, ai_providers, trigger_source="manual")
        st.rerun()

        # 모드별 기본 수집 설정 (combined 실행 시 자동 수집)
        _all_m7 = list(M7_STOCKS.keys())
        _auto_tasks = {
            "stock_": {
                "label": "📈 주식 뉴스",
                "tasks": [
                    ("Yahoo Finance", fetch_rss_feed, ["https://finance.yahoo.com/news/rssindex", "Yahoo Finance"]),
                    ("CNBC",          fetch_rss_feed, ["https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=120000000", "CNBC"]),
                    ("MarketWatch",   fetch_rss_feed, ["http://feeds.marketwatch.com/marketwatch/topstories/", "MarketWatch"]),
                    ("MNI Markets",   fetch_mni_markets, []),
                    ("MKT News",      fetch_mktnews, []),
                ] + ([("Finnhub API", fetch_finnhub, [FINNHUB_API_KEY])] if FINNHUB_API_KEY else []),
                "pq": PROMPT_STOCK_QUICK, "pd": PROMPT_STOCK_DEEP, "filter": None,
            },
            "coin_": {
                "label": "🪙 코인 뉴스",
                "tasks": [
                    ("CoinDesk",      fetch_coindesk, []),
                    ("cryptonews.net",fetch_cryptonews_net, []),
                    ("coincarp.com",  fetch_coincarp, []),
                    ("The Block",     fetch_theblock_rss, []),
                    ("cryptonews.com",fetch_cryptonews_com, []),
                    ("Decrypt",       fetch_decrypt, []),
                ] + ([("CryptoPanic", fetch_cryptopanic, [CRYPTOPANIC_API_KEY])] if CRYPTOPANIC_API_KEY else []),
                "pq": PROMPT_COIN_QUICK, "pd": PROMPT_COIN_DEEP, "filter": None,
            },
            "ta_": {
                "label": "📊 BTC 기술적 분석",
                "tasks": [
                    ("CoinTelegraph", fetch_cointelegraph_ta, []),
                    ("AMBCrypto",     fetch_ambcrypto, []),
                    ("Glassnode",     fetch_glassnode_insights, []),
                    ("CryptoSlate",   fetch_cryptoslate_research, []),
                    ("Coinglass",     fetch_coinglass_news, []),
                    ("The Block",     fetch_theblock_research, []),
                    ("CoinDesk",      fetch_coindesk_analysis, []),
                    ("Reddit",        fetch_reddit_btcmarkets, []),
                ],
                "pq": PROMPT_TA_QUICK, "pd": PROMPT_TA_DEEP, "filter": filter_ta_news,
            },
            "oc_": {
                "label": "🔗 BTC 온체인 분석",
                "tasks": [
                    ("CoinTelegraph", fetch_cointelegraph_ta, []),
                    ("AMBCrypto",     fetch_ambcrypto, []),
                    ("Glassnode",     fetch_glassnode_insights, []),
                    ("CryptoSlate",   fetch_cryptoslate_research, []),
                    ("Coinglass",     fetch_coinglass_news, []),
                    ("The Block",     fetch_theblock_research, []),
                    ("CoinDesk",      fetch_coindesk_analysis, []),
                    ("Reddit",        fetch_reddit_btcmarkets, []),
                ],
                "pq": PROMPT_OC_QUICK, "pd": PROMPT_OC_DEEP, "filter": filter_onchain_news,
            },
            "m7_": {
                "label": "🏆 M7 기술적 분석",
                "tasks": [
                    ("Yahoo Finance", fetch_yahoo_finance_m7, [_all_m7]),
                    ("Benzinga",      fetch_benzinga_m7, [_all_m7]),
                    ("MarketWatch",   fetch_marketwatch_m7, []),
                    ("CNBC",          fetch_cnbc_m7, []),
                    ("SeekingAlpha",  fetch_seekingalpha_m7, [_all_m7]),
                    ("Reddit r/stocks", fetch_reddit_stocks_m7, []),
                ] + ([("Finnhub", fetch_finnhub_m7, [FINNHUB_API_KEY, _all_m7])] if FINNHUB_API_KEY else []),
                "pq": PROMPT_M7_QUICK, "pd": PROMPT_M7_DEEP,
                "filter": lambda nl: filter_m7_news(nl, _all_m7),
            },
        }

        with st.status("🤖 AI 종합분석 실행 중...", expanded=True) as _cstatus:
            _deep_dives = {}

            for _cp, _cfg in _auto_tasks.items():
                _cl = _cfg["label"]
                _existing = st.session_state.get(f"{_cp}summary_deep", "")
                if _existing:
                    _deep_dives[_cp] = _existing
                    st.write(f"✅ {_cl}: 기존 분석 사용")
                    continue

                # 기존 데이터 없으면 자동 수집
                st.write(f"📡 {_cl} 수집 중...")
                _raw = []
                for _, _tfn, _targs in _cfg["tasks"]:
                    try:
                        _raw += _tfn(*_targs)
                    except Exception:
                        pass
                _raw = dedup(_raw)
                if _cfg["filter"]:
                    _raw = _cfg["filter"](_raw)
                _raw.sort(key=lambda x: x.get("published_at", ""), reverse=True)

                if not _raw:
                    st.write(f"  ⚠️ {_cl}: 수집된 기사 없음")
                    continue

                st.write(f"  → {len(_raw)}건 수집. AI 분석 중...")
                _q, _d = "", ""
                if use_ai and ai_providers:
                    if "Gemini 2.5 Pro" in ai_providers and GEMINI_API_KEY:
                        _q, _d = summarize_gemini(_raw, GEMINI_API_KEY, _cfg["pq"], _cfg["pd"])
                    elif "GPT-4o-mini" in ai_providers and OPENAI_API_KEY:
                        _q, _d = summarize_openai(_raw, OPENAI_API_KEY, _cfg["pq"], _cfg["pd"])

                st.session_state[f"{_cp}news_data"]     = _raw
                st.session_state[f"{_cp}summary_quick"] = _q
                st.session_state[f"{_cp}summary_deep"]  = _d
                if _d:
                    _deep_dives[_cp] = _d
                    st.write(f"  ✅ {_cl}: 분석 완료")
                else:
                    st.write(f"  ⚠️ {_cl}: AI 분석 없음 (API 키 확인)")

            if not _deep_dives:
                st.error("모든 모드에서 분석 생성 실패. API 키를 확인하세요.")
                _cstatus.update(label="❌ 실패", state="error")
            else:
                _combined_result, _used_prov = "", ""
                if use_ai and ai_providers:
                    if "Gemini 2.5 Pro" in ai_providers and GEMINI_API_KEY:
                        st.write("🤖 Gemini 2.5 Pro 종합분석 생성 중...")
                        _combined_result = summarize_combined_gemini(_deep_dives, GEMINI_API_KEY)
                        _used_prov = "Gemini 2.5 Pro"
                    elif "GPT-4o-mini" in ai_providers and OPENAI_API_KEY:
                        st.write("🤖 GPT-4o-mini 종합분석 생성 중...")
                        _combined_result = summarize_combined_openai(_deep_dives, OPENAI_API_KEY)
                        _used_prov = "GPT-4o-mini"
                    else:
                        st.write("⚠️ AI API 키가 없습니다.")
                st.session_state["combined_summary_deep"] = _combined_result
                st.session_state["combined_provider"]     = _used_prov
                _btc_s2, _stock_s2 = _parse_sentiment(_combined_result)
                st.session_state["btc_sentiment"]   = _btc_s2
                st.session_state["stock_sentiment"] = _stock_s2
                _cstatus.update(label="✅ 종합분석 완료!", state="complete")
                save_cache()
        st.rerun()

    else:
        tasks = []
        if src_yahoo_m7: tasks.append(("Yahoo Finance", fetch_yahoo_finance_m7, [selected_tickers]))
        if src_benzinga: tasks.append(("Benzinga",      fetch_benzinga_m7, [selected_tickers]))
        if src_mw_m7:    tasks.append(("MarketWatch",   fetch_marketwatch_m7, []))
        if src_cnbc_m7:  tasks.append(("CNBC",          fetch_cnbc_m7, []))
        if src_sa:       tasks.append(("SeekingAlpha",  fetch_seekingalpha_m7, [selected_tickers]))
        if src_fh_m7 and FINNHUB_API_KEY: tasks.append(("Finnhub", fetch_finnhub_m7, [FINNHUB_API_KEY, selected_tickers]))
        if src_reddit_s: tasks.append(("Reddit r/stocks", fetch_reddit_stocks_m7, []))
        prefix = "m7_"; pq, pd_ = PROMPT_M7_QUICK, PROMPT_M7_DEEP
        post_filter = lambda nl: filter_m7_news(nl, selected_tickers)

    with st.status("📡 데이터 수집 중...", expanded=True) as status:
        for name, fn, args in tasks:
            st.write(f"수집 중: **{name}**")
            try:
                items = fn(*args)
                all_raw += items; source_map[name] = len(items)
                st.write(f"  ✅ {name}: {len(items)}건")
            except Exception as e:
                source_map[name] = 0; st.write(f"  ⚠️ {name}: {e}")

        all_raw = dedup(all_raw)
        filtered = post_filter(all_raw) if post_filter else all_raw
        if post_filter:
            st.write(f"🔍 전체 {len(all_raw)}건 → 필터링 후 **{len(filtered)}건**")

        fsrc = {}
        for item in filtered:
            s = item["source"]; fsrc[s] = fsrc.get(s, 0) + 1
        filtered.sort(key=lambda x: x.get("published_at",""), reverse=True)

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
            if not used: st.write("⚠️ API 키 없음")
            st.session_state[f"{prefix}summary_quick"] = "\n\n---\n\n".join(all_quick)
            st.session_state[f"{prefix}summary_deep"]  = "\n\n---\n\n".join(all_deep)
            st.session_state[f"{prefix}provider"]      = " + ".join(used)

        status.update(label=f"✅ 수집 완료 — {len(filtered)}건", state="complete")
        save_cache()


# ══════════════════════════════════════════════════
# ── 메인 화면 ─────────────────────────────────────
# ══════════════════════════════════════════════════
prefix        = {"stock":"stock_","coin":"coin_","ta":"ta_","oc":"oc_","m7":"m7_",
                 "btc_treasury":"btc_treasury_","usdt_apy":"usdt_apy_",
                 "combined":"combined_"}[nav_mode]
news_data     = st.session_state[f"{prefix}news_data"]
source_stats  = st.session_state[f"{prefix}source_stats"]
summary_quick = st.session_state[f"{prefix}summary_quick"]
summary_deep  = st.session_state[f"{prefix}summary_deep"]
provider      = st.session_state[f"{prefix}provider"]

# 모드별 설정
MODE_CFG = {
    "stock":    {"title":"📈 미국 주식 뉴스",      "accent":"#3B82F6", "icon":"📈"},
    "coin":     {"title":"🪙 코인 뉴스",           "accent":"#F7931A", "icon":"🪙"},
    "ta":       {"title":"₿ BTC 기술적 분석",      "accent":"#F59E0B", "icon":"📊"},
    "oc":       {"title":"₿ BTC 온체인 분석",      "accent":"#8B5CF6", "icon":"🔗"},
    "m7":           {"title":"🏆 미국주식 기술적 분석", "accent":"#10B981", "icon":"🏆"},
    "btc_treasury": {"title":"🏦 BTC Treasury",      "accent":"#F59E0B", "icon":"🏦"},
    "usdt_apy":     {"title":"💵 USDT APY",           "accent":"#10B981", "icon":"💵"},
    "combined":     {"title":"🤖 AI 종합분석",         "accent":"#7C3AED", "icon":"🤖"},
}
cfg    = MODE_CFG[nav_mode]
accent = cfg["accent"]

# ── 상단 탑바
tab_html = "".join(
    f'<div class="cq-mode-tab {"active" if k==nav_mode else ""}">{v["icon"]} {v["title"].split(" ",1)[1] if " " in v["title"] else v["title"]}</div>'
    for k, v in MODE_CFG.items()
)
st.markdown(f"""
<div class="cq-topbar">
  <div class="logo">📊 통합 분석 <span>•</span></div>
  <div class="cq-mode-tabs">{tab_html}</div>
  <div class="time-info">KST {NOW_KST.strftime('%Y-%m-%d %H:%M')}</div>
</div>
<div class="cq-content">
""", unsafe_allow_html=True)

# ── BTC Treasury 모드 전용 화면
if is_treasury:
    _td    = st.session_state.get("btc_treasury_data", [])
    _tnews = st.session_state.get("btc_treasury_news_data", [])
    _tai   = st.session_state.get("btc_treasury_ai_summary", "")

    st.markdown("""
    <div class="cq-ai-card">
      <div class="cq-ai-header">
        <div class="cq-ai-dot" style="background:#F59E0B"></div>
        <div class="cq-ai-title">🏦 BTC Treasury — 기업 BTC 보유 현황</div>
      </div>
    </div>""", unsafe_allow_html=True)

    if not _td:
        st.markdown("""
        <div class="cq-empty">
          <div class="empty-icon">🏦</div>
          <h3>BTC Treasury</h3>
          <p>사이드바의 <b>🚀 BTC Treasury 조회</b> 버튼을 클릭하세요.</p>
        </div>""", unsafe_allow_html=True)
    elif "_error" in (_td[0] if _td else {}):
        st.error(f"수집 실패: {_td[0]['_error']}")
        st.markdown(f"직접 확인: [bitbo.io/treasuries]({BTC_TREASURIES_URL})")
    else:
        valid = [r for r in _td if not r.get("_error")]
        cols_show = [c for c in (valid[0].keys() if valid else []) if not c.startswith("_")]

        top_name = valid[0].get(cols_show[0], "N/A") if valid and cols_show else "N/A"
        _c1, _c2, _c3 = st.columns(3)
        with _c1: st.metric("📊 총 기업 수", f"{len(valid)}개")
        with _c2: st.metric("🏆 최대 보유", top_name)
        with _c3: st.metric("📅 업데이트", TODAY_STR)

        # 정렬 가능 테이블
        _cols_js = json.dumps(cols_show)
        _rows_js = json.dumps([[r.get(c, "") for c in cols_show] for r in valid])
        _tbl_h   = 890
        components.html(f"""
<style>
.outer{{border:1px solid #E5E7EB;border-radius:10px;overflow:hidden;margin-top:8px}}
.scroll{{overflow-y:auto;overflow-x:auto;max-height:850px}}
table{{width:100%;border-collapse:collapse;min-width:600px;font-family:sans-serif}}
th{{background:#F9FAFB;padding:8px 10px;font-size:.78rem;color:#6B7280;font-weight:600;
    border-bottom:2px solid #E5E7EB;white-space:nowrap;position:sticky;top:0;z-index:2}}
th.sortable{{cursor:pointer}}th.sortable:hover{{background:#F3F4F6}}
.arrow{{margin-left:4px;opacity:.4}}
th.asc .arrow,th.desc .arrow{{opacity:1}}
td{{padding:6px 10px;border-bottom:1px solid #F3F4F6;font-size:.82rem;white-space:nowrap}}
tr:hover td{{background:#FAFAFA}}tr:last-child td{{border-bottom:none}}
td:first-child{{font-weight:600;color:#374151;text-align:center;width:36px}}
.up{{color:#059669;font-weight:600}}.dn{{color:#DC2626;font-weight:600}}
.new{{color:#7C3AED;font-size:.75rem;font-weight:600}}
</style>
<div class="outer"><div class="scroll"><table id="tbl">
<thead><tr id="hdr"></tr></thead><tbody id="body"></tbody>
</table></div></div>
<script>
var COLS={_cols_js},rows={_rows_js},sortCol=-1,sortAsc=false;
function render(data){{
  var tb=document.getElementById('body');tb.innerHTML='';
  data.forEach(function(r,i){{
    var tr=document.createElement('tr');
    var td0=document.createElement('td');td0.textContent=i+1;tr.appendChild(td0);
    COLS.forEach(function(c,ci){{
      var td=document.createElement('td');
      var val=r[ci]!==undefined?r[ci]:'';
      td.textContent=val;
      if(c==='전회 대비'||c==='1개월 변화'||c==='3개월 변화'){{
        if(val.startsWith('+'))td.className='up';
        else if(val.startsWith('-')&&val!=='-')td.className='dn';
        else if(val==='신규')td.className='new';
      }}
      tr.appendChild(td);
    }});tb.appendChild(tr);
  }});
}}
function buildHeader(){{
  var hdr=document.getElementById('hdr');
  var th0=document.createElement('th');th0.textContent='#';hdr.appendChild(th0);
  COLS.forEach(function(col,ci){{
    var th=document.createElement('th');
    th.className='sortable';th.id='th'+ci;
    th.innerHTML=col+'<span class="arrow">⇅</span>';
    th.addEventListener('click',function(){{
      var asc=(sortCol===ci)?!sortAsc:false;sortCol=ci;sortAsc=asc;
      COLS.forEach(function(_,k){{
        var t=document.getElementById('th'+k);if(!t)return;
        t.classList.remove('asc','desc');
        var a=t.querySelector('.arrow');if(a)a.textContent='⇅';
      }});
      th.classList.add(asc?'asc':'desc');
      th.querySelector('.arrow').textContent=asc?'↑':'↓';
      var s=rows.slice().sort(function(a,b){{
        var av=a[ci],bv=b[ci];
        var an=parseFloat(String(av).replace(/[,\\$%\\s]/g,'')),
            bn=parseFloat(String(bv).replace(/[,\\$%\\s]/g,''));
        if(!isNaN(an)&&!isNaN(bn))return asc?an-bn:bn-an;
        return asc?String(av).localeCompare(String(bv)):String(bv).localeCompare(String(av));
      }});render(s);
    }});hdr.appendChild(th);
  }});
}}
buildHeader();render(rows);
</script>
""", height=_tbl_h)
        _hist = st.session_state.get("btc_treasury_history", [])
        import datetime as _dt2
        _t = _dt2.date.today()
        _prev_d = next((h["date"] for h in reversed(_hist) if h["date"] != TODAY_STR), None)
        _1m_d = next((h["date"] for h in _hist
                      if h["date"] >= (_t - _dt2.timedelta(days=30)).isoformat()), None)
        _3m_d = next((h["date"] for h in _hist
                      if h["date"] >= (_t - _dt2.timedelta(days=90)).isoformat()), None)
        _cmp_parts = []
        if _prev_d:              _cmp_parts.append(f"전회: {_prev_d}")
        if _1m_d:                _cmp_parts.append(f"1개월: {_1m_d}")
        if _3m_d and _3m_d != _1m_d: _cmp_parts.append(f"3개월: {_3m_d}")
        _cmp_label = (" | " + " · ".join(_cmp_parts)) if _cmp_parts else " | 첫 조회 (다음 조회부터 비교 가능)"
        st.caption(f"총 {len(valid)}개 기업 | 출처: bitbo.io/treasuries{_cmp_label} | 히스토리 {len(_hist)}일 축적")

        if _tai:
            st.markdown("---")
            st.markdown("### 🤖 AI 분석")
            _copy_btn(_tai)
            st.markdown(_tai)

        if _tnews:
            st.markdown("---")
            st.markdown(
                f'<div style="font-size:.78rem;color:#6b7280;margin-bottom:6px">'
                f'📌 뉴스 {len(_tnews)}건</div>'
                + "".join(render_news_row(item) for item in _tnews),
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ── USDT APY 모드 전용 화면
if is_usdt_apy:
    _ud = st.session_state.get("usdt_apy_data", [])
    st.markdown(f"""
    <div class="cq-ai-card">
      <div class="cq-ai-header">
        <div class="cq-ai-dot" style="background:#10B981"></div>
        <div class="cq-ai-title">💵 USDT APY — DeFi 수익률 순위</div>
        <div class="cq-ai-provider">출처: DefiLlama (무료 API)</div>
      </div>
    </div>""", unsafe_allow_html=True)
    if not _ud:
        st.markdown("""
        <div class="cq-empty">
          <div class="empty-icon">💵</div>
          <h3>USDT APY</h3>
          <p>사이드바의 <b>🚀 USDT APY 조회</b> 버튼을 클릭하세요.</p>
        </div>""", unsafe_allow_html=True)
    elif "_error" in (_ud[0] if _ud else {}):
        st.error(f"수집 실패: {_ud[0]['_error']}")
    else:
        _top_apy = max(r["APY(%)"] for r in _ud)
        _avg_apy = sum(r["APY(%)"] for r in _ud) / len(_ud)
        _tot_tvl = sum(r["TVL($)"] for r in _ud)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("풀 수", f"{len(_ud)}개")
        c2.metric("최고 APY", f"{_top_apy:.2f}%")
        c3.metric("평균 APY", f"{_avg_apy:.2f}%")
        c4.metric("총 TVL", _fmt_usd(_tot_tvl))

        # ── Aave V3 Ethereum USDT 1년 히스토리 ──────────────
        _ah = st.session_state.get("usdt_apy_aave_history", {})
        _hist = _ah.get("history", []) if isinstance(_ah, dict) else []
        if _hist:
            st.markdown("---")
            st.markdown("#### 📈 Aave V3 — USDT APY · TVL 변화 (2023.01~)")

            # 통계 계산
            _cur  = _hist[-1]
            _old  = _hist[0]
            _apy_cur  = _cur["apy"];    _apy_old  = _old["apy"]
            _tvl_cur  = _cur["tvlUsd"]; _tvl_old  = _old["tvlUsd"]
            _apy_chg  = _apy_cur - _apy_old
            _tvl_chg_pct = ((_tvl_cur - _tvl_old) / _tvl_old * 100) if _tvl_old else 0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("현재 APY",      f"{_apy_cur:.2f}%",
                      delta=f"{_apy_chg:+.2f}%p (2023.01~)",
                      delta_color="normal")
            m2.metric("2023-01 APY", f"{_apy_old:.2f}%")
            m3.metric("현재 TVL",      _fmt_usd(_tvl_cur),
                      delta=f"{_tvl_chg_pct:+.1f}% (2023.01~)",
                      delta_color="normal")
            m4.metric("2023-01 TVL", _fmt_usd(_tvl_old))

            # 날짜 인덱스 DataFrame으로 1년 전체 표시
            import pandas as pd
            _idx  = pd.to_datetime([h["date"] for h in _hist])
            _df_apy = pd.DataFrame({"APY(%)": [h["apy"] for h in _hist]}, index=_idx)
            _df_tvl = pd.DataFrame({"TVL($M)": [h["tvlUsd"] / 1e6 for h in _hist]}, index=_idx)

            ch1, ch2 = st.columns(2)
            with ch1:
                st.markdown("<div style='font-size:.8rem;color:#6B7280;margin-bottom:4px'>APY (%) — 2023.01~</div>", unsafe_allow_html=True)
                st.line_chart(_df_apy, height=220, use_container_width=True)
            with ch2:
                st.markdown("<div style='font-size:.8rem;color:#6B7280;margin-bottom:4px'>TVL ($M) — 2023.01~</div>", unsafe_allow_html=True)
                st.line_chart(_df_tvl, height=220, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 💹 USDT 풀 APY 전체 순위")
        _sort_cols = {"APY(%)", "APR(%)", "Base APY(%)", "Reward APY(%)", "TVL($)"}
        _cols = ["프로토콜", "체인", "풀메타", "APY(%)", "APR(%)", "Base APY(%)", "Reward APY(%)", "TVL($)"]
        _table_rows_js = json.dumps([
            [row.get(c, "") for c in _cols] for row in _ud
        ])
        _tvl_idx = _cols.index("TVL($)")
        components.html(f"""
<style>
  body{{margin:0;font-family:sans-serif}}
  .outer{{border:1px solid #E5E7EB;border-radius:10px;overflow:hidden}}
  .scroll{{overflow-y:auto;overflow-x:auto;max-height:600px}}
  table{{width:100%;border-collapse:collapse;min-width:700px}}
  th{{padding:7px 10px;background:#F9FAFB;font-size:.75rem;color:#6B7280;
      position:sticky;top:0;z-index:2;
      font-weight:600;border-bottom:2px solid #E5E7EB;white-space:nowrap;user-select:none}}
  th.sortable{{cursor:pointer}}
  th.sortable:hover{{background:#F3F4F6;color:#374151}}
  th .arrow{{margin-left:4px;opacity:.35;font-size:.7rem}}
  th.asc  .arrow{{opacity:1}}
  th.desc .arrow{{opacity:1}}
  td{{padding:6px 10px;border-bottom:1px solid #F3F4F6;font-size:.82rem;color:#374151}}
  td.num{{color:#10B981;font-weight:700}}
  td.idx{{font-weight:600;color:#111827}}
  tr:last-child td{{border-bottom:none}}
</style>
<div class="outer"><div class="scroll"><table id="tbl">
<thead><tr id="hdr"></tr></thead>
<tbody id="body"></tbody>
</table></div></div>
<script>
var COLS = {json.dumps(_cols)};
var SORT_COLS = {json.dumps(list(_sort_cols))};
var TVL_IDX = {_tvl_idx};
var rows = {_table_rows_js};
var sortCol = -1, sortAsc = false;

function fmtUsd(n) {{
  if (n >= 1e9) return '$' + (n/1e9).toFixed(2) + 'B';
  if (n >= 1e6) return '$' + (n/1e6).toFixed(2) + 'M';
  if (n >= 1e3) return '$' + (n/1e3).toFixed(1) + 'K';
  return '$' + n.toFixed(0);
}}

function render(data) {{
  var tbody = document.getElementById('body');
  tbody.innerHTML = '';
  data.forEach(function(r, i) {{
    var tr = document.createElement('tr');
    var td0 = document.createElement('td');
    td0.className = 'idx'; td0.textContent = i + 1;
    tr.appendChild(td0);
    COLS.forEach(function(col, ci) {{
      var td = document.createElement('td');
      var val = r[ci];
      if (col === 'TVL($)') {{
        td.textContent = typeof val === 'number' ? fmtUsd(val) : val;
        if (col === 'APY(%)') td.className = 'num';
      }} else if (col === 'APY(%)') {{
        td.textContent = val;
        td.className = 'num';
      }} else {{
        td.textContent = val;
      }}
      tr.appendChild(td);
    }});
    tbody.appendChild(tr);
  }});
}}

function buildHeader() {{
  var hdr = document.getElementById('hdr');
  var th0 = document.createElement('th'); th0.textContent = '#'; hdr.appendChild(th0);
  COLS.forEach(function(col, ci) {{
    var th = document.createElement('th');
    var isSortable = SORT_COLS.indexOf(col) >= 0;
    th.id = 'th' + ci;
    if (isSortable) {{
      th.className = 'sortable';
      th.innerHTML = col + '<span class="arrow">⇅</span>';
      th.addEventListener('click', function() {{
        var newAsc = (sortCol === ci) ? !sortAsc : false;
        sortCol = ci; sortAsc = newAsc;
        // update header arrows
        COLS.forEach(function(_, k) {{
          var t = document.getElementById('th' + k);
          if (!t) return;
          t.classList.remove('asc','desc');
          t.querySelector('.arrow') && (t.querySelector('.arrow').textContent = '⇅');
        }});
        th.classList.add(sortAsc ? 'asc' : 'desc');
        th.querySelector('.arrow').textContent = sortAsc ? '↑' : '↓';
        var sorted = rows.slice().sort(function(a, b) {{
          var av = a[ci], bv = b[ci];
          if (typeof av === 'number' && typeof bv === 'number')
            return sortAsc ? av - bv : bv - av;
          return sortAsc ? String(av).localeCompare(String(bv))
                         : String(bv).localeCompare(String(av));
        }});
        render(sorted);
      }});
    }} else {{
      th.textContent = col;
    }}
    hdr.appendChild(th);
  }});
}}

buildHeader();
render(rows);
</script>
""", height=660)
        st.caption("⚠️ APR은 APY에서 역산한 추정치(일 복리 기준). 투자 조언이 아닙니다.")

        # ── AI 분석 결과 ─────────────────────────────
        _ai_sum = st.session_state.get("usdt_apy_ai_summary", "")
        if _ai_sum:
            st.markdown("---")
            st.markdown("#### 🤖 AI 분석 리포트")
            _copy_btn(_ai_sum)
            st.markdown(_ai_sum)

        _unews = st.session_state.get("usdt_apy_news_data", [])
        if _unews:
            st.markdown("---")
            st.markdown(
                f'<div style="font-size:.78rem;color:#6b7280;margin-bottom:6px">'
                f'📌 뉴스 {len(_unews)}건</div>'
                + "".join(render_news_row(item) for item in _unews),
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ── 종합분석 모드 전용 화면
if is_combined:
    _cs = st.session_state.get("combined_summary_deep", "")
    _cp = st.session_state.get("combined_provider", "")

    # Discord 발송 현황 카드
    _last_sent = st.session_state.get("discord_last_sent", "")
    _last_sent_date = st.session_state.get("discord_last_sent_date", "")
    _last_run_at = st.session_state.get("combined_last_run_at", "")
    _last_run_status = st.session_state.get("combined_last_run_status", "")
    _next_kst = NOW_KST.replace(hour=8, minute=0, second=0, microsecond=0)
    if NOW_KST.hour >= 8:
        _next_kst += datetime.timedelta(days=1)
    _next_str = _next_kst.strftime("%Y-%m-%d 08:00 KST")
    _today_sent = (_last_sent_date == TODAY_STR)
    if _today_sent:
        _today_badge = '<span style="background:#D1FAE5;color:#065F46;border:1px solid #6EE7B7;padding:3px 10px;border-radius:6px;font-size:.8rem;font-weight:700">✅ 오늘 발송 완료</span>'
    else:
        _today_badge = '<span style="background:#F3F4F6;color:#6B7280;border:1px solid #E5E7EB;padding:3px 10px;border-radius:6px;font-size:.8rem;font-weight:700">— 오늘 미발송</span>'

    if _last_sent:
        _last_sent_badge = f'<span style="background:#D1FAE5;color:#065F46;border:1px solid #6EE7B7;padding:3px 10px;border-radius:6px;font-size:.8rem;font-weight:700">✅ 마지막 발송: {_last_sent}</span>'
    else:
        _last_sent_badge = '<span style="background:#F3F4F6;color:#6B7280;border:1px solid #E5E7EB;padding:3px 10px;border-radius:6px;font-size:.8rem;font-weight:700">— 마지막 발송 기록 없음</span>'

    _run_status_labels = {
        "running": "⏳ 분석 실행 중",
        "success_sent": "✅ 분석 완료 · Discord 발송 성공",
        "success_skipped_daily_limit": "ℹ️ 오늘은 발송 스킵됨 (하루 1회 제한)",
        "success_skipped_missing_webhook": "⚠️ 발송 스킵됨 (DISCORD_WEBHOOK_URL 미설정)",
        "success_send_failed": "⚠️ 분석 완료 · Discord 발송 실패",
        "failed_no_analysis": "❌ 분석 실패 (모드별 분석 생성 실패)",
        "failed_combined_generation": "❌ 분석 실패 (종합 리포트 생성 실패)",
    }
    _run_status_text = _run_status_labels.get(_last_run_status, "— 실행 상태 없음")
    _run_status_badge = (
        f'<span style="background:#FEF3C7;color:#92400E;border:1px solid #FCD34D;padding:3px 10px;border-radius:6px;font-size:.8rem;font-weight:700">{_run_status_text}</span>'
        if _last_run_status else
        '<span style="background:#F3F4F6;color:#6B7280;border:1px solid #E5E7EB;padding:3px 10px;border-radius:6px;font-size:.8rem;font-weight:700">— 실행 상태 없음</span>'
    )

    if not _get_discord_webhook():
        st.warning("DISCORD_WEBHOOK_URL이 설정되지 않아 자동 Discord 발송이 비활성화되어 있습니다.")
    st.markdown(f"""
    <div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:10px;padding:12px 18px;margin-bottom:16px;display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <span style="font-size:.85rem;color:#374151;font-weight:600">📨 Discord 자동 발송</span>
      {_today_badge}
      {_last_sent_badge}
      {_run_status_badge}
      <span style="font-size:.8rem;color:#9CA3AF">마지막 실행: {_last_run_at or '-'}</span>
      <span style="font-size:.8rem;color:#9CA3AF;margin-left:auto">다음 예정: {_next_str}</span>
    </div>""", unsafe_allow_html=True)

    if not _cs:
        st.markdown("""
        <div class="cq-empty">
          <div class="empty-icon">🤖</div>
          <h3>AI 종합분석</h3>
          <p>사이드바의 <b>🚀 AI 종합분석 실행</b> 버튼을 클릭하세요.<br>
          5개 모드 뉴스 수집 및 AI 분석이 자동으로 실행됩니다.</p>
        </div>""", unsafe_allow_html=True)
    else:
        _pv = f" — {_cp}" if _cp else ""
        st.markdown(f"""
        <div class="cq-ai-card">
          <div class="cq-ai-header">
            <div class="cq-ai-dot" style="background:#7C3AED"></div>
            <div class="cq-ai-title">🤖 AI 종합분석 리포트</div>
            <div class="cq-ai-provider">{_pv} · {TODAY_STR} KST</div>
          </div>
        </div>""", unsafe_allow_html=True)
        _copy_btn(_cs)
        st.markdown(_cs)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ── 빈 상태
if not news_data:
    EMPTY_HINT = {
        "stock": "사이드바에서 수집 소스를 선택 후 <b>주식 뉴스 수집</b> 버튼을 클릭하세요.",
        "coin":  "사이드바에서 수집 소스를 선택 후 <b>코인 뉴스 수집</b> 버튼을 클릭하세요.",
        "ta":    "사이드바에서 <b>BTC 기술적 분석 수집</b> 버튼을 클릭하세요.",
        "oc":    "사이드바에서 <b>BTC 온체인 분석 수집</b> 버튼을 클릭하세요.",
        "m7":    "종목을 선택 후 <b>미국주식 기술적 분석 수집</b> 버튼을 클릭하세요.",
    }
    st.markdown(f"""
    <div class="cq-empty">
      <div class="empty-icon">{cfg['icon']}</div>
      <h3>{cfg['title']}</h3>
      <p>{EMPTY_HINT[nav_mode]}</p>
    </div>""", unsafe_allow_html=True)
    if is_m7:
        st.markdown('<div style="margin-top:20px"></div>', unsafe_allow_html=True)
        st.markdown("**Magnificent 7 종목**")
        cols = st.columns(7)
        for col, (ticker, info) in zip(cols, M7_STOCKS.items()):
            with col:
                tc = info["color"]
                st.markdown(f"""
                <div class="cq-ticker-card" style="--tc:{tc}">
                  <div class="tc-emoji">{info['emoji']}</div>
                  <div class="tc-name">{ticker}</div>
                  <div class="tc-full">{info['name']}</div>
                </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ── 소스별 수집 현황 카드
total_html = f"""
<div class="cq-source-card" style="--sc:{accent}">
  <div class="sc-count" style="font-size:1.5rem">{len(news_data)}</div>
  <div class="sc-name">총 {'기사' if nav_mode in ('ta','oc','m7') else '뉴스'}</div>
</div>"""
src_cards = "".join(
    f'<div class="cq-source-card" style="--sc:{src_color(s)}">'
    f'<div class="sc-count">{c}</div>'
    f'<div class="sc-name">{s}</div></div>'
    for s, c in list(source_stats.items())[:8]
)
st.markdown(f'<div class="cq-source-grid">{total_html}{src_cards}</div>', unsafe_allow_html=True)

# ── 태그 현황 바
if is_m7:
    n_ta = sum(1 for x in news_data if x.get("is_ta"))
    n_fd = sum(1 for x in news_data if x.get("is_fund"))
    st.markdown(f"""
    <div class="cq-status-bar">
      <div class="item"><span class="cq-type-badge cq-type-ta">📊 TA</span>
        <span class="count" style="color:#C2410C">{n_ta}건</span></div>
      <div class="item"><span class="cq-type-badge cq-type-fund">💹 펀더멘털</span>
        <span class="count" style="color:#15803D">{n_fd}건</span></div>
    </div>""", unsafe_allow_html=True)
    # M7 종목별 카드
    ticker_counts = {}
    for item in news_data:
        t = item.get("ticker","기타"); ticker_counts[t] = ticker_counts.get(t,0)+1
    cards_html = "".join(
        f'<div class="cq-ticker-card" style="--tc:{info["color"]}">'
        f'<div class="tc-emoji">{info["emoji"]}</div>'
        f'<div class="tc-name">{ticker}</div>'
        f'<div class="tc-count">{ticker_counts.get(ticker,0)}</div>'
        f'</div>'
        for ticker, info in M7_STOCKS.items()
    )
    st.markdown(f'<div class="cq-ticker-grid">{cards_html}</div>', unsafe_allow_html=True)

elif is_ta or is_oc:
    n_ta  = sum(1 for x in news_data if x.get("is_ta"))
    n_oc  = sum(1 for x in news_data if x.get("is_onchain"))
    st.markdown(f"""
    <div class="cq-status-bar">
      <div class="item"><span class="cq-type-badge cq-type-ta">📊 기술적 분석</span>
        <span class="count" style="color:#C2410C">{n_ta}건</span></div>
      <div class="item"><span class="cq-type-badge cq-type-oc">🔗 온체인 분석</span>
        <span class="count" style="color:#1D4ED8">{n_oc}건</span></div>
    </div>""", unsafe_allow_html=True)

# ── AI 분석 탭
if summary_quick or summary_deep:
    pv_label = f" — {provider}" if provider else ""
    st.markdown(f"""
    <div class="cq-ai-card">
      <div class="cq-ai-header">
        <div class="cq-ai-dot"></div>
        <div class="cq-ai-title">AI 분석 리포트</div>
        <div class="cq-ai-provider">{pv_label}</div>
      </div>
    </div>""", unsafe_allow_html=True)
    t1, t2 = st.tabs(["⚡ Quick Summary", "🔬 Deep Dive"])
    with t1:
        if summary_quick:
            _copy_btn(summary_quick)
        st.markdown(summary_quick or "_요약 없음_")
    with t2:
        if summary_deep:
            _copy_btn(summary_deep)
        st.markdown(summary_deep  or "_분석 없음_")
    st.markdown("<br>", unsafe_allow_html=True)

# ── 검색 & 필터
st.markdown('<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:10px;padding:12px 16px;margin-bottom:14px">', unsafe_allow_html=True)
if is_m7:
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1: search_q = st.text_input("🔍", placeholder="earnings, RSI, buyback, AI...", label_visibility="collapsed")
    with c2:
        t_opts = ["전체"] + [t for t in M7_STOCKS if any(x.get("ticker")==t for x in news_data)]
        filter_ticker = st.selectbox("종목", t_opts, label_visibility="collapsed")
    with c3:
        type_filter = st.selectbox("유형", ["전체","📊 TA","💹 펀더멘털","둘다"], label_visibility="collapsed")
    with c4:
        all_srcs = sorted(set(x["source"] for x in news_data))
        filter_src = st.selectbox("소스", ["전체"]+all_srcs, label_visibility="collapsed")
elif is_ta or is_oc:
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1: search_q = st.text_input("🔍", placeholder="RSI, MACD, MVRV, funding rate...", label_visibility="collapsed")
    with c2:
        type_filter = st.selectbox("유형", ["전체","📊 TA만","🔗 온체인만","둘다"], label_visibility="collapsed")
    with c3:
        all_srcs = sorted(set(x["source"] for x in news_data))
        filter_src = st.selectbox("소스", ["전체"]+all_srcs, label_visibility="collapsed")
    filter_ticker = "전체"
else:
    c1, c2 = st.columns([3, 1])
    with c1: search_q = st.text_input("🔍", placeholder="키워드, 기업명, 코인명 검색...", label_visibility="collapsed")
    with c2:
        all_srcs = sorted(set(x["source"] for x in news_data))
        filter_src = st.selectbox("소스", ["전체"]+all_srcs, label_visibility="collapsed")
    filter_ticker = "전체"; type_filter = "전체"
st.markdown("</div>", unsafe_allow_html=True)

# ── 필터 적용
filtered = news_data
if search_q:
    q = search_q.lower()
    filtered = [n for n in filtered if q in n["title"].lower() or q in (n.get("description") or "").lower()]
if is_m7:
    if filter_ticker != "전체": filtered = [n for n in filtered if n.get("ticker")==filter_ticker]
    if type_filter == "📊 TA":      filtered = [n for n in filtered if n.get("is_ta")]
    elif type_filter == "💹 펀더멘털": filtered = [n for n in filtered if n.get("is_fund")]
    elif type_filter == "둘다":      filtered = [n for n in filtered if n.get("is_ta") and n.get("is_fund")]
elif is_ta or is_oc:
    if type_filter == "📊 TA만":   filtered = [n for n in filtered if n.get("is_ta") and not n.get("is_onchain")]
    elif type_filter == "🔗 온체인만": filtered = [n for n in filtered if n.get("is_onchain") and not n.get("is_ta")]
    elif type_filter == "둘다":    filtered = [n for n in filtered if n.get("is_ta") and n.get("is_onchain")]
if filter_src != "전체": filtered = [n for n in filtered if n["source"]==filter_src]

# ── 뉴스 북마크 렌더링
label_txt = "기사" if nav_mode in ("ta","oc","m7") else "뉴스"
st.markdown(
    f'<div style="font-size:.78rem;color:#6b7280;margin-bottom:6px">'
    f'📌 {label_txt} {len(filtered)}건</div>'
    + "".join(render_news_row(item) for item in filtered),
    unsafe_allow_html=True,
)

# ── 푸터
FOOTER_SRC = {
    "stock":        "Finnhub · Yahoo Finance · CNBC · MarketWatch · MNI Markets · MKT News",
    "coin":         "CryptoPanic · CoinDesk · cryptonews.net · coincarp · The Block · cryptonews.com · Decrypt",
    "ta":           "CoinTelegraph · AMBCrypto · Glassnode · CryptoSlate · Coinglass · The Block · CoinDesk · Reddit",
    "oc":           "CoinTelegraph · AMBCrypto · Glassnode · CryptoSlate · Coinglass · The Block · CoinDesk · Reddit",
    "m7":           "Yahoo Finance · Benzinga · MarketWatch · CNBC · Seeking Alpha · Finnhub · Reddit",
    "btc_treasury": "bitbo.io/treasuries · Google News · CoinTelegraph · CoinDesk · The Block",
    "usdt_apy":     "DefiLlama API · Google News · CoinTelegraph · CoinDesk · Yahoo Finance",
}
st.markdown(f"""
<div class="cq-footer">
  데이터 출처: {FOOTER_SRC[nav_mode]}<br>
  {NOW_KST.strftime('%Y-%m-%d %H:%M')} KST &nbsp;|&nbsp; ⚠️ 본 리포트는 정보 제공 목적이며 투자 조언이 아닙니다.
</div>
</div>
""", unsafe_allow_html=True)

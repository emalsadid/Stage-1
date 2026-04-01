"""
Path2Ascension Lead Qualifier — Halal Filter

Layer 1: Check the industry tag against the NON_HALAL_INDUSTRIES blocklist.
Layer 2: Check the company description (SEO description field) and optionally
         scrape the company website against NON_HALAL_KEYWORDS.

Returns a FilterResult for each lead so the caller can log the reason.
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import (
    NON_HALAL_INDUSTRIES,
    NON_HALAL_KEYWORDS,
    SCRAPE_TIMEOUT_SECONDS,
    SCRAPE_MAX_CHARS,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    is_halal: bool
    layer: Optional[str] = None        # "layer1", "layer2_description", "layer2_website"
    matched_term: Optional[str] = None # the offending keyword / industry


def _normalise(text: str) -> str:
    """Lowercase and collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _contains_any(text: str, terms: list[str]) -> Optional[str]:
    """
    Return the first term found in text, or None.
    Uses word-boundary matching so 'casino' won't match 'casinobrand123'
    only if it's a distinct word — but will match 'the casino platform'.
    """
    normalised = _normalise(text)
    for term in terms:
        pattern = re.compile(re.escape(_normalise(term)), re.IGNORECASE)
        if pattern.search(normalised):
            return term
    return None


# ---------------------------------------------------------------------------
# Layer 1 — Industry tag check
# ---------------------------------------------------------------------------

def check_industry_tag(industry: str) -> FilterResult:
    """
    Returns FilterResult(is_halal=False) if the industry string matches any
    entry in NON_HALAL_INDUSTRIES.
    """
    if not industry:
        return FilterResult(is_halal=True)

    matched = _contains_any(industry, NON_HALAL_INDUSTRIES)
    if matched:
        return FilterResult(
            is_halal=False,
            layer="layer1",
            matched_term=matched,
        )
    return FilterResult(is_halal=True)


# ---------------------------------------------------------------------------
# Layer 2a — SEO / company description text check
# ---------------------------------------------------------------------------

def check_description_text(description: str) -> FilterResult:
    """
    Returns FilterResult(is_halal=False) if the company description
    contains any NON_HALAL_KEYWORDS.
    """
    if not description:
        return FilterResult(is_halal=True)

    matched = _contains_any(description, NON_HALAL_KEYWORDS)
    if matched:
        return FilterResult(
            is_halal=False,
            layer="layer2_description",
            matched_term=matched,
        )
    return FilterResult(is_halal=True)


# ---------------------------------------------------------------------------
# Layer 2b — Website scrape check
# ---------------------------------------------------------------------------

def _fetch_homepage_text(url: str) -> Optional[str]:
    """
    Fetch the homepage and return visible text (title + meta description +
    first SCRAPE_MAX_CHARS of body text). Returns None on any error.
    """
    if not url:
        return None

    # Ensure scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        resp = requests.get(
            url,
            timeout=SCRAPE_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.debug("Could not fetch %s: %s", url, e)
        return None

    html = resp.text[:SCRAPE_MAX_CHARS]
    soup = BeautifulSoup(html, "html.parser")

    parts = []

    title_tag = soup.find("title")
    if title_tag:
        parts.append(title_tag.get_text())

    for meta in soup.find_all("meta"):
        content = meta.get("content", "")
        name = meta.get("name", "").lower()
        prop = meta.get("property", "").lower()
        if name in ("description", "keywords") or prop in ("og:description", "og:title"):
            parts.append(content)

    body = soup.find("body")
    if body:
        parts.append(body.get_text(separator=" ")[:2000])

    return " ".join(parts)


def check_website(website: str) -> FilterResult:
    """
    Scrape the company homepage and check for NON_HALAL_KEYWORDS.
    Returns FilterResult(is_halal=True) if scraping fails (fail-open).
    """
    text = _fetch_homepage_text(website)
    if not text:
        return FilterResult(is_halal=True)   # can't verify — allow through

    matched = _contains_any(text, NON_HALAL_KEYWORDS)
    if matched:
        return FilterResult(
            is_halal=False,
            layer="layer2_website",
            matched_term=matched,
        )
    return FilterResult(is_halal=True)


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------

def is_halal_lead(
    industry: str = "",
    description: str = "",
    website: str = "",
    scrape_website: bool = True,
) -> FilterResult:
    """
    Run all halal filter layers in order. Short-circuits on first failure.

    Args:
        industry:       Apollo "Industry" field value.
        description:    Apollo "SEO Description" or any company blurb.
        website:        Company website URL.
        scrape_website: If False, skip the website scrape (faster, less thorough).

    Returns:
        FilterResult with is_halal=True only if all layers pass.
    """
    # Layer 1 — industry tag
    result = check_industry_tag(industry)
    if not result.is_halal:
        return result

    # Layer 2a — description text
    result = check_description_text(description)
    if not result.is_halal:
        return result

    # Layer 2b — website scrape (optional, slower)
    if scrape_website and website:
        result = check_website(website)
        if not result.is_halal:
            return result

    return FilterResult(is_halal=True)

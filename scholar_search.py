import logging
import random
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


LOGGER = logging.getLogger(__name__)
DOI_PATTERN = re.compile(r"10\.\d{4,}/\S+", re.IGNORECASE)


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) LiteratureResearchBot/1.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def _extract_year(authors_blob: str) -> Optional[int]:
    match = re.search(r"\b(19|20)\d{2}\b", authors_blob)
    return int(match.group()) if match else None


def _extract_authors(authors_blob: str) -> List[str]:
    # Scholar format: "Authors\xa0- Publication, Year - Domain"
    # Extract only the authors segment (before first "\xa0-" or " - ")
    # Handle both regular space and non-breaking space
    segment = re.split(r'[\xa0\s]-', authors_blob, maxsplit=1)[0]
    return [author.strip() for author in segment.split(",") if author.strip()]


def _extract_doi(*candidates: str) -> Optional[str]:
    for value in candidates:
        if not value:
            continue
        match = DOI_PATTERN.search(value)
        if match:
            return match.group(0).rstrip(".,;)")
    return None


def _extract_citations(result_entry: BeautifulSoup) -> int:
    for link in result_entry.select(".gs_fl a"):
        text = link.get_text(" ", strip=True)
        match = re.search(r"Cited by\s+(\d+)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def _is_rate_limited(response_text: str) -> bool:
    lowered = response_text.lower()
    markers = [
        "our systems have detected unusual traffic",
        "please show you're not a robot",
        "detected unusual traffic",
    ]
    return any(marker in lowered for marker in markers)


def _parse_results(page_html: str) -> List[Dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    entries = []

    for result in soup.select("div.gs_r.gs_or.gs_scl"):
        title_anchor = result.select_one("h3.gs_rt a")
        title_element = title_anchor or result.select_one("h3.gs_rt")
        if not title_element:
            continue

        title = title_element.get_text(" ", strip=True)
        url = title_anchor.get("href", "") if title_anchor else ""
        snippet_el = result.select_one("div.gs_rs")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        authors_blob = result.select_one("div.gs_a")
        authors_text = authors_blob.get_text(" ", strip=True) if authors_blob else ""

        entry = {
            "title": title,
            "authors": _extract_authors(authors_text),
            "year": _extract_year(authors_text),
            "doi": _extract_doi(title, url, snippet),
            "url": url,
            "snippet": snippet,
            "citations": _extract_citations(result),
        }
        entries.append(entry)

    return entries


def search_scholar(query: str, max_results: int = 10) -> List[Dict]:
    """
    Search Google Scholar and return normalized metadata records.

    Returns dictionaries with:
    {title, authors, year, doi, url, snippet, citations}
    """
    if max_results <= 0:
        return []

    session = _build_session()
    results: List[Dict] = []
    start = 0
    attempts = 0
    max_attempts = 4

    while len(results) < max_results and attempts < max_attempts:
        params = {"q": query, "hl": "en", "start": start}
        scholar_url = f"https://scholar.google.com/scholar?{urlencode(params)}"
        LOGGER.info("Fetching Scholar page start=%s", start)

        try:
            response = session.get(scholar_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as error:
            wait_seconds = 2 ** attempts
            LOGGER.warning("Scholar request failed (%s). Retrying in %ss", error, wait_seconds)
            time.sleep(wait_seconds)
            attempts += 1
            continue

        if response.status_code == 429 or _is_rate_limited(response.text):
            wait_seconds = min(30, (2 ** attempts) + random.uniform(0.2, 1.5))
            LOGGER.warning("Scholar rate limit detected. Backing off for %.1fs", wait_seconds)
            time.sleep(wait_seconds)
            attempts += 1
            continue

        page_results = _parse_results(response.text)
        if not page_results:
            LOGGER.info("No further Scholar results found")
            break

        results.extend(page_results)
        start += 10
        attempts = 0
        time.sleep(random.uniform(1.0, 2.0))

    return results[:max_results]

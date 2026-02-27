import logging
import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote, urljoin

import requests
import yaml
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from doi_utils import normalize_doi, is_valid_doi


LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG = Path(__file__).with_name("config.yaml")


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.75,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) LiteratureResearchBot/1.0",
            "Accept": "text/html,application/pdf,application/json,*/*;q=0.8",
        }
    )
    return session


def _load_config(config_path: Optional[str] = None) -> dict:
    cfg_path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}


def _safe_filename(title: str, doi: str) -> str:
    compact_title = re.sub(r"[^A-Za-z0-9._-]+", "_", title.strip())[:100] or "paper"
    compact_doi = re.sub(r"[^A-Za-z0-9._-]+", "_", doi.strip())[:50]
    return f"{compact_title}_{compact_doi}.pdf"


def _download_pdf(session: requests.Session, url: str, destination: Path) -> bool:
    try:
        response = session.get(url, timeout=10, stream=True)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if "pdf" not in content_type:
            first_bytes = next(response.iter_content(chunk_size=5), b"")
            if first_bytes != b"%PDF-":
                LOGGER.info("Rejected non-PDF content from %s (Content-Type=%s)", url, content_type)
                return False
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as output_file:
                output_file.write(first_bytes)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        output_file.write(chunk)
            return True

        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    output_file.write(chunk)
        return True
    except requests.RequestException as error:
        LOGGER.info("PDF download failed from %s: %s", url, error)
        return False


def _fetch_from_unpaywall(
    session: requests.Session,
    doi: str,
    email: str,
    destination: Path,
) -> bool:
    api_url = f"https://api.unpaywall.org/v2/{quote(doi)}"
    try:
        response = session.get(api_url, params={"email": email}, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as error:
        LOGGER.info("Unpaywall lookup failed for DOI %s: %s", doi, error)
        return False

    candidate_urls = []
    best = payload.get("best_oa_location") or {}
    for key in ("url_for_pdf", "url"):
        if best.get(key):
            candidate_urls.append(best[key])

    for location in payload.get("oa_locations", []):
        for key in ("url_for_pdf", "url"):
            if location.get(key):
                candidate_urls.append(location[key])

    deduped_urls = list(dict.fromkeys(candidate_urls))
    if not deduped_urls:
        LOGGER.info("Unpaywall has no OA URLs for DOI %s", doi)
        return False

    for pdf_url in deduped_urls:
        LOGGER.info("Trying Unpaywall URL for DOI %s: %s", doi, pdf_url)
        if _download_pdf(session, pdf_url, destination):
            return True

    return False


def _extract_scihub_pdf_url(html: str, mirror_url: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")

    selectors = [
        "iframe#pdf",
        "iframe[src*='.pdf']",
        "embed[src*='.pdf']",
        "a[href$='.pdf']",
        "a[href*='/downloads/'][href*='.pdf']",
    ]
    for selector in selectors:
        element = soup.select_one(selector)
        if not element:
            continue
        source = element.get("src") or element.get("href")
        if source:
            return urljoin(mirror_url, source)
    return None


def _fetch_from_scihub(
    session: requests.Session,
    doi: str,
    mirrors: list,
    destination: Path,
) -> bool:
    for mirror in mirrors:
        base_url = mirror if mirror.startswith("http") else f"https://{mirror}"
        lookup_url = f"{base_url.rstrip('/')}/{quote(doi)}"
        LOGGER.info("Trying Sci-Hub mirror %s", lookup_url)

        try:
            response = session.get(lookup_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as error:
            LOGGER.info("Sci-Hub mirror failed %s: %s", base_url, error)
            continue

        content_type = response.headers.get("Content-Type", "").lower()
        if "pdf" in content_type:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)
            return True

        pdf_url = _extract_scihub_pdf_url(response.text, base_url)
        if not pdf_url:
            LOGGER.info("No PDF link found in Sci-Hub mirror response: %s", base_url)
            continue

        if _download_pdf(session, pdf_url, destination):
            return True

    return False


def fetch_pdf(doi: str, title: str, config_path: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch a PDF using source fallback logic.

    Source order:
    1) Unpaywall API
    2) Sci-Hub mirrors

    Returns:
        Tuple[pdf_path, source] or (None, None) when retrieval fails.
    """
    # Normalize and validate DOI
    cleaned_doi = normalize_doi(doi)
    if not cleaned_doi or not is_valid_doi(cleaned_doi):
        LOGGER.info("Skipping invalid DOI: %s (original: %s)", cleaned_doi, doi)
        return None, None

    config = _load_config(config_path)
    unpaywall_email = config.get("unpaywall_email", "")
    scihub_mirrors = config.get("scihub_mirrors", [])
    download_dir = Path(config.get("pdf_download_dir", "./pdfs")).expanduser()

    if not unpaywall_email:
        LOGGER.warning("No Unpaywall email configured; skipping Unpaywall for DOI %s", cleaned_doi)

    session = _build_session()
    filename = _safe_filename(title, cleaned_doi)
    destination = download_dir / filename

    if unpaywall_email and _fetch_from_unpaywall(session, cleaned_doi, unpaywall_email, destination):
        LOGGER.info("Fetched PDF via Unpaywall for DOI %s", cleaned_doi)
        return str(destination), "unpaywall"

    if _fetch_from_scihub(session, cleaned_doi, scihub_mirrors, destination):
        LOGGER.info("Fetched PDF via Sci-Hub for DOI %s", cleaned_doi)
        return str(destination), "sci-hub"

    LOGGER.info("All PDF sources failed for DOI %s", cleaned_doi)
    return None, None

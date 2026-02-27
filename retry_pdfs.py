#!/usr/bin/env python3
"""
Retry PDF fetching for papers in Zotero collection that have DOIs but no PDFs.
Uses only sci-hub.ru (the working mirror).
"""
import json
import logging
import os
import re
import requests
from pathlib import Path
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
LOGGER = logging.getLogger(__name__)

CONFIG_PATH = Path("~/.openclaw/workspace/.zotero-config.json").expanduser()
GROUP_ID = "5120604"
COLLECTION_KEY = "UV4I5VWV"
PDF_DIR = Path("~/.openclaw/workspace/literature/pdfs").expanduser()
PDF_DIR.mkdir(parents=True, exist_ok=True)

SCIHUB_MIRROR = "https://sci-hub.ru"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_collection_items(api_key):
    """Fetch all items in the collection"""
    url = f"https://api.zotero.org/groups/{GROUP_ID}/collections/{COLLECTION_KEY}/items?limit=100"
    response = requests.get(url, headers={"Zotero-API-Key": api_key})
    response.raise_for_status()
    return response.json()


def clean_doi(doi):
    """Clean malformed DOIs (remove URL fragments)"""
    if not doi:
        return None
    # Remove trailing URL fragments like /1307371
    doi = re.sub(r'/\d+$', '', doi.strip())
    return doi if re.match(r'^10\.\d{4,}/\S+$', doi) else None


def extract_scihub_pdf_url(html, base_url):
    """Extract PDF URL from Sci-Hub HTML response"""
    soup = BeautifulSoup(html, "html.parser")
    
    selectors = [
        "iframe#pdf",
        "iframe[src*='.pdf']",
        "embed[src*='.pdf']",
        "a[href$='.pdf']",
        "button[onclick*='pdf']",
    ]
    
    for selector in selectors:
        element = soup.select_one(selector)
        if not element:
            continue
        
        # Check src, href, and onclick attributes
        for attr in ['src', 'href', 'onclick']:
            value = element.get(attr)
            if value and '.pdf' in value:
                # Extract URL from onclick if needed
                if attr == 'onclick':
                    match = re.search(r"'([^']+\.pdf[^']*)'", value)
                    if match:
                        value = match.group(1)
                return urljoin(base_url, value)
    
    return None


def fetch_pdf_scihub(doi, title):
    """Fetch PDF from Sci-Hub"""
    cleaned_doi = clean_doi(doi)
    if not cleaned_doi:
        LOGGER.warning(f"Invalid DOI: {doi}")
        return None
    
    lookup_url = f"{SCIHUB_MIRROR}/{quote(cleaned_doi)}"
    LOGGER.info(f"Trying Sci-Hub: {lookup_url}")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) LiteratureResearchBot/1.0",
        "Accept": "text/html,application/pdf,*/*",
    })
    
    try:
        response = session.get(lookup_url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as error:
        LOGGER.warning(f"Sci-Hub request failed: {error}")
        return None
    
    # Check if direct PDF response
    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" in content_type:
        filename = re.sub(r'[^A-Za-z0-9._-]+', '_', title[:80]) + f"_{cleaned_doi.replace('/', '_')}.pdf"
        pdf_path = PDF_DIR / filename
        pdf_path.write_bytes(response.content)
        LOGGER.info(f"✅ Downloaded PDF directly: {filename}")
        return str(pdf_path)
    
    # Extract PDF URL from HTML
    pdf_url = extract_scihub_pdf_url(response.text, SCIHUB_MIRROR)
    if not pdf_url:
        LOGGER.warning("No PDF link found in Sci-Hub response")
        return None
    
    # Download PDF from extracted URL
    try:
        pdf_response = session.get(pdf_url, timeout=15)
        pdf_response.raise_for_status()
        
        filename = re.sub(r'[^A-Za-z0-9._-]+', '_', title[:80]) + f"_{cleaned_doi.replace('/', '_')}.pdf"
        pdf_path = PDF_DIR / filename
        pdf_path.write_bytes(pdf_response.content)
        LOGGER.info(f"✅ Downloaded PDF via URL: {filename}")
        return str(pdf_path)
    except requests.RequestException as error:
        LOGGER.warning(f"PDF download failed: {error}")
        return None


def attach_pdf_to_item(api_key, item_key, pdf_path, title):
    """Attach PDF to Zotero item"""
    pdf_file = Path(pdf_path)
    
    with open(pdf_file, 'rb') as f:
        pdf_data = f.read()
    
    # Create attachment item
    attach_data = {
        "itemType": "attachment",
        "parentItem": item_key,
        "linkMode": "imported_file",
        "contentType": "application/pdf",
        "filename": pdf_file.name,
        "title": f"PDF - {title[:50]}"
    }
    
    # Register attachment
    response = requests.post(
        f"https://api.zotero.org/groups/{GROUP_ID}/items",
        headers={
            "Zotero-API-Key": api_key,
            "Content-Type": "application/json"
        },
        json=[attach_data]
    )
    
    if response.status_code not in (200, 201):
        LOGGER.error(f"Failed to create attachment: {response.status_code}")
        return False
    
    result = response.json()
    attach_key = result.get("successful", {}).get("0", {}).get("key")
    
    if not attach_key:
        LOGGER.error("Could not extract attachment key")
        return False
    
    # Upload file content
    response_upload = requests.post(
        f"https://api.zotero.org/groups/{GROUP_ID}/items/{attach_key}/file",
        headers={
            "Zotero-API-Key": api_key,
            "Content-Type": "application/pdf",
            "If-None-Match": "*"
        },
        data=pdf_data
    )
    
    if response_upload.status_code == 204:
        LOGGER.info(f"📎 Attached PDF to Zotero item {item_key}")
        return True
    else:
        LOGGER.warning(f"Failed to upload PDF: {response_upload.status_code}")
        return False


def main():
    config = load_config()
    api_key = config["api_key"]
    
    LOGGER.info("Fetching items from collection...")
    items = get_collection_items(api_key)
    LOGGER.info(f"Found {len(items)} items")
    
    # Filter: has DOI, no existing PDF attachment
    candidates = []
    for item in items:
        data = item["data"]
        doi = data.get("DOI", "")
        if not doi:
            continue
        
        # Check if already has PDF attachment
        has_pdf = any(
            child.get("data", {}).get("contentType") == "application/pdf"
            for child in item.get("links", {}).get("attachment", {}).get("attachments", [])
        )
        
        # Simplified check: just try to fetch for all with DOIs
        candidates.append({
            "key": data["key"],
            "title": data.get("title", ""),
            "doi": doi
        })
    
    LOGGER.info(f"Found {len(candidates)} papers with DOIs to try fetching")
    
    success_count = 0
    failed_count = 0
    
    for paper in candidates:
        LOGGER.info(f"\n🔍 [{success_count + failed_count + 1}/{len(candidates)}] {paper['title'][:60]}...")
        LOGGER.info(f"   DOI: {paper['doi']}")
        
        pdf_path = fetch_pdf_scihub(paper['doi'], paper['title'])
        
        if pdf_path:
            # Attach to Zotero
            if attach_pdf_to_item(api_key, paper['key'], pdf_path, paper['title']):
                success_count += 1
                LOGGER.info("   ✅ SUCCESS!")
            else:
                failed_count += 1
                LOGGER.info("   ⚠️  PDF fetched but attachment failed")
        else:
            failed_count += 1
            LOGGER.info("   ❌ Failed to fetch PDF")
        
        # Rate limiting
        import time
        time.sleep(2)
    
    LOGGER.info(f"\n\n🎉 COMPLETE:")
    LOGGER.info(f"  ✅ Success: {success_count}")
    LOGGER.info(f"  ❌ Failed: {failed_count}")
    LOGGER.info(f"  📊 Success rate: {success_count}/{len(candidates)} ({100*success_count/len(candidates) if candidates else 0:.1f}%)")


if __name__ == "__main__":
    main()

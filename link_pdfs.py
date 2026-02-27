#!/usr/bin/env python3
"""
Link locally downloaded PDFs to Zotero items as file attachments.
Simpler than trying to upload to Zotero storage.
"""
import json
import logging
import requests
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
LOGGER = logging.getLogger(__name__)

CONFIG_PATH = Path("~/.openclaw/workspace/.zotero-config.json").expanduser()
GROUP_ID = "5120604"
COLLECTION_KEY = "UV4I5VWV"
PDF_DIR = Path("~/.openclaw/workspace/literature/pdfs").expanduser()


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_collection_items(api_key):
    """Fetch all items in the collection"""
    url = f"https://api.zotero.org/groups/{GROUP_ID}/collections/{COLLECTION_KEY}/items?limit=100"
    response = requests.get(url, headers={"Zotero-API-Key": api_key})
    response.raise_for_status()
    return response.json()


def find_pdf_for_doi(doi):
    """Find local PDF file matching a DOI"""
    if not doi:
        return None
    
    # Clean DOI for filename matching
    doi_clean = doi.replace('/', '_').replace(':', '_')
    
    # Look for files containing this DOI
    for pdf_path in PDF_DIR.glob("*.pdf"):
        if doi_clean in pdf_path.name:
            return pdf_path
    
    return None


def attach_linked_pdf(api_key, item_key, pdf_path, title, version):
    """Attach PDF as linked file (not imported to Zotero storage)"""
    
    # Create attachment item with linked_file mode
    attach_data = {
        "itemType": "attachment",
        "parentItem": item_key,
        "linkMode": "linked_file",
        "contentType": "application/pdf",
        "title": f"PDF - {title[:50]}",
        "path": str(pdf_path.resolve())  # Absolute path
    }
    
    # Create attachment
    response = requests.post(
        f"https://api.zotero.org/groups/{GROUP_ID}/items",
        headers={
            "Zotero-API-Key": api_key,
            "Content-Type": "application/json"
        },
        json=[attach_data]
    )
    
    if response.status_code in (200, 201):
        result = response.json()
        attach_key = result.get("successful", {}).get("0", {}).get("key")
        if attach_key:
            LOGGER.info(f"📎 Linked PDF to item {item_key}")
            return True
        else:
            LOGGER.error(f"Failed to get attachment key: {response.text}")
            return False
    else:
        LOGGER.error(f"Failed to create attachment: {response.status_code} - {response.text}")
        return False


def main():
    config = load_config()
    api_key = config["api_key"]
    
    LOGGER.info("Fetching items from collection...")
    items = get_collection_items(api_key)
    LOGGER.info(f"Found {len(items)} items")
    
    # Find items with DOIs that have local PDFs
    success_count = 0
    no_pdf_count = 0
    
    for item in items:
        data = item["data"]
        key = data["key"]
        version = data["version"]
        title = data.get("title", "")
        doi = data.get("DOI", "")
        
        if not doi:
            continue
        
        # Check for local PDF
        pdf_path = find_pdf_for_doi(doi)
        if not pdf_path:
            no_pdf_count += 1
            continue
        
        LOGGER.info(f"\n📄 {title[:60]}...")
        LOGGER.info(f"   DOI: {doi}")
        LOGGER.info(f"   PDF: {pdf_path.name}")
        
        if attach_linked_pdf(api_key, key, pdf_path, title, version):
            success_count += 1
        
    LOGGER.info(f"\n\n🎉 COMPLETE:")
    LOGGER.info(f"  ✅ Linked: {success_count}")
    LOGGER.info(f"  ⏭️  No local PDF: {no_pdf_count}")


if __name__ == "__main__":
    main()

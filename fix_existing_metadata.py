#!/usr/bin/env python3
"""
Fix metadata for papers already in Zotero with broken/missing author info.
Re-scrapes Google Scholar and updates Zotero items.
"""
import json
import logging
import requests
import sys
from pathlib import Path
from scholar_search import search_scholar

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
LOGGER = logging.getLogger(__name__)

CONFIG_PATH = Path("~/.openclaw/workspace/.zotero-config.json").expanduser()
GROUP_ID = "5120604"
COLLECTION_KEY = "UV4I5VWV"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_collection_items(api_key):
    """Fetch all items in the collection"""
    url = f"https://api.zotero.org/groups/{GROUP_ID}/collections/{COLLECTION_KEY}/items?limit=100"
    response = requests.get(url, headers={"Zotero-API-Key": api_key})
    response.raise_for_status()
    return response.json()


def _author_creators(authors):
    """Convert list of author name strings to Zotero creator objects"""
    creators = []
    for author in authors:
        parts = [p for p in author.strip().split(" ") if p]
        if len(parts) == 1:
            creators.append({"creatorType": "author", "name": parts[0]})
        elif len(parts) > 1:
            creators.append({
                "creatorType": "author",
                "firstName": " ".join(parts[:-1]),
                "lastName": parts[-1]
            })
    return creators


def update_item(api_key, item_key, item_data, version):
    """Update a Zotero item"""
    url = f"https://api.zotero.org/groups/{GROUP_ID}/items/{item_key}"
    response = requests.patch(
        url,
        headers={
            "Zotero-API-Key": api_key,
            "Content-Type": "application/json",
            "If-Unmodified-Since-Version": str(version)
        },
        json=item_data
    )
    
    if response.status_code == 204:
        return True
    else:
        LOGGER.error(f"Failed to update {item_key}: {response.status_code} - {response.text}")
        return False


def main():
    config = load_config()
    api_key = config["api_key"]
    
    LOGGER.info("Fetching all items from collection...")
    items = get_collection_items(api_key)
    LOGGER.info(f"Found {len(items)} items")
    
    fixed_count = 0
    skipped_count = 0
    failed_count = 0
    
    for item in items:
        data = item["data"]
        key = data["key"]
        version = data["version"]
        title = data.get("title", "")
        creators = data.get("creators", [])
        
        # Check if authors are missing/broken
        has_valid_authors = True
        
        if not creators:
            has_valid_authors = False
        else:
            # Check for obviously bad author data
            for creator in creators:
                author_name = creator.get("lastName", "") + creator.get("firstName", "") + creator.get("name", "")
                
                # Bad if: just numbers, contains "…", contains " - ", looks like a year
                if (
                    not author_name.strip() or  # Empty
                    author_name.strip().isdigit() or  # Just numbers (e.g., "2026")
                    "…" in author_name or  # Truncated text
                    " - " in author_name or  # Contains publication separator
                    len(author_name.strip()) > 100  # Suspiciously long
                ):
                    has_valid_authors = False
                    break
        
        if has_valid_authors:
            LOGGER.info(f"✓ {key}: Already has valid authors, skipping")
            skipped_count += 1
            continue
        
        LOGGER.info(f"🔧 {key}: Missing authors, re-scraping Scholar for: {title[:60]}...")
        
        # Search Scholar for this title
        results = search_scholar(title, max_results=1)
        
        if not results:
            LOGGER.warning(f"  ⚠️  No Scholar results found for: {title}")
            failed_count += 1
            continue
        
        # Use first result
        paper = results[0]
        new_authors = _author_creators(paper.get("authors", []))
        
        if not new_authors:
            LOGGER.warning(f"  ⚠️  No authors found in Scholar result")
            failed_count += 1
            continue
        
        LOGGER.info(f"  Found {len(new_authors)} authors: {[a.get('lastName', a.get('name')) for a in new_authors]}")
        
        # Update item
        data["creators"] = new_authors
        
        if update_item(api_key, key, data, version):
            LOGGER.info(f"  ✅ Updated {key}")
            fixed_count += 1
        else:
            failed_count += 1
    
    LOGGER.info(f"\n🎉 COMPLETE:")
    LOGGER.info(f"  ✅ Fixed: {fixed_count}")
    LOGGER.info(f"  ⏭️  Skipped (already OK): {skipped_count}")
    LOGGER.info(f"  ❌ Failed: {failed_count}")


if __name__ == "__main__":
    main()

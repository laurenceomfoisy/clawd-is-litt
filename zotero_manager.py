import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional


LOGGER = logging.getLogger(__name__)
DEFAULT_ZOTERO_CONFIG = Path("~/.openclaw/workspace/.zotero-config.json").expanduser()


def _read_zotero_config(config_path: Optional[str] = None) -> Dict:
    path = Path(config_path).expanduser() if config_path else DEFAULT_ZOTERO_CONFIG
    if not path.exists():
        raise FileNotFoundError(f"Zotero config not found at {path}")
    with path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def _base_command(config: Dict) -> List[str]:
    command = ["zotero-cli"]

    if config.get("api_key"):
        command.extend(["--api-key", str(config["api_key"])])
    if config.get("user_id"):
        command.extend(["--user-id", str(config["user_id"])])
    if config.get("group_id"):
        command.extend(["--group-id", str(config["group_id"])])
    if config.get("config"):
        command.extend(["--config", str(Path(config["config"]).expanduser())])

    return command


def _run_command(command: List[str]) -> str:
    LOGGER.info("Running command: %s", " ".join(command))
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"zotero-cli failed: {completed.stderr.strip() or completed.stdout.strip()}")
    return completed.stdout.strip()


def _resolve_collection_key(config: Dict, collection_name: Optional[str]) -> Optional[str]:
    if not collection_name:
        return None

    command = _base_command(config) + ["collections"]
    output = _run_command(command)
    try:
        collections = json.loads(output)
    except json.JSONDecodeError:
        LOGGER.warning("Could not decode collections output; skipping collection assignment")
        return None

    for collection in collections:
        data = collection.get("data", {})
        if data.get("name") == collection_name:
            return data.get("key")

    LOGGER.warning("Collection '%s' not found in Zotero library", collection_name)
    return None


def _extract_item_key(create_output: str) -> Optional[str]:
    try:
        payload = json.loads(create_output)
    except json.JSONDecodeError:
        return None

    successful = payload.get("successful", {}) if isinstance(payload, dict) else {}
    for value in successful.values():
        key = value.get("key")
        if key:
            return key

    if isinstance(payload, list) and payload:
        candidate = payload[0]
        if isinstance(candidate, dict):
            return candidate.get("key")
    return None


def _author_creators(authors: List[str]) -> List[Dict[str, str]]:
    creators = []
    for author in authors:
        parts = [part for part in author.strip().split(" ") if part]
        if len(parts) == 1:
            creators.append({"creatorType": "author", "name": parts[0]})
        elif len(parts) > 1:
            creators.append(
                {
                    "creatorType": "author",
                    "firstName": " ".join(parts[:-1]),
                    "lastName": parts[-1],
                }
            )
    return creators


def add_paper(
    metadata_dict: Dict,
    pdf_path: Optional[str],
    zotero_config_path: Optional[str] = None,
) -> Optional[str]:
    """
    Add a journal article to Zotero and optionally link a local PDF.

    Returns the Zotero item key when successful, otherwise None.
    """
    config = _read_zotero_config(zotero_config_path)
    collection_key = _resolve_collection_key(config, metadata_dict.get("collection_name"))

    item_payload = {
        "itemType": "journalArticle",
        "title": metadata_dict.get("title", ""),
        "creators": _author_creators(metadata_dict.get("authors", [])),
        "abstractNote": metadata_dict.get("snippet", ""),
        "DOI": metadata_dict.get("doi", ""),
        "url": metadata_dict.get("url", ""),
        "date": str(metadata_dict.get("year", "") or ""),
        "extra": metadata_dict.get("extra", ""),
    }

    for key in (
        "publicationTitle",
        "volume",
        "issue",
        "pages",
        "ISSN",
        "journalAbbreviation",
    ):
        if metadata_dict.get(key):
            item_payload[key] = metadata_dict[key]

    if collection_key:
        item_payload["collections"] = [collection_key]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp_file:
        json.dump([item_payload], tmp_file)
        temp_path = tmp_file.name

    command = _base_command(config) + ["create-item", temp_path]
    try:
        output = _run_command(command)
    finally:
        Path(temp_path).unlink(missing_ok=True)

    item_key = _extract_item_key(output)
    if not item_key:
        LOGGER.error("Failed to parse created Zotero item key")
        return None

    LOGGER.info("Created Zotero item with key %s", item_key)

    if pdf_path:
        pdf = Path(pdf_path).expanduser()
        if pdf.exists():
            attachment_payload = {
                "itemType": "attachment",
                "parentItem": item_key,
                "linkMode": "linked_file",
                "title": f"PDF - {metadata_dict.get('title', 'paper')}",
                "path": pdf.resolve().as_uri(),
                "contentType": "application/pdf",
            }
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp_file:
                json.dump([attachment_payload], tmp_file)
                attachment_temp_path = tmp_file.name

            attach_command = _base_command(config) + ["create-item", attachment_temp_path]
            try:
                _run_command(attach_command)
                LOGGER.info("Attached PDF to item %s", item_key)
            except Exception as error:
                LOGGER.warning("Failed to attach PDF to %s: %s", item_key, error)
            finally:
                Path(attachment_temp_path).unlink(missing_ok=True)

    return item_key

def add_paper_to_group(metadata_dict, pdf_path=None, group_id="5120604", config_path=None):
    """Add paper to CLESSN group library with proper metadata formatting"""
    import os
    import re
    import requests
    
    config = _read_zotero_config(config_path)
    api_key = config["api_key"]
    
    # Create item with PROPER author formatting (using _author_creators helper)
    item_data = {
        "itemType": "journalArticle",
        "title": metadata_dict.get("title", ""),
        "creators": _author_creators(metadata_dict.get("authors", [])),  # FIX: Use proper firstName/lastName
        "date": str(metadata_dict.get("year", "")),
        "DOI": metadata_dict.get("doi", ""),
        "url": metadata_dict.get("url", ""),
        "abstractNote": metadata_dict.get("snippet", ""),
        "extra": f"Citations: {metadata_dict.get('citations', 0)}"
    }
    
    # POST to Zotero API
    response = requests.post(
        f"https://api.zotero.org/groups/{group_id}/items",
        headers={
            "Zotero-API-Key": api_key,
            "Content-Type": "application/json"
        },
        json=[item_data]
    )
    
    if response.status_code not in (200, 201):
        LOGGER.error(f"Failed to create item: {response.status_code} - {response.text}")
        return None
    
    # Extract item key
    result = response.json()
    item_key = result.get("successful", {}).get("0", {}).get("key")
    
    if not item_key:
        LOGGER.error("Could not extract item key from response")
        return None
    
    LOGGER.info(f"✅ Added to CLESSN: {item_key} - {metadata_dict.get('title', '')[:50]}...")
    
    # Attach PDF if provided
    if pdf_path and os.path.exists(pdf_path):
        pdf_file = Path(pdf_path)
        
        # Upload file attachment
        with open(pdf_file, 'rb') as f:
            pdf_data = f.read()
        
        # Create attachment item
        attach_data = {
            "itemType": "attachment",
            "parentItem": item_key,
            "linkMode": "imported_file",
            "contentType": "application/pdf",
            "filename": pdf_file.name
        }
        
        # Register attachment
        response_attach = requests.post(
            f"https://api.zotero.org/groups/{group_id}/items",
            headers={
                "Zotero-API-Key": api_key,
                "Content-Type": "application/json"
            },
            json=[attach_data]
        )
        
        if response_attach.status_code in (200, 201):
            result_attach = response_attach.json()
            attach_key = result_attach.get("successful", {}).get("0", {}).get("key")
            
            if attach_key:
                # Upload actual file content
                response_upload = requests.post(
                    f"https://api.zotero.org/groups/{group_id}/items/{attach_key}/file",
                    headers={
                        "Zotero-API-Key": api_key,
                        "Content-Type": "application/pdf",
                        "If-None-Match": "*"
                    },
                    data=pdf_data
                )
                
                if response_upload.status_code == 204:
                    LOGGER.info(f"📎 Attached PDF to item {item_key}")
                else:
                    LOGGER.warning(f"Failed to upload PDF content: {response_upload.status_code}")
        else:
            LOGGER.warning(f"Failed to create attachment: {response_attach.status_code}")
    
    return item_key

import argparse
import logging
import re
from pathlib import Path
from typing import Dict, Optional

import yaml
from tqdm import tqdm

from pdf_fetcher import fetch_pdf
from scholar_search import search_scholar
from zotero_manager import add_paper


DOI_PATTERN = re.compile(r"10\.\d{4,}/\S+", re.IGNORECASE)
DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.FileHandler("literature.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def load_config(config_path: Optional[str] = None) -> Dict:
    path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}


def is_valid_doi(doi: Optional[str]) -> bool:
    return bool(doi and DOI_PATTERN.fullmatch(doi.strip()))


def run_pipeline(question: str, max_papers: int, collection: Optional[str], config_path: Optional[str]) -> int:
    logger = logging.getLogger(__name__)
    config = load_config(config_path)
    zotero_config_path = config.get("zotero_config_path")

    logger.info("Searching Google Scholar for query: %s", question)
    papers = search_scholar(question, max_results=max_papers)

    pdf_success_count = 0
    zotero_success_count = 0

    for paper in tqdm(papers, desc="Processing papers", unit="paper"):
        doi = (paper.get("doi") or "").strip()
        pdf_path = None
        source = None

        if is_valid_doi(doi):
            try:
                pdf_path, source = fetch_pdf(doi, paper.get("title", "paper"), config_path=config_path)
                if pdf_path:
                    pdf_success_count += 1
            except Exception as error:
                logger.warning("PDF retrieval failed for DOI %s: %s", doi, error)
        else:
            logger.info("Skipping PDF retrieval; DOI missing or invalid for '%s'", paper.get("title", ""))

        item_metadata = dict(paper)
        if collection:
            item_metadata["collection_name"] = collection
        if source:
            item_metadata["extra"] = f"PDF source: {source}"

        try:
            item_id = add_paper(item_metadata, pdf_path, zotero_config_path=zotero_config_path)
            if item_id:
                zotero_success_count += 1
        except Exception as error:
            logger.error("Failed adding paper to Zotero (%s): %s", paper.get("title", ""), error)

    summary = (
        f"Summary: {len(papers)} papers found, "
        f"{pdf_success_count} PDFs fetched, "
        f"{zotero_success_count} added to Zotero"
    )
    logger.info(summary)
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scholarly literature research pipeline")
    parser.add_argument("research_question", help="Research question to search on Google Scholar")
    parser.add_argument("--max-papers", type=int, default=10, help="Maximum papers to process")
    parser.add_argument("--collection", default=None, help="Target Zotero collection name")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to YAML config file")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging()
    return run_pipeline(
        question=args.research_question,
        max_papers=args.max_papers,
        collection=args.collection,
        config_path=args.config,
    )


if __name__ == "__main__":
    raise SystemExit(main())

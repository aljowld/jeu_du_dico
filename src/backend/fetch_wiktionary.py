"""Script to fetch rare words and their definitions from French Wiktionary."""

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from src.backend.database import SessionLocal, init_db
from src.backend.models import Word

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

USER_AGENT = "JeuDuDico/1.0 (https://github.com/aljowld/jeu_du_dico; educational party game)"
WIKTIONARY_API_URL = "https://fr.wiktionary.org/w/api.php"
WIKTIONARY_RAW_URL = "https://fr.wiktionary.org/w/index.php"

CATEGORIES = [
    "Catégorie:Termes_rares_en_français",
    "Catégorie:Termes_désuets_en_français",
    "Catégorie:Termes_littéraires_en_français",
]

WORD_REGEX = re.compile(r"^[a-zàâäéèêëîïôöùûüçœæ]{5,15}$", re.IGNORECASE)


def clean_definition(raw_line: str) -> str:
    """Clean wikitext markup from a definition line.

    Args:
        raw_line: Raw wikitext line starting with '# '.

    Returns:
        Clean human-readable definition string.
    """
    # Remove initial hash and whitespace
    text = re.sub(r"^#\s*", "", raw_line)
    # Remove templates like {{territoire|fr}} or {{figures|fr}}
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    # Convert [[target|label]] to label, and [[word]] to word
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove quotes/apostrophes markup
    text = re.sub(r"''+", "", text)
    # Collapse multiple whitespaces
    return re.sub(r"\s+", " ", text).strip()


def fetch_category_words(
    client: httpx.Client,
    category: str,
    limit: int = 100,
) -> list[str]:
    """Fetch member page titles from a Wiktionary category.

    Args:
        client: HTTP client instance.
        category: Target category title.
        limit: Maximum number of words to query.

    Returns:
        List of filtered word candidates.
    """
    params: dict[str, Any] = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmlimit": limit,
        "format": "json",
    }
    try:
        response = client.get(WIKTIONARY_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        members = data.get("query", {}).get("categorymembers", [])
        return [
            m["title"]
            for m in members
            if WORD_REGEX.match(m["title"]) and not m["title"].startswith("Catégorie:")
        ]
    except httpx.HTTPError:
        logger.exception("Failed to query category %s", category)
        return []


def fetch_word_definition(client: httpx.Client, word: str) -> str | None:
    """Fetch and parse the primary definition of a French word from Wiktionary.

    Args:
        client: HTTP client instance.
        word: The target word.

    Returns:
        Primary definition text or None if parsing fails.
    """
    params = {"action": "raw", "title": word}
    try:
        response = client.get(WIKTIONARY_RAW_URL, params=params)
        if response.status_code != 200:  # noqa: PLR2004
            return None

        # Extract lines that represent definitions (# followed by space, not examples #*)
        for line in response.text.splitlines():
            if line.startswith("# ") and not line.startswith(("#*", "#:")):
                cleaned = clean_definition(line)
                # Keep meaningful definitions between 20 and 350 chars
                min_len, max_len = 20, 350
                if min_len <= len(cleaned) <= max_len:
                    return cleaned

    except httpx.HTTPError:
        logger.warning("Failed to fetch definition for %s", word)

    return None


def fetch_and_save_words(target_count: int = 50) -> None:
    """Fetch rare words from Wiktionary and persist them to json and sqlite.

    Args:
        target_count: Desired number of new words to add.
    """
    init_db()
    json_path = Path(__file__).parent / "word_list.json"

    # Load existing words
    existing_words: dict[str, str] = {}
    if json_path.exists():
        with Path.open(json_path, encoding="utf-8") as f:
            existing_words = json.load(f)

    logger.info("Starting extraction from Wiktionary (goal: %d new words)...", target_count)
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client(headers=headers, timeout=10.0) as client:
        # Collect candidate titles across categories
        candidates: list[str] = []
        for cat in CATEGORIES:
            words = fetch_category_words(client, cat, limit=150)
            candidates.extend(words)

        # Remove duplicates while preserving order
        unique_candidates = [
            w for w in dict.fromkeys(candidates) if w.lower() not in existing_words
        ]
        logger.info("Found %d unique candidates to inspect.", len(unique_candidates))

        added = 0
        for candidate in unique_candidates:
            if added >= target_count:
                break

            definition = fetch_word_definition(client, candidate)
            if definition:
                word_lower = candidate.lower()
                existing_words[word_lower] = definition
                added += 1
                logger.info("[%d/%d] Added '%s': %s", added, target_count, candidate, definition)

    # Save to JSON
    with Path.open(json_path, "w", encoding="utf-8") as f:
        json.dump(existing_words, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d total words to %s", len(existing_words), json_path)

    # Sync to SQLite
    with SessionLocal() as db:
        db_added = 0
        for word_str, def_str in existing_words.items():
            existing = db.query(Word).filter(Word.word == word_str).first()
            if not existing:
                db.add(Word(word=word_str, definition=def_str))
                db_added += 1
        db.commit()
        logger.info("Synchronized database: %d new words inserted into SQLite.", db_added)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch rare words from Wiktionary.")
    parser.add_argument("--count", type=int, default=30, help="Number of new words to fetch")
    args = parser.parse_args()
    fetch_and_save_words(target_count=args.count)

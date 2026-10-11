"""Script to synchronize the database with word_list.json."""

import json
import logging
from pathlib import Path

from src.backend.core.database import SessionLocal, init_db
from src.backend.models.models import Word

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def sync_db_with_json() -> None:
    """Synchronize the database to match word_list.json exactly.

    Adds new words, updates modified definitions, and removes words from the database
    that are no longer present in word_list.json.
    """
    init_db()

    json_path = Path(__file__).parent / "word_list.json"

    if not json_path.exists():
        logger.error("File not found: %s", json_path)
        return

    with Path.open(json_path, encoding="utf-8") as f:
        words_data: dict[str, str] = json.load(f)

    # Normalize words from json
    json_words = {
        word.strip().lower(): definition.strip() for word, definition in words_data.items()
    }

    with SessionLocal() as db:
        # Fetch all existing words in database
        db_words = db.query(Word).all()
        db_words_dict = {w.word.lower(): w for w in db_words}

        added_count = 0
        updated_count = 0
        deleted_count = 0

        # 1. Add new words and update modified definitions
        for word_str, definition in json_words.items():
            if word_str in db_words_dict:
                existing = db_words_dict[word_str]
                if existing.definition != definition:
                    existing.definition = definition
                    updated_count += 1
            else:
                db.add(Word(word=word_str, definition=definition))
                added_count += 1

        # 2. Delete words present in DB but absent from JSON
        for word_str, db_word in db_words_dict.items():
            if word_str not in json_words:
                db.delete(db_word)
                deleted_count += 1

        db.commit()
        logger.info(
            "Sync complete: %d added, %d updated, %d removed. Total in DB: %d",
            added_count,
            updated_count,
            deleted_count,
            len(json_words),
        )


if __name__ == "__main__":
    sync_db_with_json()

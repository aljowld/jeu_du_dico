"""Script to initialize and seed the database from word_list.json."""

import json
import logging
from pathlib import Path

from src.backend.database import SessionLocal, init_db
from src.backend.models import Word

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_words() -> None:
    """Populate the database with initial entries from word_list.json."""
    init_db()

    json_path = Path(__file__).parent / "word_list.json"

    if not json_path.exists():
        logger.info("File not found: %s", json_path)
        return

    with Path.open(json_path, encoding="utf-8") as f:
        words_data = json.load(f)

    with SessionLocal() as db:
        added_count = 0
        for word_str, definition in words_data.items():
            existing_word = db.query(Word).filter(Word.word == word_str).first()
            if not existing_word:
                new_word = Word(word=word_str, definition=definition)
                db.add(new_word)
                added_count += 1

        db.commit()
        logger.info("Success: %d new words added to the database.", added_count)


if __name__ == "__main__":
    seed_words()

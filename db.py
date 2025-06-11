import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
DATABASE_FILE = Path(__file__).resolve().parent / "bot_database.db"

def _execute_query(query, params=(), fetchone=False, fetchall=False):
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            if fetchone:
                return cursor.fetchone()
            if fetchall:
                return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Ошибка БД при выполнении запроса '{query[:50]}...': {e}")
        return None

def initialize_db():
    _execute_query("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        status_message_id INTEGER,
        is_active BOOLEAN DEFAULT TRUE
    )
    """)
    logger.info("База данных инициализирована.")

def create_user(user_id: int):
    _execute_query("INSERT INTO users (user_id) VALUES (?) ON CONFLICT(user_id) DO UPDATE SET is_active=TRUE", (user_id,))

def get_user_settings(user_id: int) -> dict | None:
    row = _execute_query("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    return dict(row) if row else None

def update_user_status_message_id(user_id: int, message_id: int):
    _execute_query("UPDATE users SET status_message_id = ? WHERE user_id = ?", (message_id, user_id))

def get_all_users_with_status_message() -> list[dict]:
    rows = _execute_query("SELECT user_id, status_message_id FROM users WHERE is_active = TRUE AND status_message_id IS NOT NULL", fetchall=True)
    return [dict(row) for row in rows] if rows else []

def disable_user(user_id: int):
    _execute_query("UPDATE users SET is_active = FALSE WHERE user_id = ?", (user_id,))
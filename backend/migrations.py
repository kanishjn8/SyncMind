"""Idempotent startup migrations for the MySQL schema.

The ``db/init/*.sql`` files run only on a *fresh* MySQL volume. Once a
developer has an existing database, those files never re-run, so any
new columns / tables we add to the canonical schema need a separate
in-app migration step.

MySQL 8 supports ``CREATE TABLE IF NOT EXISTS`` but not ``ADD COLUMN
IF NOT EXISTS``. We work around that by introspecting
``INFORMATION_SCHEMA.COLUMNS`` and only running the ``ALTER TABLE``
when the column is missing.

Call :func:`run_migrations` at FastAPI startup (in ``main.py``).
"""

from __future__ import annotations

import os
from typing import Callable

import mysql.connector


def _connect():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT", "3306")),
    )


def _column_exists(cursor, table: str, column: str, schema: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (schema, table, column),
    )
    return cursor.fetchone() is not None


def _table_exists(cursor, table: str, schema: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
        """,
        (schema, table),
    )
    return cursor.fetchone() is not None


# (table, column, DDL fragment to add it). Order matters: dependent
# migrations should come after the ones they depend on.
USER_LOCATION_COLUMNS: list[tuple[str, str]] = [
    ("locale", "VARCHAR(16) NULL"),
    ("country", "VARCHAR(128) NULL"),
    ("region", "VARCHAR(128) NULL"),
    ("city", "VARCHAR(128) NULL"),
    ("country_code", "VARCHAR(8) NULL"),
    ("location_updated_at", "DATETIME NULL"),
]


JOB_RECOMMENDATIONS_DDL = """
CREATE TABLE IF NOT EXISTS job_recommendations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  job_id VARCHAR(512) NULL,
  title VARCHAR(500) NOT NULL,
  company_name VARCHAR(255) NULL,
  location VARCHAR(255) NULL,
  via VARCHAR(255) NULL,
  description TEXT NULL,
  thumbnail TEXT NULL,
  share_link TEXT NULL,
  apply_link TEXT NULL,
  posted_at VARCHAR(64) NULL,
  schedule_type VARCHAR(64) NULL,
  query_used VARCHAR(255) NULL,
  location_used VARCHAR(255) NULL,
  fetched_at DATETIME NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_jobs_user (user_id),
  CONSTRAINT fk_job_recommendations_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
)
"""


def run_migrations(logger: Callable[[str], None] = print) -> None:
    """Run all idempotent schema migrations.

    Safe to call on every process start — each step is a no-op when the
    target shape already exists.
    """
    schema = os.getenv("DB_NAME")
    if not schema:
        logger("[migrations] DB_NAME not set, skipping")
        return

    try:
        conn = _connect()
    except Exception as e:
        logger(f"[migrations] Failed to connect to MySQL: {e}")
        return

    try:
        cursor = conn.cursor()

        # 1. Add location columns to `users`.
        added = []
        for column, ddl in USER_LOCATION_COLUMNS:
            if not _column_exists(cursor, "users", column, schema):
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {ddl}")
                added.append(column)
        if added:
            logger(f"[migrations] users: added columns {added}")

        # 2. Ensure `job_recommendations` exists.
        if not _table_exists(cursor, "job_recommendations", schema):
            cursor.execute(JOB_RECOMMENDATIONS_DDL)
            logger("[migrations] created table job_recommendations")

        conn.commit()
    except Exception as e:
        logger(f"[migrations] Error during migration: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        conn.close()

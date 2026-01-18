"""
Database connection and initialization.
Uses aiosqlite for async SQLite operations.
"""
import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from ..config import settings


# Connection pool (simple singleton for SQLite)
_db_connection: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Get the database connection."""
    global _db_connection
    
    if _db_connection is None:
        _db_connection = await aiosqlite.connect(
            settings.db_path,
            isolation_level=None  # Autocommit mode, we manage transactions explicitly
        )
        # Enable foreign keys
        await _db_connection.execute("PRAGMA foreign_keys = ON")
        # Enable WAL mode for better concurrency
        await _db_connection.execute("PRAGMA journal_mode = WAL")
        # Row factory for dict-like access
        _db_connection.row_factory = aiosqlite.Row
    
    return _db_connection


@asynccontextmanager
async def get_db_transaction() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Context manager for database transactions.
    Commits on success, rolls back on exception.
    """
    db = await get_db()
    await db.execute("BEGIN")
    try:
        yield db
        await db.execute("COMMIT")
    except Exception:
        await db.execute("ROLLBACK")
        raise


async def init_database() -> None:
    """
    Initialize the database schema.
    Creates tables if they don't exist.
    """
    # Ensure hot storage directory exists
    settings.ensure_directories()
    
    # Read schema SQL
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r") as f:
        schema_sql = f.read()
    
    # Execute schema
    db = await get_db()
    await db.executescript(schema_sql)
    
    print(f"Database initialized at: {settings.db_path}")


async def close_database() -> None:
    """Close the database connection."""
    global _db_connection
    
    if _db_connection is not None:
        await _db_connection.close()
        _db_connection = None


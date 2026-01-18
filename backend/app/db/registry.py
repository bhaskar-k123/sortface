"""
Person registry database operations.
Handles persons, embeddings, and centroids.
"""
import json
import numpy as np
from typing import Optional

from .db import get_db, get_db_transaction
from ..config import settings


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """Normalize embedding to unit length (L2 norm = 1)."""
    norm = np.linalg.norm(embedding)
    if norm > 0:
        return embedding / norm
    return embedding


def serialize_embedding(embedding: np.ndarray) -> bytes:
    """Serialize numpy embedding to bytes. Always normalizes first."""
    normalized = normalize_embedding(embedding)
    return normalized.astype(np.float32).tobytes()


def deserialize_embedding(data: bytes) -> np.ndarray:
    """Deserialize bytes to numpy embedding."""
    return np.frombuffer(data, dtype=np.float32).copy()  # .copy() to make writable


async def get_all_persons() -> list[dict]:
    """Get all registered persons with embedding counts."""
    db = await get_db()
    
    query = """
        SELECT 
            p.person_id,
            p.name,
            p.output_folder_rel,
            p.created_at,
            COUNT(pe.embedding_id) as embedding_count
        FROM persons p
        LEFT JOIN person_embeddings pe ON p.person_id = pe.person_id
        GROUP BY p.person_id
        ORDER BY p.name
    """
    
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    
    return [dict(row) for row in rows]


async def get_person_by_id(person_id: int) -> Optional[dict]:
    """Get a single person by ID."""
    db = await get_db()
    
    query = """
        SELECT 
            p.person_id,
            p.name,
            p.output_folder_rel,
            p.created_at
        FROM persons p
        WHERE p.person_id = ?
    """
    
    cursor = await db.execute(query, (person_id,))
    row = await cursor.fetchone()
    
    return dict(row) if row else None


async def create_person(name: str, output_folder_rel: str) -> int:
    """
    Create a new person in the registry.
    Returns the new person_id.
    """
    db = await get_db()
    
    cursor = await db.execute(
        "INSERT INTO persons (name, output_folder_rel) VALUES (?, ?)",
        (name, output_folder_rel)
    )
    await db.commit()
    
    return cursor.lastrowid


async def delete_person(person_id: int) -> bool:
    """
    Delete a person and all their embeddings from the registry.
    Returns True if deleted, False if not found.
    """
    db = await get_db()
    
    # Delete embeddings first (foreign key)
    await db.execute(
        "DELETE FROM person_embeddings WHERE person_id = ?",
        (person_id,)
    )
    
    # Delete centroid
    await db.execute(
        "DELETE FROM person_centroids WHERE person_id = ?",
        (person_id,)
    )
    
    # Delete person
    cursor = await db.execute(
        "DELETE FROM persons WHERE person_id = ?",
        (person_id,)
    )
    await db.commit()
    
    return cursor.rowcount > 0


async def add_person_embedding(
    person_id: int,
    embedding: np.ndarray,
    source_type: str = "reference"
) -> int:
    """
    Add an embedding to a person.
    Handles FIFO trimming if max embeddings exceeded.
    Updates centroid.
    Returns the new embedding_id.
    """
    async with get_db_transaction() as db:
        # Insert new embedding
        embedding_bytes = serialize_embedding(embedding)
        cursor = await db.execute(
            """INSERT INTO person_embeddings (person_id, embedding, source_type)
               VALUES (?, ?, ?)""",
            (person_id, embedding_bytes, source_type)
        )
        embedding_id = cursor.lastrowid
        
        # Check if we need to trim (FIFO)
        cursor = await db.execute(
            """SELECT COUNT(*) as cnt FROM person_embeddings WHERE person_id = ?""",
            (person_id,)
        )
        row = await cursor.fetchone()
        count = row["cnt"]
        
        if count > settings.max_embeddings_per_person:
            # Delete oldest embeddings to stay under limit
            excess = count - settings.max_embeddings_per_person
            await db.execute(
                """DELETE FROM person_embeddings 
                   WHERE embedding_id IN (
                       SELECT embedding_id FROM person_embeddings
                       WHERE person_id = ?
                       ORDER BY created_at ASC
                       LIMIT ?
                   )""",
                (person_id, excess)
            )
        
        # Update centroid
        await _update_centroid(db, person_id)
    
    return embedding_id


async def _update_centroid(db, person_id: int) -> None:
    """
    Update the centroid for a person based on all embeddings.
    Called within a transaction.
    
    Note: Centroid is computed as mean of embeddings, then RE-NORMALIZED
    to maintain unit length for consistent distance calculations.
    """
    # Get all embeddings
    cursor = await db.execute(
        "SELECT embedding FROM person_embeddings WHERE person_id = ?",
        (person_id,)
    )
    rows = await cursor.fetchall()
    
    if not rows:
        # No embeddings, remove centroid
        await db.execute(
            "DELETE FROM person_centroids WHERE person_id = ?",
            (person_id,)
        )
        return
    
    # Compute mean centroid
    embeddings = [deserialize_embedding(row["embedding"]) for row in rows]
    centroid = np.mean(embeddings, axis=0)
    
    # IMPORTANT: Re-normalize centroid after averaging!
    # Average of unit vectors is not a unit vector
    centroid = normalize_embedding(centroid)
    
    centroid_bytes = serialize_embedding(centroid)
    
    # Upsert centroid
    await db.execute(
        """INSERT INTO person_centroids (person_id, centroid, embedding_count, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(person_id) DO UPDATE SET
               centroid = excluded.centroid,
               embedding_count = excluded.embedding_count,
               updated_at = datetime('now')""",
        (person_id, centroid_bytes, len(rows))
    )


async def get_all_centroids() -> list[dict]:
    """
    Get all person centroids for matching.
    Returns list of {person_id, name, output_folder_rel, centroid}.
    """
    db = await get_db()
    
    cursor = await db.execute(
        """SELECT p.person_id, p.name, p.output_folder_rel, pc.centroid
           FROM persons p
           INNER JOIN person_centroids pc ON p.person_id = pc.person_id"""
    )
    rows = await cursor.fetchall()
    
    return [
        {
            "person_id": row["person_id"],
            "name": row["name"],
            "output_folder_rel": row["output_folder_rel"],
            "centroid": deserialize_embedding(row["centroid"])
        }
        for row in rows
    ]


async def get_person_embeddings(person_id: int) -> list[np.ndarray]:
    """Get all embeddings for a person."""
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT embedding FROM person_embeddings WHERE person_id = ? ORDER BY created_at",
        (person_id,)
    )
    rows = await cursor.fetchall()
    
    return [deserialize_embedding(row["embedding"]) for row in rows]


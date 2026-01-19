"""
Path utilities: file hashing and deterministic output filenames.
"""
from pathlib import Path
import hashlib


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """
    Compute hash of a file using streaming to handle large files.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (default: sha256)
    
    Returns:
        Hex digest of the file hash
    """
    hasher = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        # Read in 64KB chunks for memory efficiency
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_deterministic_filename(
    original_stem: str,
    file_hash: str,
    hash_chars: int = 12
) -> str:
    """
    Generate a deterministic output filename.
    
    Format: {original_stem}__{hash_prefix}.jpg
    
    This ensures:
    - Idempotent commits (same source = same output name)
    - No collisions (hash provides uniqueness)
    - Traceability (original name preserved)
    """
    hash_prefix = file_hash[:hash_chars]
    return f"{original_stem}__{hash_prefix}.jpg"


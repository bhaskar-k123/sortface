"""
Hot/Cold path model with safety checks.
Enforces storage semantics:
- External HDD source: READ-ONLY
- External HDD output: APPEND-ONLY (no overwrite, no delete)
- Internal disk (hot): all computation
"""
from pathlib import Path
from typing import Optional
import hashlib


class StorageError(Exception):
    """Raised when storage invariants are violated."""
    pass


class PathManager:
    """
    Manages path validation and safety for hot/cold storage.
    
    Invariants:
    - Source paths are read-only (no writes allowed)
    - Output paths are append-only (no overwrites, no deletes)
    - All intermediate work happens on hot storage
    """
    
    def __init__(
        self,
        source_root: Optional[Path] = None,
        output_root: Optional[Path] = None,
        hot_root: Optional[Path] = None
    ):
        self._source_root = source_root
        self._output_root = output_root
        self._hot_root = hot_root
    
    def set_source_root(self, path: Path) -> None:
        """Set the read-only source root (external HDD)."""
        if not path.exists():
            raise StorageError(f"Source root does not exist: {path}")
        if not path.is_dir():
            raise StorageError(f"Source root is not a directory: {path}")
        self._source_root = path.resolve()
    
    def set_output_root(self, path: Path) -> None:
        """Set the append-only output root (external HDD)."""
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        self._output_root = path
    
    def set_hot_root(self, path: Path) -> None:
        """Set the hot storage root (internal disk)."""
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        self._hot_root = path
    
    @property
    def source_root(self) -> Path:
        if self._source_root is None:
            raise StorageError("Source root not configured")
        return self._source_root
    
    @property
    def output_root(self) -> Path:
        if self._output_root is None:
            raise StorageError("Output root not configured")
        return self._output_root
    
    @property
    def hot_root(self) -> Path:
        if self._hot_root is None:
            raise StorageError("Hot storage root not configured")
        return self._hot_root
    
    def validate_source_read(self, path: Path) -> Path:
        """
        Validate that a path is within source root and exists.
        Returns resolved absolute path.
        """
        resolved = path.resolve()
        if not resolved.is_relative_to(self.source_root):
            raise StorageError(
                f"Path {path} is not within source root {self.source_root}"
            )
        if not resolved.exists():
            raise StorageError(f"Source file does not exist: {path}")
        return resolved
    
    def validate_output_write(self, path: Path) -> Path:
        """
        Validate that a path is within output root.
        Enforces append-only: raises if file already exists.
        Returns resolved absolute path.
        """
        resolved = path.resolve()
        if not resolved.is_relative_to(self.output_root):
            raise StorageError(
                f"Path {path} is not within output root {self.output_root}"
            )
        # Append-only check: file must not exist
        if resolved.exists():
            raise StorageError(
                f"Append-only violation: file already exists: {path}"
            )
        return resolved
    
    def output_exists(self, path: Path) -> bool:
        """Check if an output file already exists (for idempotency)."""
        resolved = path.resolve()
        if not resolved.is_relative_to(self.output_root):
            raise StorageError(
                f"Path {path} is not within output root {self.output_root}"
            )
        return resolved.exists()
    
    def get_person_output_dir(self, person_folder_rel: str) -> Path:
        """
        Get the output directory for a person.
        Creates if it doesn't exist (append-only allows new directories).
        """
        person_dir = self.output_root / person_folder_rel
        person_dir.mkdir(parents=True, exist_ok=True)
        return person_dir
    
    def validate_hot_path(self, path: Path) -> Path:
        """Validate that a path is within hot storage."""
        resolved = path.resolve()
        if not resolved.is_relative_to(self.hot_root):
            raise StorageError(
                f"Path {path} is not within hot storage {self.hot_root}"
            )
        return resolved


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


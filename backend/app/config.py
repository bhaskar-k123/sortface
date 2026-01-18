"""
Configuration model for the Face-Based Photo Segregation System.
All paths and constants are centralized here.
"""
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""
    
    # Hot storage (internal disk) - all computation happens here
    hot_storage_root: Path = Field(
        default=Path("./hot_storage"),
        description="Root directory for all internal computation, DB, state, and staging"
    )
    
    # Face recognition thresholds (Euclidean distance on normalized embeddings)
    # For normalized 512-dim embeddings, distance range is 0-2:
    # - 0 = identical faces
    # - ~0.8 = high confidence same person
    # - ~1.0 = moderate confidence same person  
    # - >1.0 = likely different person
    # - 2 = completely opposite embeddings
    threshold_strict: float = Field(
        default=0.80,
        description="STRICT threshold: auto-match + learn new embeddings (high confidence)"
    )
    threshold_loose: float = Field(
        default=1.00,
        description="LOOSE threshold: match only, no learning (moderate confidence)"
    )
    
    # Embedding management
    max_embeddings_per_person: int = Field(
        default=30,
        description="Maximum embeddings stored per person (FIFO trimming)"
    )
    
    # Batch processing
    atomic_batch_size: int = Field(
        default=50,
        description="Number of images per atomic batch (crash boundary)"
    )
    
    # Output compression settings (locked policy)
    output_max_long_edge: int = Field(
        default=2048,
        description="Maximum long edge for output JPEGs"
    )
    output_jpeg_quality: int = Field(
        default=85,
        description="JPEG quality for output images"
    )
    
    # Server settings
    server_host: str = Field(default="127.0.0.1")
    server_port: int = Field(default=8000)
    
    # Supported input extensions
    supported_extensions: tuple = (".jpg", ".jpeg", ".arw")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def db_path(self) -> Path:
        """SQLite database path."""
        return self.hot_storage_root / "registry.db"
    
    @property
    def state_dir(self) -> Path:
        """Directory for tracker state files."""
        return self.hot_storage_root / "state"
    
    @property
    def staging_dir(self) -> Path:
        """Directory for staging deliverable JPEGs before commit."""
        return self.hot_storage_root / "staging"
    
    @property
    def temp_dir(self) -> Path:
        """Directory for temporary files (e.g., RAW conversions)."""
        return self.hot_storage_root / "temp"
    
    @property
    def models_dir(self) -> Path:
        """Directory for face recognition models."""
        return self.hot_storage_root / "models"
    
    def ensure_directories(self) -> None:
        """Create all required hot storage directories."""
        self.hot_storage_root.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "batches").mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()


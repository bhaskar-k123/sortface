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
    
    # ========================================================================
    # PARALLEL PROCESSING SETTINGS
    # ========================================================================
    
    # CPU usage mode: "adaptive", "low", "balanced", "high", or "custom"
    cpu_usage_mode: str = Field(
        default="balanced",
        description="CPU usage preset: adaptive (auto-detect), low (2 workers), balanced (4 workers), high (6+ workers), custom (manual)"
    )
    
    # Manual worker count (only used when cpu_usage_mode="custom")
    max_parallel_workers: int = Field(
        default=4,
        description="Maximum concurrent image processing workers (only used in 'custom' mode)"
    )
    
    # Enable/disable parallel processing entirely
    enable_parallel_processing: bool = Field(
        default=True,
        description="Enable parallel image processing within batches"
    )
    
    def get_worker_count(self) -> int:
        """
        Get the actual worker count based on cpu_usage_mode.
        
        Returns the number of workers to use for parallel processing.
        """
        import os
        
        cpu_count = os.cpu_count() or 4
        
        if self.cpu_usage_mode == "adaptive":
            # Use 67% of available cores (rounded)
            workers = max(2, int(cpu_count * 0.67))
        elif self.cpu_usage_mode == "low":
            # Conservative: 2 workers (~40% CPU on 6-core)
            workers = 2
        elif self.cpu_usage_mode == "balanced":
            # Balanced: 4 workers (~67% CPU on 6-core)
            workers = 4
        elif self.cpu_usage_mode == "high":
            # Aggressive: use most cores
            workers = max(4, cpu_count - 1)  # Leave 1 core free
        elif self.cpu_usage_mode == "custom":
            # Use manual setting
            workers = self.max_parallel_workers
        else:
            # Fallback to balanced
            workers = 4
        
        # Clamp to reasonable range
        return max(1, min(workers, cpu_count))
    
    def get_cpu_usage_warning(self) -> str | None:
        """
        Get a warning message if CPU usage will be high.
        
        Returns warning string or None if usage is acceptable.
        """
        import os
        
        cpu_count = os.cpu_count() or 4
        workers = self.get_worker_count()
        usage_percent = (workers / cpu_count) * 100
        
        if usage_percent >= 85:
            return f"⚠️  HIGH CPU USAGE: {workers} workers on {cpu_count} cores (~{usage_percent:.0f}% CPU). System may become sluggish."
        elif usage_percent >= 70:
            return f"⚡ MODERATE CPU USAGE: {workers} workers on {cpu_count} cores (~{usage_percent:.0f}% CPU). System will be slightly slower."
        else:
            return None

    
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
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()


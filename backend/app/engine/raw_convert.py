"""
RAW (.arw) to JPEG conversion engine.
Used for face recognition preprocessing only.

IMPORTANT: RAW files are NEVER used directly for face recognition.
They must be converted to temporary JPEGs first.

Flow:
1. ARW file on external HDD (read-only)
2. Convert to temporary JPEG (internal hot storage)
3. Run face detection + embedding on temp JPEG
4. Delete temp JPEG
5. For delivery: re-read ARW and compress to deliverable JPEG
"""
import uuid
from pathlib import Path
from typing import Optional

import rawpy
import imageio
from PIL import Image

from ..config import settings


class RawConversionEngine:
    """
    Converts RAW files (.arw) to temporary JPEGs for face recognition.
    
    All temporary files are created in hot storage and should be
    deleted after face processing is complete.
    """
    
    def __init__(self):
        self.temp_dir = settings.temp_dir
        self.max_long_edge = settings.output_max_long_edge
    
    def convert_for_recognition(
        self,
        raw_path: Path,
        resize: bool = True
    ) -> Path:
        """
        Convert a RAW file to a temporary JPEG for face recognition.
        
        Args:
            raw_path: Path to .arw file
            resize: If True, resize to max 2048px for faster processing
        
        Returns:
            Path to temporary JPEG (caller must delete after use)
        """
        # Generate unique temp filename
        temp_filename = f"raw_temp_{uuid.uuid4().hex[:12]}.jpg"
        temp_path = self.temp_dir / temp_filename
        
        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Read RAW file
        with rawpy.imread(str(raw_path)) as raw:
            # Post-process to get RGB image
            # Use camera white balance and auto brightness
            rgb = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=False,
                output_bps=8
            )
        
        # Convert to PIL Image for resize
        img = Image.fromarray(rgb)
        
        if resize:
            img = self._resize_to_max_edge(img)
        
        # Save as JPEG
        img.save(temp_path, format="JPEG", quality=90)
        
        return temp_path
    
    def convert_for_delivery(
        self,
        raw_path: Path,
        output_path: Path
    ) -> Path:
        """
        Convert a RAW file to a deliverable JPEG.
        
        Uses the same compression policy as regular JPEGs:
        - Max 2048px long edge
        - Quality 85
        - sRGB color space
        - No metadata
        
        Args:
            raw_path: Path to .arw file
            output_path: Destination path for deliverable JPEG
        
        Returns:
            Path where deliverable was written
        """
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read RAW file with high quality settings
        with rawpy.imread(str(raw_path)) as raw:
            rgb = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=False,
                output_bps=8,
                demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD
            )
        
        # Convert to PIL Image
        img = Image.fromarray(rgb)
        
        # Ensure RGB mode
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Resize to max edge
        img = self._resize_to_max_edge(img)
        
        # Save as optimized JPEG
        img.save(
            output_path,
            format="JPEG",
            quality=settings.output_jpeg_quality,
            optimize=True
        )
        
        return output_path
    
    def _resize_to_max_edge(self, img: Image.Image) -> Image.Image:
        """Resize image so long edge is at most max_long_edge."""
        width, height = img.size
        long_edge = max(width, height)
        
        if long_edge <= self.max_long_edge:
            return img
        
        scale = self.max_long_edge / long_edge
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    @staticmethod
    def is_raw_file(path: Path) -> bool:
        """Check if a file is a RAW file based on extension."""
        return path.suffix.lower() == ".arw"
    
    @staticmethod
    def cleanup_temp_file(temp_path: Path) -> None:
        """
        Delete a temporary file.
        Silently ignores errors (file may already be deleted).
        """
        try:
            temp_path.unlink()
        except Exception:
            pass


def convert_raw_for_recognition(raw_path: Path) -> Path:
    """
    Convenience function to convert RAW for face recognition.
    
    Returns path to temporary JPEG that must be deleted after use.
    """
    engine = RawConversionEngine()
    return engine.convert_for_recognition(raw_path)


def convert_raw_for_delivery(raw_path: Path, output_path: Path) -> Path:
    """
    Convenience function to convert RAW to deliverable JPEG.
    """
    engine = RawConversionEngine()
    return engine.convert_for_delivery(raw_path, output_path)


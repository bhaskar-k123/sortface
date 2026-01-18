"""
Image compression engine.
Generates deliverable JPEGs with locked output policy.

Output Policy (LOCKED):
- Max long edge: 2048 px
- Aspect ratio: preserved
- JPEG quality: 85
- Color space: sRGB
- Metadata: stripped
"""
import io
from pathlib import Path
from typing import Optional

from PIL import Image, ImageCms

from ..config import settings


# sRGB ICC profile for color space conversion
_srgb_profile: Optional[ImageCms.ImageCmsProfile] = None


def _get_srgb_profile() -> ImageCms.ImageCmsProfile:
    """Get or create sRGB ICC profile."""
    global _srgb_profile
    if _srgb_profile is None:
        _srgb_profile = ImageCms.createProfile("sRGB")
    return _srgb_profile


class CompressionEngine:
    """
    Image compression with locked output policy.
    
    All outputs are:
    - JPEG format
    - Max 2048px on long edge
    - Quality 85
    - sRGB color space
    - No metadata
    """
    
    def __init__(self):
        self.max_long_edge = settings.output_max_long_edge
        self.jpeg_quality = settings.output_jpeg_quality
    
    def compress(
        self,
        input_path: Path,
        output_path: Path,
        staging_dir: Optional[Path] = None
    ) -> Path:
        """
        Compress an image to deliverable JPEG.
        
        Args:
            input_path: Source image path
            output_path: Final destination path
            staging_dir: If provided, write to staging first then return staging path
        
        Returns:
            Path where the compressed image was written
        """
        # Determine actual output path
        if staging_dir:
            actual_output = staging_dir / output_path.name
        else:
            actual_output = output_path
        
        # Ensure output directory exists
        actual_output.parent.mkdir(parents=True, exist_ok=True)
        
        # Load image
        with Image.open(input_path) as img:
            # Convert to RGB if necessary (handles RGBA, P, L modes)
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Convert to sRGB color space
            img = self._ensure_srgb(img)
            
            # Resize if needed (preserve aspect ratio)
            img = self._resize_to_max_edge(img)
            
            # Save as JPEG without metadata
            img.save(
                actual_output,
                format="JPEG",
                quality=self.jpeg_quality,
                optimize=True,
                exif=b"",  # Strip EXIF
                icc_profile=None  # Don't embed profile (assume sRGB)
            )
        
        return actual_output
    
    def compress_bytes(
        self,
        image_data: bytes,
        output_path: Path
    ) -> Path:
        """
        Compress image from bytes data.
        
        Args:
            image_data: Raw image bytes
            output_path: Destination path
        
        Returns:
            Path where compressed image was written
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with Image.open(io.BytesIO(image_data)) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            img = self._ensure_srgb(img)
            img = self._resize_to_max_edge(img)
            
            img.save(
                output_path,
                format="JPEG",
                quality=self.jpeg_quality,
                optimize=True,
                exif=b"",
                icc_profile=None
            )
        
        return output_path
    
    def compress_to_bytes(self, image_data: bytes) -> bytes:
        """
        Compress image and return as bytes.
        Useful for in-memory processing.
        
        Args:
            image_data: Raw image bytes
        
        Returns:
            Compressed JPEG bytes
        """
        output_buffer = io.BytesIO()
        
        with Image.open(io.BytesIO(image_data)) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            img = self._ensure_srgb(img)
            img = self._resize_to_max_edge(img)
            
            img.save(
                output_buffer,
                format="JPEG",
                quality=self.jpeg_quality,
                optimize=True,
                exif=b"",
                icc_profile=None
            )
        
        return output_buffer.getvalue()
    
    def _ensure_srgb(self, img: Image.Image) -> Image.Image:
        """
        Convert image to sRGB color space if it has an embedded profile.
        """
        try:
            # Check if image has an ICC profile
            if "icc_profile" in img.info and img.info["icc_profile"]:
                # Convert from embedded profile to sRGB
                input_profile = ImageCms.ImageCmsProfile(
                    io.BytesIO(img.info["icc_profile"])
                )
                output_profile = _get_srgb_profile()
                
                img = ImageCms.profileToProfile(
                    img,
                    input_profile,
                    output_profile,
                    outputMode="RGB"
                )
        except Exception:
            # If color conversion fails, continue with original
            pass
        
        return img
    
    def _resize_to_max_edge(self, img: Image.Image) -> Image.Image:
        """
        Resize image so long edge is at most max_long_edge.
        Preserves aspect ratio.
        """
        width, height = img.size
        long_edge = max(width, height)
        
        if long_edge <= self.max_long_edge:
            # No resize needed
            return img
        
        # Calculate new dimensions
        scale = self.max_long_edge / long_edge
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Use high-quality resampling
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def get_output_size(self, input_path: Path) -> tuple[int, int]:
        """
        Calculate what the output dimensions would be.
        Useful for preview without actually compressing.
        """
        with Image.open(input_path) as img:
            width, height = img.size
            long_edge = max(width, height)
            
            if long_edge <= self.max_long_edge:
                return (width, height)
            
            scale = self.max_long_edge / long_edge
            return (int(width * scale), int(height * scale))


def compress_image(input_path: Path, output_path: Path) -> Path:
    """
    Convenience function to compress a single image.
    
    Args:
        input_path: Source image
        output_path: Destination path
    
    Returns:
        Path where compressed image was written
    """
    engine = CompressionEngine()
    return engine.compress(input_path, output_path)


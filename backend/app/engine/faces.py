"""
Face detection and embedding engine.
Uses InsightFace with ONNX Runtime (CPU) for offline face recognition.
"""
import io
import numpy as np
from pathlib import Path
from typing import Optional

from PIL import Image
import insightface
from insightface.app import FaceAnalysis

from ..config import settings


class FaceEngine:
    """
    Face detection and embedding extraction engine.
    
    Uses InsightFace buffalo_l model for:
    - Face detection
    - Face alignment
    - Face embedding (512-dim ArcFace)
    
    All operations are CPU-only.
    """
    
    _instance: Optional["FaceEngine"] = None
    _initialized: bool = False
    
    def __new__(cls):
        """Singleton pattern for heavy model loading."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the face analysis model."""
        if FaceEngine._initialized:
            return
        
        # Ensure models directory exists
        settings.ensure_directories()
        
        # Initialize InsightFace with buffalo_l model
        # This downloads models on first run (~300MB)
        self.app = FaceAnalysis(
            name="buffalo_l",
            root=str(settings.models_dir),
            providers=["CPUExecutionProvider"]
        )
        
        # Prepare model with detection size
        # Using 640 for good balance of speed and accuracy
        self.app.prepare(ctx_id=-1, det_size=(640, 640))
        
        FaceEngine._initialized = True
        print("Face engine initialized (CPU mode)")
    
    def detect_and_embed(
        self,
        image_data: bytes | np.ndarray | Path,
        max_faces: int = 100
    ) -> list[dict]:
        """
        Detect faces and compute embeddings from an image.
        
        Args:
            image_data: Image as bytes, numpy array (BGR), or file path
            max_faces: Maximum number of faces to detect
        
        Returns:
            List of face dictionaries with keys:
            - embedding: numpy array (512-dim)
            - bbox: [x1, y1, x2, y2]
            - det_score: detection confidence
            - landmark: facial landmarks
        """
        # Load image as numpy array (BGR format for InsightFace)
        img = self._load_image(image_data)
        
        # Detect faces
        faces = self.app.get(img, max_num=max_faces)
        
        results = []
        for face in faces:
            results.append({
                "embedding": face.embedding,  # 512-dim float32
                "bbox": face.bbox.tolist(),
                "det_score": float(face.det_score),
                "landmark": face.landmark.tolist() if face.landmark is not None else None
            })
        
        return results
    
    def detect_and_embed_from_path(self, image_path: Path) -> list[dict]:
        """
        Detect faces from an image file path.
        Convenience method that handles file reading.
        """
        return self.detect_and_embed(image_path)
    
    def _load_image(self, image_data: bytes | np.ndarray | Path) -> np.ndarray:
        """
        Load image data into BGR numpy array format.
        
        InsightFace expects BGR format (OpenCV convention).
        """
        if isinstance(image_data, np.ndarray):
            # Assume already in BGR format
            return image_data
        
        if isinstance(image_data, Path):
            # Load from file path
            image_data = image_data.read_bytes()
        
        # Load from bytes using PIL
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB numpy array
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        rgb_array = np.array(image)
        
        # Convert RGB to BGR for InsightFace
        bgr_array = rgb_array[:, :, ::-1]
        
        return bgr_array
    
    def compute_distance(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute Euclidean distance between two embeddings.
        
        Lower distance = more similar.
        Typical thresholds:
        - < 0.50: Same person (high confidence)
        - < 0.60: Same person (lower confidence)
        - >= 0.60: Different persons
        """
        return float(np.linalg.norm(embedding1 - embedding2))
    
    def compute_distance_to_centroid(
        self,
        embedding: np.ndarray,
        centroid: np.ndarray
    ) -> float:
        """
        Compute distance from embedding to a centroid.
        Same as compute_distance but semantically clearer.
        """
        return self.compute_distance(embedding, centroid)
    
    def normalize_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """
        Normalize embedding to unit length.
        Some distance metrics work better with normalized embeddings.
        """
        norm = np.linalg.norm(embedding)
        if norm > 0:
            return embedding / norm
        return embedding


def get_face_engine() -> FaceEngine:
    """Get the singleton face engine instance."""
    return FaceEngine()


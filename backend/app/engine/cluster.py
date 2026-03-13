"""
Auto-Discovery Engine.
Uses DBSCAN to cluster face embeddings from a sampled subset of images.
"""
import asyncio
import io
import random
from pathlib import Path
from typing import Optional, Any
from PIL import Image

import numpy as np
from sklearn.cluster import DBSCAN

from .faces import get_face_engine
from ..config import settings
from ..db.jobs import get_job_config

# Global state for the discovery job since it runs in the background
# Only one discovery job can run at a time
discovery_state = {
    "status": "idle",  # idle, running, completed, failed
    "progress": 0.0,
    "message": "Ready",
    "results": [],
    "total_images": 0,
    "processed_images": 0,
    "faces_found": 0
}


def get_discovery_state() -> dict:
    return discovery_state


def _get_thumbnails_dir() -> Path:
    thumbnails_dir = settings.hot_storage_root / "thumbnails" / "discovery"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    return thumbnails_dir


def _save_crop(image_path: Path, bbox: list, cluster_id: int, face_idx: int) -> str:
    """Save a face crop for the UI to display and return its filename/path."""
    try:
        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        x1, y1, x2, y2 = [int(coord) for coord in bbox]
        
        # Add 20% padding
        width = x2 - x1
        height = y2 - y1
        padding = int(max(width, height) * 0.2)
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(img.width, x2 + padding)
        y2 = min(img.height, y2 + padding)
        
        face_crop = img.crop((x1, y1, x2, y2))
        face_crop.thumbnail((128, 128), Image.Resampling.LANCZOS)
        
        # Save thumbnail
        filename = f"c{cluster_id}_f{face_idx}.jpg"
        thumbnail_path = _get_thumbnails_dir() / filename
        face_crop.save(thumbnail_path, "JPEG", quality=85)
        
        return filename
    except Exception as e:
        print(f"Failed to save crop for {image_path}: {e}")
        return ""

        
def _scan_images(source_root: Path, extensions: set) -> list[Path]:
    """Recursively scan for images in the source root."""
    images = []
    for ext in extensions:
        images.extend(source_root.rglob(f"*{ext}"))
        images.extend(source_root.rglob(f"*{ext.upper()}"))
    # Deduplicate and sort (to be safe)
    return list(set(images))


async def run_discovery_task(sample_size: int):
    """Background task to run the clustering."""
    global discovery_state
    
    try:
        discovery_state["status"] = "running"
        discovery_state["progress"] = 0.0
        discovery_state["message"] = "Initializing..."
        discovery_state["results"] = []
        discovery_state["processed_images"] = 0
        discovery_state["faces_found"] = 0
        
        # 1. Get job config to find source root
        config = await get_job_config()
        source_root_str = config.get("source_root")
        
        if not source_root_str:
            raise ValueError("Source directory not configured. Save Job Configuration first.")
            
        source_root = Path(source_root_str)
        if not source_root.exists() or not source_root.is_dir():
             raise ValueError(f"Source directory not found: {source_root}")
             
        # 2. Scan images
        discovery_state["message"] = "Scanning source folder for images..."
        # Yield control briefly
        await asyncio.sleep(0.1)
        
        exts = {e.lower() for e in settings.supported_extensions}
        all_images = _scan_images(source_root, exts)
        
        if not all_images:
            raise ValueError("No images found in the configured source directory.")
            
        # 3. Sample images
        total_found = len(all_images)
        actual_sample_size = min(sample_size, total_found)
        discovery_state["total_images"] = actual_sample_size
        
        sampled_images = random.sample(all_images, actual_sample_size)
        discovery_state["message"] = f"Extracting embeddings from {actual_sample_size} images..."
        
        # 4. Extract embeddings
        face_engine = get_face_engine()
        
        all_faces = []
        
        for i, img_path in enumerate(sampled_images):
            # Update progress
            discovery_state["processed_images"] = i + 1
            discovery_state["progress"] = (i / actual_sample_size) * 80.0  # 80% of task is extraction
            
            try:
                # Need to run in executor to not block event loop so API can serve status
                # but InsightFace uses ONNXRuntime which usually releases GIL.
                def _process():
                    return face_engine.detect_and_embed_from_path(img_path, max_faces=10)
                
                faces = await asyncio.to_thread(_process)
                
                for face in faces:
                    all_faces.append({
                        "image_path": img_path,
                        "bbox": face["bbox"],
                        "embedding": face["embedding"]
                    })
                    
                discovery_state["faces_found"] = len(all_faces)
            except Exception as e:
                print(f"Error processing {img_path}: {e}")
                
            # Yield control so status can be polled
            await asyncio.sleep(0.01)
            
        if not all_faces:
             raise ValueError("No faces detected in the sampled images.")
             
        # 5. Cluster embeddings
        discovery_state["message"] = "Clustering faces..."
        discovery_state["progress"] = 85.0
        await asyncio.sleep(0.1)
        
        # Extract the X matrix
        embeddings_matrix = np.array([f["embedding"] for f in all_faces])
        
        # Normalize embeddings for cosine separation in L2 space
        # distance between normalized queries is 2*(1 - cos_sim)
        norms = np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
        # Avoid divide by zero
        norms[norms == 0] = 1 
        normalized_embeddings = embeddings_matrix / norms
        
        # Run DBSCAN
        # eps 0.40 in euclidean of normalized embeddings corresponds to high similarity
        # min_samples requires at least X faces to form a cluster representing a person
        min_cluster_size = max(2, int(actual_sample_size * 0.01)) # e.g. 500 images -> min 5 faces
        min_cluster_size = min(min_cluster_size, 10) # cap
        
        # We need to run it in a thread
        def _cluster():
            dbscan = DBSCAN(eps=settings.threshold_strict, min_samples=min_cluster_size, metric="euclidean")
            return dbscan.fit_predict(normalized_embeddings)
            
        labels = await asyncio.to_thread(_cluster)
        
        # 6. Group results by cluster
        discovery_state["progress"] = 90.0
        discovery_state["message"] = "Generating thumbnails..."
        await asyncio.sleep(0.1)
        
        clusters = {}
        for i, label in enumerate(labels):
            if label == -1: # Noise
                continue
                
            if label not in clusters:
                clusters[label] = {
                    "cluster_id": int(label),
                    "faces": [],
                    "embeddings": []
                }
            clusters[label]["faces"].append(all_faces[i])
            clusters[label]["embeddings"].append(all_faces[i]["embedding"])
            
        # 7. Format and save thumbnails
        # Sort clusters by size (most frequent first)
        sorted_clusters = sorted(clusters.values(), key=lambda c: len(c["faces"]), reverse=True)
        
        results = []
        for c in sorted_clusters[:20]: # Keep top 20
            # Clean up out dir first? We might just overwrite.
            # Pick a max of 5 thumbnails to show
            sample_faces = random.sample(c["faces"], min(5, len(c["faces"])))
            thumbnail_files = []
            
            for idx, f in enumerate(sample_faces):
                fname = await asyncio.to_thread(_save_crop, f["image_path"], f["bbox"], c["cluster_id"], idx)
                if fname:
                    thumbnail_files.append(fname)
                    
            if thumbnail_files:
                results.append({
                    "cluster_id": c["cluster_id"],
                    "face_count": len(c["faces"]),
                    "thumbnails": thumbnail_files,
                    "avg_embedding": np.mean(c["embeddings"], axis=0).tolist(), # Store to use in registration
                })
                
        discovery_state["results"] = results
        discovery_state["status"] = "completed"
        discovery_state["progress"] = 100.0
        discovery_state["message"] = f"Finished. Found {len(results)} valid persons."
        
    except Exception as e:
        import traceback
        discovery_state["status"] = "failed"
        discovery_state["message"] = f"Error: {str(e)}"
        print(f"Discovery Error: {e}")
        traceback.print_exc()


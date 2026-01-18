"""
Face matching algorithm - deterministic identity resolution.

Matching policy:
- Euclidean distance metric on NORMALIZED embeddings
- For normalized 512-dim embeddings, distance range is 0-2:
  - 0 = identical
  - ~1.0 = typical same-person threshold
  - 2 = completely opposite
- STRICT threshold (0.80): auto-match + learn new embedding  
- LOOSE threshold (1.00): match only (no learning)
- Above 1.00: unknown (no match)

Note: Thresholds updated for normalized embeddings (was 0.5/0.6 which
is too strict for Euclidean distance on unit vectors).
"""
import numpy as np
from typing import Optional

from ..config import settings
from ..db.registry import (
    get_all_centroids,
    add_person_embedding,
    get_person_embeddings,
    normalize_embedding,
)


class MatchResult:
    """Result of matching a face embedding against the registry."""
    
    def __init__(
        self,
        person_id: Optional[int],
        name: Optional[str],
        output_folder_rel: Optional[str],
        distance: float,
        match_type: str  # "strict", "loose", or "unknown"
    ):
        self.person_id = person_id
        self.name = name
        self.output_folder_rel = output_folder_rel
        self.distance = distance
        self.match_type = match_type
    
    @property
    def is_matched(self) -> bool:
        """Whether this is a valid match (not unknown)."""
        return self.match_type in ("strict", "loose")
    
    def to_dict(self) -> dict:
        return {
            "person_id": self.person_id,
            "name": self.name,
            "output_folder_rel": self.output_folder_rel,
            "distance": self.distance,
            "match_type": self.match_type,
            "is_matched": self.is_matched
        }


class FaceMatcher:
    """
    Deterministic face matching against the person registry.
    
    Algorithm:
    1. Load all person centroids (pre-normalized)
    2. Normalize input embedding
    3. Compute Euclidean distance to each centroid
    4. Find minimum distance
    5. Apply thresholds:
       - STRICT (≤0.80): Match + eligible for learning
       - LOOSE (≤1.00): Match only
       - Above 1.00: Unknown
    
    For normalized 512-dim embeddings:
    - Distance range: 0 to 2
    - Same person: typically < 1.0
    - Different person: typically > 1.0
    """
    
    def __init__(self, selected_person_ids: Optional[list[int]] = None):
        """
        Initialize matcher.
        
        Args:
            selected_person_ids: If provided, only match against these persons.
                                 If None or empty, match against all persons.
        """
        # Override config thresholds with correct values for normalized embeddings
        # The config values (0.5, 0.6) were for non-normalized embeddings
        self.threshold_strict = 0.80  # High confidence match
        self.threshold_loose = 1.00   # Lower confidence match
        self._centroids_cache: Optional[list[dict]] = None
        self._selected_person_ids: Optional[set[int]] = (
            set(selected_person_ids) if selected_person_ids else None
        )
    
    async def refresh_centroids(self) -> None:
        """Refresh the centroids cache from database, filtering by selected persons."""
        all_centroids = await get_all_centroids()
        
        # Filter by selected persons if specified
        if self._selected_person_ids:
            self._centroids_cache = [
                c for c in all_centroids 
                if c["person_id"] in self._selected_person_ids
            ]
            print(f"  Matching against {len(self._centroids_cache)} selected person(s)")
        else:
            self._centroids_cache = all_centroids
            print(f"  Matching against all {len(self._centroids_cache)} person(s)")
    
    async def match(
        self,
        embedding: np.ndarray,
        learn_on_strict: bool = True
    ) -> MatchResult:
        """
        Match a face embedding against the registry.
        
        Args:
            embedding: 512-dim face embedding
            learn_on_strict: If True and match is STRICT, add embedding to person
        
        Returns:
            MatchResult with match details
        """
        # Ensure centroids are loaded
        if self._centroids_cache is None:
            await self.refresh_centroids()
        
        # No persons registered
        if not self._centroids_cache:
            return MatchResult(
                person_id=None,
                name=None,
                output_folder_rel=None,
                distance=float("inf"),
                match_type="unknown"
            )
        
        # IMPORTANT: Normalize the input embedding before comparison
        # Centroids are already normalized when stored
        embedding_normalized = normalize_embedding(embedding)
        
        # Compute distances to all centroids
        distances = []
        for person in self._centroids_cache:
            dist = float(np.linalg.norm(embedding_normalized - person["centroid"]))
            distances.append((dist, person))
        
        # Find minimum distance
        distances.sort(key=lambda x: x[0])
        min_dist, best_match = distances[0]
        
        # DEBUG: Log match distances (for normalized embeddings, range 0-2)
        print(f"  [MATCH] {best_match['name']}: dist={min_dist:.3f} (strict<{self.threshold_strict}, loose<{self.threshold_loose})", end="")
        if min_dist > self.threshold_loose:
            print(f" → NO MATCH")
        elif min_dist > self.threshold_strict:
            print(f" → LOOSE MATCH ✓")
        else:
            print(f" → STRICT MATCH ✓✓")
        
        # Apply thresholds
        if min_dist <= self.threshold_strict:
            match_type = "strict"
            
            # Learn this embedding (adds to person's collection)
            if learn_on_strict:
                await add_person_embedding(
                    best_match["person_id"],
                    embedding,
                    source_type="learned"
                )
                # Refresh centroids since we added an embedding
                await self.refresh_centroids()
            
        elif min_dist <= self.threshold_loose:
            match_type = "loose"
        else:
            # Unknown - no match
            return MatchResult(
                person_id=None,
                name=None,
                output_folder_rel=None,
                distance=min_dist,
                match_type="unknown"
            )
        
        return MatchResult(
            person_id=best_match["person_id"],
            name=best_match["name"],
            output_folder_rel=best_match["output_folder_rel"],
            distance=min_dist,
            match_type=match_type
        )
    
    async def match_many(
        self,
        embeddings: list[np.ndarray],
        learn_on_strict: bool = True
    ) -> list[MatchResult]:
        """
        Match multiple embeddings against the registry.
        
        Args:
            embeddings: List of face embeddings
            learn_on_strict: If True, learn from strict matches
        
        Returns:
            List of MatchResults in same order as input
        """
        results = []
        for embedding in embeddings:
            result = await self.match(embedding, learn_on_strict)
            results.append(result)
        return results
    
    async def match_no_learn(self, embedding: np.ndarray) -> MatchResult:
        """Match without learning (read-only operation)."""
        return await self.match(embedding, learn_on_strict=False)


async def match_faces_for_image(
    face_embeddings: list[np.ndarray],
    matcher: Optional[FaceMatcher] = None
) -> tuple[list[int], int]:
    """
    Match all faces in an image against the registry.
    
    Args:
        face_embeddings: List of face embeddings from the image
        matcher: Optional matcher instance (creates new if None)
    
    Returns:
        Tuple of (matched_person_ids, unknown_count)
        - matched_person_ids: Deduplicated list of matched person IDs
        - unknown_count: Number of faces that didn't match
    """
    if matcher is None:
        matcher = FaceMatcher()
    
    matched_ids = set()
    unknown_count = 0
    
    for embedding in face_embeddings:
        result = await matcher.match(embedding, learn_on_strict=True)
        
        if result.is_matched:
            matched_ids.add(result.person_id)
        else:
            unknown_count += 1
    
    return list(matched_ids), unknown_count


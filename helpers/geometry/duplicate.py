# -*- coding: utf-8 -*-
"""
Duplicate Geometry Check (CHK_DUPLICATE).
Detects 100% coincident polygons and distinguishes them from regular overlaps.
"""

from typing import List, Tuple, Any, Dict, Set
from ..models.qc_issue import QCIssue, Severity, CheckID
from .spatial_index import SpatialGridIndex


def check_duplicate_geometry(
    features: Dict[Any, Any],  # fid -> shape
    layer_name: str,
    source: str = "INPUT",
    coincidence_threshold: float = 0.999,  # >= 99.9% overlap ratio of area
    issue_id_start: int = 1,
    spatial_index: SpatialGridIndex = None,
) -> Tuple[List[QCIssue], Set[Tuple[Any, Any]]]:
    """
    Finds 100% duplicate / coincident geometries.
    Returns detected duplicate issues and a set of (fid1, fid2) pairs to exclude from overlap checks.
    """
    issues: List[QCIssue] = []
    duplicate_pairs: Set[Tuple[Any, Any]] = set()
    current_id = issue_id_start

    if not features:
        return issues, duplicate_pairs

    if spatial_index is None:
        spatial_index = SpatialGridIndex(cell_size=100.0)
        for fid, shape in features.items():
            if shape and hasattr(shape, "extent"):
                spatial_index.insert(fid, shape.extent)

    candidate_pairs = spatial_index.get_candidate_pairs()

    for f1, f2 in candidate_pairs:
        s1 = features.get(f1)
        s2 = features.get(f2)
        if not s1 or not s2:
            continue

        # Area check
        a1 = getattr(s1, "area", 0.0)
        a2 = getattr(s2, "area", 0.0)
        if a1 <= 0.0 or a2 <= 0.0:
            continue

        # If areas are very close, test intersection
        ratio_area = min(a1, a2) / max(a1, a2)
        if ratio_area >= coincidence_threshold:
            try:
                # ArcPy intersect
                intersect_geom = s1.intersect(s2, 4)  # 4 = polygon dimension
                if intersect_geom and hasattr(intersect_geom, "area"):
                    int_area = intersect_geom.area
                    if int_area / min(a1, a2) >= coincidence_threshold:
                        pair = (f1, f2) if f1 < f2 else (f2, f1)
                        duplicate_pairs.add(pair)

                        loc = None
                        if hasattr(intersect_geom, "trueCentroid"):
                            loc = (intersect_geom.trueCentroid.X, intersect_geom.trueCentroid.Y)

                        issues.append(
                            QCIssue(
                                issue_id=current_id,
                                check_id=CheckID.CHK_DUPLICATE,
                                issue_type="DUPLICATE_GEOMETRY",
                                severity=Severity.ERROR,
                                layer_name=layer_name,
                                source=source,
                                object_id=f1,
                                related_object_id=f2,
                                measurement=round(int_area, 6),
                                unit="m²",
                                geometry=intersect_geom,
                                location=loc,
                                details=f"100% coincident polygon geometry between OID {f1} and OID {f2} (Coincident Area: {int_area:.4f} m²).",
                            )
                        )
                        current_id += 1
            except Exception:
                pass

    return issues, duplicate_pairs

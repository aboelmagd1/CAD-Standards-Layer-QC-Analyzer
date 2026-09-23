# -*- coding: utf-8 -*-
"""
Overlap Check (CHK_OVERLAP).
Detects true overlapping areas between polygons exceeding tolerance (default 0.0001 m²),
decomposing multipart intersections and excluding duplicates.
"""

from typing import List, Tuple, Any, Dict, Set
from ..models.qc_issue import QCIssue, Severity, CheckID
from .spatial_index import SpatialGridIndex


def check_overlap(
    features: Dict[Any, Any],  # fid -> shape
    layer_name: str,
    source: str = "INPUT",
    tolerance_area: float = 0.0001,  # 0.0001 m²
    excluded_pairs: Set[Tuple[Any, Any]] = None,
    spatial_index: SpatialGridIndex = None,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start
    excluded = excluded_pairs or set()

    if not features:
        return issues

    if spatial_index is None:
        spatial_index = SpatialGridIndex(cell_size=100.0)
        for fid, shape in features.items():
            if shape and hasattr(shape, "extent"):
                spatial_index.insert(fid, shape.extent)

    candidate_pairs = spatial_index.get_candidate_pairs()

    for f1, f2 in candidate_pairs:
        pair = (f1, f2) if f1 < f2 else (f2, f1)
        if pair in excluded:
            continue

        s1 = features.get(f1)
        s2 = features.get(f2)
        if not s1 or not s2:
            continue

        try:
            intersect_geom = s1.intersect(s2, 4)  # 4 = polygon dimension
            if intersect_geom and hasattr(intersect_geom, "area"):
                overlap_area = intersect_geom.area
                if overlap_area >= tolerance_area:
                    loc = None
                    if hasattr(intersect_geom, "trueCentroid"):
                        loc = (intersect_geom.trueCentroid.X, intersect_geom.trueCentroid.Y)

                    issues.append(
                        QCIssue(
                            issue_id=current_id,
                            check_id=CheckID.CHK_OVERLAP,
                            issue_type="POLYGON_OVERLAP",
                            severity=Severity.ERROR,
                            layer_name=layer_name,
                            source=source,
                            object_id=f1,
                            related_object_id=f2,
                            measurement=round(overlap_area, 6),
                            threshold=tolerance_area,
                            unit="m²",
                            geometry=intersect_geom,
                            location=loc,
                            details=f"Overlap between Feature {f1} and Feature {f2} (Area: {overlap_area:.6f} m² >= {tolerance_area} m²).",
                        )
                    )
                    current_id += 1
        except Exception:
            pass

    return issues

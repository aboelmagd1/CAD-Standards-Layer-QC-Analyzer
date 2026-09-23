# -*- coding: utf-8 -*-
"""
Snap Issue Check (CHK_SNAP).
Detects near-coincident vertices between features (or parts) within snap tolerance (default 1.0 cm),
strictly excluding identical/zero-distance vertices.
"""

from typing import List, Tuple, Any, Dict, Set
from ..models.qc_issue import QCIssue, Severity, CheckID
from .vertex_index import VertexGridIndex


def check_snap_issues(
    features: Dict[Any, Any],  # fid -> shape
    layer_name: str,
    source: str = "INPUT",
    tolerance_meters: float = 0.01,  # 1 cm
    min_dist_meters: float = 1e-5,  # Exclude identical vertices (< 0.01 mm)
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    if not features:
        return issues

    # Populate vertex grid index
    vindex = VertexGridIndex(tolerance=tolerance_meters)
    for fid, shape in features.items():
        if not shape or not hasattr(shape, "partCount"):
            continue
        for part_idx in range(shape.partCount):
            part = shape.getPart(part_idx)
            if not part:
                continue
            for v_idx, pt in enumerate(part):
                if pt is not None:
                    vindex.insert(pt.X, pt.Y, fid, part_idx, v_idx)

    checked_pairs: Set[Tuple[int, int]] = set()

    for idx, v_rec in enumerate(vindex.records):
        nearby = vindex.query_radius(v_rec.x, v_rec.y, tolerance_meters)
        for other_rec, dist in nearby:
            # Avoid self-comparison
            if v_rec.feature_id == other_rec.feature_id and v_rec.vertex_idx == other_rec.vertex_idx:
                continue

            # Only check between different features or non-adjacent vertices
            if v_rec.feature_id == other_rec.feature_id:
                if abs(v_rec.vertex_idx - other_rec.vertex_idx) <= 1:
                    continue

            # Exclude truly identical coordinates
            if dist < min_dist_meters:
                continue

            # Avoid reporting the same pair twice
            f1, f2 = v_rec.feature_id, other_rec.feature_id
            p_key = (min(id(v_rec), id(other_rec)), max(id(v_rec), id(other_rec)))
            if p_key in checked_pairs:
                continue
            checked_pairs.add(p_key)

            # High precision display
            if dist < 0.01:
                disp_str = f"{dist * 1000.0:.2f} mm"
            else:
                disp_str = f"{dist * 100.0:.2f} cm"

            issues.append(
                QCIssue(
                    issue_id=current_id,
                    check_id=CheckID.CHK_SNAP,
                    issue_type="SNAP_ISSUE",
                    severity=Severity.ERROR,
                    layer_name=layer_name,
                    source=source,
                    object_id=v_rec.feature_id,
                    related_object_id=other_rec.feature_id,
                    measurement=round(dist, 6),
                    threshold=tolerance_meters,
                    unit="m",
                    location=(v_rec.x, v_rec.y),
                    details=(
                        f"Snap issue between Feature {v_rec.feature_id} (Vertex {v_rec.vertex_idx}) "
                        f"and Feature {other_rec.feature_id} (Vertex {other_rec.vertex_idx}): "
                        f"Distance = {disp_str} <= {tolerance_meters * 100:.1f} cm."
                    ),
                )
            )
            current_id += 1

    return issues

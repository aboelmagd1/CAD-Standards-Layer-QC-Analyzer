# -*- coding: utf-8 -*-
"""
Missing Junction Check (CHK_JUNCTION).
Detects T-junction conditions where a vertex of Polygon A touches or lies on an edge
of Polygon B within tolerance (default 1.0 cm) without Polygon B having a matching snapped node.
"""

import math
from typing import List, Tuple, Any, Dict, Set
from ..models.qc_issue import QCIssue, Severity, CheckID
from .spatial_index import SpatialGridIndex


def point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> Tuple[float, float, float, float]:
    """
    Calculates euclidean distance from point P to line segment AB.
    Returns (distance, t, nearest_x, nearest_y).
    """
    abx = bx - ax
    aby = by - ay
    ab2 = abx * abx + aby * aby

    if ab2 < 1e-12:
        d = math.hypot(px - ax, py - ay)
        return d, 0.0, ax, ay

    t = ((px - ax) * abx + (py - ay) * aby) / ab2
    t_clamped = max(0.0, min(1.0, t))

    nx = ax + t_clamped * abx
    ny = ay + t_clamped * aby
    dist = math.hypot(px - nx, py - ny)

    return dist, t, nx, ny


def check_missing_junctions(
    features: Dict[Any, Any],  # fid -> shape
    layer_name: str,
    source: str = "INPUT",
    tolerance_meters: float = 0.01,  # 1.0 cm
    issue_id_start: int = 1,
    spatial_index: SpatialGridIndex = None,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    if len(features) < 2:
        return issues

    if spatial_index is None:
        spatial_index = SpatialGridIndex(cell_size=100.0)
        for fid, shape in features.items():
            if shape and hasattr(shape, "extent"):
                spatial_index.insert(fid, shape.extent)

    # For each candidate pair of adjacent features
    candidate_pairs = spatial_index.get_candidate_pairs()
    tested_events: Set[Tuple[Any, Any, int]] = set()

    for f1, f2 in candidate_pairs:
        s1 = features.get(f1)
        s2 = features.get(f2)
        if not s1 or not s2 or not hasattr(s1, "partCount") or not hasattr(s2, "partCount"):
            continue

        # Extract segments from s2
        s2_segments = []
        for p2_idx in range(s2.partCount):
            part2 = s2.getPart(p2_idx)
            if not part2:
                continue
            for j in range(len(part2) - 1):
                p_a = part2[j]
                p_b = part2[j + 1]
                if p_a and p_b:
                    s2_segments.append((p_a.X, p_a.Y, p_b.X, p_b.Y, j))

        if not s2_segments:
            continue

        # Test each vertex of s1 against segments of s2
        for p1_idx in range(s1.partCount):
            part1 = s1.getPart(p1_idx)
            if not part1:
                continue

            for v_idx, pt in enumerate(part1):
                if not pt:
                    continue

                vx, vy = pt.X, pt.Y

                for ax, ay, bx, by, seg_idx in s2_segments:
                    # Quick bounding box pre-filter for segment
                    seg_min_x = min(ax, bx) - tolerance_meters
                    seg_max_x = max(ax, bx) + tolerance_meters
                    seg_min_y = min(ay, by) - tolerance_meters
                    seg_max_y = max(ay, by) + tolerance_meters

                    if vx < seg_min_x or vx > seg_max_x or vy < seg_min_y or vy > seg_max_y:
                        continue

                    dist, t, nx, ny = point_segment_distance(vx, vy, ax, ay, bx, by)

                    # Node must be strictly interior to segment (not at endpoints)
                    dist_to_a = math.hypot(vx - ax, vy - ay)
                    dist_to_b = math.hypot(vx - bx, vy - by)

                    if dist <= tolerance_meters and dist_to_a > tolerance_meters and dist_to_b > tolerance_meters:
                        ev_key = (f1, f2, v_idx)
                        if ev_key in tested_events:
                            continue
                        tested_events.add(ev_key)

                        if dist < 0.01:
                            disp_str = f"{dist * 1000.0:.2f} mm"
                        else:
                            disp_str = f"{dist * 100.0:.2f} cm"

                        issues.append(
                            QCIssue(
                                issue_id=current_id,
                                check_id=CheckID.CHK_JUNCTION,
                                issue_type="MISSING_JUNCTION",
                                severity=Severity.ERROR,
                                layer_name=layer_name,
                                source=source,
                                object_id=f1,
                                related_object_id=f2,
                                measurement=round(dist, 6),
                                threshold=tolerance_meters,
                                unit="m",
                                location=(vx, vy),
                                details=(
                                    f"Feature {f1} vertex {v_idx} touches Feature {f2} edge {seg_idx} "
                                    f"without matching node (Distance: {disp_str} <= {tolerance_meters * 100:.1f} cm)."
                                ),
                            )
                        )
                        current_id += 1

    return issues

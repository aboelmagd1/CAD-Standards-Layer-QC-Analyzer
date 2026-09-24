# -*- coding: utf-8 -*-
"""
Redundant Vertex Check (CHK_REDUNDANT).
Detects unnecessary collinear vertices (angle >= 179.9° default) that do not
meaningfully change the direction of an edge.
"""

import math
from typing import List, Any
from ..models.qc_issue import QCIssue, Severity, CheckID
from .angle import calculate_vertex_angle


def check_redundant_vertices(
    feature_id: Any,
    shape: Any,
    layer_name: str,
    source: str = "INPUT",
    collinear_threshold_deg: float = 179.9,  # 179.9°
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    if shape is None or not hasattr(shape, "partCount"):
        return issues

    for part_idx in range(shape.partCount):
        part = shape.getPart(part_idx)
        if not part:
            continue

        n_pts = len(part)
        if n_pts < 3:
            continue

        is_ring = (part[0].X == part[-1].X) and (part[0].Y == part[-1].Y)

        indices = [(i - 1, i, i + 1) for i in range(1, n_pts - 1)]
        if is_ring and n_pts >= 4:
            indices.append((n_pts - 2, 0, 1))

        for idx_prev, idx_curr, idx_next in indices:
            p_prev = part[idx_prev]
            p_curr = part[idx_curr]
            p_next = part[idx_next]

            if p_prev is None or p_curr is None or p_next is None:
                continue

            angle_deg = calculate_vertex_angle(p_prev, p_curr, p_next)

            # Check if nearly straight collinear line (angle near 180°)
            if angle_deg >= collinear_threshold_deg:
                len1 = math.hypot(p_curr.X - p_prev.X, p_curr.Y - p_prev.Y)
                len2 = math.hypot(p_next.X - p_curr.X, p_next.Y - p_curr.Y)

                issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_REDUNDANT,
                        issue_type="REDUNDANT_VERTEX",
                        severity=Severity.WARNING,
                        layer_name=layer_name,
                        source=source,
                        object_id=feature_id,
                        measurement=round(angle_deg, 2),
                        threshold=collinear_threshold_deg,
                        unit="degrees",
                        location=(p_curr.X, p_curr.Y),
                        details=(
                            f"Redundant collinear vertex at index {idx_curr} "
                            f"(Angle: {angle_deg:.2f}° >= {collinear_threshold_deg:.1f}°, "
                            f"Adjacent segment lengths: {len1:.3f} m, {len2:.3f} m)."
                        ),
                    )
                )
                current_id += 1

    return issues

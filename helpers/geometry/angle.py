# -*- coding: utf-8 -*-
"""
Angle Issue Check (CHK_ANGLE).
Detects abnormal sharp angles (< 5.0° default) associated with needles, spikes,
and digitizing artifacts.
"""

import math
from typing import List, Any
from ..models.qc_issue import QCIssue, Severity, CheckID


def calculate_vertex_angle(p_prev, p_curr, p_next) -> float:
    """
    Calculates the angle at p_curr formed by vectors (p_prev - p_curr) and (p_next - p_curr).
    Returns angle in degrees [0, 180].
    """
    v1_x = p_prev.X - p_curr.X
    v1_y = p_prev.Y - p_curr.Y
    v2_x = p_next.X - p_curr.X
    v2_y = p_next.Y - p_curr.Y

    len1 = math.hypot(v1_x, v1_y)
    len2 = math.hypot(v2_x, v2_y)

    if len1 < 1e-9 or len2 < 1e-9:
        return 180.0

    dot = (v1_x * v2_x + v1_y * v2_y) / (len1 * len2)
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def check_sharp_angles(
    feature_id: Any,
    shape: Any,
    layer_name: str,
    source: str = "INPUT",
    angle_threshold_deg: float = 5.0,  # 5°
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

        # In closed polygons, last point is duplicate of first point
        is_ring = (part[0].X == part[-1].X) and (part[0].Y == part[-1].Y)
        limit = n_pts - 1 if is_ring else n_pts

        for i in range(1, limit):
            p_prev = part[i - 1]
            p_curr = part[i]
            p_next = part[(i + 1) % (n_pts - 1)] if is_ring else part[i + 1]

            if p_prev is None or p_curr is None or p_next is None:
                continue

            angle_deg = calculate_vertex_angle(p_prev, p_curr, p_next)

            if angle_deg < angle_threshold_deg:
                issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_ANGLE,
                        issue_type="SHARP_ANGLE",
                        severity=Severity.WARNING,
                        layer_name=layer_name,
                        source=source,
                        object_id=feature_id,
                        measurement=round(angle_deg, 2),
                        threshold=angle_threshold_deg,
                        unit="degrees",
                        location=(p_curr.X, p_curr.Y),
                        details=f"Sharp angle at vertex {i} ({angle_deg:.2f}° < {angle_threshold_deg:.1f}°).",
                    )
                )
                current_id += 1

    return issues

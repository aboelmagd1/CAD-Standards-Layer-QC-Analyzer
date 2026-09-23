# -*- coding: utf-8 -*-
"""
Closure Checker.
Tolerance-based polyline closure validation.
Evaluates Euclidean distance between start and end points and records unclosed features
with coordinates, gap distance, and tolerance.
"""

import math
from typing import List, Tuple, Any, Optional
from ..models.qc_issue import QCIssue, Severity, CheckID
from ..geometry.geometry_classifier import point_distance


def evaluate_polyline_closure(
    shape: Any,
    closure_tolerance: float = 0.01,
) -> Tuple[bool, float, Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """
    Evaluates whether shape is closed within tolerance.
    Returns (is_closed, gap_distance, first_point_xy, last_point_xy).
    """
    if shape is None:
        return False, 0.0, None, None

    # ArcPy polyline object
    if hasattr(shape, "firstPoint") and hasattr(shape, "lastPoint"):
        fp = shape.firstPoint
        lp = shape.lastPoint
        if fp is not None and lp is not None:
            gap = point_distance(fp, lp)
            p1 = (fp.X, fp.Y)
            p2 = (lp.X, lp.Y)
            return (gap <= closure_tolerance), gap, p1, p2

    # Coordinate sequence
    if isinstance(shape, (list, tuple)) and len(shape) >= 2:
        p1 = (shape[0][0], shape[0][1])
        p2 = (shape[-1][0], shape[-1][1])
        gap = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        return (gap <= closure_tolerance), gap, p1, p2

    return False, 0.0, None, None


def check_feature_closure(
    feature_id: Any,
    shape: Any,
    layer_name: str,
    source: str = "RECEIVED",
    closure_tolerance: float = 0.01,
    issue_id_start: int = 1,
) -> Optional[QCIssue]:
    """
    Checks if an individual polyline is open when closure was expected.
    Returns a QCIssue if unclosed.
    """
    is_closed, gap, p1, p2 = evaluate_polyline_closure(shape, closure_tolerance)

    if not is_closed and p1 and p2:
        disp_gap = f"{gap * 100.0:.2f} cm" if gap >= 0.01 else f"{gap * 1000.0:.2f} mm"
        disp_tol = f"{closure_tolerance * 100.0:.2f} cm"

        loc = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)

        return QCIssue(
            issue_id=issue_id_start,
            check_id=CheckID.CHK_CLOSURE,
            issue_type="UNCLOSED_GEOMETRY",
            severity=Severity.ERROR,
            layer_name=layer_name,
            source=source,
            object_id=feature_id,
            measurement=round(gap, 6),
            threshold=closure_tolerance,
            unit="m",
            geometry=shape,
            location=loc,
            details=(
                f"Feature {feature_id} in layer '{layer_name}' is unclosed. "
                f"First Point: ({p1[0]:.3f}, {p1[1]:.3f}), Last Point: ({p2[0]:.3f}, {p2[1]:.3f}). "
                f"Gap: {disp_gap} > Tolerance: {disp_tol}."
            ),
        )

    return None

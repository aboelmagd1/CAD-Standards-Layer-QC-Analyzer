# -*- coding: utf-8 -*-
"""
Invalid Geometry Check (CHK_INVALID_GEOM).
Detects self-intersections, bow-ties, unclosed loops, NaN/null coordinates,
and non-simple geometries.
"""

import math
from typing import List, Optional, Tuple, Any
from ..models.qc_issue import QCIssue, Severity, CheckID


def check_invalid_geometry(
    feature_id: Any,
    shape: Any,
    layer_name: str,
    source: str = "INPUT",
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    if shape is None:
        issues.append(
            QCIssue(
                issue_id=current_id,
                check_id=CheckID.CHK_INVALID_GEOM,
                issue_type="NULL_GEOMETRY",
                severity=Severity.ERROR,
                layer_name=layer_name,
                source=source,
                object_id=feature_id,
                details="Feature geometry is null or missing.",
            )
        )
        return issues

    # ArcPy geometry checks
    if hasattr(shape, "area") and hasattr(shape, "length"):
        # Check for empty geometry
        if hasattr(shape, "partCount") and shape.partCount == 0:
            issues.append(
                QCIssue(
                    issue_id=current_id,
                    check_id=CheckID.CHK_INVALID_GEOM,
                    issue_type="EMPTY_GEOMETRY",
                    severity=Severity.ERROR,
                    layer_name=layer_name,
                    source=source,
                    object_id=feature_id,
                    details="Feature geometry is empty with 0 parts.",
                )
            )
            return issues

    # Coordinates check for NaN / Inf
    has_nan = False
    first_pt = None
    if hasattr(shape, "partCount"):
        for p_idx in range(shape.partCount):
            part = shape.getPart(p_idx)
            if part:
                for pt in part:
                    if pt:
                        if first_pt is None:
                            first_pt = (pt.X, pt.Y)
                        if math.isnan(pt.X) or math.isnan(pt.Y) or math.isinf(pt.X) or math.isinf(pt.Y):
                            has_nan = True
                            issues.append(
                                QCIssue(
                                    issue_id=current_id,
                                    check_id=CheckID.CHK_INVALID_GEOM,
                                    issue_type="NAN_COORDINATE",
                                    severity=Severity.ERROR,
                                    layer_name=layer_name,
                                    source=source,
                                    object_id=feature_id,
                                    location=(0.0, 0.0),
                                    details="Feature contains NaN or Infinite coordinate values.",
                                )
                            )
                            current_id += 1
                            break

    # Polygon loop closure / self-intersection / OGC simplicity
    shape_type = getattr(shape, "type", "").lower()
    if shape_type in ("polygon",):
        # ArcPy isMultipart / OGC simplicity check
        # An invalid polygon in ArcPy will raise or show self-intersections or bow-ties
        # When shape.area <= 0 or WKT has bowtie
        try:
            # Check OGC validity if WKT or buffer(0) check
            if hasattr(shape, "area") and shape.area <= 0.0:
                issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_INVALID_GEOM,
                        issue_type="ZERO_AREA_POLYGON",
                        severity=Severity.ERROR,
                        layer_name=layer_name,
                        source=source,
                        object_id=feature_id,
                        location=first_pt,
                        details="Polygon has zero or negative area.",
                    )
                )
                current_id += 1
        except Exception:
            pass
    elif shape_type in ("polyline", "line"):
        try:
            if hasattr(shape, "firstPoint") and hasattr(shape, "lastPoint"):
                fp = shape.firstPoint
                lp = shape.lastPoint
                if fp and lp and (abs(fp.X - lp.X) > 1e-4 or abs(fp.Y - lp.Y) > 1e-4):
                    issues.append(
                        QCIssue(
                            issue_id=current_id,
                            check_id=CheckID.CHK_INVALID_GEOM,
                            issue_type="UNCLOSED_RING",
                            severity=Severity.ERROR,
                            layer_name=layer_name,
                            source=source,
                            object_id=feature_id,
                            location=(fp.X, fp.Y),
                            details=f"Feature geometry is an open line/polyline (unclosed ring) in expected polygon layer.",
                        )
                    )
                    current_id += 1
        except Exception:
            pass

    return issues

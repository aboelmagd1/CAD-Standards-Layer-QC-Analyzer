# -*- coding: utf-8 -*-
"""
Multipart Feature Check (CHK_MULTIPART).
Detects features that contain more than one part when singlepart geometry is expected.
"""

from typing import List, Any
from ..models.qc_issue import QCIssue, Severity, CheckID


def check_multipart(
    feature_id: Any,
    shape: Any,
    layer_name: str,
    source: str = "INPUT",
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []

    if shape is None:
        return issues

    part_count = getattr(shape, "partCount", 1)
    # Note: In ArcPy, a polygon with an interior ring has partCount > 1 if getPart() includes holes.
    # To count distinct outer parts, we inspect whether parts are disjoint or exterior.
    # If isMultipart is True:
    is_multi = getattr(shape, "isMultipart", False)
    if not is_multi and part_count > 1:
        # Check if there are multiple exterior rings
        is_multi = True

    if is_multi:
        loc = None
        if hasattr(shape, "trueCentroid"):
            loc = (shape.trueCentroid.X, shape.trueCentroid.Y)
        elif hasattr(shape, "firstPoint"):
            loc = (shape.firstPoint.X, shape.firstPoint.Y)

        issues.append(
            QCIssue(
                issue_id=issue_id_start,
                check_id=CheckID.CHK_MULTIPART,
                issue_type="MULTIPART_FEATURE",
                severity=Severity.WARNING,
                layer_name=layer_name,
                source=source,
                object_id=feature_id,
                measurement=float(part_count),
                unit="parts",
                geometry=shape,
                location=loc,
                details=f"Feature contains {part_count} parts (expected singlepart).",
            )
        )

    return issues

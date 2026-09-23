# -*- coding: utf-8 -*-
"""
Short Segment Check (CHK_SHORT_SEG).
Detects polygon/polyline edges shorter than the configured tolerance (default 10.0 cm).
Supports sub-millimeter precision reporting (mm when < 1 cm).
"""

import math
from typing import List, Any
from ..models.qc_issue import QCIssue, Severity, CheckID


def check_short_segments(
    feature_id: Any,
    shape: Any,
    layer_name: str,
    source: str = "INPUT",
    tolerance_meters: float = 0.10,  # 10 cm
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
        for i in range(n_pts - 1):
            p1 = part[i]
            p2 = part[i + 1]
            if p1 is None or p2 is None:
                continue

            dx = p2.X - p1.X
            dy = p2.Y - p1.Y
            seg_len = math.hypot(dx, dy)

            # Ignore true identical zero points if handled by duplicate vertex
            if 0.0 < seg_len < tolerance_meters:
                # Format measurement and unit with high precision
                if seg_len < 0.01:
                    meas_val = seg_len * 1000.0
                    unit = "mm"
                    disp_str = f"{meas_val:.2f} mm"
                else:
                    meas_val = seg_len * 100.0
                    unit = "cm"
                    disp_str = f"{meas_val:.2f} cm"

                mid_x = (p1.X + p2.X) / 2.0
                mid_y = (p1.Y + p2.Y) / 2.0

                issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_SHORT_SEG,
                        issue_type="SHORT_SEGMENT",
                        severity=Severity.WARNING,
                        layer_name=layer_name,
                        source=source,
                        object_id=feature_id,
                        measurement=round(seg_len, 6),
                        threshold=tolerance_meters,
                        unit="m",
                        location=(mid_x, mid_y),
                        details=f"Segment {i} in Part {part_idx} is short ({disp_str} < {tolerance_meters * 100:.1f} cm).",
                    )
                )
                current_id += 1

    return issues

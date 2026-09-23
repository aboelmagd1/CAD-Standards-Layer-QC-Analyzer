# -*- coding: utf-8 -*-
"""
Property Comparator.
Compares CAD property distributions (Color, Linetype, Lineweight, Text, etc.)
between Reference and Received layers without hardcoded assumptions.
Gracefully handles unavailable properties (MATCH, DIFFERENT, NOT AVAILABLE, NOT APPLICABLE, NOT CHECKED).
"""

from typing import Dict, Tuple, List, Optional, Any
from ..models.qc_issue import QCIssue, Severity, CheckID


class PropertyStatus:
    MATCH = "MATCH"
    DIFFERENT = "DIFFERENT"
    NOT_AVAILABLE = "NOT AVAILABLE"
    NOT_APPLICABLE = "NOT APPLICABLE"
    NOT_CHECKED = "NOT CHECKED"


def compare_distribution(
    ref_dist: Dict[str, int],
    rec_dist: Dict[str, int],
    property_name: str,
    layer_name: str,
    check_id: str,
    issue_id_start: int = 1,
) -> Tuple[str, List[QCIssue], str]:
    """
    Compares two property distributions (e.g. Color, Linetype, Lineweight).
    Returns (status, list_of_issues, summary_string).
    """
    issues: List[QCIssue] = []

    # If neither side has data for this property
    if not ref_dist and not rec_dist:
        return PropertyStatus.NOT_AVAILABLE, issues, "Not available in either dataset."

    if not ref_dist:
        return PropertyStatus.NOT_AVAILABLE, issues, f"{property_name} not available in Reference."

    if not rec_dist:
        return PropertyStatus.NOT_AVAILABLE, issues, f"{property_name} not available in Received."

    # If both sides are identical
    if ref_dist == rec_dist:
        return PropertyStatus.MATCH, issues, f"{property_name} distribution matches."

    # Find dominant values
    ref_dominant = max(ref_dist.items(), key=lambda x: x[1])[0]
    rec_dominant = max(rec_dist.items(), key=lambda x: x[1])[0]

    # Check differences
    diff_items = []
    for val, count in rec_dist.items():
        ref_count = ref_dist.get(val, 0)
        if ref_count == 0:
            diff_items.append(f"Unexpected {val} ({count} features)")
        elif ref_count != count:
            diff_items.append(f"{val} count delta: {count - ref_count:+d}")

    summary_str = f"Reference: {ref_dominant} vs Received: {rec_dominant}"
    if diff_items:
        summary_str += " (" + ", ".join(diff_items[:3]) + ")"

    # Generate QC issue for mismatch
    issue = QCIssue(
        issue_id=issue_id_start,
        check_id=check_id,
        issue_type=f"{property_name.upper()}_DIFFERENCE",
        severity=Severity.ERROR if ref_dominant != rec_dominant else Severity.WARNING,
        layer_name=layer_name,
        source="RECEIVED",
        property_name=property_name,
        expected_value=str(ref_dominant),
        actual_value=str(rec_dominant),
        details=(
            f"Layer '{layer_name}' {property_name} difference. "
            f"Expected (Reference): {ref_dominant} ({ref_dist.get(ref_dominant, 0)} features). "
            f"Received: {rec_dominant} ({rec_dist.get(rec_dominant, 0)} features). "
            f"Details: {', '.join(diff_items) if diff_items else 'Distribution shift'}."
        ),
    )
    issues.append(issue)

    return PropertyStatus.DIFFERENT, issues, summary_str

# -*- coding: utf-8 -*-
"""
Geometry Comparator.
Compares geometry distributions and flags unexpected feature types within layers.
"""

from typing import Dict, List, Tuple
from ..models.qc_issue import QCIssue, Severity, CheckID
from ..models.reference_profile import LayerProfile


def compare_geometry_composition(
    ref_layer: LayerProfile,
    rec_layer: LayerProfile,
    layer_name: str,
    issue_id_start: int = 1,
) -> Tuple[List[QCIssue], str, List[str]]:
    """
    Compares the geometry distribution of the Received layer against the Reference Layer Profile.
    Returns (issues, status, unexpected_summary_list).
    """
    issues: List[QCIssue] = []
    current_id = issue_id_start
    status = "MATCH"
    unexpected_summary = []

    ref_geoms = ref_layer.geometry_distribution
    rec_geoms = rec_layer.geometry_distribution

    # Identify unexpected geometry types (present in Received but 0 in Reference)
    for geom_type, rec_count in rec_geoms.items():
        ref_count = ref_geoms.get(geom_type, 0)
        if ref_count == 0 and rec_count > 0:
            unexpected_summary.append(f"{rec_count} unexpected {geom_type}")
            status = "ERROR"

            issue = QCIssue(
                issue_id=current_id,
                check_id=CheckID.CHK_UNEXPECTED_FEATURE,
                issue_type="UNEXPECTED_GEOMETRY_TYPE",
                severity=Severity.ERROR,
                layer_name=layer_name,
                source="RECEIVED",
                property_name="GeometryType",
                expected_value=ref_layer.dominant_geometry or "None",
                actual_value=geom_type,
                measurement=float(rec_count),
                unit="features",
                details=(
                    f"Layer '{layer_name}' contains {rec_count} unexpected {geom_type} features "
                    f"not present in Reference profile (Expected: {ref_layer.dominant_geometry})."
                ),
            )
            issues.append(issue)
            current_id += 1

    # Check dominant geometry mismatch
    if ref_layer.dominant_geometry != "MIXED" and rec_layer.dominant_geometry != "MIXED":
        if ref_layer.dominant_geometry != rec_layer.dominant_geometry:
            status = "ERROR"
            issue = QCIssue(
                issue_id=current_id,
                check_id=CheckID.CHK_GEOMETRY_TYPE,
                issue_type="DOMINANT_GEOMETRY_MISMATCH",
                severity=Severity.ERROR,
                layer_name=layer_name,
                source="RECEIVED",
                property_name="DominantGeometry",
                expected_value=ref_layer.dominant_geometry,
                actual_value=rec_layer.dominant_geometry,
                details=(
                    f"Dominant geometry mismatch for layer '{layer_name}': "
                    f"Expected '{ref_layer.dominant_geometry}' ({ref_layer.dominant_percentage * 100:.1f}%) "
                    f"but Received '{rec_layer.dominant_geometry}' ({rec_layer.dominant_percentage * 100:.1f}%)."
                ),
            )
            issues.append(issue)
            current_id += 1

    # Check mixed profile warning
    if ref_layer.is_mixed_geometry:
        if status == "MATCH":
            status = "REVIEW"
        issue = QCIssue(
            issue_id=current_id,
            check_id=CheckID.CHK_MIXED_PROFILE,
            issue_type="REFERENCE_MIXED_GEOMETRY",
            severity=Severity.WARNING,
            layer_name=layer_name,
            source="REFERENCE",
            details=(
                f"Reference layer '{layer_name}' has mixed geometry composition "
                f"without a clear dominant type (Top: {ref_layer.dominant_percentage * 100:.1f}%). Review required."
            ),
        )
        issues.append(issue)
        current_id += 1

    return issues, status, unexpected_summary

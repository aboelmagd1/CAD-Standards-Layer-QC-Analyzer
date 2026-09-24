# -*- coding: utf-8 -*-
"""
Comparison Engine.
Core orchestrator for Reference-vs-Received CAD Comparison QC.
Analyzes differences without hardcoded rules, building LayerQCStatuses and QCIssue models.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from ..models.qc_issue import QCIssue, Severity, CheckID
from ..models.reference_profile import ReferenceProfile, LayerProfile
from ..models.qc_result import QCResult, LayerQCStatus, LayerStatus
from .layer_analyzer import analyze_dataset, normalize_layer_name
from .property_comparator import compare_distribution, PropertyStatus
from .geometry_comparator import compare_geometry_composition
from .closure_checker import check_feature_closure


class ComparisonConfig:
    def __init__(
        self,
        compare_layer_names: bool = True,
        compare_feature_counts: bool = False,
        compare_geometry_types: bool = True,
        compare_geometry_distribution: bool = True,
        compare_closure: bool = True,
        compare_color: bool = True,
        compare_linetype: bool = True,
        compare_lineweight: bool = True,
        detect_unexpected_features: bool = True,
        closure_tolerance: float = 0.01,
        dominant_threshold: float = 0.50,
        count_difference_tolerance_pct: float = 0.0,
        case_sensitive: bool = False,
        trim_whitespace: bool = True,
        scope: str = "All Layers",  # "All Layers", "Polygon / Closed-Geometry Layers", "Custom Layer Selection"
        selected_layers: Optional[List[str]] = None,
    ):
        self.compare_layer_names = compare_layer_names
        self.compare_feature_counts = compare_feature_counts
        self.compare_geometry_types = compare_geometry_types
        self.compare_geometry_distribution = compare_geometry_distribution
        self.compare_closure = compare_closure
        self.compare_color = compare_color
        self.compare_linetype = compare_linetype
        self.compare_lineweight = compare_lineweight
        self.detect_unexpected_features = detect_unexpected_features
        self.closure_tolerance = closure_tolerance
        self.dominant_threshold = dominant_threshold
        self.count_difference_tolerance_pct = count_difference_tolerance_pct
        self.case_sensitive = case_sensitive
        self.trim_whitespace = trim_whitespace
        self.scope = scope
        self.selected_layers = [s.upper() if not case_sensitive else s for s in (selected_layers or [])]


def run_cad_comparison(
    reference_profile: ReferenceProfile,
    received_source: Any,
    received_layer_field: str = "Layer",
    config: Optional[ComparisonConfig] = None,
    progress_callback: Optional[Any] = None,
) -> QCResult:
    """
    Executes the full Reference-vs-Received CAD comparison.
    """
    if config is None:
        config = ComparisonConfig()

    def notify(msg: str):
        if progress_callback:
            progress_callback(msg)

    result = QCResult(
        reference_source=reference_profile.source_path,
        received_source=str(received_source),
        execution_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        reference_profile=reference_profile,
        spatial_reference_ref=reference_profile.spatial_reference_name,
    )

    # 1. Analyze Received CAD
    notify("Analyzing Received CAD...")
    received_analysis = analyze_dataset(
        source_dataset=received_source,
        layer_field_name=received_layer_field,
        closure_tolerance=config.closure_tolerance,
        dominant_threshold=config.dominant_threshold,
        case_sensitive=config.case_sensitive,
        trim_whitespace=config.trim_whitespace,
        progress_callback=progress_callback,
    )

    received_profile = ReferenceProfile(
        source_path=received_analysis.source_path,
        spatial_reference_name=received_analysis.spatial_reference_name,
        spatial_reference_wkid=received_analysis.spatial_reference_wkid,
        total_features=received_analysis.total_features,
        layers=received_analysis.layers,
        available_cad_fields=received_analysis.available_cad_fields,
        analysis_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    result.received_profile = received_profile
    result.spatial_reference_rec = received_profile.spatial_reference_name

    # Check spatial reference match
    if (
        reference_profile.spatial_reference_name != "Unknown"
        and received_profile.spatial_reference_name != "Unknown"
        and reference_profile.spatial_reference_name != received_profile.spatial_reference_name
    ):
        result.spatial_reference_warning = True
        result.add_issue(
            QCIssue(
                issue_id=len(result.issues) + 1,
                check_id=CheckID.CHK_COORDINATE_SYSTEM,
                issue_type="COORDINATE_SYSTEM_MISMATCH",
                severity=Severity.WARNING,
                layer_name="GLOBAL",
                source="RECEIVED",
                expected_value=reference_profile.spatial_reference_name,
                actual_value=received_profile.spatial_reference_name,
                details=(
                    f"Spatial reference mismatch: Reference is '{reference_profile.spatial_reference_name}' "
                    f"but Received is '{received_profile.spatial_reference_name}'. Reprojection is not performed."
                ),
            )
        )

    ref_keys = set(reference_profile.layers.keys())
    rec_keys = set(received_profile.layers.keys())

    result.matching_layers = sorted(list(ref_keys.intersection(rec_keys)))
    result.missing_layers = sorted(list(ref_keys - rec_keys))
    result.extra_layers = sorted(list(rec_keys - ref_keys))

    # Check for reserved system layer '0' in Reference dataset
    for r_key, lp_ref in reference_profile.layers.items():
        if lp_ref.layer_name.strip() in ("0", "Defpoints", "DEFPOINTS") and lp_ref.feature_count > 0:
            result.add_issue(
                QCIssue(
                    issue_id=len(result.issues) + 1,
                    check_id=CheckID.CHK_RESERVED_LAYER,
                    issue_type="RESERVED_LAYER_CONTAINS_DATA",
                    severity=Severity.WARNING,
                    layer_name=lp_ref.layer_name,
                    source="REFERENCE",
                    expected_value="Empty (0 features)",
                    actual_value=f"{lp_ref.feature_count} features",
                    details=(
                        f"Reference CAD contains {lp_ref.feature_count} features on reserved system layer '{lp_ref.layer_name}'. "
                        f"Standard CAD drafting rules require layer '0' to remain empty without drawing entities."
                    ),
                )
            )

    # 2. Report Missing Layers
    notify("Comparing Layer inventories...")
    for m_key in result.missing_layers:
        lp_ref = reference_profile.layers[m_key]
        orig_name = lp_ref.layer_name

        # If layer 0 is missing in Received, that is actually good practice (Received cleaned layer 0)
        if orig_name.strip() in ("0", "Defpoints", "DEFPOINTS"):
            result.layer_statuses[orig_name] = LayerQCStatus(
                layer_name=orig_name,
                status=LayerStatus.PASS,
                ref_count=lp_ref.feature_count,
                rec_count=0,
                expected_geom="None (Empty)",
                received_geom="Empty",
                geom_status="MATCH",
                color_status="N/A",
                lineweight_status="N/A",
                linetype_status="N/A",
                closure_status="N/A",
                issues_count=0,
                reasons=["Reserved layer '0' is empty in Received dataset (compliant with CAD standards)"],
            )
            continue

        issue = QCIssue(
            issue_id=len(result.issues) + 1,
            check_id=CheckID.CHK_MISSING_LAYER,
            issue_type="MISSING_LAYER",
            severity=Severity.ERROR,
            layer_name=orig_name,
            source="REFERENCE",
            expected_value="Present in Received",
            actual_value="Missing",
            details=f"Required layer '{orig_name}' ({lp_ref.feature_count} features in Reference) is missing from Received CAD.",
        )
        result.add_issue(issue)

        result.layer_statuses[orig_name] = LayerQCStatus(
            layer_name=orig_name,
            status=LayerStatus.MISSING,
            ref_count=lp_ref.feature_count,
            rec_count=0,
            expected_geom=lp_ref.dominant_geometry or "Unknown",
            received_geom="Missing",
            geom_status="MISSING",
            color_status="N/A",
            lineweight_status="N/A",
            linetype_status="N/A",
            closure_status="N/A",
            issues_count=1,
            reasons=[f"Layer missing from Received dataset ({lp_ref.feature_count} features expected)"],
        )

    # 3. Report Extra Layers
    for e_key in result.extra_layers:
        lp_rec = received_profile.layers[e_key]
        orig_name = lp_rec.layer_name

        is_reserved = orig_name.strip() in ("0", "Defpoints", "DEFPOINTS")
        issue_sev = Severity.WARNING if is_reserved else Severity.INFO
        issue_chk = CheckID.CHK_RESERVED_LAYER if is_reserved else CheckID.CHK_EXTRA_LAYER
        issue_details = (
            f"Received CAD contains {lp_rec.feature_count} features on reserved system layer '{orig_name}'. "
            f"CAD standards require layer '0' to remain empty."
            if is_reserved else
            f"Extra layer '{orig_name}' present in Received CAD ({lp_rec.feature_count} features) but not in Reference."
        )

        issue = QCIssue(
            issue_id=len(result.issues) + 1,
            check_id=issue_chk,
            issue_type="RESERVED_LAYER_CONTAINS_DATA" if is_reserved else "EXTRA_LAYER",
            severity=issue_sev,
            layer_name=orig_name,
            source="RECEIVED",
            expected_value="Empty (0 features)" if is_reserved else "Not in Reference",
            actual_value=f"{lp_rec.feature_count} features" if is_reserved else "Present",
            measurement=float(lp_rec.feature_count),
            unit="features",
            details=issue_details,
        )
        result.add_issue(issue)

        result.layer_statuses[orig_name] = LayerQCStatus(
            layer_name=orig_name,
            status=LayerStatus.WARNING if is_reserved else LayerStatus.EXTRA,
            ref_count=0,
            rec_count=lp_rec.feature_count,
            expected_geom="None",
            received_geom=lp_rec.dominant_geometry or "Unknown",
            geom_status="EXTRA",
            color_status="N/A",
            lineweight_status="N/A",
            linetype_status="N/A",
            closure_status="N/A",
            issues_count=1,
            reasons=[
                f"Reserved system layer '{orig_name}' contains {lp_rec.feature_count} features (should be empty)"
                if is_reserved else
                f"Extra layer present in Received CAD ({lp_rec.feature_count} features)"
            ],
        )

    # 4. Compare Matching Layers
    notify("Validating matching layers...")
    for key in result.matching_layers:
        lp_ref = reference_profile.layers[key]
        lp_rec = received_profile.layers[key]
        orig_name = lp_ref.layer_name

        # Scope filter check
        if config.scope == "Polygon / Closed-Geometry Layers":
            if not lp_ref.closure_required and lp_ref.dominant_geometry not in ("POLYGON", "CLOSED_POLYLINE"):
                continue
        elif config.scope == "Custom Layer Selection":
            if key not in config.selected_layers and orig_name not in config.selected_layers:
                continue

        layer_issues: List[QCIssue] = []
        layer_reasons: List[str] = []
        status = LayerStatus.PASS

        # Reserved layer check if layer 0 is matched and has features
        if orig_name.strip() in ("0", "Defpoints", "DEFPOINTS") and lp_rec.feature_count > 0:
            res_issue = QCIssue(
                issue_id=len(result.issues) + 1,
                check_id=CheckID.CHK_RESERVED_LAYER,
                issue_type="RESERVED_LAYER_CONTAINS_DATA",
                severity=Severity.WARNING,
                layer_name=orig_name,
                source="RECEIVED",
                expected_value="Empty (0 features)",
                actual_value=f"{lp_rec.feature_count} features",
                details=(
                    f"Received CAD contains {lp_rec.feature_count} features on reserved system layer '{orig_name}'. "
                    f"CAD standards require layer '0' to remain empty without drawing entities."
                ),
            )
            result.add_issue(res_issue)
            layer_issues.append(res_issue)
            layer_reasons.append(f"Reserved system layer '{orig_name}' contains {lp_rec.feature_count} features (should be empty)")
            status = LayerStatus.WARNING

        # A. Empty Received Layer Check
        if lp_rec.feature_count == 0 and lp_ref.feature_count > 0:
            result.empty_received_layers.append(orig_name)
            issue = QCIssue(
                issue_id=len(result.issues) + 1,
                check_id=CheckID.CHK_FEATURE_COUNT,
                issue_type="EMPTY_RECEIVED_LAYER",
                severity=Severity.ERROR,
                layer_name=orig_name,
                source="RECEIVED",
                expected_value=str(lp_ref.feature_count),
                actual_value="0",
                details=f"Layer '{orig_name}' exists in Received CAD but contains 0 valid entities ({lp_ref.feature_count} expected).",
            )
            result.add_issue(issue)
            layer_issues.append(issue)
            layer_reasons.append("Layer is empty in Received dataset")
            status = LayerStatus.ERROR

        # B. Feature Count Difference Check
        if config.compare_feature_counts and lp_rec.feature_count > 0:
            diff_count = lp_rec.feature_count - lp_ref.feature_count
            pct_diff = (diff_count / lp_ref.feature_count * 100.0) if lp_ref.feature_count > 0 else 0.0

            if abs(diff_count) > 0 and abs(pct_diff) > config.count_difference_tolerance_pct:
                issue = QCIssue(
                    issue_id=len(result.issues) + 1,
                    check_id=CheckID.CHK_FEATURE_COUNT,
                    issue_type="FEATURE_COUNT_DIFFERENCE",
                    severity=Severity.WARNING,
                    layer_name=orig_name,
                    source="RECEIVED",
                    expected_value=str(lp_ref.feature_count),
                    actual_value=str(lp_rec.feature_count),
                    measurement=float(diff_count),
                    unit="features",
                    details=f"Feature count difference in '{orig_name}': Reference={lp_ref.feature_count}, Received={lp_rec.feature_count} (Delta: {diff_count:+d}, {pct_diff:+.1f}%).",
                )
                result.add_issue(issue)
                layer_issues.append(issue)
                layer_reasons.append(f"Feature count delta: {diff_count:+d} ({pct_diff:+.1f}%)")
                if status == LayerStatus.PASS:
                    status = LayerStatus.WARNING

        # C. Geometry Distribution & Unexpected Features
        geom_status_str = "MATCH"
        if config.compare_geometry_types or config.compare_geometry_distribution or config.detect_unexpected_features:
            g_issues, g_status, unexpected_summary = compare_geometry_composition(
                lp_ref, lp_rec, orig_name, len(result.issues) + 1
            )
            geom_status_str = g_status
            if g_issues:
                for gi in g_issues:
                    result.add_issue(gi)
                    layer_issues.append(gi)
                layer_reasons.extend(unexpected_summary)
                if g_status == "ERROR":
                    status = LayerStatus.ERROR
                elif g_status == "REVIEW" and status != LayerStatus.ERROR:
                    status = LayerStatus.REVIEW

        # D. Closure Comparison
        closure_status_str = "N/A"
        if config.compare_closure:
            if lp_ref.closure_required or lp_ref.dominant_geometry in ("POLYGON", "CLOSED_POLYLINE"):
                closure_status_str = "MATCH"
                # Inspect closure percentage
                if lp_rec.open_count > 0:
                    closure_status_str = "ERROR"
                    status = LayerStatus.ERROR
                    layer_reasons.append(f"{lp_rec.open_count} open polylines where closed geometry was expected")

                    # Add feature-level closure issues if shapes sampled
                    sampled = received_analysis.sampled_features.get(key, {})
                    for oid, shp in sampled.items():
                        c_issue = check_feature_closure(
                            oid, shp, orig_name, "RECEIVED", config.closure_tolerance, len(result.issues) + 1
                        )
                        if c_issue:
                            result.add_issue(c_issue)
                            layer_issues.append(c_issue)

                    # Also add a layer-level summary issue for closure
                    issue = QCIssue(
                        issue_id=len(result.issues) + 1,
                        check_id=CheckID.CHK_CLOSURE,
                        issue_type="CLOSURE_DIFFERENCE",
                        severity=Severity.ERROR,
                        layer_name=orig_name,
                        source="RECEIVED",
                        expected_value=f"{lp_ref.closure_percentage * 100:.1f}% Closed",
                        actual_value=f"{lp_rec.closure_percentage * 100:.1f}% Closed",
                        measurement=float(lp_rec.open_count),
                        unit="features",
                        details=(
                            f"Layer '{orig_name}' closure difference. "
                            f"Reference: {lp_ref.closure_percentage * 100:.1f}% Closed. "
                            f"Received: {lp_rec.closure_percentage * 100:.1f}% Closed ({lp_rec.open_count} open features)."
                        ),
                    )
                    result.add_issue(issue)
                    layer_issues.append(issue)

        # E. Color Comparison
        color_status_str = "NOT AVAILABLE"
        if config.compare_color:
            c_stat, c_issues, c_summary = compare_distribution(
                lp_ref.color_distribution,
                lp_rec.color_distribution,
                "Color",
                orig_name,
                CheckID.CHK_COLOR,
                len(result.issues) + 1,
            )
            color_status_str = c_stat
            if c_issues:
                for ci in c_issues:
                    result.add_issue(ci)
                    layer_issues.append(ci)
                layer_reasons.append(f"Color: {c_summary}")
                if c_stat == PropertyStatus.DIFFERENT:
                    if status != LayerStatus.ERROR:
                        status = LayerStatus.WARNING

        # F. Linetype Comparison
        linetype_status_str = "NOT AVAILABLE"
        if config.compare_linetype:
            lt_stat, lt_issues, lt_summary = compare_distribution(
                lp_ref.linetype_distribution,
                lp_rec.linetype_distribution,
                "Linetype",
                orig_name,
                CheckID.CHK_LINETYPE,
                len(result.issues) + 1,
            )
            linetype_status_str = lt_stat
            if lt_issues:
                for lti in lt_issues:
                    result.add_issue(lti)
                    layer_issues.append(lti)
                layer_reasons.append(f"Linetype: {lt_summary}")
                if lt_stat == PropertyStatus.DIFFERENT:
                    if status != LayerStatus.ERROR:
                        status = LayerStatus.WARNING

        # G. Lineweight Comparison
        lineweight_status_str = "NOT AVAILABLE"
        if config.compare_lineweight:
            lw_stat, lw_issues, lw_summary = compare_distribution(
                lp_ref.lineweight_distribution,
                lp_rec.lineweight_distribution,
                "Lineweight",
                orig_name,
                CheckID.CHK_LINEWEIGHT,
                len(result.issues) + 1,
            )
            lineweight_status_str = lw_stat
            if lw_issues:
                for lwi in lw_issues:
                    result.add_issue(lwi)
                    layer_issues.append(lwi)
                layer_reasons.append(f"Lineweight: {lw_summary}")
                if lw_stat == PropertyStatus.DIFFERENT:
                    if status != LayerStatus.ERROR:
                        status = LayerStatus.WARNING

        # Construct Layer QC Status record
        result.layer_statuses[orig_name] = LayerQCStatus(
            layer_name=orig_name,
            status=status,
            ref_count=lp_ref.feature_count,
            rec_count=lp_rec.feature_count,
            expected_geom=lp_ref.dominant_geometry or "Unknown",
            received_geom=lp_rec.dominant_geometry or "Unknown",
            geom_status=geom_status_str,
            color_status=color_status_str,
            lineweight_status=lineweight_status_str,
            linetype_status=linetype_status_str,
            closure_status=closure_status_str,
            issues_count=len(layer_issues),
            reasons=layer_reasons,
        )

    notify("Comparison completed.")
    return result

# -*- coding: utf-8 -*-
"""
CAD Standards & Layer QC Analyzer Helpers.
"""

from .models import QCIssue, Severity, CheckID, ReferenceProfile, LayerProfile, QCResult, LayerQCStatus, LayerStatus
from .geometry import (
    GeometryCategory,
    classify_geometry,
    is_closed_polyline,
    point_distance,
    SpatialGridIndex,
    VertexGridIndex,
    GeometryQCConfig,
    run_geometry_qc,
)
from .comparison import (
    evaluate_polyline_closure,
    check_feature_closure,
    compare_distribution,
    PropertyStatus,
    analyze_dataset,
    normalize_layer_name,
    build_reference_profile,
    ComparisonConfig,
    run_cad_comparison,
)
from .reporting import create_excel_report, create_html_report, create_text_report
from .issue_writer import write_issues_to_feature_class, write_issues_to_table, export_qc_errors_to_geodatabase_dataset
from .utilities import get_dataset_spatial_reference, compare_spatial_references, auto_detect_layer_field
from .validation import validate_cad_comparison_parameters, validate_geometry_qc_parameters

__all__ = [
    "QCIssue",
    "Severity",
    "CheckID",
    "ReferenceProfile",
    "LayerProfile",
    "QCResult",
    "LayerQCStatus",
    "LayerStatus",
    "GeometryCategory",
    "classify_geometry",
    "is_closed_polyline",
    "point_distance",
    "SpatialGridIndex",
    "VertexGridIndex",
    "GeometryQCConfig",
    "run_geometry_qc",
    "evaluate_polyline_closure",
    "check_feature_closure",
    "compare_distribution",
    "PropertyStatus",
    "analyze_dataset",
    "normalize_layer_name",
    "build_reference_profile",
    "ComparisonConfig",
    "run_cad_comparison",
    "create_excel_report",
    "create_html_report",
    "create_text_report",
    "write_issues_to_feature_class",
    "get_dataset_spatial_reference",
    "compare_spatial_references",
    "auto_detect_layer_field",
    "validate_cad_comparison_parameters",
    "validate_geometry_qc_parameters",
]

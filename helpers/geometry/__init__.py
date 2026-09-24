# -*- coding: utf-8 -*-
from .geometry_classifier import GeometryCategory, classify_geometry, is_closed_polyline, point_distance
from .geometry_types import GeometryType, normalize_geometry_type, classify_feature_geometry
from .spatial_index import SpatialGridIndex
from .vertex_index import VertexGridIndex, VertexRecord
from .invalid_geometry import check_invalid_geometry
from .duplicate import check_duplicate_geometry
from .overlap import check_overlap
from .gap import check_enclosed_gaps
from .multipart import check_multipart
from .short_segment import check_short_segments
from .angle import check_sharp_angles, calculate_vertex_angle
from .snap import check_snap_issues
from .redundant_vertex import check_redundant_vertices
from .junction import check_missing_junctions
from .geometry_qc_runner import GeometryQCConfig, run_geometry_qc
from .line_qc import (
    LineQCConfig,
    run_line_qc,
    check_invalid_line,
    check_duplicate_lines,
    check_line_overlaps,
    check_line_self_intersection,
    check_line_dangles,
    check_line_disconnected,
    check_short_lines_and_segments,
    check_line_sharp_angles,
    check_line_redundant_vertices,
    check_line_snap_issues,
    check_line_missing_junctions,
    evaluate_line_closure_behavior,
)
from .point_qc import (
    PointQCConfig,
    run_point_qc,
    check_invalid_point,
    check_point_duplicates,
    check_point_distribution,
    check_cross_layer_coincident_points,
)
from .qc_profiles import (
    GeometryQCProfile,
    PolygonQCProfile,
    LineQCProfile,
    PointQCProfile,
    MultipointQCProfile,
    UnknownQCProfile,
    get_qc_profile_for_type,
    GetApplicableChecks,
    get_applicable_qc_profile,
)

__all__ = [
    "GeometryCategory",
    "GeometryType",
    "normalize_geometry_type",
    "classify_feature_geometry",
    "classify_geometry",
    "is_closed_polyline",
    "point_distance",
    "SpatialGridIndex",
    "VertexGridIndex",
    "VertexRecord",
    "check_invalid_geometry",
    "check_duplicate_geometry",
    "check_overlap",
    "check_enclosed_gaps",
    "check_multipart",
    "check_short_segments",
    "check_sharp_angles",
    "calculate_vertex_angle",
    "check_snap_issues",
    "check_redundant_vertices",
    "check_missing_junctions",
    "GeometryQCConfig",
    "run_geometry_qc",
    "LineQCConfig",
    "run_line_qc",
    "check_invalid_line",
    "check_duplicate_lines",
    "check_line_overlaps",
    "check_line_self_intersection",
    "check_line_dangles",
    "check_line_disconnected",
    "check_short_lines_and_segments",
    "check_line_sharp_angles",
    "check_line_redundant_vertices",
    "check_line_snap_issues",
    "check_line_missing_junctions",
    "evaluate_line_closure_behavior",
    "PointQCConfig",
    "run_point_qc",
    "check_invalid_point",
    "check_point_duplicates",
    "check_point_distribution",
    "check_cross_layer_coincident_points",
    "GeometryQCProfile",
    "PolygonQCProfile",
    "LineQCProfile",
    "PointQCProfile",
    "MultipointQCProfile",
    "UnknownQCProfile",
    "get_qc_profile_for_type",
    "GetApplicableChecks",
    "get_applicable_qc_profile",
]


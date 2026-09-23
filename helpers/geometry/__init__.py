# -*- coding: utf-8 -*-
from .geometry_classifier import GeometryCategory, classify_geometry, is_closed_polyline, point_distance
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

__all__ = [
    "GeometryCategory",
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
]

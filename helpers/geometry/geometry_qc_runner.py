# -*- coding: utf-8 -*-
"""
Geometry QC Runner.
Executes the full suite of 10 geometry QC checks against a dataset or feature collection,
with configurable thresholds and progress tracking.
"""

from typing import Dict, List, Any, Optional, Tuple
from ..models.qc_issue import QCIssue, CheckID, Severity
from .spatial_index import SpatialGridIndex
from .invalid_geometry import check_invalid_geometry
from .duplicate import check_duplicate_geometry
from .overlap import check_overlap
from .gap import check_enclosed_gaps
from .multipart import check_multipart
from .short_segment import check_short_segments
from .angle import check_sharp_angles
from .snap import check_snap_issues
from .redundant_vertex import check_redundant_vertices
from .junction import check_missing_junctions


class GeometryQCConfig:
    def __init__(
        self,
        check_invalid: bool = True,
        check_overlap: bool = True,
        check_duplicate: bool = True,
        check_gap: bool = True,
        check_multipart: bool = True,
        check_short_seg: bool = True,
        check_angle: bool = True,
        check_snap: bool = True,
        check_redundant: bool = True,
        check_junction: bool = True,
        overlap_tolerance_sqm: float = 0.0001,
        gap_tolerance_sqm: float = 0.001,
        short_seg_tolerance_m: float = 0.10,  # 10 cm
        angle_tolerance_deg: float = 5.0,  # 5°
        snap_tolerance_m: float = 0.01,  # 1 cm
        redundant_vertex_deg: float = 179.9,  # 179.9°
        junction_tolerance_m: float = 0.01,  # 1 cm
    ):
        self.check_invalid = check_invalid
        self.check_overlap = check_overlap
        self.check_duplicate = check_duplicate
        self.check_gap = check_gap
        self.check_multipart = check_multipart
        self.check_short_seg = check_short_seg
        self.check_angle = check_angle
        self.check_snap = check_snap
        self.check_redundant = check_redundant
        self.check_junction = check_junction

        self.overlap_tolerance_sqm = overlap_tolerance_sqm
        self.gap_tolerance_sqm = gap_tolerance_sqm
        self.short_seg_tolerance_m = short_seg_tolerance_m
        self.angle_tolerance_deg = angle_tolerance_deg
        self.snap_tolerance_m = snap_tolerance_m
        self.redundant_vertex_deg = redundant_vertex_deg
        self.junction_tolerance_m = junction_tolerance_m


def run_geometry_qc(
    features: Dict[Any, Any],  # fid -> shape
    layer_name: str = "GeometryQC",
    source: str = "INPUT",
    config: Optional[GeometryQCConfig] = None,
    progress_callback: Optional[Any] = None,
) -> Tuple[List[QCIssue], Dict[str, Dict[str, Any]]]:
    """
    Runs all enabled geometry QC checks against the given features dictionary.
    Returns (all_issues, summary_dict).
    """
    if config is None:
        config = GeometryQCConfig()

    issues: List[QCIssue] = []
    current_issue_id = 1

    summary: Dict[str, Dict[str, Any]] = {
        CheckID.CHK_INVALID_GEOM: {"name": "Invalid Geometry", "count": 0, "status": "PASS"},
        CheckID.CHK_OVERLAP: {"name": "Overlap", "count": 0, "status": "PASS"},
        CheckID.CHK_DUPLICATE: {"name": "Duplicate Geometry", "count": 0, "status": "PASS"},
        CheckID.CHK_GAP: {"name": "Enclosed Gap", "count": 0, "status": "PASS"},
        CheckID.CHK_MULTIPART: {"name": "Multipart Feature", "count": 0, "status": "PASS"},
        CheckID.CHK_SHORT_SEG: {"name": "Short Segment", "count": 0, "status": "PASS"},
        CheckID.CHK_ANGLE: {"name": "Angle Issue", "count": 0, "status": "PASS"},
        CheckID.CHK_SNAP: {"name": "Snap Issue", "count": 0, "status": "PASS"},
        CheckID.CHK_REDUNDANT: {"name": "Redundant Vertex", "count": 0, "status": "PASS"},
        CheckID.CHK_JUNCTION: {"name": "Missing Junction", "count": 0, "status": "PASS"},
    }

    def notify(msg: str):
        if progress_callback:
            progress_callback(msg)

    # Build spatial index
    notify("Building in-memory spatial index...")
    spatial_index = SpatialGridIndex(cell_size=100.0)
    for fid, shape in features.items():
        if shape and hasattr(shape, "extent"):
            spatial_index.insert(fid, shape.extent)

    # 1. Invalid Geometry
    if config.check_invalid:
        notify("Running Invalid Geometry check...")
        chk_count = 0
        for fid, shape in features.items():
            errs = check_invalid_geometry(fid, shape, layer_name, source, current_issue_id)
            if errs:
                issues.extend(errs)
                current_issue_id += len(errs)
                chk_count += len(errs)
        summary[CheckID.CHK_INVALID_GEOM]["count"] = chk_count
        if chk_count > 0:
            summary[CheckID.CHK_INVALID_GEOM]["status"] = "ERROR"

    # 2. Duplicate Geometry
    excluded_duplicate_pairs = set()
    if config.check_duplicate:
        notify("Running Duplicate Geometry check...")
        dup_issues, dup_pairs = check_duplicate_geometry(
            features, layer_name, source, 0.999, current_issue_id, spatial_index
        )
        excluded_duplicate_pairs = dup_pairs
        issues.extend(dup_issues)
        current_issue_id += len(dup_issues)
        summary[CheckID.CHK_DUPLICATE]["count"] = len(dup_issues)
        if dup_issues:
            summary[CheckID.CHK_DUPLICATE]["status"] = "ERROR"

    # 3. Overlap Check
    if config.check_overlap:
        notify("Running Overlap check...")
        ov_issues = check_overlap(
            features,
            layer_name,
            source,
            config.overlap_tolerance_sqm,
            excluded_duplicate_pairs,
            spatial_index,
            current_issue_id,
        )
        issues.extend(ov_issues)
        current_issue_id += len(ov_issues)
        summary[CheckID.CHK_OVERLAP]["count"] = len(ov_issues)
        if ov_issues:
            summary[CheckID.CHK_OVERLAP]["status"] = "ERROR"

    # 4. Enclosed Gap
    if config.check_gap:
        notify("Running Enclosed Gap check...")
        gap_issues = check_enclosed_gaps(
            features, layer_name, source, config.gap_tolerance_sqm, 100.0, current_issue_id
        )
        issues.extend(gap_issues)
        current_issue_id += len(gap_issues)
        summary[CheckID.CHK_GAP]["count"] = len(gap_issues)
        if gap_issues:
            summary[CheckID.CHK_GAP]["status"] = "ERROR"

    # 5. Multipart Feature
    if config.check_multipart:
        notify("Running Multipart check...")
        mp_count = 0
        for fid, shape in features.items():
            mp_issues = check_multipart(fid, shape, layer_name, source, current_issue_id)
            if mp_issues:
                issues.extend(mp_issues)
                current_issue_id += len(mp_issues)
                mp_count += len(mp_issues)
        summary[CheckID.CHK_MULTIPART]["count"] = mp_count
        if mp_count > 0:
            summary[CheckID.CHK_MULTIPART]["status"] = "WARNING"

    # 6. Short Segment
    if config.check_short_seg:
        notify("Running Short Segment check...")
        seg_count = 0
        for fid, shape in features.items():
            seg_issues = check_short_segments(
                fid, shape, layer_name, source, config.short_seg_tolerance_m, current_issue_id
            )
            if seg_issues:
                issues.extend(seg_issues)
                current_issue_id += len(seg_issues)
                seg_count += len(seg_issues)
        summary[CheckID.CHK_SHORT_SEG]["count"] = seg_count
        if seg_count > 0:
            summary[CheckID.CHK_SHORT_SEG]["status"] = "WARNING"

    # 7. Sharp Angle
    if config.check_angle:
        notify("Running Sharp Angle check...")
        ang_count = 0
        for fid, shape in features.items():
            ang_issues = check_sharp_angles(
                fid, shape, layer_name, source, config.angle_tolerance_deg, current_issue_id
            )
            if ang_issues:
                issues.extend(ang_issues)
                current_issue_id += len(ang_issues)
                ang_count += len(ang_issues)
        summary[CheckID.CHK_ANGLE]["count"] = ang_count
        if ang_count > 0:
            summary[CheckID.CHK_ANGLE]["status"] = "WARNING"

    # 8. Snap Issue
    if config.check_snap:
        notify("Running Snap Issue check...")
        snap_issues = check_snap_issues(
            features, layer_name, source, config.snap_tolerance_m, 1e-5, current_issue_id
        )
        issues.extend(snap_issues)
        current_issue_id += len(snap_issues)
        summary[CheckID.CHK_SNAP]["count"] = len(snap_issues)
        if snap_issues:
            summary[CheckID.CHK_SNAP]["status"] = "ERROR"

    # 9. Redundant Vertex
    if config.check_redundant:
        notify("Running Redundant Vertex check...")
        red_count = 0
        for fid, shape in features.items():
            red_issues = check_redundant_vertices(
                fid, shape, layer_name, source, config.redundant_vertex_deg, current_issue_id
            )
            if red_issues:
                issues.extend(red_issues)
                current_issue_id += len(red_issues)
                red_count += len(red_issues)
        summary[CheckID.CHK_REDUNDANT]["count"] = red_count
        if red_count > 0:
            summary[CheckID.CHK_REDUNDANT]["status"] = "WARNING"

    # 10. Missing Junction
    if config.check_junction:
        notify("Running Missing Junction check...")
        junc_issues = check_missing_junctions(
            features, layer_name, source, config.junction_tolerance_m, current_issue_id, spatial_index
        )
        issues.extend(junc_issues)
        current_issue_id += len(junc_issues)
        summary[CheckID.CHK_JUNCTION]["count"] = len(junc_issues)
        if junc_issues:
            summary[CheckID.CHK_JUNCTION]["status"] = "ERROR"

    notify("Geometry QC completed.")
    return issues, summary

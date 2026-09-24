# -*- coding: utf-8 -*-
"""
Point QC Module.
Implements the dedicated Point QC checks:
PT01 — Invalid Point
PT02 — Duplicate Point
PT03 — Near-Duplicate Point
PT04 — Point Distribution Difference (Reference-driven)
PT05 — Cross-Layer Coincident Points

Uses VertexGridIndex for fast spatial proximity detection without O(N^2) loops.
Works with ArcPy PointGeometry objects or pure-python coordinate tuples (X, Y).
"""

import math
from typing import Dict, List, Tuple, Any, Optional, Set
from ..models.qc_issue import QCIssue, CheckID, Severity
from .vertex_index import VertexGridIndex


class PointQCConfig:
    """Configurable thresholds and toggles for Point QC."""
    def __init__(
        self,
        check_invalid: bool = True,
        check_duplicate: bool = True,
        check_near_duplicate: bool = True,
        check_distribution: bool = True,
        check_cross_layer: bool = False,
        duplicate_tolerance_m: float = 1e-4,       # 0.1 mm
        near_duplicate_tolerance_m: float = 0.01,  # 1 cm
        reference_feature_count: Optional[int] = None,
        reference_extent: Optional[Tuple[float, float, float, float]] = None,
        other_point_layers: Optional[Dict[str, Dict[Any, Any]]] = None,
    ):
        self.check_invalid = check_invalid
        self.check_duplicate = check_duplicate
        self.check_near_duplicate = check_near_duplicate
        self.check_distribution = check_distribution
        self.check_cross_layer = check_cross_layer

        self.duplicate_tolerance_m = duplicate_tolerance_m
        self.near_duplicate_tolerance_m = near_duplicate_tolerance_m
        self.reference_feature_count = reference_feature_count
        self.reference_extent = reference_extent
        self.other_point_layers = other_point_layers or {}


def extract_point_coord(shape: Any) -> Optional[Tuple[float, float]]:
    """Extracts (x, y) float tuple from an ArcPy Point/PointGeometry or sequence."""
    if shape is None:
        return None

    # ArcPy PointGeometry / Point
    if hasattr(shape, "firstPoint") and shape.firstPoint is not None:
        fp = shape.firstPoint
        if not math.isnan(fp.X) and not math.isnan(fp.Y):
            return (float(fp.X), float(fp.Y))
    elif hasattr(shape, "X") and hasattr(shape, "Y"):
        if not math.isnan(shape.X) and not math.isnan(shape.Y):
            return (float(shape.X), float(shape.Y))

    # Tuple / list (x, y)
    if isinstance(shape, (list, tuple)) and len(shape) >= 2:
        try:
            x, y = float(shape[0]), float(shape[1])
            if not math.isnan(x) and not math.isnan(y):
                return (x, y)
        except (ValueError, TypeError):
            return None

    return None


# ==============================================================================
# PT01 — Invalid Point
# ==============================================================================

def check_invalid_point(
    fid: Any,
    shape: Any,
    layer_name: str,
    source: str,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    if shape is None:
        issues.append(
            QCIssue(
                issue_id=current_id,
                check_id=CheckID.CHK_PT_INVALID,
                issue_type="NULL_POINT_GEOMETRY",
                severity=Severity.ERROR,
                layer_name=layer_name,
                geometry_type="Point",
                source=source,
                object_id=fid,
                details="Point feature geometry is null or missing.",
            )
        )
        return issues

    # ArcPy Point empty check
    if hasattr(shape, "partCount") and shape.partCount == 0:
        issues.append(
            QCIssue(
                issue_id=current_id,
                check_id=CheckID.CHK_PT_INVALID,
                issue_type="EMPTY_POINT_GEOMETRY",
                severity=Severity.ERROR,
                layer_name=layer_name,
                geometry_type="Point",
                source=source,
                object_id=fid,
                details="Point geometry is empty with 0 parts.",
            )
        )
        return issues

    # Extract coordinates and test for NaN / Inf
    coord = extract_point_coord(shape)
    if coord is None:
        # Check if coordinates contain NaN / Inf
        has_invalid_num = False
        if hasattr(shape, "firstPoint") and shape.firstPoint is not None:
            fp = shape.firstPoint
            if math.isnan(fp.X) or math.isnan(fp.Y) or math.isinf(fp.X) or math.isinf(fp.Y):
                has_invalid_num = True

        issues.append(
            QCIssue(
                issue_id=current_id,
                check_id=CheckID.CHK_PT_INVALID,
                issue_type="NAN_COORDINATE" if has_invalid_num else "INVALID_POINT_COORDINATES",
                severity=Severity.ERROR,
                layer_name=layer_name,
                geometry_type="Point",
                source=source,
                object_id=fid,
                location=(0.0, 0.0),
                details="Point contains invalid, NaN, or Infinite coordinates.",
            )
        )
        return issues

    # Check Z/M validity if present
    if hasattr(shape, "firstPoint") and shape.firstPoint is not None:
        fp = shape.firstPoint
        if hasattr(fp, "Z") and fp.Z is not None and (math.isnan(fp.Z) or math.isinf(fp.Z)):
            issues.append(
                QCIssue(
                    issue_id=current_id,
                    check_id=CheckID.CHK_PT_INVALID,
                    issue_type="INVALID_Z_COORDINATE",
                    severity=Severity.ERROR,
                    layer_name=layer_name,
                    geometry_type="Point",
                    source=source,
                    object_id=fid,
                    location=coord,
                    details="Point contains NaN or Infinite Z elevation coordinate.",
                )
            )

    return issues


# ==============================================================================
# PT02 & PT03 — Duplicate & Near-Duplicate Points
# ==============================================================================

def check_point_duplicates(
    point_map: Dict[Any, Tuple[float, float]],
    layer_name: str,
    source: str,
    duplicate_tolerance_m: float = 1e-4,
    near_duplicate_tolerance_m: float = 0.01,
    check_duplicates: bool = True,
    check_near_duplicates: bool = True,
    issue_id_start: int = 1,
) -> Tuple[List[QCIssue], List[QCIssue]]:
    """
    Detects exact coincident duplicate points and near-duplicate points.
    Returns (duplicate_issues, near_duplicate_issues).
    """
    dup_issues: List[QCIssue] = []
    near_dup_issues: List[QCIssue] = []
    current_id = issue_id_start

    fids = list(point_map.keys())
    if len(fids) < 2:
        return dup_issues, near_dup_issues

    max_search_radius = max(near_duplicate_tolerance_m, duplicate_tolerance_m)
    vertex_grid = VertexGridIndex(tolerance=max_search_radius)

    for fid, coord in point_map.items():
        vertex_grid.insert(coord[0], coord[1], fid)

    reported_pairs = set()

    for rec in vertex_grid.records:
        nearby = vertex_grid.query_radius(rec.x, rec.y, max_search_radius)
        for other, dist in nearby:
            if other.feature_id == rec.feature_id:
                continue

            pair = (min(rec.feature_id, other.feature_id), max(rec.feature_id, other.feature_id))
            if pair in reported_pairs:
                continue

            # Exact duplicate (dist <= duplicate_tolerance)
            if check_duplicates and dist <= duplicate_tolerance_m:
                reported_pairs.add(pair)
                dup_issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_PT_DUPLICATE,
                        issue_type="POINT_DUPLICATE",
                        severity=Severity.ERROR,
                        layer_name=layer_name,
                        geometry_type="Point",
                        source=source,
                        object_id=rec.feature_id,
                        related_object_id=other.feature_id,
                        measurement=round(dist, 5),
                        threshold=duplicate_tolerance_m,
                        unit="m",
                        location=(rec.x, rec.y),
                        details=(
                            f"Duplicate Point: Feature {rec.feature_id} is coincident with feature {other.feature_id} "
                            f"(distance {dist * 1000.0:.2f} mm <= {duplicate_tolerance_m * 1000.0:.1f} mm)."
                        ),
                    )
                )
                current_id += 1

            # Near duplicate (duplicate_tolerance < dist <= near_duplicate_tolerance)
            elif check_near_duplicates and (duplicate_tolerance_m < dist <= near_duplicate_tolerance_m):
                reported_pairs.add(pair)
                near_dup_issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_PT_NEAR_DUPLICATE,
                        issue_type="POINT_NEAR_DUPLICATE",
                        severity=Severity.WARNING,
                        layer_name=layer_name,
                        geometry_type="Point",
                        source=source,
                        object_id=rec.feature_id,
                        related_object_id=other.feature_id,
                        measurement=round(dist, 4),
                        threshold=near_duplicate_tolerance_m,
                        unit="m",
                        location=(rec.x, rec.y),
                        details=(
                            f"Near-Duplicate Point: Feature {rec.feature_id} is extremely close to feature {other.feature_id} "
                            f"({dist * 100:.2f} cm <= {near_duplicate_tolerance_m * 100:.1f} cm threshold)."
                        ),
                    )
                )
                current_id += 1

    return dup_issues, near_dup_issues


# ==============================================================================
# PT04 — Point Distribution Difference
# ==============================================================================

def check_point_distribution(
    point_map: Dict[Any, Tuple[float, float]],
    layer_name: str,
    source: str,
    reference_feature_count: Optional[int] = None,
    reference_extent: Optional[Tuple[float, float, float, float]] = None,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    actual_count = len(point_map)

    # Count difference check
    if reference_feature_count is not None and reference_feature_count != actual_count:
        delta = actual_count - reference_feature_count
        issues.append(
            QCIssue(
                issue_id=current_id,
                check_id=CheckID.CHK_PT_DISTRIBUTION,
                issue_type="POINT_COUNT_DIFFERENCE",
                severity=Severity.WARNING,
                layer_name=layer_name,
                geometry_type="Point",
                source=source,
                property_name="FeatureCount",
                expected_value=str(reference_feature_count),
                actual_value=str(actual_count),
                measurement=float(delta),
                unit="features",
                details=(
                    f"Point feature count difference in '{layer_name}': "
                    f"Reference={reference_feature_count}, Received={actual_count} (Delta: {delta:+d})."
                ),
            )
        )
        current_id += 1

    return issues


# ==============================================================================
# PT05 — Cross-Layer Coincident Points
# ==============================================================================

def check_cross_layer_coincident_points(
    current_layer_name: str,
    current_point_map: Dict[Any, Tuple[float, float]],
    other_point_layers: Dict[str, Dict[Any, Tuple[float, float]]],
    tolerance_m: float = 1e-4,
    source: str = "RECEIVED",
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    if not other_point_layers or not current_point_map:
        return issues

    vertex_grid = VertexGridIndex(tolerance=tolerance_m)
    rec_to_layer: Dict[int, str] = {}
    for other_layer, o_map in other_point_layers.items():
        if other_layer == current_layer_name:
            continue
        for o_fid, o_coord in o_map.items():
            rec = vertex_grid.insert(o_coord[0], o_coord[1], o_fid)
            rec_to_layer[id(rec)] = other_layer

    reported_cross_pairs = set()

    for cur_fid, cur_coord in current_point_map.items():
        near = vertex_grid.query_radius(cur_coord[0], cur_coord[1], tolerance_m)
        for other_rec, dist in near:
            other_layer = rec_to_layer.get(id(other_rec), "OTHER")
            pair_key = (current_layer_name, cur_fid, other_layer, other_rec.feature_id)
            if pair_key not in reported_cross_pairs:
                reported_cross_pairs.add(pair_key)
                issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_PT_CROSS_LAYER,
                        issue_type="CROSS_LAYER_COINCIDENT_POINT",
                        severity=Severity.INFO,
                        layer_name=current_layer_name,
                        geometry_type="Point",
                        source=source,
                        object_id=cur_fid,
                        related_object_id=f"{other_layer}:{other_rec.feature_id}",
                        measurement=round(dist, 5),
                        threshold=tolerance_m,
                        unit="m",
                        location=cur_coord,
                        details=(
                            f"Cross-layer coincident point: Point {cur_fid} on layer '{current_layer_name}' "
                            f"shares location with feature {other_rec.feature_id} on layer '{other_layer}'."
                        ),
                    )
                )
                current_id += 1

    return issues


# ==============================================================================
# Comprehensive Point QC Runner
# ==============================================================================

def run_point_qc(
    features: Dict[Any, Any],  # fid -> shape
    layer_name: str = "PointQC",
    source: str = "INPUT",
    config: Optional[PointQCConfig] = None,
    progress_callback: Optional[Any] = None,
    issue_id_start: int = 1,
) -> Tuple[List[QCIssue], Dict[str, Dict[str, Any]]]:
    """
    Executes the suite of Point QC checks (PT01-PT05).
    Returns (issues_list, summary_dict).
    """
    if config is None:
        config = PointQCConfig()

    issues: List[QCIssue] = []
    current_issue_id = issue_id_start

    summary: Dict[str, Dict[str, Any]] = {
        CheckID.CHK_PT_INVALID: {"name": "PT01 — Invalid Point", "count": 0, "status": "PASS"},
        CheckID.CHK_PT_DUPLICATE: {"name": "PT02 — Duplicate Point", "count": 0, "status": "PASS"},
        CheckID.CHK_PT_NEAR_DUPLICATE: {"name": "PT03 — Near-Duplicate Point", "count": 0, "status": "PASS"},
        CheckID.CHK_PT_DISTRIBUTION: {"name": "PT04 — Point Distribution", "count": 0, "status": "PASS"},
        CheckID.CHK_PT_CROSS_LAYER: {"name": "PT05 — Cross-Layer Coincidence", "count": 0, "status": "PASS"},
    }

    def notify(msg: str):
        if progress_callback:
            progress_callback(msg)

    # 1. Extract valid coordinates and run PT01
    point_map: Dict[Any, Tuple[float, float]] = {}

    if config.check_invalid:
        notify("Running PT01 — Invalid Point check...")
        inv_cnt = 0
        for fid, shape in features.items():
            errs = check_invalid_point(fid, shape, layer_name, source, current_issue_id)
            if errs:
                issues.extend(errs)
                current_issue_id += len(errs)
                inv_cnt += len(errs)
            else:
                c = extract_point_coord(shape)
                if c:
                    point_map[fid] = c
        summary[CheckID.CHK_PT_INVALID]["count"] = inv_cnt
        if inv_cnt > 0:
            summary[CheckID.CHK_PT_INVALID]["status"] = "ERROR"
    else:
        for fid, shape in features.items():
            c = extract_point_coord(shape)
            if c:
                point_map[fid] = c

    # 2. PT02 & PT03 — Duplicate and Near-Duplicate Points
    if config.check_duplicate or config.check_near_duplicate:
        notify("Running PT02 & PT03 — Point Duplicate checks...")
        dup_issues, near_issues = check_point_duplicates(
            point_map,
            layer_name,
            source,
            config.duplicate_tolerance_m,
            config.near_duplicate_tolerance_m,
            config.check_duplicate,
            config.check_near_duplicate,
            current_issue_id,
        )
        if dup_issues:
            issues.extend(dup_issues)
            current_issue_id += len(dup_issues)
            summary[CheckID.CHK_PT_DUPLICATE]["count"] = len(dup_issues)
            summary[CheckID.CHK_PT_DUPLICATE]["status"] = "ERROR"

        if near_issues:
            issues.extend(near_issues)
            current_issue_id += len(near_issues)
            summary[CheckID.CHK_PT_NEAR_DUPLICATE]["count"] = len(near_issues)
            summary[CheckID.CHK_PT_NEAR_DUPLICATE]["status"] = "WARNING"

    # 3. PT04 — Point Distribution Difference
    if config.check_distribution:
        dist_issues = check_point_distribution(
            point_map,
            layer_name,
            source,
            config.reference_feature_count,
            config.reference_extent,
            current_issue_id,
        )
        if dist_issues:
            issues.extend(dist_issues)
            current_issue_id += len(dist_issues)
            summary[CheckID.CHK_PT_DISTRIBUTION]["count"] = len(dist_issues)
            summary[CheckID.CHK_PT_DISTRIBUTION]["status"] = "WARNING"

    # 4. PT05 — Cross-Layer Coincidence
    if config.check_cross_layer and config.other_point_layers:
        other_extracted = {}
        for o_layer, o_features in config.other_point_layers.items():
            other_extracted[o_layer] = {
                f: extract_point_coord(s) for f, s in o_features.items() if extract_point_coord(s)
            }
        cross_issues = check_cross_layer_coincident_points(
            layer_name,
            point_map,
            other_extracted,
            config.duplicate_tolerance_m,
            source,
            current_issue_id,
        )
        if cross_issues:
            issues.extend(cross_issues)
            current_issue_id += len(cross_issues)
            summary[CheckID.CHK_PT_CROSS_LAYER]["count"] = len(cross_issues)
            summary[CheckID.CHK_PT_CROSS_LAYER]["status"] = "INFO"

    notify("Point QC completed.")
    return issues, summary

# -*- coding: utf-8 -*-
"""
Line / Polyline QC Module.
Implements the complete suite of 12 Line / Polyline Geometry QC checks:
L01 — Invalid Line Geometry
L02 — Duplicate Line
L03 — Overlapping Lines
L04 — Self-Intersecting Line
L05 — Dangle
L06 — Disconnected Line
L07 — Short Line / Short Segment
L08 — Sharp Angle / Cutback
L09 — Redundant Vertex
L10 — Snap / Near-Coincident Issue
L11 — Missing Junction
L12 — Open / Closed Line Behavior

Uses SpatialGridIndex and VertexGridIndex for high-performance spatial queries (O(N log N)).
Works seamlessly on both ArcPy Polyline objects and pure-python coordinate structures.
"""

import math
from typing import Dict, List, Tuple, Any, Optional, Set
from ..models.qc_issue import QCIssue, CheckID, Severity
from .spatial_index import SpatialGridIndex
from .vertex_index import VertexGridIndex


# ==============================================================================
# Configuration
# ==============================================================================

class LineQCConfig:
    """Configurable thresholds and toggles for Line / Polyline QC."""
    def __init__(
        self,
        check_invalid: bool = True,
        check_duplicate: bool = True,
        check_overlap: bool = True,
        check_self_intersect: bool = True,
        check_dangle: bool = True,
        check_disconnected: bool = True,
        check_short_seg: bool = True,
        check_angle: bool = True,
        check_redundant: bool = True,
        check_snap: bool = True,
        check_junction: bool = True,
        check_closure: bool = True,
        short_seg_tolerance_m: float = 0.10,      # 10 cm
        short_feature_tolerance_m: float = 0.10,  # 10 cm
        angle_tolerance_deg: float = 5.0,         # 5°
        redundant_vertex_deg: float = 179.9,      # 179.9°
        snap_tolerance_m: float = 0.01,           # 1 cm
        junction_tolerance_m: float = 0.01,       # 1 cm
        dangle_tolerance_m: float = 0.50,         # 50 cm search radius for undershoots
        overlap_tolerance_m: float = 0.01,        # 1 cm linear overlap threshold
        duplicate_tolerance_m: float = 0.001,     # 1 mm vertex coincidence
        expected_closed_percentage: Optional[float] = None,
        enforce_closure_match: bool = False,
    ):
        self.check_invalid = check_invalid
        self.check_duplicate = check_duplicate
        self.check_overlap = check_overlap
        self.check_self_intersect = check_self_intersect
        self.check_dangle = check_dangle
        self.check_disconnected = check_disconnected
        self.check_short_seg = check_short_seg
        self.check_angle = check_angle
        self.check_redundant = check_redundant
        self.check_snap = check_snap
        self.check_junction = check_junction
        self.check_closure = check_closure

        self.short_seg_tolerance_m = short_seg_tolerance_m
        self.short_feature_tolerance_m = short_feature_tolerance_m
        self.angle_tolerance_deg = angle_tolerance_deg
        self.redundant_vertex_deg = redundant_vertex_deg
        self.snap_tolerance_m = snap_tolerance_m
        self.junction_tolerance_m = junction_tolerance_m
        self.dangle_tolerance_m = dangle_tolerance_m
        self.overlap_tolerance_m = overlap_tolerance_m
        self.duplicate_tolerance_m = duplicate_tolerance_m
        self.expected_closed_percentage = expected_closed_percentage
        self.enforce_closure_match = enforce_closure_match


# ==============================================================================
# Geometric Utilities & Coordinate Extraction
# ==============================================================================

def extract_line_parts(shape: Any) -> List[List[Tuple[float, float]]]:
    """
    Extracts parts as lists of (x, y) float tuples from ArcPy Polyline or sequence.
    """
    if shape is None:
        return []

    # Check ArcPy geometry
    if hasattr(shape, "partCount"):
        parts = []
        for i in range(shape.partCount):
            part = shape.getPart(i)
            if not part:
                continue
            pt_list = []
            for pt in part:
                if pt is not None and not math.isnan(pt.X) and not math.isnan(pt.Y):
                    pt_list.append((float(pt.X), float(pt.Y)))
            if pt_list:
                parts.append(pt_list)
        return parts

    # Check list of lists (multi-part)
    if isinstance(shape, (list, tuple)):
        if len(shape) == 0:
            return []
        if isinstance(shape[0], (list, tuple)) and len(shape[0]) > 0 and isinstance(shape[0][0], (list, tuple)):
            # Nested list of parts
            parts = []
            for part in shape:
                pts = [(float(p[0]), float(p[1])) for p in part if len(p) >= 2]
                if pts:
                    parts.append(pts)
            return parts
        else:
            # Single part list of (x, y)
            pts = [(float(p[0]), float(p[1])) for p in shape if len(p) >= 2]
            return [pts] if pts else []

    return []


def get_line_extent(parts: List[List[Tuple[float, float]]]) -> Optional[Tuple[float, float, float, float]]:
    """Calculates (minx, miny, maxx, maxy) extent from coordinates."""
    if not parts or not parts[0]:
        return None
    minx = min(pt[0] for part in parts for pt in part)
    miny = min(pt[1] for part in parts for pt in part)
    maxx = max(pt[0] for part in parts for pt in part)
    maxy = max(pt[1] for part in parts for pt in part)
    return (minx, miny, maxx, maxy)


def point_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def polyline_length(parts: List[List[Tuple[float, float]]]) -> float:
    total = 0.0
    for part in parts:
        for i in range(len(part) - 1):
            total += point_distance(part[i], part[i + 1])
    return total


def point_to_segment_dist(
    p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]
) -> Tuple[float, Tuple[float, float], float]:
    """
    Computes distance from point p to line segment ab.
    Returns (distance, nearest_point_on_segment, projection_t).
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        return point_distance(p, a), a, 0.0

    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2
    t = max(0.0, min(1.0, t))
    proj = (a[0] + t * dx, a[1] + t * dy)
    dist = point_distance(p, proj)
    return dist, proj, t


def segments_intersection(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    p4: Tuple[float, float],
) -> Optional[Tuple[float, float]]:
    """
    Computes intersection point of segment p1-p2 and p3-p4 if they cross internally.
    Returns (x, y) or None if collinear / disjoint / endpoint-touching.
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
    if abs(denom) < 1e-12:
        return None  # Parallel or collinear

    ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
    ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom

    eps = 1e-6
    if eps < ua < (1.0 - eps) and eps < ub < (1.0 - eps):
        ix = x1 + ua * (x2 - x1)
        iy = y1 + ua * (y2 - y1)
        return (ix, iy)

    return None


def calculate_turn_angle(
    p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float]
) -> float:
    """Calculates interior deflection angle at vertex p2 in degrees (0° to 180°)."""
    v1x = p1[0] - p2[0]
    v1y = p1[1] - p2[1]
    v2x = p3[0] - p2[0]
    v2y = p3[1] - p2[1]

    len1 = math.hypot(v1x, v1y)
    len2 = math.hypot(v2x, v2y)
    if len1 == 0.0 or len2 == 0.0:
        return 0.0

    cos_ang = (v1x * v2x + v1y * v2y) / (len1 * len2)
    cos_ang = max(-1.0, min(1.0, cos_ang))
    return math.degrees(math.acos(cos_ang))


# ==============================================================================
# L01 — Invalid Line Geometry
# ==============================================================================

def check_invalid_line(
    fid: Any,
    shape: Any,
    parts: List[List[Tuple[float, float]]],
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
                check_id=CheckID.CHK_LINE_INVALID,
                issue_type="NULL_LINE_GEOMETRY",
                severity=Severity.ERROR,
                layer_name=layer_name,
                geometry_type="Polyline",
                source=source,
                object_id=fid,
                details="Line feature geometry is null or missing.",
            )
        )
        return issues

    if not parts or sum(len(p) for p in parts) == 0:
        issues.append(
            QCIssue(
                issue_id=current_id,
                check_id=CheckID.CHK_LINE_INVALID,
                issue_type="EMPTY_LINE_GEOMETRY",
                severity=Severity.ERROR,
                layer_name=layer_name,
                geometry_type="Polyline",
                source=source,
                object_id=fid,
                details="Line feature is empty with 0 parts or 0 vertices.",
            )
        )
        return issues

    # Coordinates check for NaN / Inf
    for p_idx, part in enumerate(parts):
        for v_idx, pt in enumerate(part):
            if math.isnan(pt[0]) or math.isnan(pt[1]) or math.isinf(pt[0]) or math.isinf(pt[1]):
                issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_LINE_INVALID,
                        issue_type="NAN_COORDINATE",
                        severity=Severity.ERROR,
                        layer_name=layer_name,
                        geometry_type="Polyline",
                        source=source,
                        object_id=fid,
                        location=(0.0, 0.0),
                        details=f"Line contains NaN or Infinite coordinate at part {p_idx} vertex {v_idx}.",
                    )
                )
                current_id += 1
                break

    # Check for invalid parts with fewer than 2 distinct points
    for p_idx, part in enumerate(parts):
        if len(part) < 2:
            issues.append(
                QCIssue(
                    issue_id=current_id,
                    check_id=CheckID.CHK_LINE_INVALID,
                    issue_type="INVALID_SEGMENT_COUNT",
                    severity=Severity.ERROR,
                    layer_name=layer_name,
                    geometry_type="Polyline",
                    source=source,
                    object_id=fid,
                    location=part[0] if part else (0.0, 0.0),
                    details=f"Line part {p_idx} has fewer than 2 vertices ({len(part)} vertex).",
                )
            )
            current_id += 1

    return issues


# ==============================================================================
# L02 — Duplicate Line
# ==============================================================================

def check_duplicate_lines(
    line_parts_map: Dict[Any, List[List[Tuple[float, float]]]],
    layer_name: str,
    source: str,
    tolerance_m: float = 0.001,
    spatial_index: Optional[SpatialGridIndex] = None,
    issue_id_start: int = 1,
) -> Tuple[List[QCIssue], Set[Tuple[Any, Any]]]:
    """
    Detects 100% identical coincident polylines (forward or reversed).
    Returns (issues, duplicate_pairs_set).
    """
    issues: List[QCIssue] = []
    duplicate_pairs: Set[Tuple[Any, Any]] = set()
    current_id = issue_id_start

    fids = list(line_parts_map.keys())
    if len(fids) < 2:
        return issues, duplicate_pairs

    pairs_to_test = spatial_index.get_candidate_pairs() if spatial_index else {
        (fids[i], fids[j]) for i in range(len(fids)) for j in range(i + 1, len(fids))
    }

    for fid1, fid2 in pairs_to_test:
        parts1 = line_parts_map.get(fid1)
        parts2 = line_parts_map.get(fid2)
        if not parts1 or not parts2 or len(parts1) != len(parts2):
            continue

        # Single-part polyline fast comparison
        if len(parts1) == 1 and len(parts2) == 1:
            pts1 = parts1[0]
            pts2 = parts2[0]
            if len(pts1) != len(pts2) or len(pts1) < 2:
                continue

            # Forward match
            forward_match = all(point_distance(pts1[k], pts2[k]) <= tolerance_m for k in range(len(pts1)))
            # Reversed match
            rev_match = False
            if not forward_match:
                n = len(pts1)
                rev_match = all(point_distance(pts1[k], pts2[n - 1 - k]) <= tolerance_m for k in range(n))

            if forward_match or rev_match:
                pair = (min(fid1, fid2), max(fid1, fid2))
                if pair not in duplicate_pairs:
                    duplicate_pairs.add(pair)
                    mid_pt = pts1[len(pts1) // 2]
                    issues.append(
                        QCIssue(
                            issue_id=current_id,
                            check_id=CheckID.CHK_LINE_DUPLICATE,
                            issue_type="LINE_DUPLICATE",
                            severity=Severity.ERROR,
                            layer_name=layer_name,
                            geometry_type="Polyline",
                            source=source,
                            object_id=fid1,
                            related_object_id=fid2,
                            measurement=1.0,
                            threshold=1.0,
                            unit="ratio",
                            location=mid_pt,
                            details=(
                                f"Line feature {fid1} is identical (100% duplicate) to line {fid2} "
                                f"({'forward' if forward_match else 'reversed'})."
                            ),
                        )
                    )
                    current_id += 1

    return issues, duplicate_pairs


# ==============================================================================
# L03 — Overlapping Lines
# ==============================================================================

def check_line_overlaps(
    line_parts_map: Dict[Any, List[List[Tuple[float, float]]]],
    layer_name: str,
    source: str,
    tolerance_m: float = 0.01,
    excluded_duplicate_pairs: Optional[Set[Tuple[Any, Any]]] = None,
    spatial_index: Optional[SpatialGridIndex] = None,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    """
    Detects partial linear overlaps between distinct lines.
    Excludes exact duplicates reported in L02.
    """
    issues: List[QCIssue] = []
    current_id = issue_id_start
    excluded = excluded_duplicate_pairs or set()

    fids = list(line_parts_map.keys())
    if len(fids) < 2:
        return issues

    pairs_to_test = spatial_index.get_candidate_pairs() if spatial_index else {
        (fids[i], fids[j]) for i in range(len(fids)) for j in range(i + 1, len(fids))
    }

    reported_pairs = set()

    for fid1, fid2 in pairs_to_test:
        pair = (min(fid1, fid2), max(fid1, fid2))
        if pair in excluded or pair in reported_pairs:
            continue

        parts1 = line_parts_map.get(fid1)
        parts2 = line_parts_map.get(fid2)
        if not parts1 or not parts2:
            continue

        # Sample segments and check for shared collinear sections
        overlap_len = 0.0
        overlap_mid = None

        for p1 in parts1:
            for i in range(len(p1) - 1):
                s1_a, s1_b = p1[i], p1[i + 1]
                seg1_len = point_distance(s1_a, s1_b)
                if seg1_len == 0.0:
                    continue

                for p2 in parts2:
                    for j in range(len(p2) - 1):
                        s2_a, s2_b = p2[j], p2[j + 1]
                        # Test if endpoints of s1 are close to segment s2 and collinear
                        d_a, proj_a, t_a = point_to_segment_dist(s1_a, s2_a, s2_b)
                        d_b, proj_b, t_b = point_to_segment_dist(s1_b, s2_a, s2_b)

                        if d_a <= tolerance_m and d_b <= tolerance_m:
                            # Both endpoints of s1 lie on s2!
                            overlap_len += seg1_len
                            if overlap_mid is None:
                                overlap_mid = ((s1_a[0] + s1_b[0]) / 2.0, (s1_a[1] + s1_b[1]) / 2.0)
                        elif (d_a <= tolerance_m or d_b <= tolerance_m) and abs(t_a - t_b) > 0.05:
                            # Partial segment overlap
                            overlap_dist = abs(t_a - t_b) * point_distance(s2_a, s2_b)
                            if overlap_dist >= tolerance_m:
                                overlap_len += overlap_dist
                                if overlap_mid is None:
                                    overlap_mid = proj_a if d_a <= tolerance_m else proj_b

        if overlap_len >= tolerance_m:
            reported_pairs.add(pair)
            issues.append(
                QCIssue(
                    issue_id=current_id,
                    check_id=CheckID.CHK_LINE_OVERLAP,
                    issue_type="LINE_OVERLAP",
                    severity=Severity.ERROR,
                    layer_name=layer_name,
                    geometry_type="Polyline",
                    source=source,
                    object_id=fid1,
                    related_object_id=fid2,
                    measurement=round(overlap_len, 4),
                    threshold=tolerance_m,
                    unit="m",
                    location=overlap_mid,
                    details=(
                        f"Partial line overlap of {overlap_len:.3f} m detected between line "
                        f"{fid1} and line {fid2}."
                    ),
                )
            )
            current_id += 1

    return issues


# ==============================================================================
# L04 — Self-Intersecting Line
# ==============================================================================

def check_line_self_intersection(
    fid: Any,
    parts: List[List[Tuple[float, float]]],
    layer_name: str,
    source: str,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    """Detects invalid self-intersection loops within a polyline feature."""
    issues: List[QCIssue] = []
    current_id = issue_id_start

    for p_idx, part in enumerate(parts):
        n = len(part)
        if n < 4:
            continue

        for i in range(n - 1):
            p1 = part[i]
            p2 = part[i + 1]
            for j in range(i + 2, n - 1):
                # If first and last segment of a closed loop, skip only if endpoints touch
                if i == 0 and j == n - 2 and point_distance(part[0], part[-1]) <= 1e-4:
                    continue
                p3 = part[j]
                p4 = part[j + 1]

                ix = segments_intersection(p1, p2, p3, p4)
                if ix:
                    issues.append(
                        QCIssue(
                            issue_id=current_id,
                            check_id=CheckID.CHK_LINE_SELF_INTERSECT,
                            issue_type="LINE_SELF_INTERSECTION",
                            severity=Severity.ERROR,
                            layer_name=layer_name,
                            geometry_type="Polyline",
                            source=source,
                            object_id=fid,
                            location=ix,
                            details=(
                                f"Line {fid} self-intersects at ({ix[0]:.3f}, {ix[1]:.3f}) "
                                f"between segment {i} and segment {j} (Part {p_idx})."
                            ),
                        )
                    )
                    current_id += 1

    return issues


# ==============================================================================
# L05 — Dangle Check
# ==============================================================================

def check_line_dangles(
    line_parts_map: Dict[Any, List[List[Tuple[float, float]]]],
    layer_name: str,
    source: str,
    dangle_tolerance_m: float = 0.50,
    snap_tolerance_m: float = 0.01,
    spatial_index: Optional[SpatialGridIndex] = None,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    """
    Detects line endpoints that terminate as undershoots/overshoots:
    An endpoint that falls within dangle_tolerance of another feature without snapping (dist > snap_tol).
    Does NOT flag natural isolated dead-ends that don't approach other lines.
    """
    issues: List[QCIssue] = []
    current_id = issue_id_start

    if len(line_parts_map) < 2:
        return issues

    for fid, parts in line_parts_map.items():
        if not parts:
            continue
        for p_idx, part in enumerate(parts):
            if len(part) < 2:
                continue

            endpoints = [(part[0], 0), (part[-1], len(part) - 1)]
            for ep, ep_idx in endpoints:
                # Query candidate neighbor features around endpoint
                query_bbox = (
                    ep[0] - dangle_tolerance_m,
                    ep[1] - dangle_tolerance_m,
                    ep[0] + dangle_tolerance_m,
                    ep[1] + dangle_tolerance_m,
                )
                candidates = spatial_index.query(query_bbox) if spatial_index else set(line_parts_map.keys())

                closest_dist = float("inf")
                closest_fid = None

                for other_fid in candidates:
                    if other_fid == fid:
                        continue
                    other_parts = line_parts_map.get(other_fid, [])
                    for op in other_parts:
                        for s_idx in range(len(op) - 1):
                            dist, _, _ = point_to_segment_dist(ep, op[s_idx], op[s_idx + 1])
                            if dist < closest_dist:
                                closest_dist = dist
                                closest_fid = other_fid

                # If endpoint is within dangle threshold of another line but not connected (undershoot)
                if snap_tolerance_m < closest_dist <= dangle_tolerance_m:
                    issues.append(
                        QCIssue(
                            issue_id=current_id,
                            check_id=CheckID.CHK_LINE_DANGLE,
                            issue_type="LINE_DANGLE",
                            severity=Severity.WARNING,
                            layer_name=layer_name,
                            geometry_type="Polyline",
                            source=source,
                            object_id=fid,
                            related_object_id=closest_fid,
                            measurement=round(closest_dist, 4),
                            threshold=dangle_tolerance_m,
                            unit="m",
                            location=ep,
                            details=(
                                f"Dangle/undershoot: Endpoint of line {fid} terminates {closest_dist:.3f} m "
                                f"from line {closest_fid} without connecting (< {dangle_tolerance_m:.2f} m)."
                            ),
                        )
                    )
                    current_id += 1

    return issues


# ==============================================================================
# L06 — Disconnected Line
# ==============================================================================

def check_line_disconnected(
    line_parts_map: Dict[Any, List[List[Tuple[float, float]]]],
    layer_name: str,
    source: str,
    connection_tolerance_m: float = 0.05,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    """
    Detects line features that are completely isolated when the rest of the layer forms connected networks.
    Carefully designed to avoid false positives if the dataset is inherently multi-network.
    """
    issues: List[QCIssue] = []
    current_id = issue_id_start

    n_feats = len(line_parts_map)
    if n_feats < 4:
        return issues  # Do not make network assumptions on tiny datasets

    # Build adjacency graph of endpoints
    vertex_grid = VertexGridIndex(tolerance=connection_tolerance_m)
    for fid, parts in line_parts_map.items():
        for part in parts:
            if len(part) >= 2:
                vertex_grid.insert(part[0][0], part[0][1], fid)
                vertex_grid.insert(part[-1][0], part[-1][1], fid)

    adjacency: Dict[Any, Set[Any]] = {fid: set() for fid in line_parts_map.keys()}
    for fid, parts in line_parts_map.items():
        for part in parts:
            if len(part) >= 2:
                for ep in (part[0], part[-1]):
                    near = vertex_grid.query_radius(ep[0], ep[1], connection_tolerance_m)
                    for rec, d in near:
                        if rec.feature_id != fid:
                            adjacency[fid].add(rec.feature_id)
                            adjacency[rec.feature_id].add(fid)

    # Find connected components
    visited = set()
    components = []
    for fid in line_parts_map.keys():
        if fid not in visited:
            comp = set()
            queue = [fid]
            visited.add(fid)
            while queue:
                curr = queue.pop()
                comp.add(curr)
                for neighbor in adjacency.get(curr, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(comp)

    # If dominant component has >= 70% of features and some components have size 1
    total_in_components = sum(len(c) for c in components)
    if not components or total_in_components == 0:
        return issues

    largest_comp_size = max(len(c) for c in components)
    if largest_comp_size / total_in_components >= 0.70:
        for comp in components:
            if len(comp) == 1:
                iso_fid = list(comp)[0]
                parts = line_parts_map[iso_fid]
                loc = parts[0][0] if parts and parts[0] else (0.0, 0.0)
                issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_LINE_DISCONNECTED,
                        issue_type="LINE_DISCONNECTED",
                        severity=Severity.WARNING,
                        layer_name=layer_name,
                        geometry_type="Polyline",
                        source=source,
                        object_id=iso_fid,
                        location=loc,
                        details=(
                            f"Isolated line feature {iso_fid} is disconnected from the main network cluster "
                            f"(no endpoint connections within {connection_tolerance_m * 100:.1f} cm)."
                        ),
                    )
                )
                current_id += 1

    return issues


# ==============================================================================
# L07 — Short Line / Short Segment
# ==============================================================================

def check_short_lines_and_segments(
    fid: Any,
    parts: List[List[Tuple[float, float]]],
    layer_name: str,
    source: str,
    short_seg_tolerance_m: float = 0.10,
    short_feature_tolerance_m: float = 0.10,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    tot_len = polyline_length(parts)
    if 0.0 < tot_len < short_feature_tolerance_m:
        mid_loc = parts[0][0] if parts and parts[0] else (0.0, 0.0)
        issues.append(
            QCIssue(
                issue_id=current_id,
                check_id=CheckID.CHK_LINE_SHORT_SEG,
                issue_type="LINE_SHORT_FEATURE",
                severity=Severity.WARNING,
                layer_name=layer_name,
                geometry_type="Polyline",
                source=source,
                object_id=fid,
                measurement=round(tot_len, 4),
                threshold=short_feature_tolerance_m,
                unit="m",
                location=mid_loc,
                details=(
                    f"Line feature {fid} total length is unusually short "
                    f"({tot_len * 100:.2f} cm < {short_feature_tolerance_m * 100:.1f} cm)."
                ),
            )
        )
        current_id += 1

    # Check individual segments
    for p_idx, part in enumerate(parts):
        for i in range(len(part) - 1):
            s_len = point_distance(part[i], part[i + 1])
            if 0.0 < s_len < short_seg_tolerance_m:
                mid_x = (part[i][0] + part[i + 1][0]) / 2.0
                mid_y = (part[i][1] + part[i + 1][1]) / 2.0
                issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_LINE_SHORT_SEG,
                        issue_type="LINE_SHORT_SEGMENT",
                        severity=Severity.WARNING,
                        layer_name=layer_name,
                        geometry_type="Polyline",
                        source=source,
                        object_id=fid,
                        measurement=round(s_len, 4),
                        threshold=short_seg_tolerance_m,
                        unit="m",
                        location=(mid_x, mid_y),
                        details=(
                            f"Segment {i} in Part {p_idx} of line {fid} is short "
                            f"({s_len * 100:.2f} cm < {short_seg_tolerance_m * 100:.1f} cm)."
                        ),
                    )
                )
                current_id += 1

    return issues


# ==============================================================================
# L08 — Sharp Angle / Cutback
# ==============================================================================

def check_line_sharp_angles(
    fid: Any,
    parts: List[List[Tuple[float, float]]],
    layer_name: str,
    source: str,
    angle_tolerance_deg: float = 5.0,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    for p_idx, part in enumerate(parts):
        n = len(part)
        if n < 3:
            continue
        for i in range(1, n - 1):
            ang = calculate_turn_angle(part[i - 1], part[i], part[i + 1])
            if 0.0 < ang < angle_tolerance_deg:
                issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_LINE_ANGLE,
                        issue_type="LINE_SHARP_ANGLE",
                        severity=Severity.WARNING,
                        layer_name=layer_name,
                        geometry_type="Polyline",
                        source=source,
                        object_id=fid,
                        measurement=round(ang, 2),
                        threshold=angle_tolerance_deg,
                        unit="deg",
                        location=part[i],
                        details=(
                            f"Sharp angle/cutback of {ang:.2f}° at vertex {i} of line {fid} "
                            f"(< {angle_tolerance_deg:.1f}° threshold)."
                        ),
                    )
                )
                current_id += 1

    return issues


# ==============================================================================
# L09 — Redundant Vertex
# ==============================================================================

def check_line_redundant_vertices(
    fid: Any,
    parts: List[List[Tuple[float, float]]],
    layer_name: str,
    source: str,
    redundant_vertex_deg: float = 179.9,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    for p_idx, part in enumerate(parts):
        n = len(part)
        if n < 3:
            continue
        for i in range(1, n - 1):
            ang = calculate_turn_angle(part[i - 1], part[i], part[i + 1])
            if ang >= redundant_vertex_deg:
                issues.append(
                    QCIssue(
                        issue_id=current_id,
                        check_id=CheckID.CHK_LINE_REDUNDANT,
                        issue_type="LINE_REDUNDANT_VERTEX",
                        severity=Severity.WARNING,
                        layer_name=layer_name,
                        geometry_type="Polyline",
                        source=source,
                        object_id=fid,
                        measurement=round(ang, 2),
                        threshold=redundant_vertex_deg,
                        unit="deg",
                        location=part[i],
                        details=(
                            f"Redundant collinear vertex {i} in line {fid} "
                            f"(deflection angle {ang:.2f}° >= {redundant_vertex_deg:.1f}°)."
                        ),
                    )
                )
                current_id += 1

    return issues


# ==============================================================================
# L10 — Snap / Near-Coincident Issue
# ==============================================================================

def check_line_snap_issues(
    line_parts_map: Dict[Any, List[List[Tuple[float, float]]]],
    layer_name: str,
    source: str,
    snap_tolerance_m: float = 0.01,
    coincident_tolerance_m: float = 1e-4,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    """
    Detects near-coincident vertices or endpoints:
    Distinguishes true coincidence (dist <= 1e-4) from near-coincidence (1e-4 < dist <= snap_tol).
    """
    issues: List[QCIssue] = []
    current_id = issue_id_start

    vertex_grid = VertexGridIndex(tolerance=snap_tolerance_m)
    for fid, parts in line_parts_map.items():
        for p_idx, part in enumerate(parts):
            for v_idx, pt in enumerate(part):
                vertex_grid.insert(pt[0], pt[1], fid, p_idx, v_idx)

    reported_pairs = set()

    for rec in vertex_grid.records:
        nearby = vertex_grid.query_radius(rec.x, rec.y, snap_tolerance_m)
        for other, dist in nearby:
            if other.feature_id == rec.feature_id and other.part_idx == rec.part_idx:
                # Within same part, skip adjacent vertices
                if abs(other.vertex_idx - rec.vertex_idx) <= 1:
                    continue

            # Check near-coincidence
            if coincident_tolerance_m < dist <= snap_tolerance_m:
                pair_key = (
                    min((rec.feature_id, rec.part_idx, rec.vertex_idx), (other.feature_id, other.part_idx, other.vertex_idx)),
                    max((rec.feature_id, rec.part_idx, rec.vertex_idx), (other.feature_id, other.part_idx, other.vertex_idx)),
                )
                if pair_key not in reported_pairs:
                    reported_pairs.add(pair_key)
                    issues.append(
                        QCIssue(
                            issue_id=current_id,
                            check_id=CheckID.CHK_LINE_SNAP,
                            issue_type="LINE_SNAP_ISSUE",
                            severity=Severity.ERROR,
                            layer_name=layer_name,
                            geometry_type="Polyline",
                            source=source,
                            object_id=rec.feature_id,
                            related_object_id=other.feature_id,
                            measurement=round(dist, 4),
                            threshold=snap_tolerance_m,
                            unit="m",
                            location=(rec.x, rec.y),
                            details=(
                                f"Near-coincident vertex: Line {rec.feature_id} (V{rec.vertex_idx}) is "
                                f"{dist * 100:.2f} cm from Line {other.feature_id} (V{other.vertex_idx}) "
                                f"(< {snap_tolerance_m * 100:.1f} cm snap threshold)."
                            ),
                        )
                    )
                    current_id += 1

    return issues


# ==============================================================================
# L11 — Missing Junction
# ==============================================================================

def check_line_missing_junctions(
    line_parts_map: Dict[Any, List[List[Tuple[float, float]]]],
    layer_name: str,
    source: str,
    junction_tolerance_m: float = 0.01,
    spatial_index: Optional[SpatialGridIndex] = None,
    issue_id_start: int = 1,
) -> List[QCIssue]:
    """
    Detects T-junctions or cross-intersections where one line touches/crosses another
    without having a node/vertex on both lines at the intersection.
    """
    issues: List[QCIssue] = []
    current_id = issue_id_start

    fids = list(line_parts_map.keys())
    if len(fids) < 2:
        return issues

    pairs_to_test = spatial_index.get_candidate_pairs() if spatial_index else {
        (fids[i], fids[j]) for i in range(len(fids)) for j in range(i + 1, len(fids))
    }

    reported_junctions = set()

    for fid1, fid2 in pairs_to_test:
        parts1 = line_parts_map.get(fid1)
        parts2 = line_parts_map.get(fid2)
        if not parts1 or not parts2:
            continue

        # Check endpoints of line 1 touching interior of line 2
        for p1 in parts1:
            if len(p1) < 2:
                continue
            for ep in (p1[0], p1[-1]):
                for p2 in parts2:
                    for j in range(len(p2) - 1):
                        s2_a, s2_b = p2[j], p2[j + 1]
                        dist, proj, t = point_to_segment_dist(ep, s2_a, s2_b)
                        # Touches interior of segment (0.01 < t < 0.99)
                        if dist <= junction_tolerance_m and 0.01 < t < 0.99:
                            junc_key = (round(proj[0], 2), round(proj[1], 2))
                            if junc_key not in reported_junctions:
                                reported_junctions.add(junc_key)
                                issues.append(
                                    QCIssue(
                                        issue_id=current_id,
                                        check_id=CheckID.CHK_LINE_JUNCTION,
                                        issue_type="LINE_MISSING_JUNCTION",
                                        severity=Severity.ERROR,
                                        layer_name=layer_name,
                                        geometry_type="Polyline",
                                        source=source,
                                        object_id=fid1,
                                        related_object_id=fid2,
                                        measurement=round(dist, 4),
                                        threshold=junction_tolerance_m,
                                        unit="m",
                                        location=proj,
                                        details=(
                                            f"Missing T-junction node: Endpoint of line {fid1} touches interior of "
                                            f"line {fid2} at ({proj[0]:.3f}, {proj[1]:.3f}) without a shared vertex."
                                        ),
                                    )
                                )
                                current_id += 1

        # Check internal crossing intersections
        for p1 in parts1:
            for i in range(len(p1) - 1):
                for p2 in parts2:
                    for j in range(len(p2) - 1):
                        ix = segments_intersection(p1[i], p1[i + 1], p2[j], p2[j + 1])
                        if ix:
                            junc_key = (round(ix[0], 2), round(ix[1], 2))
                            if junc_key not in reported_junctions:
                                reported_junctions.add(junc_key)
                                issues.append(
                                    QCIssue(
                                        issue_id=current_id,
                                        check_id=CheckID.CHK_LINE_JUNCTION,
                                        issue_type="LINE_MISSING_JUNCTION",
                                        severity=Severity.ERROR,
                                        layer_name=layer_name,
                                        geometry_type="Polyline",
                                        source=source,
                                        object_id=fid1,
                                        related_object_id=fid2,
                                        location=ix,
                                        details=(
                                            f"Missing intersection node: Line {fid1} crosses line {fid2} "
                                            f"at ({ix[0]:.3f}, {ix[1]:.3f}) without a junction vertex on both lines."
                                        ),
                                    )
                                )
                                current_id += 1

    return issues


# ==============================================================================
# L12 — Open / Closed Line Behavior
# ==============================================================================

def evaluate_line_closure_behavior(
    line_parts_map: Dict[Any, List[List[Tuple[float, float]]]],
    layer_name: str,
    source: str,
    closure_tolerance_m: float = 0.01,
    expected_closed_percentage: Optional[float] = None,
    enforce_closure_match: bool = False,
    issue_id_start: int = 1,
) -> Tuple[List[QCIssue], Dict[str, Any]]:
    """
    Evaluates open vs closed distribution for polyline features.
    CRITICAL: Does NOT automatically treat closed polylines as an error!
    Only flags issues if enforce_closure_match is enabled or expected reference behavior is violated.
    """
    issues: List[QCIssue] = []
    current_id = issue_id_start

    total = len(line_parts_map)
    if total == 0:
        return issues, {"open": 0, "closed": 0, "closed_pct": 0.0}

    closed_count = 0
    open_count = 0

    for fid, parts in line_parts_map.items():
        is_closed = False
        if parts and parts[0] and len(parts[0]) >= 3:
            dist = point_distance(parts[0][0], parts[0][-1])
            if dist <= closure_tolerance_m:
                is_closed = True
        if is_closed:
            closed_count += 1
        else:
            open_count += 1

    closed_pct = closed_count / total

    # Reference-driven comparison check
    if enforce_closure_match and expected_closed_percentage is not None:
        diff = abs(closed_pct - expected_closed_percentage)
        if diff > 0.20:  # Significant > 20% deviation from Reference CAD closure expectation
            issues.append(
                QCIssue(
                    issue_id=current_id,
                    check_id=CheckID.CHK_LINE_CLOSURE,
                    issue_type="LINE_CLOSURE_UNEXPECTED",
                    severity=Severity.WARNING,
                    layer_name=layer_name,
                    geometry_type="Polyline",
                    source=source,
                    property_name="ClosedPercentage",
                    expected_value=f"{expected_closed_percentage * 100:.1f}% Closed",
                    actual_value=f"{closed_pct * 100:.1f}% Closed",
                    measurement=round(closed_pct, 4),
                    threshold=expected_closed_percentage,
                    details=(
                        f"Layer '{layer_name}' closure behavior deviates from Reference CAD standard. "
                        f"Expected {expected_closed_percentage * 100:.1f}% Closed, but received "
                        f"{closed_pct * 100:.1f}% Closed ({closed_count} closed, {open_count} open)."
                    ),
                )
            )

    return issues, {"open": open_count, "closed": closed_count, "closed_pct": closed_pct}


# ==============================================================================
# Comprehensive Line QC Runner
# ==============================================================================

def run_line_qc(
    features: Dict[Any, Any],  # fid -> shape
    layer_name: str = "LineQC",
    source: str = "INPUT",
    config: Optional[LineQCConfig] = None,
    progress_callback: Optional[Any] = None,
    issue_id_start: int = 1,
) -> Tuple[List[QCIssue], Dict[str, Dict[str, Any]]]:
    """
    Executes the complete suite of 12 Line / Polyline QC checks.
    Returns (issues_list, summary_dict).
    """
    if config is None:
        config = LineQCConfig()

    issues: List[QCIssue] = []
    current_issue_id = issue_id_start

    summary: Dict[str, Dict[str, Any]] = {
        CheckID.CHK_LINE_INVALID: {"name": "L01 — Invalid Line Geometry", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_DUPLICATE: {"name": "L02 — Duplicate Line", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_OVERLAP: {"name": "L03 — Overlapping Lines", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_SELF_INTERSECT: {"name": "L04 — Self-Intersecting Line", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_DANGLE: {"name": "L05 — Dangle", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_DISCONNECTED: {"name": "L06 — Disconnected Line", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_SHORT_SEG: {"name": "L07 — Short Line / Short Segment", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_ANGLE: {"name": "L08 — Sharp Angle / Cutback", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_REDUNDANT: {"name": "L09 — Redundant Vertex", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_SNAP: {"name": "L10 — Snap / Near-Coincident Issue", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_JUNCTION: {"name": "L11 — Missing Junction", "count": 0, "status": "PASS"},
        CheckID.CHK_LINE_CLOSURE: {"name": "L12 — Open / Closed Line Behavior", "count": 0, "status": "PASS"},
    }

    def notify(msg: str):
        if progress_callback:
            progress_callback(msg)

    # 1. Extract coordinates and build spatial index
    line_parts_map: Dict[Any, List[List[Tuple[float, float]]]] = {}
    spatial_index = SpatialGridIndex(cell_size=100.0)

    for fid, shape in features.items():
        parts = extract_line_parts(shape)
        line_parts_map[fid] = parts
        ext = get_line_extent(parts)
        if ext:
            spatial_index.insert(fid, ext)

    # L01 — Invalid Line Geometry
    if config.check_invalid:
        notify("Running L01 — Invalid Line Geometry check...")
        chk_cnt = 0
        for fid, shape in features.items():
            errs = check_invalid_line(
                fid, shape, line_parts_map.get(fid, []), layer_name, source, current_issue_id
            )
            if errs:
                issues.extend(errs)
                current_issue_id += len(errs)
                chk_cnt += len(errs)
        summary[CheckID.CHK_LINE_INVALID]["count"] = chk_cnt
        if chk_cnt > 0:
            summary[CheckID.CHK_LINE_INVALID]["status"] = "ERROR"

    # L02 — Duplicate Line
    excluded_duplicates = set()
    if config.check_duplicate:
        notify("Running L02 — Duplicate Line check...")
        dup_issues, dup_pairs = check_duplicate_lines(
            line_parts_map, layer_name, source, config.duplicate_tolerance_m, spatial_index, current_issue_id
        )
        excluded_duplicates = dup_pairs
        issues.extend(dup_issues)
        current_issue_id += len(dup_issues)
        summary[CheckID.CHK_LINE_DUPLICATE]["count"] = len(dup_issues)
        if dup_issues:
            summary[CheckID.CHK_LINE_DUPLICATE]["status"] = "ERROR"

    # L03 — Overlapping Lines
    if config.check_overlap:
        notify("Running L03 — Overlapping Lines check...")
        ov_issues = check_line_overlaps(
            line_parts_map, layer_name, source, config.overlap_tolerance_m, excluded_duplicates, spatial_index, current_issue_id
        )
        issues.extend(ov_issues)
        current_issue_id += len(ov_issues)
        summary[CheckID.CHK_LINE_OVERLAP]["count"] = len(ov_issues)
        if ov_issues:
            summary[CheckID.CHK_LINE_OVERLAP]["status"] = "ERROR"

    # L04 — Self-Intersecting Line
    if config.check_self_intersect:
        notify("Running L04 — Self-Intersecting Line check...")
        self_cnt = 0
        for fid, parts in line_parts_map.items():
            self_issues = check_line_self_intersection(
                fid, parts, layer_name, source, current_issue_id
            )
            if self_issues:
                issues.extend(self_issues)
                current_issue_id += len(self_issues)
                self_cnt += len(self_issues)
        summary[CheckID.CHK_LINE_SELF_INTERSECT]["count"] = self_cnt
        if self_cnt > 0:
            summary[CheckID.CHK_LINE_SELF_INTERSECT]["status"] = "ERROR"

    # L05 — Dangle
    if config.check_dangle:
        notify("Running L05 — Dangle check...")
        dangle_issues = check_line_dangles(
            line_parts_map, layer_name, source, config.dangle_tolerance_m, config.snap_tolerance_m, spatial_index, current_issue_id
        )
        issues.extend(dangle_issues)
        current_issue_id += len(dangle_issues)
        summary[CheckID.CHK_LINE_DANGLE]["count"] = len(dangle_issues)
        if dangle_issues:
            summary[CheckID.CHK_LINE_DANGLE]["status"] = "WARNING"

    # L06 — Disconnected Line
    if config.check_disconnected:
        notify("Running L06 — Disconnected Line check...")
        disc_issues = check_line_disconnected(
            line_parts_map, layer_name, source, config.snap_tolerance_m * 5.0, current_issue_id
        )
        issues.extend(disc_issues)
        current_issue_id += len(disc_issues)
        summary[CheckID.CHK_LINE_DISCONNECTED]["count"] = len(disc_issues)
        if disc_issues:
            summary[CheckID.CHK_LINE_DISCONNECTED]["status"] = "WARNING"

    # L07 — Short Line / Short Segment
    if config.check_short_seg:
        notify("Running L07 — Short Line / Short Segment check...")
        short_cnt = 0
        for fid, parts in line_parts_map.items():
            short_issues = check_short_lines_and_segments(
                fid, parts, layer_name, source, config.short_seg_tolerance_m, config.short_feature_tolerance_m, current_issue_id
            )
            if short_issues:
                issues.extend(short_issues)
                current_issue_id += len(short_issues)
                short_cnt += len(short_issues)
        summary[CheckID.CHK_LINE_SHORT_SEG]["count"] = short_cnt
        if short_cnt > 0:
            summary[CheckID.CHK_LINE_SHORT_SEG]["status"] = "WARNING"

    # L08 — Sharp Angle / Cutback
    if config.check_angle:
        notify("Running L08 — Sharp Angle / Cutback check...")
        ang_cnt = 0
        for fid, parts in line_parts_map.items():
            ang_issues = check_line_sharp_angles(
                fid, parts, layer_name, source, config.angle_tolerance_deg, current_issue_id
            )
            if ang_issues:
                issues.extend(ang_issues)
                current_issue_id += len(ang_issues)
                ang_cnt += len(ang_issues)
        summary[CheckID.CHK_LINE_ANGLE]["count"] = ang_cnt
        if ang_cnt > 0:
            summary[CheckID.CHK_LINE_ANGLE]["status"] = "WARNING"

    # L09 — Redundant Vertex
    if config.check_redundant:
        notify("Running L09 — Redundant Vertex check...")
        red_cnt = 0
        for fid, parts in line_parts_map.items():
            red_issues = check_line_redundant_vertices(
                fid, parts, layer_name, source, config.redundant_vertex_deg, current_issue_id
            )
            if red_issues:
                issues.extend(red_issues)
                current_issue_id += len(red_issues)
                red_cnt += len(red_issues)
        summary[CheckID.CHK_LINE_REDUNDANT]["count"] = red_cnt
        if red_cnt > 0:
            summary[CheckID.CHK_LINE_REDUNDANT]["status"] = "WARNING"

    # L10 — Snap / Near-Coincident Issue
    if config.check_snap:
        notify("Running L10 — Snap / Near-Coincident check...")
        snap_issues = check_line_snap_issues(
            line_parts_map, layer_name, source, config.snap_tolerance_m, 1e-4, current_issue_id
        )
        issues.extend(snap_issues)
        current_issue_id += len(snap_issues)
        summary[CheckID.CHK_LINE_SNAP]["count"] = len(snap_issues)
        if snap_issues:
            summary[CheckID.CHK_LINE_SNAP]["status"] = "ERROR"

    # L11 — Missing Junction
    if config.check_junction:
        notify("Running L11 — Missing Junction check...")
        junc_issues = check_line_missing_junctions(
            line_parts_map, layer_name, source, config.junction_tolerance_m, spatial_index, current_issue_id
        )
        issues.extend(junc_issues)
        current_issue_id += len(junc_issues)
        summary[CheckID.CHK_LINE_JUNCTION]["count"] = len(junc_issues)
        if junc_issues:
            summary[CheckID.CHK_LINE_JUNCTION]["status"] = "ERROR"

    # L12 — Open / Closed Line Behavior
    if config.check_closure:
        notify("Running L12 — Open / Closed Line Behavior check...")
        clos_issues, clos_stats = evaluate_line_closure_behavior(
            line_parts_map,
            layer_name,
            source,
            config.snap_tolerance_m,
            config.expected_closed_percentage,
            config.enforce_closure_match,
            current_issue_id,
        )
        issues.extend(clos_issues)
        current_issue_id += len(clos_issues)
        summary[CheckID.CHK_LINE_CLOSURE]["count"] = len(clos_issues)
        summary[CheckID.CHK_LINE_CLOSURE]["stats"] = clos_stats
        if clos_issues:
            summary[CheckID.CHK_LINE_CLOSURE]["status"] = "WARNING"

    notify("Line QC completed.")
    return issues, summary

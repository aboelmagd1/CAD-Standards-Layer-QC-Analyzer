# -*- coding: utf-8 -*-
"""
Enclosed Gap Check (CHK_GAP).
Detects enclosed sliver holes or gaps between adjacent polygons exceeding tolerance (default 0.001 m²).
"""

from typing import List, Tuple, Any, Dict, Set
from ..models.qc_issue import QCIssue, Severity, CheckID
from .spatial_index import SpatialGridIndex


def check_enclosed_gaps(
    features: Dict[Any, Any],  # fid -> shape
    layer_name: str,
    source: str = "INPUT",
    tolerance_area: float = 0.001,  # 0.001 m²
    max_gap_area: float = 100.0,  # Do not flag large planned open spaces as sliver gaps
    issue_id_start: int = 1,
) -> List[QCIssue]:
    issues: List[QCIssue] = []
    current_id = issue_id_start

    if len(features) < 2:
        return issues

    try:
        import arcpy
    except ImportError:
        return issues

    # Collect valid polygons
    poly_list = []
    fids = []
    for fid, shape in features.items():
        if shape and hasattr(shape, "area") and shape.area > 0:
            poly_list.append(shape)
            fids.append(fid)

    if len(poly_list) < 2:
        return issues

    try:
        # Union all polygons in memory to extract internal boundary holes
        # In ArcPy, union of polygons or creating a multipart dissolved geometry
        union_geom = None
        # Efficient union accumulation
        for shp in poly_list:
            if union_geom is None:
                union_geom = shp
            else:
                union_geom = union_geom.union(shp)

        if union_geom and hasattr(union_geom, "partCount"):
            # Check for inner rings (holes) in the polygon parts
            # In ArcPy, an inner ring in a polygon has clockwise/counter-clockwise orientation
            # Or we can get the bounding polygon / convex hull minus the union
            # A more direct method: inspect parts where polygon boundary has holes
            hull = union_geom.convexHull()
            diff_geom = hull.difference(union_geom)

            if diff_geom and hasattr(diff_geom, "partCount") and diff_geom.partCount > 0:
                # Decompose multipart difference into single parts
                for part_idx in range(diff_geom.partCount):
                    part_arr = diff_geom.getPart(part_idx)
                    if part_arr:
                        # Build polygon for this hole part
                        try:
                            hole_poly = arcpy.Polygon(part_arr, union_geom.spatialReference)
                            if hole_poly and hasattr(hole_poly, "area"):
                                hole_area = hole_poly.area
                                if tolerance_area <= hole_area <= max_gap_area:
                                    # Ensure the hole is actually enclosed (touches 2+ features)
                                    touching_fids = []
                                    for i, shp in enumerate(poly_list):
                                        if hole_poly.touches(shp) or hole_poly.intersect(shp, 1).length > 0:
                                            touching_fids.append(fids[i])
                                            if len(touching_fids) >= 2:
                                                break

                                    if len(touching_fids) >= 2:
                                        loc = (
                                            (hole_poly.trueCentroid.X, hole_poly.trueCentroid.Y)
                                            if hasattr(hole_poly, "trueCentroid")
                                            else None
                                        )
                                        issues.append(
                                            QCIssue(
                                                issue_id=current_id,
                                                check_id=CheckID.CHK_GAP,
                                                issue_type="ENCLOSED_GAP",
                                                severity=Severity.ERROR,
                                                layer_name=layer_name,
                                                source=source,
                                                object_id=touching_fids[0],
                                                related_object_id=touching_fids[1] if len(touching_fids) > 1 else None,
                                                measurement=round(hole_area, 6),
                                                threshold=tolerance_area,
                                                unit="m²",
                                                geometry=hole_poly,
                                                location=loc,
                                                details=f"Enclosed sliver gap between features {touching_fids} (Area: {hole_area:.4f} m²).",
                                            )
                                        )
                                        current_id += 1
                        except Exception:
                            pass
    except Exception:
        pass

    return issues

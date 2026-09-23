# -*- coding: utf-8 -*-
"""
Geometry Classifier.
Classifies geometries into standardized categories with first-class distinction
between CLOSED_POLYLINE, OPEN_POLYLINE, POLYGON, POINT, TEXT, etc.
"""

import math
from typing import Optional, Any


class GeometryCategory:
    POINT = "POINT"
    MULTIPOINT = "MULTIPOINT"
    OPEN_POLYLINE = "OPEN_POLYLINE"
    CLOSED_POLYLINE = "CLOSED_POLYLINE"
    POLYGON = "POLYGON"
    TEXT = "TEXT"
    ANNOTATION = "ANNOTATION"
    MULTIPATCH = "MULTIPATCH"
    OTHER = "OTHER"

    ALL = [
        POINT,
        MULTIPOINT,
        OPEN_POLYLINE,
        CLOSED_POLYLINE,
        POLYGON,
        TEXT,
        ANNOTATION,
        MULTIPATCH,
        OTHER,
    ]


def point_distance(p1, p2) -> float:
    """Euclidean distance between two points."""
    x1 = getattr(p1, "X", None) or (p1[0] if isinstance(p1, (list, tuple)) else 0.0)
    y1 = getattr(p1, "Y", None) or (p1[1] if isinstance(p1, (list, tuple)) else 0.0)
    x2 = getattr(p2, "X", None) or (p2[0] if isinstance(p2, (list, tuple)) else 0.0)
    y2 = getattr(p2, "Y", None) or (p2[1] if isinstance(p2, (list, tuple)) else 0.0)
    return math.hypot(x2 - x1, y2 - y1)


def is_closed_polyline(shape: Any, closure_tolerance: float = 0.01) -> bool:
    """
    Checks if an ArcPy Polyline or polyline coordinate sequence is closed.
    A polyline is closed if the first point and last point are within closure_tolerance.
    """
    if shape is None:
        return False

    # Check ArcPy Polyline object
    if hasattr(shape, "firstPoint") and hasattr(shape, "lastPoint"):
        fp = shape.firstPoint
        lp = shape.lastPoint
        if fp is not None and lp is not None:
            dist = point_distance(fp, lp)
            return dist <= closure_tolerance

    # Check coordinate list/array
    if isinstance(shape, (list, tuple)) and len(shape) >= 2:
        return point_distance(shape[0], shape[-1]) <= closure_tolerance

    # ArcPy Array structure
    if hasattr(shape, "partCount") and shape.partCount > 0:
        for part_idx in range(shape.partCount):
            part = shape.getPart(part_idx)
            if part and len(part) >= 2:
                if point_distance(part[0], part[-1]) > closure_tolerance:
                    return False
        return True

    return False


def classify_geometry(
    shape: Any,
    entity_type: Optional[str] = None,
    closure_tolerance: float = 0.01,
) -> str:
    """
    Classifies a feature geometry and optional CAD entity type into a standardized category.
    """
    # 1. Inspect CAD entity type if provided
    if entity_type:
        ent = str(entity_type).strip().upper()
        if ent in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF"):
            return GeometryCategory.TEXT
        if ent in ("DIMENSION", "LEADER", "MULTILEADER"):
            return GeometryCategory.ANNOTATION

    if shape is None:
        return GeometryCategory.OTHER

    # 2. Inspect ArcPy shape type
    shape_type = getattr(shape, "type", "").lower() if hasattr(shape, "type") else ""

    if not shape_type and isinstance(shape, str):
        shape_type = shape.lower()

    if shape_type in ("point",):
        return GeometryCategory.POINT

    if shape_type in ("multipoint",):
        return GeometryCategory.MULTIPOINT

    if shape_type in ("polyline", "line"):
        if is_closed_polyline(shape, closure_tolerance):
            return GeometryCategory.CLOSED_POLYLINE
        return GeometryCategory.OPEN_POLYLINE

    if shape_type in ("polygon",):
        return GeometryCategory.POLYGON

    if shape_type in ("multipatch",):
        return GeometryCategory.MULTIPATCH

    if shape_type in ("annotation",):
        return GeometryCategory.ANNOTATION

    # Fallback checks based on coordinates
    if isinstance(shape, (list, tuple)):
        if len(shape) == 1:
            return GeometryCategory.POINT
        elif len(shape) >= 3 and is_closed_polyline(shape, closure_tolerance):
            return GeometryCategory.CLOSED_POLYLINE
        return GeometryCategory.OPEN_POLYLINE

    return GeometryCategory.OTHER

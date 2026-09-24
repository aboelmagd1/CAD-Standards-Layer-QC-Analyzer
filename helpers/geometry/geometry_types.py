# -*- coding: utf-8 -*-
"""
Geometry Types & Standardized Classification Layer.
Provides first-class, reusable geometry type classification:
POLYGON, POLYLINE, POINT, MULTIPOINT, UNKNOWN / UNSUPPORTED.

Designed to be extensible so future geometry types (e.g. MESH, MULTIPATCH, ANNOTATION)
can be added without redesigning the QC engine.
Zero hardcoded domain assumptions: all types are derived from CAD data.
"""

from typing import Any, Optional


class GeometryType:
    POLYGON = "Polygon"
    POLYLINE = "Polyline"
    POINT = "Point"
    MULTIPOINT = "Multipoint"
    ANNOTATION = "Annotation"
    MULTIPATCH = "MultiPatch"
    UNKNOWN = "Unknown"
    UNSUPPORTED = "Unsupported"

    ALL_CANONICAL = [
        POLYGON,
        POLYLINE,
        POINT,
        MULTIPOINT,
        ANNOTATION,
        MULTIPATCH,
        UNKNOWN,
        UNSUPPORTED,
    ]


def normalize_geometry_type(val: Any) -> str:
    """
    Normalizes any geometry category string, ArcPy shape type, or CAD entity name
    into a canonical GeometryType.
    """
    if val is None:
        return GeometryType.UNKNOWN

    s = str(val).strip().upper()

    # Polygons
    if s in ("POLYGON", "PG", "POLY", "2D POLYGON", "3D POLYGON"):
        return GeometryType.POLYGON

    # Polylines / Lines
    if s in (
        "POLYLINE",
        "LINE",
        "OPEN_POLYLINE",
        "CLOSED_POLYLINE",
        "LWPOLYLINE",
        "MLINE",
        "SPLINE",
        "ARC",
        "CIRCLE",
        "LEADER",
    ):
        return GeometryType.POLYLINE

    # Points
    if s in ("POINT", "PT", "NODE", "VERTEX"):
        return GeometryType.POINT

    # Multipoints
    if s in ("MULTIPOINT", "MPT"):
        return GeometryType.MULTIPOINT

    # Text / Annotation
    if s in ("TEXT", "MTEXT", "ANNOTATION", "ATTRIB", "ATTDEF", "DIMENSION"):
        return GeometryType.ANNOTATION

    # Multipatch / 3D
    if s in ("MULTIPATCH", "3DFACE", "MESH", "SOLID", "BODY"):
        return GeometryType.MULTIPATCH

    return GeometryType.UNKNOWN


def classify_feature_geometry(shape: Any, entity_type: Optional[str] = None) -> str:
    """
    Determines the canonical GeometryType for an ArcPy Geometry object, coordinate list,
    or CAD entity description.
    """
    # 1. Check CAD entity type if provided
    if entity_type:
        ent = str(entity_type).strip().upper()
        if ent in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF", "DIMENSION", "LEADER", "MULTILEADER"):
            return GeometryType.ANNOTATION
        if ent in ("POINT",):
            return GeometryType.POINT
        if ent in ("LINE", "POLYLINE", "LWPOLYLINE", "SPLINE", "ARC", "CIRCLE"):
            return GeometryType.POLYLINE
        if ent in ("3DFACE", "SOLID3D", "BODY"):
            return GeometryType.MULTIPATCH

    if shape is None:
        return GeometryType.UNKNOWN

    # 2. Check ArcPy shape type property
    shape_type = getattr(shape, "type", "").strip().lower() if hasattr(shape, "type") else ""
    if not shape_type and isinstance(shape, str):
        shape_type = shape.strip().lower()

    if shape_type in ("polygon",):
        return GeometryType.POLYGON
    elif shape_type in ("polyline", "line"):
        return GeometryType.POLYLINE
    elif shape_type in ("point",):
        return GeometryType.POINT
    elif shape_type in ("multipoint",):
        return GeometryType.MULTIPOINT
    elif shape_type in ("multipatch",):
        return GeometryType.MULTIPATCH
    elif shape_type in ("annotation",):
        return GeometryType.ANNOTATION

    # 3. Check coordinates list/tuple structures
    if isinstance(shape, (list, tuple)):
        if len(shape) == 0:
            return GeometryType.UNKNOWN
        if len(shape) == 1:
            return GeometryType.POINT
        # Check if first and last points are identical to differentiate polygon vs polyline
        # Note: in CAD, a closed polyline is still a Polyline geometry type unless typed as Polygon
        return GeometryType.POLYLINE

    return GeometryType.UNKNOWN

# -*- coding: utf-8 -*-
"""
QC Issue Data Model.
Standardized issue structure shared across Geometry QC and CAD Comparison QC.
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Tuple


class Severity:
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    PASS = "PASS"


class CheckID:
    # Geometry QC — Polygon checks (P01-P10)
    CHK_INVALID_GEOM = "CHK_INVALID_GEOM"
    CHK_OVERLAP = "CHK_OVERLAP"
    CHK_DUPLICATE = "CHK_DUPLICATE"
    CHK_GAP = "CHK_GAP"
    CHK_MULTIPART = "CHK_MULTIPART"
    CHK_SHORT_SEG = "CHK_SHORT_SEG"
    CHK_ANGLE = "CHK_ANGLE"
    CHK_SNAP = "CHK_SNAP"
    CHK_REDUNDANT = "CHK_REDUNDANT"
    CHK_JUNCTION = "CHK_JUNCTION"

    # Geometry QC — Line / Polyline checks (L01-L12)
    CHK_LINE_INVALID = "CHK_LINE_INVALID"
    CHK_LINE_DUPLICATE = "CHK_LINE_DUPLICATE"
    CHK_LINE_OVERLAP = "CHK_LINE_OVERLAP"
    CHK_LINE_SELF_INTERSECT = "CHK_LINE_SELF_INTERSECT"
    CHK_LINE_DANGLE = "CHK_LINE_DANGLE"
    CHK_LINE_DISCONNECTED = "CHK_LINE_DISCONNECTED"
    CHK_LINE_SHORT_SEG = "CHK_LINE_SHORT_SEG"
    CHK_LINE_ANGLE = "CHK_LINE_ANGLE"
    CHK_LINE_REDUNDANT = "CHK_LINE_REDUNDANT"
    CHK_LINE_SNAP = "CHK_LINE_SNAP"
    CHK_LINE_JUNCTION = "CHK_LINE_JUNCTION"
    CHK_LINE_CLOSURE = "CHK_LINE_CLOSURE"

    # Geometry QC — Point checks (PT01-PT05)
    CHK_PT_INVALID = "CHK_PT_INVALID"
    CHK_PT_DUPLICATE = "CHK_PT_DUPLICATE"
    CHK_PT_NEAR_DUPLICATE = "CHK_PT_NEAR_DUPLICATE"
    CHK_PT_DISTRIBUTION = "CHK_PT_DISTRIBUTION"
    CHK_PT_CROSS_LAYER = "CHK_PT_CROSS_LAYER"

    # CAD Comparison checks
    CHK_MISSING_LAYER = "CHK_MISSING_LAYER"
    CHK_EXTRA_LAYER = "CHK_EXTRA_LAYER"
    CHK_GEOMETRY_TYPE = "CHK_GEOMETRY_TYPE"
    CHK_UNEXPECTED_FEATURE = "CHK_UNEXPECTED_FEATURE"
    CHK_CLOSURE = "CHK_CLOSURE"
    CHK_COLOR = "CHK_COLOR"
    CHK_LINEWEIGHT = "CHK_LINEWEIGHT"
    CHK_LINETYPE = "CHK_LINETYPE"
    CHK_FEATURE_COUNT = "CHK_FEATURE_COUNT"
    CHK_TEXT_PROPERTY = "CHK_TEXT_PROPERTY"
    CHK_MIXED_PROFILE = "CHK_MIXED_PROFILE"
    CHK_COORDINATE_SYSTEM = "CHK_COORDINATE_SYSTEM"
    CHK_RESERVED_LAYER = "CHK_RESERVED_LAYER"


@dataclass
class QCIssue:
    issue_id: int
    check_id: str
    issue_type: str
    severity: str
    layer_name: str
    geometry_type: Optional[str] = None
    source: str = "RECEIVED"  # "REFERENCE", "RECEIVED", "INPUT", "Reference Comparison"
    object_id: Optional[Any] = None
    related_object_id: Optional[Any] = None
    property_name: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    measurement: Optional[float] = None
    threshold: Optional[float] = None
    unit: Optional[str] = None
    geometry: Optional[Any] = None  # ArcPy Geometry object if available
    location: Optional[Tuple[float, float]] = None  # (X, Y)
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "issue_id": self.issue_id,
            "check_id": self.check_id,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "source": self.source,
            "layer_name": self.layer_name,
            "geometry_type": self.geometry_type,
            "object_id": self.object_id,
            "related_object_id": self.related_object_id,
            "property_name": self.property_name,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "measurement": self.measurement,
            "threshold": self.threshold,
            "unit": self.unit,
            "x": self.location[0] if self.location else None,
            "y": self.location[1] if self.location else None,
            "details": self.details,
        }

# -*- coding: utf-8 -*-
"""
QC Profiles & Centralized QC Selector.
Implements the modular GeometryQCProfile hierarchy and GetApplicableChecks selector:

GeometryQCProfile (Abstract Base)
    ├── PolygonQCProfile      (10 Polygon checks: P01 - P10)
    ├── LineQCProfile         (12 Line checks: L01 - L12)
    ├── PointQCProfile        (5 Point checks: PT01 - PT05)
    ├── MultipointQCProfile   (Multipoint checks)
    └── UnknownQCProfile      (Safe generic checks for unknown/unsupported types)

Provides dynamic, reference-driven QC check selection with zero hardcoded domain assumptions.
"""

from typing import Dict, List, Any, Optional, Tuple
from abc import ABC, abstractmethod

from ..models.qc_issue import QCIssue, CheckID, Severity
from .geometry_types import GeometryType, normalize_geometry_type
from .geometry_qc_runner import run_geometry_qc, GeometryQCConfig
from .line_qc import run_line_qc, LineQCConfig
from .point_qc import run_point_qc, PointQCConfig
from .invalid_geometry import check_invalid_geometry


class GeometryQCProfile(ABC):
    """Abstract base class for geometry-type-aware QC profiles."""

    def __init__(self, name: str, geometry_type: str):
        self.name = name
        self.geometry_type = geometry_type

    @abstractmethod
    def get_applicable_checks(self) -> List[str]:
        """Returns the list of check IDs applicable to this geometry profile."""
        pass

    @abstractmethod
    def run(
        self,
        features: Dict[Any, Any],
        layer_name: str,
        source: str = "INPUT",
        config: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
        issue_id_start: int = 1,
    ) -> Tuple[List[QCIssue], Dict[str, Dict[str, Any]]]:
        """Executes the applicable checks and returns (issues, summary)."""
        pass


class PolygonQCProfile(GeometryQCProfile):
    """
    Polygon QC Profile.
    Executes the complete suite of 10 Polygon & Topology checks (P01-P10).
    Strictly isolated: NEVER runs against line or point layers.
    """

    def __init__(self):
        super().__init__(name="Polygon QC", geometry_type=GeometryType.POLYGON)

    def get_applicable_checks(self) -> List[str]:
        return [
            CheckID.CHK_INVALID_GEOM,
            CheckID.CHK_OVERLAP,
            CheckID.CHK_DUPLICATE,
            CheckID.CHK_GAP,
            CheckID.CHK_MULTIPART,
            CheckID.CHK_SHORT_SEG,
            CheckID.CHK_ANGLE,
            CheckID.CHK_SNAP,
            CheckID.CHK_REDUNDANT,
            CheckID.CHK_JUNCTION,
        ]

    def run(
        self,
        features: Dict[Any, Any],
        layer_name: str,
        source: str = "INPUT",
        config: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
        issue_id_start: int = 1,
    ) -> Tuple[List[QCIssue], Dict[str, Dict[str, Any]]]:
        cfg = config if isinstance(config, GeometryQCConfig) else GeometryQCConfig()
        issues, summary = run_geometry_qc(
            features=features,
            layer_name=layer_name,
            source=source,
            config=cfg,
            progress_callback=progress_callback,
        )
        # Ensure correct issue IDs and geometry_type label
        for idx, iss in enumerate(issues, start=issue_id_start):
            iss.issue_id = idx
            if not iss.geometry_type:
                iss.geometry_type = GeometryType.POLYGON
        return issues, summary


class LineQCProfile(GeometryQCProfile):
    """
    Line / Polyline QC Profile.
    Executes the dedicated suite of 12 Line checks (L01-L12).
    Operates strictly on layers classified as Polyline by Reference CAD.
    """

    def __init__(self):
        super().__init__(name="Line QC", geometry_type=GeometryType.POLYLINE)

    def get_applicable_checks(self) -> List[str]:
        return [
            CheckID.CHK_LINE_INVALID,
            CheckID.CHK_LINE_DUPLICATE,
            CheckID.CHK_LINE_OVERLAP,
            CheckID.CHK_LINE_SELF_INTERSECT,
            CheckID.CHK_LINE_DANGLE,
            CheckID.CHK_LINE_DISCONNECTED,
            CheckID.CHK_LINE_SHORT_SEG,
            CheckID.CHK_LINE_ANGLE,
            CheckID.CHK_LINE_REDUNDANT,
            CheckID.CHK_LINE_SNAP,
            CheckID.CHK_LINE_JUNCTION,
            CheckID.CHK_LINE_CLOSURE,
        ]

    def run(
        self,
        features: Dict[Any, Any],
        layer_name: str,
        source: str = "INPUT",
        config: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
        issue_id_start: int = 1,
    ) -> Tuple[List[QCIssue], Dict[str, Dict[str, Any]]]:
        cfg = config if isinstance(config, LineQCConfig) else LineQCConfig()
        issues, summary = run_line_qc(
            features=features,
            layer_name=layer_name,
            source=source,
            config=cfg,
            progress_callback=progress_callback,
            issue_id_start=issue_id_start,
        )
        for iss in issues:
            if not iss.geometry_type:
                iss.geometry_type = GeometryType.POLYLINE
        return issues, summary


class PointQCProfile(GeometryQCProfile):
    """
    Point QC Profile.
    Executes the dedicated suite of Point checks (PT01-PT05).
    Operates strictly on layers classified as Point by Reference CAD.
    """

    def __init__(self):
        super().__init__(name="Point QC", geometry_type=GeometryType.POINT)

    def get_applicable_checks(self) -> List[str]:
        return [
            CheckID.CHK_PT_INVALID,
            CheckID.CHK_PT_DUPLICATE,
            CheckID.CHK_PT_NEAR_DUPLICATE,
            CheckID.CHK_PT_DISTRIBUTION,
            CheckID.CHK_PT_CROSS_LAYER,
        ]

    def run(
        self,
        features: Dict[Any, Any],
        layer_name: str,
        source: str = "INPUT",
        config: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
        issue_id_start: int = 1,
    ) -> Tuple[List[QCIssue], Dict[str, Dict[str, Any]]]:
        cfg = config if isinstance(config, PointQCConfig) else PointQCConfig()
        issues, summary = run_point_qc(
            features=features,
            layer_name=layer_name,
            source=source,
            config=cfg,
            progress_callback=progress_callback,
            issue_id_start=issue_id_start,
        )
        for iss in issues:
            if not iss.geometry_type:
                iss.geometry_type = GeometryType.POINT
        return issues, summary


class MultipointQCProfile(GeometryQCProfile):
    """
    Multipoint QC Profile.
    Executes checks suitable for Multipoint collections.
    """

    def __init__(self):
        super().__init__(name="Multipoint QC", geometry_type=GeometryType.MULTIPOINT)

    def get_applicable_checks(self) -> List[str]:
        return [
            CheckID.CHK_PT_INVALID,
            CheckID.CHK_PT_DUPLICATE,
            CheckID.CHK_PT_DISTRIBUTION,
        ]

    def run(
        self,
        features: Dict[Any, Any],
        layer_name: str,
        source: str = "INPUT",
        config: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
        issue_id_start: int = 1,
    ) -> Tuple[List[QCIssue], Dict[str, Dict[str, Any]]]:
        cfg = config if isinstance(config, PointQCConfig) else PointQCConfig()
        issues, summary = run_point_qc(
            features=features,
            layer_name=layer_name,
            source=source,
            config=cfg,
            progress_callback=progress_callback,
            issue_id_start=issue_id_start,
        )
        for iss in issues:
            if not iss.geometry_type:
                iss.geometry_type = GeometryType.MULTIPOINT
        return issues, summary


class UnknownQCProfile(GeometryQCProfile):
    """
    Safe Generic QC Profile for unknown or unsupported geometry types.
    Executes only null/empty validity tests without making geometry-specific assumptions.
    """

    def __init__(self, geometry_type: str = GeometryType.UNKNOWN):
        super().__init__(name="Generic QC", geometry_type=geometry_type)

    def get_applicable_checks(self) -> List[str]:
        return [CheckID.CHK_INVALID_GEOM]

    def run(
        self,
        features: Dict[Any, Any],
        layer_name: str,
        source: str = "INPUT",
        config: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
        issue_id_start: int = 1,
    ) -> Tuple[List[QCIssue], Dict[str, Dict[str, Any]]]:
        issues: List[QCIssue] = []
        curr_id = issue_id_start
        chk_cnt = 0

        for fid, shape in features.items():
            errs = check_invalid_geometry(fid, shape, layer_name, source, curr_id)
            if errs:
                for e in errs:
                    e.geometry_type = self.geometry_type
                issues.extend(errs)
                curr_id += len(errs)
                chk_cnt += len(errs)

        summary = {
            CheckID.CHK_INVALID_GEOM: {
                "name": "Generic Validity Check",
                "count": chk_cnt,
                "status": "ERROR" if chk_cnt > 0 else "PASS",
            }
        }
        return issues, summary


# ==============================================================================
# Centralized Factory & Selector
# ==============================================================================

def get_qc_profile_for_type(geometry_type: Any) -> GeometryQCProfile:
    """
    Returns the appropriate GeometryQCProfile instance for the given geometry type.
    """
    norm = normalize_geometry_type(geometry_type)

    if norm == GeometryType.POLYGON:
        return PolygonQCProfile()
    elif norm == GeometryType.POLYLINE:
        return LineQCProfile()
    elif norm == GeometryType.POINT:
        return PointQCProfile()
    elif norm == GeometryType.MULTIPOINT:
        return MultipointQCProfile()
    else:
        return UnknownQCProfile(geometry_type=norm)


def GetApplicableChecks(layer_profile: Any) -> List[str]:
    """
    Centralized check selector required by Section 10 of prompt.
    Takes a LayerProfile or geometry type string and returns the list of check IDs.
    """
    if layer_profile is None:
        return UnknownQCProfile().get_applicable_checks()

    # If it's a string, normalize and resolve
    if isinstance(layer_profile, str):
        profile = get_qc_profile_for_type(layer_profile)
        return profile.get_applicable_checks()

    # If it's a LayerProfile object
    geom_type = getattr(layer_profile, "geometry_type", None)
    if not geom_type or geom_type == GeometryType.UNKNOWN:
        geom_type = getattr(layer_profile, "dominant_geometry", None)

    profile = get_qc_profile_for_type(geom_type)
    return profile.get_applicable_checks()


def get_applicable_qc_profile(layer_profile_or_type: Any) -> GeometryQCProfile:
    """
    Returns the GeometryQCProfile appropriate for the given LayerProfile or geometry type.
    """
    if isinstance(layer_profile_or_type, GeometryQCProfile):
        return layer_profile_or_type

    if isinstance(layer_profile_or_type, str):
        return get_qc_profile_for_type(layer_profile_or_type)

    geom_type = getattr(layer_profile_or_type, "geometry_type", None)
    if not geom_type or geom_type == GeometryType.UNKNOWN:
        geom_type = getattr(layer_profile_or_type, "dominant_geometry", None)

    return get_qc_profile_for_type(geom_type)

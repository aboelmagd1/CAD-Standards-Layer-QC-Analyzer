# -*- coding: utf-8 -*-
"""
QC Result Data Model.
Aggregates QC outcomes, layer statuses, and issue lists for reporting.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from .qc_issue import QCIssue, Severity, CheckID
from .reference_profile import ReferenceProfile, LayerProfile


class LayerStatus:
    PASS = "PASS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    MISSING = "MISSING"
    EXTRA = "EXTRA"
    REVIEW = "REVIEW"


@dataclass
class LayerQCStatus:
    layer_name: str
    status: str
    ref_count: int = 0
    rec_count: int = 0
    expected_geom: str = "N/A"
    received_geom: str = "N/A"
    geom_status: str = "MATCH"
    color_status: str = "MATCH"
    lineweight_status: str = "MATCH"
    linetype_status: str = "MATCH"
    closure_status: str = "N/A"
    issues_count: int = 0
    reasons: List[str] = field(default_factory=list)


@dataclass
class QCResult:
    # Metadata
    reference_source: str = ""
    received_source: str = ""
    execution_date: str = ""
    spatial_reference_ref: str = ""
    spatial_reference_rec: str = ""
    spatial_reference_warning: bool = False

    # Profiles & Inventories
    reference_profile: Optional[ReferenceProfile] = None
    received_profile: Optional[ReferenceProfile] = None

    # Layer Diffs
    matching_layers: List[str] = field(default_factory=list)
    missing_layers: List[str] = field(default_factory=list)
    extra_layers: List[str] = field(default_factory=list)
    empty_received_layers: List[str] = field(default_factory=list)

    # Layer Overview Statuses
    layer_statuses: Dict[str, LayerQCStatus] = field(default_factory=dict)

    # All QC Issues
    issues: List[QCIssue] = field(default_factory=list)

    # Geometry QC specific summary (if Geometry QC was run)
    geometry_qc_run: bool = False
    geometry_qc_summary: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Per-layer geometry QC summaries: layer_name -> {check_id: {...}} or {feature_count, issues_count, error_count, warning_count, checks: {...}}
    layer_geometry_qc_summaries: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def total_reference_layers(self) -> int:
        return len(self.reference_profile.layers) if self.reference_profile else 0

    def total_received_layers(self) -> int:
        return len(self.received_profile.layers) if self.received_profile else 0

    def passed_layers_count(self) -> int:
        return sum(1 for s in self.layer_statuses.values() if s.status == LayerStatus.PASS)

    def error_layers_count(self) -> int:
        return sum(1 for s in self.layer_statuses.values() if s.status == LayerStatus.ERROR)

    def warning_layers_count(self) -> int:
        return sum(1 for s in self.layer_statuses.values() if s.status == LayerStatus.WARNING)

    def issues_by_severity(self, severity: str) -> List[QCIssue]:
        return [i for i in self.issues if i.severity == severity]

    def issues_by_check(self, check_id: str) -> List[QCIssue]:
        return [i for i in self.issues if i.check_id == check_id]

    def issues_by_layer(self, layer_name: str) -> List[QCIssue]:
        return [i for i in self.issues if i.layer_name and i.layer_name.strip().lower() == layer_name.strip().lower()]

    def layers_with_issues(self) -> List[str]:
        seen = []
        for i in self.issues:
            if i.layer_name and i.layer_name not in seen:
                seen.append(i.layer_name)
        return seen

    def add_issue(self, issue: QCIssue):
        self.issues.append(issue)

    def geometry_qc_issues(self) -> List[QCIssue]:
        geom_ids = {
            CheckID.CHK_INVALID_GEOM, CheckID.CHK_OVERLAP, CheckID.CHK_DUPLICATE,
            CheckID.CHK_GAP, CheckID.CHK_MULTIPART, CheckID.CHK_SHORT_SEG,
            CheckID.CHK_ANGLE, CheckID.CHK_SNAP, CheckID.CHK_REDUNDANT, CheckID.CHK_JUNCTION,
            CheckID.CHK_LINE_INVALID, CheckID.CHK_LINE_DUPLICATE, CheckID.CHK_LINE_OVERLAP,
            CheckID.CHK_LINE_SELF_INTERSECT, CheckID.CHK_LINE_DANGLE, CheckID.CHK_LINE_DISCONNECTED,
            CheckID.CHK_LINE_SHORT_SEG, CheckID.CHK_LINE_ANGLE, CheckID.CHK_LINE_REDUNDANT,
            CheckID.CHK_LINE_SNAP, CheckID.CHK_LINE_JUNCTION, CheckID.CHK_LINE_CLOSURE,
            CheckID.CHK_PT_INVALID, CheckID.CHK_PT_DUPLICATE, CheckID.CHK_PT_NEAR_DUPLICATE,
            CheckID.CHK_PT_DISTRIBUTION, CheckID.CHK_PT_CROSS_LAYER,
        }
        return [i for i in self.issues if i.check_id in geom_ids or i.source == "INPUT"]

    def reference_comparison_issues(self) -> List[QCIssue]:
        g_issues = set(id(i) for i in self.geometry_qc_issues())
        return [i for i in self.issues if id(i) not in g_issues]

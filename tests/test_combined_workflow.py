# -*- coding: utf-8 -*-
"""
Integration Tests for Combined QC Workflow & Report Generators.
Validates end-to-end report generation (Excel, HTML, Text).
"""

import os
import unittest
import openpyxl

from helpers.models import (
    ReferenceProfile,
    LayerProfile,
    QCResult,
    LayerQCStatus,
    LayerStatus,
    QCIssue,
    Severity,
    CheckID,
)
from helpers.reporting import (
    create_excel_report,
    create_html_report,
    create_text_report,
)


class TestCombinedWorkflow(unittest.TestCase):

    def setUp(self):
        self.output_dir = os.path.join(os.path.dirname(__file__), "test_outputs")
        os.makedirs(self.output_dir, exist_ok=True)

        # Build mock Reference Profile
        self.ref_profile = ReferenceProfile(
            source_path=r"D:\CAD\Reference_Approved.dwg",
            spatial_reference_name="WGS_1984_Web_Mercator_Auxiliary_Sphere",
            total_features=1200,
            layers={
                "PARCEL": LayerProfile(
                    layer_name="PARCEL",
                    feature_count=1000,
                    geometry_distribution={"CLOSED_POLYLINE": 1000},
                    dominant_geometry="CLOSED_POLYLINE",
                    dominant_percentage=1.0,
                    closure_required=True,
                    closure_percentage=1.0,
                    color_distribution={"7": 1000},
                    linetype_distribution={"Continuous": 1000},
                    lineweight_distribution={"0.25": 1000},
                ),
                "ROAD": LayerProfile(
                    layer_name="ROAD",
                    feature_count=200,
                    geometry_distribution={"OPEN_POLYLINE": 200},
                    dominant_geometry="OPEN_POLYLINE",
                    dominant_percentage=1.0,
                    closure_required=False,
                    color_distribution={"1": 200},
                    linetype_distribution={"Continuous": 200},
                    lineweight_distribution={"0.50": 200},
                ),
                "BUILDING": LayerProfile(
                    layer_name="BUILDING",
                    feature_count=50,
                    geometry_distribution={"POLYGON": 50},
                    dominant_geometry="POLYGON",
                    dominant_percentage=1.0,
                    closure_required=True,
                ),
            },
        )

        # Build mock QC Result
        self.qc_result = QCResult(
            reference_source=r"D:\CAD\Reference_Approved.dwg",
            received_source=r"D:\CAD\Client_Received.dwg",
            execution_date="2026-09-23 20:00:00",
            spatial_reference_ref="WGS_1984_Web_Mercator_Auxiliary_Sphere",
            spatial_reference_rec="WGS_1984_Web_Mercator_Auxiliary_Sphere",
            reference_profile=self.ref_profile,
            matching_layers=["PARCEL", "ROAD"],
            missing_layers=["BUILDING"],
            extra_layers=["TEMP_SKETCH"],
            layer_statuses={
                "PARCEL": LayerQCStatus(
                    layer_name="PARCEL",
                    status=LayerStatus.ERROR,
                    ref_count=1000,
                    rec_count=980,
                    expected_geom="CLOSED_POLYLINE",
                    received_geom="CLOSED_POLYLINE",
                    geom_status="ERROR",
                    color_status="DIFFERENT",
                    closure_status="ERROR",
                    issues_count=3,
                    reasons=["20 unexpected OPEN_POLYLINE features", "Color mismatch: 7 vs 1", "Closure: 20 open features"],
                ),
                "ROAD": LayerQCStatus(
                    layer_name="ROAD",
                    status=LayerStatus.PASS,
                    ref_count=200,
                    rec_count=200,
                    expected_geom="OPEN_POLYLINE",
                    received_geom="OPEN_POLYLINE",
                    geom_status="MATCH",
                    color_status="MATCH",
                ),
                "BUILDING": LayerQCStatus(
                    layer_name="BUILDING",
                    status=LayerStatus.MISSING,
                    ref_count=50,
                    rec_count=0,
                    expected_geom="POLYGON",
                    received_geom="Missing",
                    issues_count=1,
                    reasons=["Required layer missing from Received CAD"],
                ),
            },
            issues=[
                QCIssue(
                    issue_id=1,
                    check_id=CheckID.CHK_MISSING_LAYER,
                    issue_type="MISSING_LAYER",
                    severity=Severity.ERROR,
                    layer_name="BUILDING",
                    details="Layer BUILDING is missing from Received CAD.",
                ),
                QCIssue(
                    issue_id=2,
                    check_id=CheckID.CHK_UNEXPECTED_FEATURE,
                    issue_type="UNEXPECTED_GEOMETRY_TYPE",
                    severity=Severity.ERROR,
                    layer_name="PARCEL",
                    expected_value="CLOSED_POLYLINE",
                    actual_value="OPEN_POLYLINE",
                    measurement=20.0,
                    unit="features",
                    details="PARCEL layer contains 20 unexpected OPEN_POLYLINE features.",
                ),
                QCIssue(
                    issue_id=3,
                    check_id=CheckID.CHK_COLOR,
                    issue_type="COLOR_DIFFERENCE",
                    severity=Severity.ERROR,
                    layer_name="PARCEL",
                    expected_value="7",
                    actual_value="1",
                    details="PARCEL layer color mismatch: Expected 7, Received 1.",
                ),
            ],
            geometry_qc_run=True,
            geometry_qc_summary={
                CheckID.CHK_INVALID_GEOM: {"name": "Invalid Geometry", "count": 0, "status": "PASS"},
                CheckID.CHK_OVERLAP: {"name": "Overlap", "count": 2, "status": "ERROR"},
                CheckID.CHK_DUPLICATE: {"name": "Duplicate Geometry", "count": 0, "status": "PASS"},
            },
        )

    def test_01_excel_report_generation(self):
        excel_path = os.path.join(self.output_dir, "test_qc_report.xlsx")
        out_file = create_excel_report(self.qc_result, excel_path)
        self.assertTrue(os.path.exists(out_file))

        # Inspect workbook
        wb = openpyxl.load_workbook(out_file)
        expected_sheets = [
            "Summary",
            "Reference Profile",
            "Layer Overview",
            "Layer Differences",
            "Geometry Comparison",
            "Property Comparison",
            "Unexpected Features",
            "Closure Issues",
            "Feature Count Differences",
            "Geometry QC Summary",
            "Geometry QC Issues",
            "Issue Details",
        ]
        for s in expected_sheets:
            self.assertIn(s, wb.sheetnames, f"Sheet '{s}' missing from Excel report.")

    def test_02_html_report_generation(self):
        html_path = os.path.join(self.output_dir, "test_qc_report.html")
        out_file = create_html_report(self.qc_result, html_path)
        self.assertTrue(os.path.exists(out_file))
        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("CAD Standards & Geometry Quality Control Report", content)
        self.assertIn("PARCEL", content)
        self.assertIn("BUILDING", content)

    def test_03_text_report_generation(self):
        txt_path = os.path.join(self.output_dir, "test_qc_report.txt")
        out_file = create_text_report(self.qc_result, txt_path)
        self.assertTrue(os.path.exists(out_file))
        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("CAD REFERENCE-BASED QC", content)
        self.assertIn("Missing Layers:   1", content)
        self.assertIn("[ERROR] PARCEL", content)


if __name__ == "__main__":
    unittest.main()

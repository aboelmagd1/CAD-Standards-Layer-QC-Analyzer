# -*- coding: utf-8 -*-
"""
Tests for write_issues_to_table and separate feature classes per geometry error.
"""

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    import arcpy
except ImportError:
    from tests import mock_arcpy as arcpy
    sys.modules["arcpy"] = arcpy

from helpers.models.qc_issue import QCIssue, CheckID, Severity
from helpers.issue_writer import (
    write_issues_to_table,
    write_issues_to_feature_class,
    export_qc_errors_to_geodatabase_dataset,
)


class TestIssueWriterTableAndFeatureClasses(unittest.TestCase):

    def setUp(self):
        self.out_dir = os.path.join(os.path.dirname(__file__), "out")
        os.makedirs(self.out_dir, exist_ok=True)
        self.test_gdb = os.path.join(self.out_dir, "test_table_export.gdb")
        if not arcpy.Exists(self.test_gdb):
            arcpy.management.CreateFileGDB(self.out_dir, "test_table_export.gdb")

        self.sr = arcpy.SpatialReference(3857)

    def test_write_issues_to_standalone_table(self):
        """Verify write_issues_to_table creates a non-spatial table without Shape column."""
        issues = [
            QCIssue(
                issue_id=1,
                check_id=CheckID.CHK_COLOR,
                issue_type="COLOR_DIFFERENCE",
                severity=Severity.WARNING,
                layer_name="parcel",
                expected_value="1",
                actual_value="2",
                details="Color mismatch",
            ),
            QCIssue(
                issue_id=2,
                check_id=CheckID.CHK_OVERLAP,
                issue_type="POLYGON_OVERLAP",
                severity=Severity.ERROR,
                layer_name="parcel",
                location=(10.0, 20.0),
                measurement=0.5,
                unit="m²",
                details="Overlap detected",
            ),
        ]

        table_path = os.path.join(self.test_gdb, "QC_All_Issues_Table")
        out_table = write_issues_to_table(issues, table_path)
        self.assertTrue(arcpy.Exists(out_table))

    def test_export_geometry_issues_by_error_type(self):
        """Verify each geometry check gets its own feature class."""
        issues = [
            QCIssue(
                issue_id=1,
                check_id=CheckID.CHK_OVERLAP,
                issue_type="POLYGON_OVERLAP",
                severity=Severity.ERROR,
                layer_name="parcel",
                location=(10.0, 20.0),
                details="Overlap",
            ),
            QCIssue(
                issue_id=2,
                check_id=CheckID.CHK_ANGLE,
                issue_type="SHARP_ANGLE",
                severity=Severity.WARNING,
                layer_name="parcel",
                location=(15.0, 25.0),
                details="Sharp angle",
            ),
            QCIssue(
                issue_id=3,
                check_id=CheckID.CHK_COLOR,
                issue_type="COLOR_DIFFERENCE",
                severity=Severity.WARNING,
                layer_name="parcel",
                details="Non-spatial color difference",
            ),
        ]

        results = export_qc_errors_to_geodatabase_dataset(
            issues=issues,
            gdb_path=self.test_gdb,
            dataset_name="Test_Geometry_Errors",
            spatial_reference=self.sr,
            create_all_ten=False,
            add_to_map=False,
        )

        # Overlaps FC should be created
        self.assertIn("QC02_Overlaps", results)
        # Sharp Angles FC should be created
        self.assertIn("QC07_Sharp_Angles", results)
        # Standalone Table should be created
        self.assertIn("CAD_QC_All_Issues_Table", results)

    def test_get_or_create_reports_gdb(self):
        """Verify get_or_create_reports_gdb creates the GDB directly in the reports folder."""
        from helpers.issue_writer import get_or_create_reports_gdb
        reports_dir = os.path.join(self.out_dir, "run_reports")
        gdb = get_or_create_reports_gdb(reports_dir, "CAD_QC_Results.gdb")
        self.assertTrue(arcpy.Exists(gdb))
        self.assertEqual(os.path.basename(gdb), "CAD_QC_Results.gdb")
        self.assertEqual(os.path.dirname(gdb), os.path.abspath(reports_dir))


if __name__ == "__main__":
    unittest.main()

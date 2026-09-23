# -*- coding: utf-8 -*-
"""
Tests for Feature Dataset & 10 QC Error Feature Classes Export in Default Geodatabase.
"""

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from helpers.models.qc_issue import QCIssue, CheckID, Severity
from helpers.issue_writer import (
    get_default_geodatabase,
    export_qc_errors_to_geodatabase_dataset,
    GEOMETRY_10_CHECKS,
)


class TestGDBDatasetExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import arcpy
            cls.arcpy = arcpy
        except ImportError:
            cls.arcpy = None
            return

        cls.out_dir = os.path.join(os.path.dirname(__file__), "out")
        os.makedirs(cls.out_dir, exist_ok=True)
        cls.test_gdb = os.path.join(cls.out_dir, "test_qc_export.gdb")
        if not arcpy.Exists(cls.test_gdb):
            arcpy.management.CreateFileGDB(cls.out_dir, "test_qc_export.gdb")

    def test_01_get_default_geodatabase(self):
        if not self.arcpy:
            self.skipTest("ArcPy not installed")
        gdb = get_default_geodatabase()
        self.assertTrue(bool(gdb))
        self.assertTrue(self.arcpy.Exists(gdb))

    def test_02_export_10_error_classes_to_dataset(self):
        if not self.arcpy:
            self.skipTest("ArcPy not installed")

        sr = self.arcpy.SpatialReference(3857)
        ds_name = "Test_CAD_Geometry_QC_Errors"

        # Create mock issues spanning multiple checks
        issues = [
            QCIssue(
                issue_id=1,
                check_id=CheckID.CHK_INVALID_GEOM,
                issue_type="NULL_GEOMETRY",
                severity=Severity.ERROR,
                layer_name="parcel",
                location=(10.0, 20.0),
                details="Null geometry test",
            ),
            QCIssue(
                issue_id=2,
                check_id=CheckID.CHK_OVERLAP,
                issue_type="POLYGON_OVERLAP",
                severity=Severity.ERROR,
                layer_name="parcel",
                measurement=12.5,
                unit="m²",
                location=(15.0, 25.0),
                details="Overlap test",
            ),
            QCIssue(
                issue_id=3,
                check_id=CheckID.CHK_SNAP,
                issue_type="UNDERSHOOT",
                severity=Severity.ERROR,
                layer_name="roads",
                measurement=0.005,
                unit="m",
                location=(30.0, 40.0),
                details="Snap undershoot test",
            ),
            QCIssue(
                issue_id=4,
                check_id=CheckID.CHK_RESERVED_LAYER,
                issue_type="RESERVED_LAYER_CONTAINS_DATA",
                severity=Severity.WARNING,
                layer_name="0",
                details="Layer 0 contains data test",
                location=(5.0, 5.0),
            ),
        ]

        results = export_qc_errors_to_geodatabase_dataset(
            issues=issues,
            gdb_path=self.test_gdb,
            dataset_name=ds_name,
            spatial_reference=sr,
            create_all_ten=True,
            add_to_map=False,
        )

        ds_path = os.path.join(self.test_gdb, ds_name)
        self.assertTrue(self.arcpy.Exists(ds_path), "Feature Dataset was not created.")

        # Verify all 10 checks exist in results and in GDB
        for cid, fc_name, title in GEOMETRY_10_CHECKS:
            self.assertIn(fc_name, results, f"Missing FC {fc_name} in results.")
            fc_path = results[fc_name]
            self.assertTrue(self.arcpy.Exists(fc_path), f"FC {fc_name} does not exist in GDB.")

        # Check counts
        # Overlap has 1 issue
        fc_overlap = results["QC02_Overlaps"]
        self.assertEqual(int(self.arcpy.management.GetCount(fc_overlap)[0]), 1)

        # Snap has 1 issue
        fc_snap = results["QC08_Snap_Issues"]
        self.assertEqual(int(self.arcpy.management.GetCount(fc_snap)[0]), 1)

        # Duplicate has 0 issues (empty FC preserved)
        fc_dup = results["QC03_Duplicate_Geometries"]
        self.assertEqual(int(self.arcpy.management.GetCount(fc_dup)[0]), 0)

        # Reserved layer 0 issue
        self.assertIn("QC11_Reserved_Layer_0", results)
        fc_r0 = results["QC11_Reserved_Layer_0"]
        self.assertEqual(int(self.arcpy.management.GetCount(fc_r0)[0]), 1)

        # Master layer QC_All_Errors
        self.assertIn("QC_All_Errors", results)
        fc_all = results["QC_All_Errors"]
        self.assertEqual(int(self.arcpy.management.GetCount(fc_all)[0]), 4)


if __name__ == "__main__":
    unittest.main()

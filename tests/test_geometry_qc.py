# -*- coding: utf-8 -*-
"""
Automated Unit Tests for Geometry QC Engine (10 Checks).
Validates each of the 10 checks using synthetic geometries.
"""

import math
import unittest
import arcpy

from helpers.models import CheckID, Severity
from helpers.geometry import (
    GeometryQCConfig,
    run_geometry_qc,
    check_invalid_geometry,
    check_duplicate_geometry,
    check_overlap,
    check_multipart,
    check_short_segments,
    check_sharp_angles,
    check_snap_issues,
    check_redundant_vertices,
    check_missing_junctions,
)


class TestGeometryQC(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sr = arcpy.SpatialReference(3857)  # Web Mercator metric

    def create_polygon(self, coords):
        """Creates an ArcPy Polygon from a list of (x, y) tuples."""
        arr = arcpy.Array([arcpy.Point(x, y) for x, y in coords])
        return arcpy.Polygon(arr, self.sr)

    def test_01_invalid_geometry(self):
        # Null geometry
        issues = check_invalid_geometry(1, None, "PARCEL", "INPUT")
        self.assertTrue(any(i.check_id == CheckID.CHK_INVALID_GEOM for i in issues))

    def test_02_duplicate_geometry(self):
        # Two identical squares
        coords = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        p1 = self.create_polygon(coords)
        p2 = self.create_polygon(coords)
        features = {101: p1, 102: p2}

        issues, dup_pairs = check_duplicate_geometry(features, "PARCEL", "INPUT", 0.99)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_DUPLICATE)
        self.assertEqual(issues[0].object_id, 101)
        self.assertEqual(issues[0].related_object_id, 102)

    def test_03_overlap(self):
        # Two overlapping squares (not duplicates)
        p1 = self.create_polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        p2 = self.create_polygon([(5, 0), (15, 0), (15, 10), (5, 10), (5, 0)])
        features = {1: p1, 2: p2}

        issues = check_overlap(features, "PARCEL", "INPUT", tolerance_area=0.0001)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_OVERLAP)
        self.assertAlmostEqual(issues[0].measurement, 50.0, places=2)

    def test_04_multipart(self):
        # Two separate square rings in one polygon
        p1_arr = arcpy.Array([arcpy.Point(x, y) for x, y in [(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)]])
        p2_arr = arcpy.Array([arcpy.Point(x, y) for x, y in [(10, 0), (15, 0), (15, 5), (10, 5), (10, 0)]])
        multi_poly = arcpy.Polygon(arcpy.Array([p1_arr, p2_arr]), self.sr)

        issues = check_multipart(1, multi_poly, "PARCEL", "INPUT")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_MULTIPART)

    def test_05_short_segment(self):
        # Polygon with one edge of 0.05 m (5 cm) < 10 cm default threshold
        coords = [(0, 0), (10, 0), (10, 10), (0.05, 10), (0, 10), (0, 0)]
        poly = self.create_polygon(coords)

        issues = check_short_segments(1, poly, "PARCEL", "INPUT", tolerance_meters=0.10)
        self.assertTrue(len(issues) >= 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_SHORT_SEG)
        self.assertAlmostEqual(issues[0].measurement, 0.05, places=3)

    def test_06_sharp_angle(self):
        # Triangle with a sharp 2.0° needle apex
        coords = [(0, 0), (100, 2), (0, 4), (0, 0)]
        poly = self.create_polygon(coords)

        issues = check_sharp_angles(1, poly, "PARCEL", "INPUT", angle_threshold_deg=5.0)
        self.assertTrue(len(issues) >= 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_ANGLE)
        self.assertTrue(issues[0].measurement < 5.0)

    def test_07_snap_issue(self):
        # Two polygons with vertices 5 mm (0.005 m) apart (within 1 cm snap tolerance)
        p1 = self.create_polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        p2 = self.create_polygon([(10.005, 0), (20, 0), (20, 10), (10.005, 10), (10.005, 0)])
        features = {1: p1, 2: p2}

        issues = check_snap_issues(features, "PARCEL", "INPUT", tolerance_meters=0.01)
        self.assertTrue(len(issues) >= 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_SNAP)
        self.assertAlmostEqual(issues[0].measurement, 0.005, places=3)

    def test_08_redundant_vertex(self):
        # Collinear vertex at (5, 0) on straight line (0,0) -> (10,0) (180°)
        coords = [(0, 0), (5, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        poly = self.create_polygon(coords)

        issues = check_redundant_vertices(1, poly, "PARCEL", "INPUT", collinear_threshold_deg=179.9)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_REDUNDANT)
        self.assertAlmostEqual(issues[0].measurement, 180.0, places=1)

    def test_09_missing_junction(self):
        # Polygon A touches Polygon B edge at (5, 0) but Polygon B has no vertex at (5, 0)
        p_b = self.create_polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])  # Edge from (0,0) to (10,0)
        p_a = self.create_polygon([(5, 0), (5, -5), (10, -5), (10, 0), (5, 0)])  # Has node at (5, 0)
        features = {1: p_a, 2: p_b}

        issues = check_missing_junctions(features, "PARCEL", "INPUT", tolerance_meters=0.01)
        self.assertTrue(len(issues) >= 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_JUNCTION)

    def test_10_full_runner(self):
        # Full suite execution
        p1 = self.create_polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        features = {1: p1}
        issues, summary = run_geometry_qc(features, "PARCEL")
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary[CheckID.CHK_INVALID_GEOM]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()

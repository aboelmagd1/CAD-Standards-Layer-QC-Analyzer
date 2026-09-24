# -*- coding: utf-8 -*-
"""
Automated Unit Tests for Geometry-Type-Aware CAD QC.
Tests:
- Dedicated Line QC checks (L01–L12)
- Dedicated Point QC checks (PT01–PT05)
- Centralized QC Profiles and GetApplicableChecks selector
- Reference-Driven Behavior & Geometry Type Mismatch isolation
"""

import math
import sys
import unittest

try:
    import arcpy
    _sr = arcpy.SpatialReference(3857)
except Exception:
    from tests import mock_arcpy as arcpy
    sys.modules["arcpy"] = arcpy

from helpers.models import CheckID, Severity, LayerProfile, ReferenceProfile
from helpers.geometry import (
    GeometryType,
    normalize_geometry_type,
    classify_feature_geometry,
    GetApplicableChecks,
    get_applicable_qc_profile,
    PolygonQCProfile,
    LineQCProfile,
    PointQCProfile,
    LineQCConfig,
    PointQCConfig,
    run_line_qc,
    run_point_qc,
    check_invalid_line,
    check_duplicate_lines,
    check_line_overlaps,
    check_line_self_intersection,
    check_line_dangles,
    check_line_disconnected,
    check_short_lines_and_segments,
    check_line_sharp_angles,
    check_line_redundant_vertices,
    check_line_snap_issues,
    check_line_missing_junctions,
    evaluate_line_closure_behavior,
    check_invalid_point,
    check_point_duplicates,
    check_point_distribution,
    check_cross_layer_coincident_points,
)
from helpers.comparison.geometry_comparator import compare_geometry_composition


class TestLineQC(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sr = arcpy.SpatialReference(3857)

    def create_line(self, coords):
        """Creates an ArcPy Polyline from a list of (x, y) tuples."""
        arr = arcpy.Array([arcpy.Point(x, y) for x, y in coords])
        return arcpy.Polyline(arr, self.sr)

    def test_l01_invalid_line(self):
        # Null geometry
        issues = check_invalid_line(1, None, [], "ROAD", "INPUT")
        self.assertTrue(any(i.check_id == CheckID.CHK_LINE_INVALID for i in issues))

        # Single vertex line part (invalid segment count)
        issues = check_invalid_line(2, object(), [[(0.0, 0.0)]], "ROAD", "INPUT")
        self.assertTrue(any(i.check_id == CheckID.CHK_LINE_INVALID and i.issue_type == "INVALID_SEGMENT_COUNT" for i in issues))

    def test_l02_duplicate_lines(self):
        # Identical polylines (forward and reversed)
        line1 = [[(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]]
        line2 = [[(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]]  # forward match
        line3 = [[(20.0, 0.0), (10.0, 0.0), (0.0, 0.0)]]  # reversed match

        features = {1: line1, 2: line2, 3: line3}
        issues, dup_pairs = check_duplicate_lines(features, "ROAD", "INPUT", tolerance_m=0.001)
        self.assertGreaterEqual(len(issues), 2)
        self.assertTrue(any(i.check_id == CheckID.CHK_LINE_DUPLICATE for i in issues))

    def test_l03_overlapping_lines(self):
        # Line 1: (0,0) -> (20,0); Line 2: (10,0) -> (30,0) - overlap from 10 to 20 (10m)
        line1 = [[(0.0, 0.0), (20.0, 0.0)]]
        line2 = [[(10.0, 0.0), (30.0, 0.0)]]
        features = {1: line1, 2: line2}

        issues = check_line_overlaps(features, "ROAD", "INPUT", tolerance_m=0.01)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_LINE_OVERLAP)
        self.assertAlmostEqual(issues[0].measurement, 10.0, places=1)

    def test_l04_self_intersecting_line(self):
        # Polyline forming an hourglass/figure-8 self-intersection
        part = [[(0.0, 0.0), (10.0, 10.0), (0.0, 10.0), (10.0, 0.0)]]
        issues = check_line_self_intersection(1, part, "ROAD", "INPUT")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_LINE_SELF_INTERSECT)
        # Intersection at (5, 5)
        self.assertAlmostEqual(issues[0].location[0], 5.0, places=1)
        self.assertAlmostEqual(issues[0].location[1], 5.0, places=1)

    def test_l05_dangle(self):
        # Main line from (0,0) to (100,0)
        # Branch line terminating at (50, 0.20) without connecting (within 0.50m dangle tolerance)
        line_main = [[(0.0, 0.0), (100.0, 0.0)]]
        line_branch = [[(50.0, 10.0), (50.0, 0.20)]]
        features = {1: line_main, 2: line_branch}

        issues = check_line_dangles(features, "ROAD", "INPUT", dangle_tolerance_m=0.50, snap_tolerance_m=0.01)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_LINE_DANGLE)
        self.assertAlmostEqual(issues[0].measurement, 0.20, places=2)

    def test_l06_disconnected_line(self):
        # Main connected network of 4 lines + 1 isolated disconnected line
        features = {
            1: [[(0.0, 0.0), (10.0, 0.0)]],
            2: [[(10.0, 0.0), (20.0, 0.0)]],
            3: [[(20.0, 0.0), (30.0, 0.0)]],
            4: [[(30.0, 0.0), (40.0, 0.0)]],
            5: [[(500.0, 500.0), (510.0, 500.0)]],  # completely isolated
        }
        issues = check_line_disconnected(features, "ROAD", "INPUT", connection_tolerance_m=0.05)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_LINE_DISCONNECTED)
        self.assertEqual(issues[0].object_id, 5)

    def test_l07_short_lines_and_segments(self):
        # Short feature: total length 0.05m < 0.10m threshold
        short_line = [[(0.0, 0.0), (0.05, 0.0)]]
        issues = check_short_lines_and_segments(1, short_line, "ROAD", "INPUT", short_seg_tolerance_m=0.10, short_feature_tolerance_m=0.10)
        self.assertTrue(any(i.check_id == CheckID.CHK_LINE_SHORT_SEG for i in issues))

    def test_l08_sharp_angles(self):
        # Sharp hairpin turn with angle ~2° (< 5° threshold)
        hairpin = [[(0.0, 0.0), (100.0, 0.0), (0.0, 2.0)]]
        issues = check_line_sharp_angles(1, hairpin, "ROAD", "INPUT", angle_tolerance_deg=5.0)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_LINE_ANGLE)
        self.assertLess(issues[0].measurement, 5.0)

    def test_l09_redundant_vertices(self):
        # Redundant collinear vertex at (5, 0) along straight line from (0,0) to (10,0) (180°)
        collinear = [[(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)]]
        issues = check_line_redundant_vertices(1, collinear, "ROAD", "INPUT", redundant_vertex_deg=179.9)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_LINE_REDUNDANT)
        self.assertAlmostEqual(issues[0].measurement, 180.0, places=1)

    def test_l10_snap_issues(self):
        # Two lines with endpoints 5 mm apart (0.005 m, between 1 mm and 1 cm snap tolerance)
        line1 = [[(0.0, 0.0), (10.0, 0.0)]]
        line2 = [[(10.005, 0.0), (20.0, 0.0)]]
        features = {1: line1, 2: line2}

        issues = check_line_snap_issues(features, "ROAD", "INPUT", snap_tolerance_m=0.01)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_LINE_SNAP)
        self.assertAlmostEqual(issues[0].measurement, 0.005, places=3)

    def test_l11_missing_junction(self):
        # Horizontal line from (0,0) to (20,0)
        # Vertical line terminating at (10,0) touching horizontal line without a shared vertex
        h_line = [[(0.0, 0.0), (20.0, 0.0)]]
        v_line = [[(10.0, 10.0), (10.0, 0.0)]]
        features = {1: v_line, 2: h_line}

        issues = check_line_missing_junctions(features, "ROAD", "INPUT", junction_tolerance_m=0.01)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_LINE_JUNCTION)
        self.assertAlmostEqual(issues[0].location[0], 10.0, places=1)
        self.assertAlmostEqual(issues[0].location[1], 0.0, places=1)

    def test_l12_open_closed_behavior(self):
        # 1. By default, closed polylines are NOT errors (safety against false positives)
        closed_ring = [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]]
        features = {1: closed_ring}
        issues, stats = evaluate_line_closure_behavior(features, "ROAD", "INPUT", enforce_closure_match=False)
        self.assertEqual(len(issues), 0)
        self.assertEqual(stats["closed"], 1)
        self.assertEqual(stats["open"], 0)

        # 2. When reference explicitly expects 100% open and enforcement is enabled
        issues, stats = evaluate_line_closure_behavior(
            features, "ROAD", "INPUT", expected_closed_percentage=0.0, enforce_closure_match=True
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_LINE_CLOSURE)

    def test_line_qc_runner(self):
        line = self.create_line([(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)])
        features = {1: line}
        issues, summary = run_line_qc(features, "ROAD")
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary[CheckID.CHK_LINE_INVALID]["status"], "PASS")


class TestPointQC(unittest.TestCase):

    def test_pt01_invalid_point(self):
        # Null point
        issues = check_invalid_point(1, None, "MANHOLE", "INPUT")
        self.assertTrue(any(i.check_id == CheckID.CHK_PT_INVALID for i in issues))

        # NaN coordinates
        issues = check_invalid_point(2, (float("nan"), 10.0), "MANHOLE", "INPUT")
        self.assertTrue(any(i.check_id == CheckID.CHK_PT_INVALID for i in issues))

    def test_pt02_duplicate_point(self):
        # Exact coincident points at (100.0, 200.0)
        points = {
            1: (100.0, 200.0),
            2: (100.0, 200.0),
        }
        dup_issues, near_dup = check_point_duplicates(points, "MANHOLE", "INPUT", duplicate_tolerance_m=1e-4)
        self.assertEqual(len(dup_issues), 1)
        self.assertEqual(dup_issues[0].check_id, CheckID.CHK_PT_DUPLICATE)
        self.assertEqual(len(near_dup), 0)

    def test_pt03_near_duplicate_point(self):
        # Near coincident points 5 mm apart (tolerance 10 mm)
        points = {
            1: (100.0, 200.0),
            2: (100.005, 200.0),
        }
        dup_issues, near_dup = check_point_duplicates(
            points, "MANHOLE", "INPUT", duplicate_tolerance_m=1e-4, near_duplicate_tolerance_m=0.01
        )
        self.assertEqual(len(dup_issues), 0)
        self.assertEqual(len(near_dup), 1)
        self.assertEqual(near_dup[0].check_id, CheckID.CHK_PT_NEAR_DUPLICATE)
        self.assertAlmostEqual(near_dup[0].measurement, 0.005, places=3)

    def test_pt04_point_distribution(self):
        # Reference expected 10 points, Received has 8 points
        points = {i: (float(i), float(i)) for i in range(8)}
        issues = check_point_distribution(points, "MANHOLE", "INPUT", reference_feature_count=10)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_PT_DISTRIBUTION)
        self.assertEqual(issues[0].expected_value, "10")
        self.assertEqual(issues[0].actual_value, "8")

    def test_pt05_cross_layer_coincident(self):
        # Manhole layer point coincident with CatchBasin layer point
        layer_a = {1: (50.0, 50.0)}
        layer_b = {"CATCH_BASIN": {101: (50.0, 50.0)}}
        issues = check_cross_layer_coincident_points("MANHOLE", layer_a, layer_b, tolerance_m=1e-4)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, CheckID.CHK_PT_CROSS_LAYER)

    def test_point_qc_runner(self):
        points = {1: (10.0, 20.0), 2: (30.0, 40.0)}
        issues, summary = run_point_qc(points, "MANHOLE")
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary[CheckID.CHK_PT_INVALID]["status"], "PASS")


class TestQCProfilesAndSelection(unittest.TestCase):

    def test_applicable_checks_polygon(self):
        poly_profile = LayerProfile(layer_name="PARCEL", geometry_type=GeometryType.POLYGON)
        checks = GetApplicableChecks(poly_profile)
        self.assertEqual(len(checks), 10)
        self.assertIn(CheckID.CHK_INVALID_GEOM, checks)
        self.assertIn(CheckID.CHK_OVERLAP, checks)

    def test_applicable_checks_polyline(self):
        line_profile = LayerProfile(layer_name="ROAD_EDGE", geometry_type=GeometryType.POLYLINE)
        checks = GetApplicableChecks(line_profile)
        self.assertEqual(len(checks), 12)
        self.assertIn(CheckID.CHK_LINE_INVALID, checks)
        self.assertIn(CheckID.CHK_LINE_DUPLICATE, checks)
        self.assertIn(CheckID.CHK_LINE_DANGLE, checks)

    def test_applicable_checks_point(self):
        pt_profile = LayerProfile(layer_name="MANHOLE", geometry_type=GeometryType.POINT)
        checks = GetApplicableChecks(pt_profile)
        self.assertEqual(len(checks), 5)
        self.assertIn(CheckID.CHK_PT_INVALID, checks)
        self.assertIn(CheckID.CHK_PT_DUPLICATE, checks)

    def test_profile_routing(self):
        poly_qc = get_applicable_qc_profile(GeometryType.POLYGON)
        self.assertIsInstance(poly_qc, PolygonQCProfile)

        line_qc = get_applicable_qc_profile(GeometryType.POLYLINE)
        self.assertIsInstance(line_qc, LineQCProfile)

        pt_qc = get_applicable_qc_profile(GeometryType.POINT)
        self.assertIsInstance(pt_qc, PointQCProfile)


class TestReferenceDrivenBehaviorAndMismatch(unittest.TestCase):

    def setUp(self):
        self.sr = arcpy.SpatialReference(3857)

    def test_matching_polygon_to_polygon(self):
        ref_layer = LayerProfile(layer_name="PARCEL", geometry_type=GeometryType.POLYGON, dominant_geometry="POLYGON")
        rec_layer = LayerProfile(layer_name="PARCEL", geometry_type=GeometryType.POLYGON, dominant_geometry="POLYGON")
        issues, status, _ = compare_geometry_composition(ref_layer, rec_layer, "PARCEL")
        self.assertEqual(len(issues), 0)
        self.assertEqual(status, "MATCH")

    def test_matching_polyline_to_polyline(self):
        ref_layer = LayerProfile(layer_name="ROAD_EDGE", geometry_type=GeometryType.POLYLINE, dominant_geometry="POLYLINE")
        rec_layer = LayerProfile(layer_name="ROAD_EDGE", geometry_type=GeometryType.POLYLINE, dominant_geometry="POLYLINE")
        issues, status, _ = compare_geometry_composition(ref_layer, rec_layer, "ROAD_EDGE")
        self.assertEqual(len(issues), 0)
        self.assertEqual(status, "MATCH")

    def test_geometry_type_mismatch_prevents_polygon_qc(self):
        """
        Original has ROAD_EDGE = Polyline, Received has ROAD_EDGE = Polygon.
        Must report GEOMETRY_TYPE_MISMATCH with Expected=Polyline, Actual=Polygon.
        Must strictly isolate layer and prevent Polygon QC from running.
        """
        ref_layer = LayerProfile(
            layer_name="ROAD_EDGE",
            geometry_type=GeometryType.POLYLINE,
            dominant_geometry="POLYLINE",
        )
        rec_layer = LayerProfile(
            layer_name="ROAD_EDGE",
            geometry_type=GeometryType.POLYGON,
            dominant_geometry="POLYGON",
        )

        # 1. Comparison must flag GEOMETRY_TYPE_MISMATCH
        mismatch_issues, status, _ = compare_geometry_composition(ref_layer, rec_layer, "ROAD_EDGE")
        self.assertEqual(len(mismatch_issues), 1)
        issue = mismatch_issues[0]
        self.assertEqual(issue.issue_type, "GEOMETRY_TYPE_MISMATCH")
        self.assertEqual(issue.severity, Severity.ERROR)
        self.assertEqual(issue.source, "Reference Comparison")
        self.assertEqual(issue.expected_value, GeometryType.POLYLINE)
        self.assertEqual(issue.actual_value, GeometryType.POLYGON)

        # 2. Geometry QC dispatcher must select Profile based on REFERENCE, not received type
        expected_type = normalize_geometry_type(ref_layer.geometry_type)
        self.assertEqual(expected_type, GeometryType.POLYLINE)

        # Verify that Polygon QC profile is NOT selected for this layer
        profile = get_applicable_qc_profile(expected_type)
        self.assertIsInstance(profile, LineQCProfile)
        self.assertNotIsInstance(profile, PolygonQCProfile)

    def test_polygon_qc_runs_on_unclosed_line_and_flags_unclosed_ring(self):
        """
        If a layer is expected to be Polygon, but received features are open polylines,
        Polygon QC profile must run and flag UNCLOSED_RING under CHK_INVALID_GEOM.
        """
        profile = PolygonQCProfile()
        # Create an open line: (0, 0) -> (10, 0) -> (10, 10) -> (0, 10) (missing closure back to 0,0)
        open_line = arcpy.Polyline(
            arcpy.Array([
                arcpy.Point(0.0, 0.0),
                arcpy.Point(10.0, 0.0),
                arcpy.Point(10.0, 10.0),
                arcpy.Point(0.0, 10.0),
            ]),
            self.sr
        )
        features = {1: open_line}
        issues, summary = profile.run(features=features, layer_name="PARCEL", source="RECEIVED")
        self.assertTrue(any(iss.check_id == CheckID.CHK_INVALID_GEOM and iss.issue_type == "UNCLOSED_RING" for iss in issues))


if __name__ == "__main__":
    unittest.main()


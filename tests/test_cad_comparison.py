# -*- coding: utf-8 -*-
"""
Automated Unit Tests for CAD Reference-Based QC Engine.
Covers all comparison categories from Section 43 & 57 of the prompt.
"""

import unittest
from helpers.models import (
    ReferenceProfile,
    LayerProfile,
    QCResult,
    LayerStatus,
    CheckID,
    Severity,
)
from helpers.comparison.geometry_comparator import compare_geometry_composition
from helpers.comparison.property_comparator import compare_distribution, PropertyStatus
from helpers.comparison.closure_checker import evaluate_polyline_closure


class TestCADComparison(unittest.TestCase):

    def test_01_identical_layers(self):
        # Layer identical in Reference and Received
        ref_lp = LayerProfile(
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
        )
        rec_lp = LayerProfile(
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
        )

        issues, status, _ = compare_geometry_composition(ref_lp, rec_lp, "PARCEL")
        self.assertEqual(len(issues), 0)
        self.assertEqual(status, "MATCH")

    def test_02_unexpected_feature_types(self):
        # Reference has CLOSED_POLYLINE only; Received has unexpected OPEN_POLYLINE and TEXT
        ref_lp = LayerProfile(
            layer_name="PARCEL",
            feature_count=1000,
            geometry_distribution={"CLOSED_POLYLINE": 1000},
            dominant_geometry="CLOSED_POLYLINE",
            dominant_percentage=1.0,
        )
        rec_lp = LayerProfile(
            layer_name="PARCEL",
            feature_count=1000,
            geometry_distribution={"CLOSED_POLYLINE": 950, "OPEN_POLYLINE": 40, "TEXT": 10},
            dominant_geometry="CLOSED_POLYLINE",
            dominant_percentage=0.95,
        )

        issues, status, unexpected = compare_geometry_composition(ref_lp, rec_lp, "PARCEL")
        self.assertEqual(status, "ERROR")
        unexp_issues = [i for i in issues if i.check_id == CheckID.CHK_UNEXPECTED_FEATURE]
        self.assertEqual(len(unexp_issues), 2)  # OPEN_POLYLINE and TEXT
        types_found = {i.actual_value for i in unexp_issues}
        self.assertIn("OPEN_POLYLINE", types_found)
        self.assertIn("TEXT", types_found)

    def test_03_closure_detection(self):
        # Open polyline with gap
        open_coords = [(0, 0), (10, 0), (10, 10), (0, 10.05)]  # gap = 10.05
        is_closed, gap, p1, p2 = evaluate_polyline_closure(open_coords, closure_tolerance=0.01)
        self.assertFalse(is_closed)
        self.assertGreater(gap, 0.01)

        # Closed polyline within tolerance
        closed_coords = [(0, 0), (10, 0), (10, 10), (0, 0.005)]  # gap = 0.005 <= 0.01
        is_closed, gap, _, _ = evaluate_polyline_closure(closed_coords, closure_tolerance=0.01)
        self.assertTrue(is_closed)
        self.assertLessEqual(gap, 0.01)

    def test_04_color_difference(self):
        ref_colors = {"7": 1000}
        rec_colors = {"1": 1000}

        status, issues, summary = compare_distribution(
            ref_colors, rec_colors, "Color", "PARCEL", CheckID.CHK_COLOR
        )
        self.assertEqual(status, PropertyStatus.DIFFERENT)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].expected_value, "7")
        self.assertEqual(issues[0].actual_value, "1")

    def test_05_lineweight_difference(self):
        ref_lw = {"0.25": 500}
        rec_lw = {"0.50": 500}

        status, issues, summary = compare_distribution(
            ref_lw, rec_lw, "Lineweight", "ROAD", CheckID.CHK_LINEWEIGHT
        )
        self.assertEqual(status, PropertyStatus.DIFFERENT)
        self.assertEqual(issues[0].expected_value, "0.25")
        self.assertEqual(issues[0].actual_value, "0.50")

    def test_06_linetype_difference(self):
        ref_lt = {"Continuous": 200}
        rec_lt = {"DASHED": 200}

        status, issues, summary = compare_distribution(
            ref_lt, rec_lt, "Linetype", "ROAD", CheckID.CHK_LINETYPE
        )
        self.assertEqual(status, PropertyStatus.DIFFERENT)
        self.assertEqual(issues[0].expected_value, "Continuous")
        self.assertEqual(issues[0].actual_value, "DASHED")

    def test_07_mixed_reference_layer(self):
        # Reference is mixed (50% Closed Polyline, 50% Open Polyline)
        ref_lp = LayerProfile(
            layer_name="SURVEY",
            feature_count=100,
            geometry_distribution={"CLOSED_POLYLINE": 50, "OPEN_POLYLINE": 50},
            dominant_geometry="MIXED",
            dominant_percentage=0.50,
            is_mixed_geometry=True,
        )
        rec_lp = LayerProfile(
            layer_name="SURVEY",
            feature_count=100,
            geometry_distribution={"CLOSED_POLYLINE": 50, "OPEN_POLYLINE": 50},
            dominant_geometry="MIXED",
            dominant_percentage=0.50,
        )

        issues, status, _ = compare_geometry_composition(ref_lp, rec_lp, "SURVEY")
        self.assertEqual(status, "REVIEW")
        self.assertTrue(any(i.check_id == CheckID.CHK_MIXED_PROFILE for i in issues))

    def test_08_property_distribution_comparison(self):
        # Reference has multiple colors: Color 7=980, Color 1=20
        # Received has Color 7=950, Color 1=50
        ref_colors = {"7": 980, "1": 20}
        rec_colors = {"7": 950, "1": 50}

        status, issues, summary = compare_distribution(
            ref_colors, rec_colors, "Color", "PARCEL", CheckID.CHK_COLOR
        )
        self.assertEqual(status, PropertyStatus.DIFFERENT)
        # Dominants match ("7"), but distribution shifted -> WARNING
        self.assertEqual(issues[0].severity, Severity.WARNING)

    def test_09_property_unavailable_graceful_handling(self):
        # Property not in reference
        status, issues, summary = compare_distribution(
            {}, {"1": 100}, "Color", "TEST", CheckID.CHK_COLOR
        )
        self.assertEqual(status, PropertyStatus.NOT_AVAILABLE)
        self.assertEqual(len(issues), 0)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""
Tests for Reserved CAD Layer '0' handling and warning generation.
"""

import unittest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from helpers.models.reference_profile import ReferenceProfile, LayerProfile
from helpers.models.qc_issue import Severity, CheckID
from helpers.comparison.comparison_engine import run_cad_comparison, ComparisonConfig


class TestLayerZero(unittest.TestCase):
    def test_01_reference_contains_layer_zero_warning(self):
        """Verify that when Reference CAD contains Layer 0, a WARNING is generated."""
        ref_profile = ReferenceProfile(source_path="mock_ref.dwg")
        lp_zero = LayerProfile(layer_name="0", feature_count=15, dominant_geometry="POLYGON")
        lp_parcels = LayerProfile(layer_name="PARCELS", feature_count=50, dominant_geometry="POLYGON")
        ref_profile.layers["0"] = lp_zero
        ref_profile.layers["PARCELS"] = lp_parcels

        # Mock received profile with parcels and layer 0
        from helpers.comparison import comparison_engine
        orig_analyze = comparison_engine.analyze_dataset

        class MockAnalysis:
            source_path = "mock_rec.dwg"
            spatial_reference_name = "Unknown"
            spatial_reference_wkid = None
            total_features = 65
            layers = {
                "0": LayerProfile(layer_name="0", feature_count=10, dominant_geometry="POLYGON"),
                "PARCELS": LayerProfile(layer_name="PARCELS", feature_count=50, dominant_geometry="POLYGON"),
            }
            available_cad_fields = []

        try:
            comparison_engine.analyze_dataset = lambda **kwargs: MockAnalysis()
            res = run_cad_comparison(ref_profile, "mock_rec.dwg", config=ComparisonConfig())

            # Check that reserved layer issues were raised
            res_issues = res.issues_by_check(CheckID.CHK_RESERVED_LAYER)
            self.assertGreaterEqual(len(res_issues), 2, "Expected warnings for both Reference and Received Layer 0")
            
            ref_zero_issues = [i for i in res_issues if i.source == "REFERENCE"]
            rec_zero_issues = [i for i in res_issues if i.source == "RECEIVED"]

            self.assertEqual(len(ref_zero_issues), 1)
            self.assertEqual(ref_zero_issues[0].severity, Severity.WARNING)
            self.assertIn("Reference CAD contains 15 features", ref_zero_issues[0].details)

            self.assertEqual(len(rec_zero_issues), 1)
            self.assertEqual(rec_zero_issues[0].severity, Severity.WARNING)
            self.assertIn("Received CAD contains 10 features", rec_zero_issues[0].details)

            # Check layer status is marked as WARNING
            self.assertIn("0", res.layer_statuses)
            self.assertEqual(res.layer_statuses["0"].status, "WARNING")

        finally:
            comparison_engine.analyze_dataset = orig_analyze

    def test_02_received_cleaned_layer_zero_compliant(self):
        """Verify that when Received cleans/removes Layer 0, it is not flagged as a missing layer error."""
        ref_profile = ReferenceProfile(source_path="mock_ref.dwg")
        ref_profile.layers["0"] = LayerProfile(layer_name="0", feature_count=5, dominant_geometry="POLYGON")
        ref_profile.layers["PARCELS"] = LayerProfile(layer_name="PARCELS", feature_count=50, dominant_geometry="POLYGON")

        from helpers.comparison import comparison_engine
        orig_analyze = comparison_engine.analyze_dataset

        class MockAnalysisClean:
            source_path = "mock_rec.dwg"
            spatial_reference_name = "Unknown"
            spatial_reference_wkid = None
            total_features = 50
            layers = {
                "PARCELS": LayerProfile(layer_name="PARCELS", feature_count=50, dominant_geometry="POLYGON"),
            }
            available_cad_fields = []

        try:
            comparison_engine.analyze_dataset = lambda **kwargs: MockAnalysisClean()
            res = run_cad_comparison(ref_profile, "mock_rec.dwg", config=ComparisonConfig())

            # Layer 0 in Reference should raise a warning
            ref_zero_issues = [i for i in res.issues if i.check_id == CheckID.CHK_RESERVED_LAYER and i.source == "REFERENCE"]
            self.assertEqual(len(ref_zero_issues), 1)

            # Layer 0 must NOT be flagged as MISSING_LAYER error
            missing_errors = [i for i in res.issues if i.check_id == CheckID.CHK_MISSING_LAYER and i.layer_name == "0"]
            self.assertEqual(len(missing_errors), 0, "Cleaned layer 0 must not be flagged as missing layer error")

            self.assertEqual(res.layer_statuses["0"].status, "PASS")

        finally:
            comparison_engine.analyze_dataset = orig_analyze


if __name__ == "__main__":
    unittest.main()

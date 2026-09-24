# -*- coding: utf-8 -*-
"""
Tests for Toolbox Parameter Loading and Multi-Layer Geometry QC.
"""

import unittest
import os
import sys

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import importlib.util
from helpers.utilities import (
    is_cad_drawing_dataset,
    get_dataset_cad_layers,
    extract_features_by_layer,
)


class TestToolboxAndLayers(unittest.TestCase):
    def test_01_toolbox_parameter_loading(self):
        """Verify CAD_QC_Toolbox.pyt loads cleanly with valid parameter datatypes in arcpy."""
        pyt_path = os.path.join(PROJECT_ROOT, "CAD_QC_Toolbox.pyt")
        self.assertTrue(os.path.exists(pyt_path), "CAD_QC_Toolbox.pyt not found")

        try:
            import arcpy
            _ = arcpy.SpatialReference(3857)
        except Exception:
            from tests import mock_arcpy as arcpy
            sys.modules["arcpy"] = arcpy

        loader = importlib.machinery.SourceFileLoader("cad_qc_test", pyt_path)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)

        tb = mod.Toolbox()
        self.assertEqual(len(tb.tools), 2)

        for tool_cls in tb.tools:
            tool = tool_cls()
            params = tool.getParameterInfo()
            self.assertGreater(len(params), 0)
            for p in params:
                self.assertIsNotNone(p.name)
                self.assertIsNotNone(p.datatype)

    def test_02_cad_dataset_layer_extraction(self):
        """Verify DWG drawing dataset layer discovery and feature extraction."""
        dwg_path = os.path.join(PROJECT_ROOT, "orig.dwg")
        if not os.path.exists(dwg_path):
            self.skipTest("orig.dwg not found")

        if not is_cad_drawing_dataset(dwg_path):
            self.skipTest("ArcPy with CAD drawing dataset license not available in current environment")
        layers = get_dataset_cad_layers(dwg_path)
        if not layers:
            self.skipTest("ArcPy CAD engine not functional in current environment")
        self.assertIn("parcel", [l.lower() for l in layers])
        self.assertIn("roud", [l.lower() for l in layers])

        features_by_layer, field, sr = extract_features_by_layer(dwg_path)
        self.assertIn("parcel", [k.lower() for k in features_by_layer.keys()])
        self.assertIn("roud", [k.lower() for k in features_by_layer.keys()])
        self.assertGreater(len(features_by_layer["parcel"]), 0)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
from .closure_checker import evaluate_polyline_closure, check_feature_closure
from .property_comparator import compare_distribution, PropertyStatus
from .layer_analyzer import analyze_dataset, normalize_layer_name, DatasetAnalysisResult
from .reference_profiler import build_reference_profile
from .geometry_comparator import compare_geometry_composition
from .comparison_engine import ComparisonConfig, run_cad_comparison

__all__ = [
    "evaluate_polyline_closure",
    "check_feature_closure",
    "compare_distribution",
    "PropertyStatus",
    "analyze_dataset",
    "normalize_layer_name",
    "DatasetAnalysisResult",
    "build_reference_profile",
    "compare_geometry_composition",
    "ComparisonConfig",
    "run_cad_comparison",
]

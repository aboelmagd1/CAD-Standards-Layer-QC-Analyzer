# -*- coding: utf-8 -*-
"""
Reference Profiler.
Analyzes the Original / Reference CAD dataset and builds the authoritative Reference Profile.
Strictly read-only; learns expected characteristics directly from data with zero hardcoded assumptions.
"""

from datetime import datetime
from typing import Optional, Any
from ..models.reference_profile import ReferenceProfile
from .layer_analyzer import analyze_dataset


def build_reference_profile(
    reference_source: Any,
    layer_field_name: str = "Layer",
    closure_tolerance: float = 0.01,
    dominant_threshold: float = 0.50,
    case_sensitive: bool = False,
    trim_whitespace: bool = True,
    progress_callback: Optional[Any] = None,
) -> ReferenceProfile:
    """
    Builds the Reference Profile from the Original CAD dataset.
    """
    def notify(msg: str):
        if progress_callback:
            progress_callback(msg)

    notify("Analyzing Reference CAD...")
    notify("Extracting Layers...")
    notify("Extracting Feature Types...")
    notify("Extracting Geometry Properties...")
    notify("Extracting CAD Properties...")
    notify("Building Reference Profile...")

    analysis = analyze_dataset(
        source_dataset=reference_source,
        layer_field_name=layer_field_name,
        closure_tolerance=closure_tolerance,
        dominant_threshold=dominant_threshold,
        case_sensitive=case_sensitive,
        trim_whitespace=trim_whitespace,
        progress_callback=progress_callback,
    )

    profile = ReferenceProfile(
        source_path=analysis.source_path,
        spatial_reference_name=analysis.spatial_reference_name,
        spatial_reference_wkid=analysis.spatial_reference_wkid,
        total_features=analysis.total_features,
        layers=analysis.layers,
        available_cad_fields=analysis.available_cad_fields,
        analysis_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    notify(f"Reference Profile generated: {len(profile.layers)} layers analyzed.")
    return profile

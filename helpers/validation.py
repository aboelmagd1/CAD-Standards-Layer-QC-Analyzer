# -*- coding: utf-8 -*-
"""
Validation Module.
Validates ArcGIS Pro geoprocessing parameters and enforces pre-execution safety rules.
"""

import os
from typing import List, Any


def validate_cad_comparison_parameters(parameters: List[Any]):
    """
    Validates parameters in updateMessages() for CADReferenceComparisonQCTool.
    """
    try:
        import arcpy
    except ImportError:
        return

    # Indices matching CADReferenceComparisonQCTool getParameterInfo()
    # 0: reference_source
    # 1: reference_layer_field
    # 2: received_source
    # 3: received_layer_field
    # 4: scope
    # 5: dominant_threshold
    # 6: closure_tolerance
    # 7: output_folder

    p_ref = parameters[0]
    p_ref_field = parameters[1]
    p_rec = parameters[2]
    p_rec_field = parameters[3]
    p_dom = parameters[5]
    p_clos = parameters[6]
    p_out = parameters[7]

    # Validate Reference Source
    if p_ref.altered and p_ref.value:
        if not arcpy.Exists(p_ref.valueAsText):
            p_ref.setErrorMessage(f"Reference dataset '{p_ref.valueAsText}' does not exist.")

    # Validate Received Source
    if p_rec.altered and p_rec.value:
        if not arcpy.Exists(p_rec.valueAsText):
            p_rec.setErrorMessage(f"Received dataset '{p_rec.valueAsText}' does not exist.")

    # Validate Dominant Threshold
    if p_dom.altered and p_dom.value is not None:
        try:
            val = float(p_dom.value)
            if not (0.0 < val <= 1.0):
                p_dom.setErrorMessage("Dominant Geometry Threshold must be between 0.0 and 1.0 (e.g. 0.50).")
        except ValueError:
            p_dom.setErrorMessage("Dominant Geometry Threshold must be a numeric value.")

    # Validate Closure Tolerance
    if p_clos.altered and p_clos.value is not None:
        try:
            val = float(p_clos.value)
            if val <= 0.0:
                p_clos.setErrorMessage("Closure Tolerance must be greater than 0.0 (e.g. 0.01).")
        except ValueError:
            p_clos.setErrorMessage("Closure Tolerance must be a numeric value.")

    # Validate Output Folder
    if p_out.altered and p_out.valueAsText:
        folder = p_out.valueAsText
        if not os.path.exists(folder):
            try:
                os.makedirs(folder, exist_ok=True)
            except Exception:
                p_out.setErrorMessage(f"Output folder '{folder}' cannot be created.")


def validate_geometry_qc_parameters(parameters: List[Any]):
    """
    Validates parameters in updateMessages() for GeometryQCTool.
    """
    try:
        import arcpy
    except ImportError:
        return

    p_map = {getattr(p, "name", ""): p for p in parameters}

    p_in = p_map.get("input_features")
    p_short = p_map.get("short_seg_tolerance")
    p_angle = p_map.get("angle_tolerance")
    p_snap = p_map.get("snap_tolerance")
    p_red = p_map.get("redundant_vertex_tolerance")
    p_junc = p_map.get("junction_tolerance")
    p_out = p_map.get("output_folder")

    if p_in and p_in.altered and p_in.value:
        if not arcpy.Exists(p_in.valueAsText):
            p_in.setErrorMessage(f"Input dataset '{p_in.valueAsText}' does not exist.")

    # Short segment
    if p_short and p_short.altered and p_short.value is not None:
        if float(p_short.value) <= 0.0:
            p_short.setErrorMessage("Short Segment threshold must be > 0 (meters).")

    # Angle
    if p_angle and p_angle.altered and p_angle.value is not None:
        val = float(p_angle.value)
        if not (0.0 < val < 90.0):
            p_angle.setErrorMessage("Angle threshold must be between 0° and 90° (degrees).")

    # Snap
    if p_snap and p_snap.altered and p_snap.value is not None:
        if float(p_snap.value) <= 0.0:
            p_snap.setErrorMessage("Snap threshold must be > 0 (meters).")

    # Redundant vertex
    if p_red and p_red.altered and p_red.value is not None:
        val = float(p_red.value)
        if not (90.0 < val <= 180.0):
            p_red.setErrorMessage("Redundant Vertex threshold must be between 90° and 180°.")

    # Junction
    if p_junc and p_junc.altered and p_junc.value is not None:
        if float(p_junc.value) <= 0.0:
            p_junc.setErrorMessage("Junction threshold must be > 0 (meters).")

    # Output Folder
    if p_out and p_out.altered and p_out.valueAsText:
        folder = p_out.valueAsText
        if not os.path.exists(folder):
            try:
                os.makedirs(folder, exist_ok=True)
            except Exception:
                p_out.setErrorMessage(f"Output folder '{folder}' cannot be created.")

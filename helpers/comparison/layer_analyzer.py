# -*- coding: utf-8 -*-
"""
Layer Analyzer.
Performs high-performance, single-pass streaming analysis of CAD/GIS datasets
using arcpy.da.SearchCursor to build layer inventories and property distributions.
"""

from typing import Dict, List, Tuple, Any, Optional, Set
from ..models.reference_profile import LayerProfile, ReferenceProfile
from ..geometry.geometry_classifier import classify_geometry, is_closed_polyline, GeometryCategory
from .closure_checker import evaluate_polyline_closure


class DatasetAnalysisResult:
    def __init__(self, source_path: str):
        self.source_path = source_path
        self.spatial_reference_name = "Unknown"
        self.spatial_reference_wkid = None
        self.total_features = 0
        self.layers: Dict[str, LayerProfile] = {}
        # Stores feature geometries for features with issues (closure/unexpected)
        self.sampled_features: Dict[str, Dict[Any, Any]] = {}  # layer -> {fid: shape}
        # Original name lookup: normalized_name -> original_name
        self.normalized_map: Dict[str, str] = {}
        self.available_cad_fields: List[str] = []


def normalize_layer_name(
    name: str,
    case_sensitive: bool = False,
    trim_whitespace: bool = True,
) -> str:
    """Normalizes a layer name according to configuration while keeping original reference."""
    if name is None:
        return ""
    result = str(name)
    if trim_whitespace:
        result = result.strip()
    if not case_sensitive:
        result = result.upper()
    return result


def analyze_dataset(
    source_dataset: Any,
    layer_field_name: str = "Layer",
    closure_tolerance: float = 0.01,
    dominant_threshold: float = 0.50,
    case_sensitive: bool = False,
    trim_whitespace: bool = True,
    max_stored_geometries_per_layer: int = 200,
    progress_callback: Optional[Any] = None,
) -> DatasetAnalysisResult:
    """
    Scans source_dataset in a single pass using arcpy.da.SearchCursor.
    Constructs LayerProfiles with geometry, closure, color, linetype, and lineweight distributions.
    """
    result = DatasetAnalysisResult(str(source_dataset))

    try:
        import arcpy
    except ImportError:
        return result

    def notify(msg: str):
        if progress_callback:
            progress_callback(msg)

    # 1. Discover fields and spatial reference
    desc = arcpy.Describe(source_dataset)
    if hasattr(desc, "spatialReference") and desc.spatialReference:
        result.spatial_reference_name = desc.spatialReference.name
        result.spatial_reference_wkid = desc.spatialReference.factoryCode

    from ..utilities import is_cad_drawing_dataset, get_cad_child_feature_classes

    # Determine targets (children if CAD Drawing Dataset, else source itself)
    if is_cad_drawing_dataset(source_dataset):
        targets = get_cad_child_feature_classes(source_dataset, ["Polygon", "Polyline", "Point", "Annotation", "MultiPatch"])
    else:
        targets = [source_dataset]

    layer_profiles: Dict[str, LayerProfile] = {}
    sampled_shapes: Dict[str, Dict[Any, Any]] = {}

    for target in targets:
        try:
            existing_field_names = [f.name for f in arcpy.ListFields(target)]
        except Exception:
            continue

        actual_layer_field = None
        for cand in [layer_field_name, "Layer", "LAYER", "CadLayer", "CADLAYER", "LAYER_NAME", "LayerName"]:
            for ef in existing_field_names:
                if ef.lower() == cand.lower():
                    actual_layer_field = ef
                    break
            if actual_layer_field:
                break

        if not actual_layer_field:
            actual_layer_field = existing_field_names[0] if existing_field_names else "OBJECTID"

        color_field = None
        linetype_field = None
        lineweight_field = None
        entity_field = None
        text_field = None

        for f in existing_field_names:
            fl = f.lower()
            if fl in ("color", "cadcolor", "cad_color"):
                color_field = f
            elif fl in ("linetype", "cadlinetype", "lt_name", "cad_linetype"):
                linetype_field = f
            elif fl in ("linewt", "lineweight", "cadlineweight", "cad_lineweight", "line_weight"):
                lineweight_field = f
            elif fl in ("entity", "cadtype", "entity_type"):
                entity_field = f
            elif fl in ("text", "txtmemo", "textstring", "annotation"):
                text_field = f

        cursor_fields = ["OID@", "SHAPE@", actual_layer_field]
        idx_map = {"oid": 0, "shape": 1, "layer": 2}

        if color_field:
            idx_map["color"] = len(cursor_fields)
            cursor_fields.append(color_field)
            if "Color" not in result.available_cad_fields:
                result.available_cad_fields.append("Color")

        if linetype_field:
            idx_map["linetype"] = len(cursor_fields)
            cursor_fields.append(linetype_field)
            if "Linetype" not in result.available_cad_fields:
                result.available_cad_fields.append("Linetype")

        if lineweight_field:
            idx_map["lineweight"] = len(cursor_fields)
            cursor_fields.append(lineweight_field)
            if "Lineweight" not in result.available_cad_fields:
                result.available_cad_fields.append("Lineweight")

        if entity_field:
            idx_map["entity"] = len(cursor_fields)
            cursor_fields.append(entity_field)
            if "Entity" not in result.available_cad_fields:
                result.available_cad_fields.append("Entity")

        if text_field:
            idx_map["text"] = len(cursor_fields)
            cursor_fields.append(text_field)
            if "Text" not in result.available_cad_fields:
                result.available_cad_fields.append("Text")

        notify(f"Streaming features from {target}...")

        try:
            with arcpy.da.SearchCursor(target, cursor_fields) as cursor:
                for row in cursor:
                    result.total_features += 1
                    oid = row[idx_map["oid"]]
                    shape = row[idx_map["shape"]]
                    raw_layer = str(row[idx_map["layer"]] or "0")

                    norm_layer = normalize_layer_name(raw_layer, case_sensitive, trim_whitespace)
                    if norm_layer not in result.normalized_map:
                        result.normalized_map[norm_layer] = raw_layer

                    if norm_layer not in layer_profiles:
                        layer_profiles[norm_layer] = LayerProfile(layer_name=raw_layer)
                        sampled_shapes[norm_layer] = {}

                    lp = layer_profiles[norm_layer]
                    lp.feature_count += 1

                    entity_val = str(row[idx_map["entity"]]) if "entity" in idx_map and row[idx_map["entity"]] is not None else None

                    geom_cat = classify_geometry(shape, entity_val, closure_tolerance)
                    lp.geometry_distribution[geom_cat] = lp.geometry_distribution.get(geom_cat, 0) + 1

                    if geom_cat in (GeometryCategory.CLOSED_POLYLINE, GeometryCategory.OPEN_POLYLINE):
                        is_closed, gap, _, _ = evaluate_polyline_closure(shape, closure_tolerance)
                        if is_closed:
                            lp.closed_count += 1
                        else:
                            lp.open_count += 1
                            if len(sampled_shapes[norm_layer]) < max_stored_geometries_per_layer:
                                sampled_shapes[norm_layer][oid] = shape

                    if "color" in idx_map and row[idx_map["color"]] is not None:
                        c_val = str(row[idx_map["color"]]).strip()
                        if c_val:
                            lp.color_distribution[c_val] = lp.color_distribution.get(c_val, 0) + 1

                    if "linetype" in idx_map and row[idx_map["linetype"]] is not None:
                        lt_val = str(row[idx_map["linetype"]]).strip()
                        if lt_val:
                            lp.linetype_distribution[lt_val] = lp.linetype_distribution.get(lt_val, 0) + 1

                    if "lineweight" in idx_map and row[idx_map["lineweight"]] is not None:
                        lw_val = str(row[idx_map["lineweight"]]).strip()
                        if lw_val:
                            lp.lineweight_distribution[lw_val] = lp.lineweight_distribution.get(lw_val, 0) + 1
        except Exception:
            continue

    # Post-process distributions to determine Dominant Geometry and Mixed profile
    for norm_name, lp in layer_profiles.items():
        total_feats = lp.feature_count
        if total_feats > 0:
            # Dominant geometry
            sorted_geoms = sorted(lp.geometry_distribution.items(), key=lambda x: x[1], reverse=True)
            top_geom, top_count = sorted_geoms[0]
            dom_pct = top_count / total_feats
            lp.dominant_percentage = dom_pct

            if dom_pct >= dominant_threshold:
                lp.dominant_geometry = top_geom
                lp.is_mixed_geometry = False
            else:
                lp.dominant_geometry = "MIXED"
                lp.is_mixed_geometry = True

            # Closure requirement derivation
            total_polylines = lp.closed_count + lp.open_count
            if total_polylines > 0:
                lp.closure_percentage = lp.closed_count / total_polylines
                # If dominant is closed polyline or polygon or > 50% closed
                if lp.dominant_geometry in (GeometryCategory.CLOSED_POLYLINE, GeometryCategory.POLYGON) or lp.closure_percentage >= 0.50:
                    lp.closure_required = True
            elif lp.dominant_geometry == GeometryCategory.POLYGON:
                lp.closure_required = True
                lp.closure_percentage = 1.0

        lp.available_properties = list(result.available_cad_fields)

    result.layers = layer_profiles
    result.sampled_features = sampled_shapes
    return result

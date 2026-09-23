# -*- coding: utf-8 -*-
"""
Utilities.
Helper functions for spatial reference inspection, layer field detection,
CAD drawing dataset exploration, and layer-aware feature extraction.
"""

import os
from typing import Optional, List, Dict, Tuple, Any


def get_dataset_spatial_reference(dataset: Any) -> Optional[Any]:
    """Retrieves the arcpy.SpatialReference of a dataset if available."""
    try:
        import arcpy
        desc = arcpy.Describe(dataset)
        return getattr(desc, "spatialReference", None)
    except Exception:
        return None


def compare_spatial_references(sr1: Any, sr2: Any) -> bool:
    """
    Returns True if spatial references match in factoryCode or name, False otherwise.
    """
    if sr1 is None or sr2 is None:
        return True  # Cannot compare, do not flag false mismatch

    # Compare factory code (WKID)
    wkid1 = getattr(sr1, "factoryCode", None)
    wkid2 = getattr(sr2, "factoryCode", None)
    if wkid1 and wkid2 and wkid1 > 0 and wkid2 > 0:
        return wkid1 == wkid2

    # Compare name
    name1 = getattr(sr1, "name", "").strip().lower()
    name2 = getattr(sr2, "name", "").strip().lower()
    if name1 and name2:
        return name1 == name2

    return True


def is_cad_drawing_dataset(dataset: Any) -> bool:
    """Returns True if the dataset is an AutoCAD DWG/DXF drawing dataset."""
    try:
        import arcpy
        desc = arcpy.Describe(dataset)
        dt = getattr(desc, "dataType", "")
        if dt.lower() in ("caddrawingdataset", "decaddrawingdataset"):
            return True
        path_str = str(dataset).lower()
        if (path_str.endswith(".dwg") or path_str.endswith(".dxf")) and hasattr(desc, "children"):
            return True
    except Exception:
        pass
    return False


def get_cad_child_feature_classes(
    dataset: Any,
    geom_types: Optional[List[str]] = None,
) -> List[str]:
    """
    If dataset is a CadDrawingDataset, returns paths to child feature classes.
    Optionally filters by child names (e.g. ['Polygon', 'Polyline', 'Point']).
    """
    results: List[str] = []
    try:
        import arcpy
        desc = arcpy.Describe(dataset)
        base_path = getattr(desc, "catalogPath", str(dataset))
        children = getattr(desc, "children", [])
        for c in children:
            c_name = getattr(c, "name", "")
            if geom_types:
                if any(c_name.lower() == gt.lower() for gt in geom_types):
                    results.append(os.path.join(base_path, c_name))
            else:
                results.append(os.path.join(base_path, c_name))
    except Exception:
        pass
    return results


def auto_detect_layer_field(dataset: Any) -> str:
    """Auto-detects the layer field from a dataset or returns 'Layer'."""
    try:
        import arcpy
        # If CAD drawing dataset, check child Polyline or Polygon
        if is_cad_drawing_dataset(dataset):
            children = get_cad_child_feature_classes(dataset, ["Polyline", "Polygon"])
            if children:
                dataset = children[0]

        fields = [f.name for f in arcpy.ListFields(dataset)]
        candidates = ["Layer", "LAYER", "CadLayer", "CADLAYER", "LAYER_NAME", "LayerName"]
        for c in candidates:
            for f in fields:
                if f.lower() == c.lower():
                    return f
        # Fallback to first text field
        for f in arcpy.ListFields(dataset):
            if f.type.lower() in ("string", "text"):
                return f.name
    except Exception:
        pass
    return "Layer"


def get_dataset_cad_layers(dataset: Any, layer_field: Optional[str] = None) -> List[str]:
    """
    Returns a sorted list of unique CAD layer names found in the dataset.
    Works for both CAD Drawing Datasets and standard feature layers/classes.
    """
    cad_layers = set()
    try:
        import arcpy
        targets = []
        if is_cad_drawing_dataset(dataset):
            targets = get_cad_child_feature_classes(dataset, ["Polygon", "Polyline", "Point"])
        else:
            targets = [dataset]

        for target in targets:
            actual_field = layer_field or auto_detect_layer_field(target)
            f_names = [f.name.lower() for f in arcpy.ListFields(target)]
            if actual_field.lower() not in f_names:
                continue

            with arcpy.da.SearchCursor(target, [actual_field]) as cursor:
                for row in cursor:
                    if row[0] is not None:
                        val = str(row[0]).strip()
                        if val:
                            cad_layers.add(val)
    except Exception:
        pass

    return sorted(list(cad_layers))


def extract_features_by_layer(
    dataset: Any,
    layer_field: Optional[str] = None,
    target_layer: Optional[str] = None,
) -> Tuple[Dict[str, Dict[Any, Any]], str, Optional[Any]]:
    """
    Extracts features grouped by CAD layer.
    Returns:
        (features_by_layer, actual_layer_field, spatial_reference)
    where features_by_layer is {layer_name: {fid: arcpy.Geometry}}.
    """
    import arcpy

    sr = get_dataset_spatial_reference(dataset)
    targets = []
    if is_cad_drawing_dataset(dataset):
        # Prioritize geometry feature classes (Polygon, Polyline, Point)
        targets = get_cad_child_feature_classes(dataset, ["Polygon", "Polyline", "Point"])
    else:
        targets = [dataset]

    features_by_layer: Dict[str, Dict[Any, Any]] = {}
    actual_layer_field = "Layer"

    target_layer_clean = None
    if target_layer and target_layer.strip().lower() not in ("all layers", "(all detected layers)", "all", ""):
        target_layer_clean = target_layer.strip().lower()

    global_oid_counter = 1

    for target in targets:
        curr_field = layer_field or auto_detect_layer_field(target)
        actual_layer_field = curr_field

        f_names = [f.name.lower() for f in arcpy.ListFields(target)]
        has_layer_field = curr_field.lower() in f_names

        fields_to_read = ["OID@", "SHAPE@"]
        if has_layer_field:
            fields_to_read.append(curr_field)

        try:
            with arcpy.da.SearchCursor(target, fields_to_read) as cursor:
                for row in cursor:
                    orig_oid = row[0]
                    shp = row[1]
                    if not shp:
                        continue

                    if has_layer_field and len(row) > 2 and row[2] is not None:
                        l_name = str(row[2]).strip()
                        if not l_name:
                            l_name = "0"
                    else:
                        # Fallback to feature class name
                        l_name = os.path.basename(str(target))

                    # If filtering by specific target layer
                    if target_layer_clean and l_name.strip().lower() != target_layer_clean:
                        continue

                    if l_name not in features_by_layer:
                        features_by_layer[l_name] = {}

                    # Ensure unique FID within the layer dictionary
                    unique_fid = orig_oid if orig_oid not in features_by_layer[l_name] else global_oid_counter
                    features_by_layer[l_name][unique_fid] = shp
                    global_oid_counter += 1
        except Exception:
            continue

    return features_by_layer, actual_layer_field, sr

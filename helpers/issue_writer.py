# -*- coding: utf-8 -*-
"""
Issue Writer.
Exports QCIssue objects into ArcGIS Geodatabase Feature Datasets and Feature Classes
for direct visual inspection, defect navigation, and editing in ArcGIS Pro.
"""

import os
from typing import List, Optional, Any, Dict, Tuple
from .models.qc_issue import QCIssue, CheckID, Severity


# The canonical 10 Geometry & Topology QC checks
GEOMETRY_10_CHECKS: List[Tuple[str, str, str]] = [
    (CheckID.CHK_INVALID_GEOM, "QC01_Invalid_Geometries", "Invalid Geometry"),
    (CheckID.CHK_OVERLAP, "QC02_Overlaps", "Polygon Overlaps"),
    (CheckID.CHK_DUPLICATE, "QC03_Duplicate_Geometries", "Duplicate Geometries"),
    (CheckID.CHK_GAP, "QC04_Enclosed_Gaps", "Enclosed Gaps"),
    (CheckID.CHK_MULTIPART, "QC05_Multipart_Features", "Multipart Features"),
    (CheckID.CHK_SHORT_SEG, "QC06_Short_Segments", "Short Segments"),
    (CheckID.CHK_ANGLE, "QC07_Sharp_Angles", "Sharp Angles"),
    (CheckID.CHK_SNAP, "QC08_Snap_Issues", "Snap Issues"),
    (CheckID.CHK_REDUNDANT, "QC09_Redundant_Vertices", "Redundant Vertices"),
    (CheckID.CHK_JUNCTION, "QC10_Missing_Junctions", "Missing Junctions"),
]


def get_default_geodatabase() -> str:
    """
    Resolves the default File Geodatabase (.gdb) in the current environment:
    1. Active ArcGIS Pro project defaultGeodatabase (when running inside ArcGIS Pro)
    2. arcpy.env.workspace (if configured as a .gdb)
    3. arcpy.env.scratchGDB
    4. User Documents ArcGIS Default.gdb
    """
    try:
        import arcpy

        # 1. Check active ArcGIS Pro project default geodatabase
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            if aprx and getattr(aprx, "defaultGeodatabase", None):
                def_gdb = aprx.defaultGeodatabase
                if arcpy.Exists(def_gdb):
                    return def_gdb
        except Exception:
            pass

        # 2. Check current workspace environment
        if arcpy.env.workspace and arcpy.env.workspace.lower().endswith(".gdb") and arcpy.Exists(arcpy.env.workspace):
            return arcpy.env.workspace

        # 3. Check scratchGDB
        if arcpy.env.scratchGDB and arcpy.Exists(arcpy.env.scratchGDB):
            return arcpy.env.scratchGDB

        # 4. Check user Documents/ArcGIS/Projects or Default.gdb
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents", "ArcGIS")
        doc_gdb = os.path.join(docs_dir, "Default.gdb")
        if arcpy.Exists(doc_gdb):
            return doc_gdb

        # Fallback: create a Default_CAD_QC.gdb in temp folder
        temp_dir = os.environ.get("TEMP", "C:/Temp")
        fallback_gdb = os.path.join(temp_dir, "CAD_QC_Default.gdb")
        if not arcpy.Exists(fallback_gdb):
            arcpy.management.CreateFileGDB(temp_dir, "CAD_QC_Default.gdb")
        return fallback_gdb

    except Exception:
        return ""


def write_issues_to_feature_class(
    issues: List[QCIssue],
    output_feature_class: str,
    spatial_reference: Optional[Any] = None,
    progress_callback: Optional[Any] = None,
    allow_empty: bool = False,
) -> Optional[str]:
    """
    Creates a Point Feature Class representing QC issues with standardized attribute schema.
    If allow_empty is True, creates the empty feature class even if issues list is empty.
    """
    if not issues and not allow_empty:
        return None

    try:
        import arcpy
    except ImportError:
        return None

    def notify(msg: str):
        if progress_callback:
            progress_callback(msg)

    out_folder = os.path.dirname(output_feature_class)
    out_name = os.path.basename(output_feature_class)

    # Determine spatial reference
    sr = spatial_reference
    if sr is None:
        sr = arcpy.SpatialReference(3857)  # Web Mercator default if not provided

    # Overwrite if exists
    if arcpy.Exists(output_feature_class):
        try:
            arcpy.management.Delete(output_feature_class)
        except Exception:
            pass

    # Create empty point feature class
    arcpy.management.CreateFeatureclass(
        out_path=out_folder,
        out_name=out_name,
        geometry_type="POINT",
        spatial_reference=sr,
    )

    # Add attribute fields (batch optimized)
    fields_spec = [
        ["ISSUE_ID", "LONG", "Issue ID", None, None, None],
        ["CHECK_ID", "TEXT", "Check ID", 50, None, None],
        ["ISSUE_TYPE", "TEXT", "Issue Type", 50, None, None],
        ["SEVERITY", "TEXT", "Severity", 20, None, None],
        ["LAYER_NAME", "TEXT", "CAD Layer", 100, None, None],
        ["FEATURE_OID", "TEXT", "Feature OID", 50, None, None],
        ["RELATED_OID", "TEXT", "Related OID", 50, None, None],
        ["PROPERTY", "TEXT", "Property", 50, None, None],
        ["EXPECTED", "TEXT", "Expected Value", 100, None, None],
        ["ACTUAL", "TEXT", "Actual Value", 100, None, None],
        ["MEASURE", "DOUBLE", "Measurement", None, None, None],
        ["UNIT", "TEXT", "Unit", 20, None, None],
        ["DETAIL", "TEXT", "Details", 500, None, None],
    ]
    try:
        arcpy.management.AddFields(output_feature_class, fields_spec)
    except Exception:
        for f in fields_spec:
            fname, ftype, _, flen, _, _ = f
            if flen:
                arcpy.management.AddField(output_feature_class, fname, ftype, field_length=flen)
            else:
                arcpy.management.AddField(output_feature_class, fname, ftype)

    if issues:
        insert_fields = [
            "SHAPE@XY", "ISSUE_ID", "CHECK_ID", "ISSUE_TYPE", "SEVERITY", "LAYER_NAME",
            "FEATURE_OID", "RELATED_OID", "PROPERTY", "EXPECTED", "ACTUAL", "MEASURE", "UNIT", "DETAIL"
        ]

        with arcpy.da.InsertCursor(output_feature_class, insert_fields) as cursor:
            for iss in issues:
                xy = (0.0, 0.0)
                if iss.location:
                    xy = (iss.location[0], iss.location[1])
                elif iss.geometry and hasattr(iss.geometry, "trueCentroid"):
                    xy = (iss.geometry.trueCentroid.X, iss.geometry.trueCentroid.Y)
                elif iss.geometry and hasattr(iss.geometry, "firstPoint"):
                    xy = (iss.geometry.firstPoint.X, iss.geometry.firstPoint.Y)

                row = [
                    xy,
                    iss.issue_id,
                    (iss.check_id or "")[:50],
                    (iss.issue_type or "")[:50],
                    (iss.severity or "")[:20],
                    (iss.layer_name or "")[:100],
                    str(iss.object_id or "")[:50] if iss.object_id is not None else "",
                    str(iss.related_object_id or "")[:50] if iss.related_object_id is not None else "",
                    (iss.property_name or "")[:50],
                    str(iss.expected_value or "")[:100] if iss.expected_value is not None else "",
                    str(iss.actual_value or "")[:100] if iss.actual_value is not None else "",
                    iss.measurement if iss.measurement is not None else 0.0,
                    (iss.unit or "")[:20],
                    (iss.details or "")[:500],
                ]
                cursor.insertRow(row)

    return output_feature_class


def export_qc_errors_to_geodatabase_dataset(
    issues: List[QCIssue],
    gdb_path: Optional[str] = None,
    dataset_name: str = "CAD_Geometry_QC_Errors",
    spatial_reference: Optional[Any] = None,
    create_all_ten: bool = True,
    add_to_map: bool = True,
    progress_callback: Optional[Any] = None,
) -> Dict[str, str]:
    """
    Exports QC issues into a dedicated Feature Dataset inside a File Geodatabase.
    Creates individual Feature Classes for each of the 10 Geometry QC checks,
    plus a master 'QC_All_Errors' layer.
    
    Returns a dictionary of {layer_name: feature_class_path}.
    """
    try:
        import arcpy
    except ImportError:
        return {}

    def notify(msg: str):
        if progress_callback:
            progress_callback(msg)

    # 1. Resolve Target Geodatabase
    target_gdb = gdb_path or get_default_geodatabase()
    if not target_gdb or not arcpy.Exists(target_gdb):
        notify(f"Geodatabase '{target_gdb}' not found; resolving fallback...")
        target_gdb = get_default_geodatabase()

    notify(f"Target Geodatabase: {target_gdb}")

    # 2. Determine Spatial Reference
    sr = spatial_reference
    if sr is None:
        sr = arcpy.SpatialReference(3857)

    # 3. Create or access Feature Dataset
    clean_ds_name = arcpy.ValidateTableName(dataset_name, target_gdb)
    dataset_path = os.path.join(target_gdb, clean_ds_name)

    if not arcpy.Exists(dataset_path):
        notify(f"Creating Feature Dataset '{clean_ds_name}' in '{target_gdb}'...")
        arcpy.management.CreateFeatureDataset(
            out_dataset_path=target_gdb,
            out_name=clean_ds_name,
            spatial_reference=sr,
        )
    else:
        notify(f"Using existing Feature Dataset '{clean_ds_name}'...")

    created_classes: Dict[str, str] = {}

    # 4. Group issues by check_id
    issues_by_check: Dict[str, List[QCIssue]] = {}
    for iss in issues:
        issues_by_check.setdefault(iss.check_id, []).append(iss)

    # 5. Export each of the 10 Geometry QC Checks
    for cid, fc_base_name, check_title in GEOMETRY_10_CHECKS:
        chk_issues = issues_by_check.get(cid, [])
        if not chk_issues and not create_all_ten:
            continue

        fc_path = os.path.join(dataset_path, fc_base_name)
        write_issues_to_feature_class(
            issues=chk_issues,
            output_feature_class=fc_path,
            spatial_reference=sr,
            allow_empty=True,
        )
        created_classes[fc_base_name] = fc_path
        notify(f"  • {fc_base_name} ({check_title}): {len(chk_issues)} error(s)")

    # 6. Check for Reserved System Layer 0 issues
    reserved_issues = issues_by_check.get(CheckID.CHK_RESERVED_LAYER, [])
    if reserved_issues:
        fc_r0 = os.path.join(dataset_path, "QC11_Reserved_Layer_0")
        write_issues_to_feature_class(
            issues=reserved_issues,
            output_feature_class=fc_r0,
            spatial_reference=sr,
            allow_empty=False,
        )
        created_classes["QC11_Reserved_Layer_0"] = fc_r0
        notify(f"  • QC11_Reserved_Layer_0: {len(reserved_issues)} issue(s)")

    # 7. Create master combined layer 'QC_All_Errors'
    if issues or create_all_ten:
        fc_all = os.path.join(dataset_path, "QC_All_Errors")
        write_issues_to_feature_class(
            issues=issues,
            output_feature_class=fc_all,
            spatial_reference=sr,
            allow_empty=True,
        )
        created_classes["QC_All_Errors"] = fc_all
        notify(f"  • QC_All_Errors (Combined): {len(issues)} total issue(s)")

    # 8. Optionally add populated feature classes to active ArcGIS Pro Map
    if add_to_map:
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            active_map = getattr(aprx, "activeMap", None)
            if active_map:
                for fc_name, fc_p in created_classes.items():
                    # Only add classes with features or the master layer to prevent empty clutter
                    cnt = int(arcpy.management.GetCount(fc_p)[0]) if arcpy.Exists(fc_p) else 0
                    if cnt > 0 or fc_name == "QC_All_Errors":
                        try:
                            active_map.addDataFromPath(fc_p)
                            notify(f"Added layer '{fc_name}' to active map.")
                        except Exception:
                            pass
        except Exception:
            # Running outside ArcGIS Pro UI or standalone script
            pass

    return created_classes

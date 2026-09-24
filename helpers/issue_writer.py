# -*- coding: utf-8 -*-
"""
Issue Writer.
Exports QCIssue objects into:
1. Pure descriptive ArcGIS Standalone Tables (non-spatial, no Shape column).
2. Dedicated ArcGIS Feature Classes grouped by geometry check/error type.
"""

import os
from typing import List, Optional, Any, Dict, Tuple
from .models.qc_issue import QCIssue, CheckID, Severity


# All Geometry QC checks mapped to dedicated Feature Class names and titles
ALL_GEOMETRY_CHECKS: List[Tuple[str, str, str]] = [
    # Polygon & General Geometry Checks
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
    # Line QC Checks
    (CheckID.CHK_LINE_INVALID, "QC11_Line_Invalid", "Line Invalid Geometries"),
    (CheckID.CHK_LINE_CLOSURE, "QC12_Line_Closure_Issues", "Polyline Closure Issues"),
    (CheckID.CHK_LINE_DANGLE, "QC13_Line_Dangles", "Line Dangles"),
    (CheckID.CHK_LINE_OVERLAP, "QC14_Line_Overlaps", "Line Overlaps"),
    (CheckID.CHK_LINE_SELF_INTERSECT, "QC15_Line_Self_Intersections", "Line Self Intersections"),
    (CheckID.CHK_LINE_DISCONNECTED, "QC16_Line_Disconnected", "Disconnected Lines"),
    (CheckID.CHK_LINE_SHORT_SEG, "QC17_Line_Short_Segments", "Line Short Segments"),
    (CheckID.CHK_LINE_ANGLE, "QC18_Line_Sharp_Angles", "Line Sharp Angles"),
    (CheckID.CHK_LINE_REDUNDANT, "QC19_Line_Redundant_Vertices", "Line Redundant Vertices"),
    (CheckID.CHK_LINE_SNAP, "QC20_Line_Snap_Issues", "Line Snap Issues"),
    (CheckID.CHK_LINE_JUNCTION, "QC21_Line_Missing_Junctions", "Line Missing Junctions"),
    (CheckID.CHK_LINE_DUPLICATE, "QC22_Line_Duplicates", "Line Duplicates"),
    # Point QC Checks
    (CheckID.CHK_PT_INVALID, "QC23_Point_Invalid", "Point Invalid"),
    (CheckID.CHK_PT_DUPLICATE, "QC24_Point_Duplicates", "Point Duplicates"),
    (CheckID.CHK_PT_NEAR_DUPLICATE, "QC25_Point_Near_Duplicates", "Point Near Duplicates"),
    (CheckID.CHK_PT_DISTRIBUTION, "QC26_Point_Distribution", "Point Distribution"),
    (CheckID.CHK_PT_CROSS_LAYER, "QC27_Point_Cross_Layer", "Point Cross Layer"),
]

GEOMETRY_10_CHECKS: List[Tuple[str, str, str]] = ALL_GEOMETRY_CHECKS[:10]
GEOMETRY_CHECK_IDS = {cid for cid, _, _ in ALL_GEOMETRY_CHECKS}


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

        # 5. Fallback: Create CAD_QC_Default.gdb in temp directory
        import tempfile
        temp_dir = tempfile.gettempdir()
        fallback_gdb = os.path.join(temp_dir, "CAD_QC_Default.gdb")
        if not arcpy.Exists(fallback_gdb):
            arcpy.management.CreateFileGDB(temp_dir, "CAD_QC_Default.gdb")
        return fallback_gdb

    except Exception:
        return ""


def get_or_create_reports_gdb(reports_folder: str, gdb_name: str = "CAD_QC_Results.gdb") -> str:
    """
    Creates or returns a File Geodatabase inside the reports output folder.
    Ensures all QC feature classes and tables are saved directly alongside the reports.
    """
    os.makedirs(reports_folder, exist_ok=True)
    gdb_path = os.path.join(reports_folder, gdb_name)
    try:
        import arcpy
        if not arcpy.Exists(gdb_path):
            arcpy.management.CreateFileGDB(reports_folder, gdb_name)
    except Exception:
        os.makedirs(gdb_path, exist_ok=True)

    return os.path.abspath(gdb_path)


def write_issues_to_table(
    issues: List[QCIssue],
    output_table: str,
    progress_callback: Optional[Any] = None,
    allow_empty: bool = True,
) -> Optional[str]:
    """
    Creates an ArcGIS Standalone Table (non-spatial, no Shape column)
    representing all QC issues (Standards Comparison & Geometry QC).
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

    out_folder = os.path.dirname(output_table) or "."
    out_name = os.path.basename(output_table)

    # Overwrite if exists
    if arcpy.Exists(output_table):
        try:
            arcpy.management.Delete(output_table)
        except Exception:
            pass

    # Create empty standalone table
    arcpy.management.CreateTable(
        out_path=out_folder,
        out_name=out_name,
    )

    # Add attribute fields (batch optimized)
    fields_spec = [
        ["ISSUE_ID", "LONG", "Issue ID", None, None, None],
        ["CHECK_ID", "TEXT", "Check ID", 50, None, None],
        ["ISSUE_TYPE", "TEXT", "Issue Type", 50, None, None],
        ["SEVERITY", "TEXT", "Severity", 20, None, None],
        ["SOURCE", "TEXT", "Source", 30, None, None],
        ["LAYER_NAME", "TEXT", "CAD Layer", 100, None, None],
        ["GEOM_TYPE", "TEXT", "Geometry Type", 50, None, None],
        ["FEATURE_OID", "TEXT", "Feature OID", 50, None, None],
        ["RELATED_OID", "TEXT", "Related OID", 50, None, None],
        ["PROPERTY", "TEXT", "Property", 50, None, None],
        ["EXPECTED", "TEXT", "Expected Value", 100, None, None],
        ["ACTUAL", "TEXT", "Actual Value", 100, None, None],
        ["MEASURE", "DOUBLE", "Measurement", None, None, None],
        ["THRESHOLD", "DOUBLE", "Threshold", None, None, None],
        ["UNIT", "TEXT", "Unit", 20, None, None],
        ["DETAIL", "TEXT", "Details", 500, None, None],
    ]
    try:
        arcpy.management.AddFields(output_table, fields_spec)
    except Exception:
        for f in fields_spec:
            fname, ftype, _, flen, _, _ = f
            if flen:
                arcpy.management.AddField(output_table, fname, ftype, field_length=flen)
            else:
                arcpy.management.AddField(output_table, fname, ftype)

    if issues:
        insert_fields = [
            "ISSUE_ID", "CHECK_ID", "ISSUE_TYPE", "SEVERITY", "SOURCE",
            "LAYER_NAME", "GEOM_TYPE", "FEATURE_OID", "RELATED_OID", "PROPERTY",
            "EXPECTED", "ACTUAL", "MEASURE", "THRESHOLD", "UNIT", "DETAIL"
        ]
        with arcpy.da.InsertCursor(output_table, insert_fields) as cursor:
            for iss in issues:
                row = [
                    iss.issue_id,
                    (iss.check_id or "")[:50],
                    (iss.issue_type or "")[:50],
                    (iss.severity or "")[:20],
                    (iss.source or "")[:30],
                    (iss.layer_name or "")[:100],
                    (iss.geometry_type or "")[:50],
                    str(iss.object_id or "")[:50] if iss.object_id is not None else "",
                    str(iss.related_object_id or "")[:50] if iss.related_object_id is not None else "",
                    (iss.property_name or "")[:50],
                    str(iss.expected_value or "")[:100] if iss.expected_value is not None else "",
                    str(iss.actual_value or "")[:100] if iss.actual_value is not None else "",
                    iss.measurement if iss.measurement is not None else 0.0,
                    iss.threshold if iss.threshold is not None else 0.0,
                    (iss.unit or "")[:20],
                    (iss.details or "")[:500],
                ]
                cursor.insertRow(row)

    return output_table


def get_parent_gdb(path: str) -> Optional[str]:
    """Finds the containing .gdb or .sde folder path if path is inside a geodatabase."""
    curr = os.path.abspath(path)
    while curr and curr != os.path.dirname(curr):
        if curr.lower().endswith(".gdb") or curr.lower().endswith(".sde"):
            return curr
        curr = os.path.dirname(curr)
    return None


def delete_conflicting_feature_classes(target_gdb: str, fc_name: str, keep_path: Optional[str] = None):
    """
    Deletes any feature class with fc_name anywhere in target_gdb to avoid
    ArcGIS ERROR 002851 (names must be unique across the entire geodatabase).
    """
    try:
        import arcpy
        arcpy.env.overwriteOutput = True

        # Check direct path at GDB root
        root_path = os.path.join(target_gdb, fc_name)
        if arcpy.Exists(root_path):
            if not keep_path or os.path.abspath(root_path).lower() != os.path.abspath(keep_path).lower():
                try:
                    arcpy.management.Delete(root_path)
                except Exception:
                    pass

        # Check all datasets and feature classes in target_gdb using da.Walk
        if hasattr(arcpy, "da") and hasattr(arcpy.da, "Walk"):
            for dirpath, _, filenames in arcpy.da.Walk(target_gdb, datatype="FeatureClass"):
                for fn in filenames:
                    if fn.lower() == fc_name.lower():
                        full_p = os.path.join(dirpath, fn)
                        if not keep_path or os.path.abspath(full_p).lower() != os.path.abspath(keep_path).lower():
                            try:
                                arcpy.management.Delete(full_p)
                            except Exception:
                                pass
    except Exception:
        pass


def write_issues_to_feature_class(
    issues: List[QCIssue],
    output_feature_class: str,
    geometry_type: str = "POINT",
    spatial_reference: Optional[Any] = None,
    progress_callback: Optional[Any] = None,
    allow_empty: bool = False,
) -> Optional[str]:
    """
    Creates a Feature Class representing QC issues with standardized attribute schema.
    Supports POINT, POLYLINE, and POLYGON geometries.
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

    out_folder = os.path.dirname(output_feature_class) or "."
    out_name = os.path.basename(output_feature_class)

    # Determine spatial reference
    sr = spatial_reference
    if sr is None:
        sr = arcpy.SpatialReference(3857)

    # Overwrite if exists
    arcpy.env.overwriteOutput = True
    if arcpy.Exists(output_feature_class):
        try:
            arcpy.management.Delete(output_feature_class)
        except Exception:
            pass

    # Ensure no conflicting feature class with same name exists anywhere in parent GDB
    parent_gdb = get_parent_gdb(out_folder)
    if parent_gdb and arcpy.Exists(parent_gdb):
        delete_conflicting_feature_classes(parent_gdb, out_name, keep_path=output_feature_class)

    # Create empty feature class
    arcpy.management.CreateFeatureclass(
        out_path=out_folder,
        out_name=out_name,
        geometry_type=geometry_type.upper(),
        spatial_reference=sr,
    )

    # Add attribute fields (batch optimized)
    fields_spec = [
        ["ISSUE_ID", "LONG", "Issue ID", None, None, None],
        ["CHECK_ID", "TEXT", "Check ID", 50, None, None],
        ["ISSUE_TYPE", "TEXT", "Issue Type", 50, None, None],
        ["SEVERITY", "TEXT", "Severity", 20, None, None],
        ["SOURCE", "TEXT", "Source", 30, None, None],
        ["LAYER_NAME", "TEXT", "CAD Layer", 100, None, None],
        ["GEOM_TYPE", "TEXT", "Geometry Type", 50, None, None],
        ["FEATURE_OID", "TEXT", "Feature OID", 50, None, None],
        ["RELATED_OID", "TEXT", "Related OID", 50, None, None],
        ["PROPERTY", "TEXT", "Property", 50, None, None],
        ["EXPECTED", "TEXT", "Expected Value", 100, None, None],
        ["ACTUAL", "TEXT", "Actual Value", 100, None, None],
        ["MEASURE", "DOUBLE", "Measurement", None, None, None],
        ["THRESHOLD", "DOUBLE", "Threshold", None, None, None],
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
        is_point = geometry_type.upper() == "POINT"
        shape_field = "SHAPE@XY" if is_point else "SHAPE@"

        insert_fields = [
            shape_field, "ISSUE_ID", "CHECK_ID", "ISSUE_TYPE", "SEVERITY", "SOURCE",
            "LAYER_NAME", "GEOM_TYPE", "FEATURE_OID", "RELATED_OID", "PROPERTY",
            "EXPECTED", "ACTUAL", "MEASURE", "THRESHOLD", "UNIT", "DETAIL"
        ]

        with arcpy.da.InsertCursor(output_feature_class, insert_fields) as cursor:
            for iss in issues:
                geom_val = None
                if is_point:
                    xy = (0.0, 0.0)
                    if iss.location:
                        xy = (iss.location[0], iss.location[1])
                    elif iss.geometry and hasattr(iss.geometry, "trueCentroid"):
                        xy = (iss.geometry.trueCentroid.X, iss.geometry.trueCentroid.Y)
                    elif iss.geometry and hasattr(iss.geometry, "firstPoint"):
                        xy = (iss.geometry.firstPoint.X, iss.geometry.firstPoint.Y)
                    geom_val = xy
                else:
                    if iss.geometry:
                        geom_val = iss.geometry
                    elif iss.location:
                        geom_val = arcpy.PointGeometry(arcpy.Point(iss.location[0], iss.location[1]), sr)

                row = [
                    geom_val,
                    iss.issue_id,
                    (iss.check_id or "")[:50],
                    (iss.issue_type or "")[:50],
                    (iss.severity or "")[:20],
                    (iss.source or "")[:30],
                    (iss.layer_name or "")[:100],
                    (iss.geometry_type or "")[:50],
                    str(iss.object_id or "")[:50] if iss.object_id is not None else "",
                    str(iss.related_object_id or "")[:50] if iss.related_object_id is not None else "",
                    (iss.property_name or "")[:50],
                    str(iss.expected_value or "")[:100] if iss.expected_value is not None else "",
                    str(iss.actual_value or "")[:100] if iss.actual_value is not None else "",
                    iss.measurement if iss.measurement is not None else 0.0,
                    iss.threshold if iss.threshold is not None else 0.0,
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
    create_all_ten: bool = False,
    add_to_map: bool = True,
    progress_callback: Optional[Any] = None,
) -> Dict[str, str]:
    """
    Exports QC issues into dedicated Feature Classes in a File Geodatabase.
    - Each geometry error type gets its own Feature Class (only created if errors exist!).
    - Also creates a master standalone table 'CAD_QC_All_Issues_Table' (descriptive, no Shape column).
    
    Returns a dictionary of {layer_name: path}.
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
    arcpy.env.overwriteOutput = True

    # 2. Determine Spatial Reference
    sr = spatial_reference
    if sr is None:
        sr = arcpy.SpatialReference(3857)

    # 3. Create or access Feature Dataset
    clean_ds_name = arcpy.ValidateTableName(dataset_name, target_gdb)
    dataset_path = os.path.join(target_gdb, clean_ds_name)

    # Clean up legacy dataset if it exists in target_gdb (e.g. CAD_QC_Errors from previous version)
    legacy_dataset = os.path.join(target_gdb, "CAD_QC_Errors")
    if clean_ds_name.lower() != "cad_qc_errors" and arcpy.Exists(legacy_dataset):
        try:
            arcpy.management.Delete(legacy_dataset)
        except Exception:
            pass

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

    # 5. Export each Geometry QC check into its own Feature Class
    for cid, fc_base_name, check_title in ALL_GEOMETRY_CHECKS:
        chk_issues = issues_by_check.get(cid, [])
        # Only create feature classes for checks that actually have issues
        if not chk_issues and not create_all_ten:
            fc_path = os.path.join(dataset_path, fc_base_name)
            if arcpy.Exists(fc_path):
                try:
                    arcpy.management.Delete(fc_path)
                except Exception:
                    pass
            continue

        # Determine geometry type based on issues
        geom_type = "POINT"
        for i in chk_issues:
            if i.geometry and hasattr(i.geometry, "type"):
                t = i.geometry.type.upper()
                if t in ("POLYGON", "POLYLINE", "POINT"):
                    geom_type = t
                    break

        fc_path = os.path.join(dataset_path, fc_base_name)
        write_issues_to_feature_class(
            issues=chk_issues,
            output_feature_class=fc_path,
            geometry_type=geom_type,
            spatial_reference=sr,
            allow_empty=True,
        )
        created_classes[fc_base_name] = fc_path
        notify(f"  • Feature Class '{fc_base_name}' ({check_title}): {len(chk_issues)} error(s)")

    # 6. Check for Reserved System Layer 0 issues
    reserved_issues = issues_by_check.get(CheckID.CHK_RESERVED_LAYER, [])
    fc_r0 = os.path.join(dataset_path, "QC11_Reserved_Layer_0")
    if reserved_issues:
        write_issues_to_feature_class(
            issues=reserved_issues,
            output_feature_class=fc_r0,
            geometry_type="POINT",
            spatial_reference=sr,
            allow_empty=False,
        )
        created_classes["QC11_Reserved_Layer_0"] = fc_r0
        notify(f"  • Feature Class 'QC11_Reserved_Layer_0': {len(reserved_issues)} issue(s)")
    elif arcpy.Exists(fc_r0):
        try:
            arcpy.management.Delete(fc_r0)
        except Exception:
            pass

    # 7. Create master combined layer 'QC_All_Errors' if create_all_ten
    fc_all = os.path.join(dataset_path, "QC_All_Errors")
    if create_all_ten:
        write_issues_to_feature_class(
            issues=issues,
            output_feature_class=fc_all,
            geometry_type="POINT",
            spatial_reference=sr,
            allow_empty=True,
        )
        created_classes["QC_All_Errors"] = fc_all
        notify(f"  • Feature Class 'QC_All_Errors' (Combined): {len(issues)} total issue(s)")
    elif arcpy.Exists(fc_all):
        try:
            arcpy.management.Delete(fc_all)
        except Exception:
            pass

    # 8. Export all issues into a standalone descriptive Table (no Shape column)
    all_table_path = os.path.join(target_gdb, "CAD_QC_All_Issues_Table")
    write_issues_to_table(
        issues=issues,
        output_table=all_table_path,
        progress_callback=progress_callback,
    )
    created_classes["CAD_QC_All_Issues_Table"] = all_table_path
    notify(f"  • Standalone Table 'CAD_QC_All_Issues_Table': {len(issues)} total issue(s)")

    # 9. Optionally add populated feature classes and table to active ArcGIS Pro Map inside a Group Layer
    if add_to_map:
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            active_map = getattr(aprx, "activeMap", None)
            if active_map:
                # 9.1 Create or resolve Group Layer for geometry QC errors
                group_name = dataset_name.replace("_", " ")
                group_layer = None
                try:
                    # Remove any existing group layer with same name from previous runs
                    for lyr in active_map.listLayers():
                        if getattr(lyr, "isGroupLayer", False) and getattr(lyr, "name", "").lower() == group_name.lower():
                            try:
                                active_map.removeLayer(lyr)
                            except Exception:
                                pass

                    if hasattr(active_map, "createGroupLayer"):
                        group_layer = active_map.createGroupLayer(group_name)
                        notify(f"Created Group Layer '{group_name}' in active map.")
                except Exception:
                    group_layer = None

                # 9.2 Add each populated item
                for fc_name, fc_p in created_classes.items():
                    cnt = int(arcpy.management.GetCount(fc_p)[0]) if arcpy.Exists(fc_p) else 0
                    if cnt > 0:
                        try:
                            added_item = active_map.addDataFromPath(fc_p)
                            is_table = (fc_name == "CAD_QC_All_Issues_Table" or fc_p.lower().endswith("_table"))

                            # Add spatial layers into the Group Layer
                            if group_layer and not is_table and hasattr(active_map, "addLayerToGroup"):
                                target_lyr = added_item
                                if not target_lyr:
                                    for lyr in active_map.listLayers():
                                        if not getattr(lyr, "isGroupLayer", False) and getattr(lyr, "name", "") == fc_name:
                                            target_lyr = lyr
                                            break
                                if target_lyr:
                                    active_map.addLayerToGroup(group_layer, target_lyr, "BOTTOM")
                                    if hasattr(active_map, "removeLayer"):
                                        try:
                                            active_map.removeLayer(target_lyr)
                                        except Exception:
                                            pass
                                notify(f"Added '{fc_name}' into Group Layer '{group_name}'.")
                            else:
                                notify(f"Added '{fc_name}' to active map.")
                        except Exception:
                            pass
        except Exception:
            pass

    return created_classes

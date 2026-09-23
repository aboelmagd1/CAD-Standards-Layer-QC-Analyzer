# -*- coding: utf-8 -*-
"""
Issue Writer.
Exports QCIssue objects into an ArcGIS Feature Class (Shapefile or Geodatabase)
for direct visual inspection and issue navigation in ArcGIS Pro.
"""

import os
from typing import List, Optional, Any
from .models.qc_issue import QCIssue


def write_issues_to_feature_class(
    issues: List[QCIssue],
    output_feature_class: str,
    spatial_reference: Optional[Any] = None,
    progress_callback: Optional[Any] = None,
) -> Optional[str]:
    """
    Creates a Point Feature Class representing QC issues with standardized attribute schema.
    """
    if not issues:
        return None

    try:
        import arcpy
    except ImportError:
        return None

    def notify(msg: str):
        if progress_callback:
            progress_callback(msg)

    notify(f"Writing {len(issues)} QC issues to feature class: {output_feature_class}...")

    out_folder = os.path.dirname(output_feature_class)
    out_name = os.path.basename(output_feature_class)

    # Determine spatial reference
    sr = spatial_reference
    if sr is None:
        # Fallback to WGS84 or default
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

    # Add attribute fields
    fields_to_add = [
        ("ISSUE_ID", "LONG", 0),
        ("CHECK_ID", "TEXT", 50),
        ("ISSUE_TYPE", "TEXT", 50),
        ("SEVERITY", "TEXT", 20),
        ("LAYER_NAME", "TEXT", 100),
        ("FEATURE_OID", "TEXT", 50),
        ("RELATED_OID", "TEXT", 50),
        ("PROPERTY", "TEXT", 50),
        ("EXPECTED", "TEXT", 100),
        ("ACTUAL", "TEXT", 100),
        ("MEASURE", "DOUBLE", 0),
        ("UNIT", "TEXT", 20),
        ("DETAIL", "TEXT", 500),
    ]

    for fname, ftype, flen in fields_to_add:
        if flen > 0:
            arcpy.management.AddField(output_feature_class, fname, ftype, field_length=flen)
        else:
            arcpy.management.AddField(output_feature_class, fname, ftype)

    insert_fields = ["SHAPE@XY", "ISSUE_ID", "CHECK_ID", "ISSUE_TYPE", "SEVERITY", "LAYER_NAME",
                     "FEATURE_OID", "RELATED_OID", "PROPERTY", "EXPECTED", "ACTUAL", "MEASURE", "UNIT", "DETAIL"]

    with arcpy.da.InsertCursor(output_feature_class, insert_fields) as cursor:
        for iss in issues:
            # Determine XY coordinate
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
                iss.check_id[:50] if iss.check_id else "",
                iss.issue_type[:50] if iss.issue_type else "",
                iss.severity[:20] if iss.severity else "",
                iss.layer_name[:100] if iss.layer_name else "",
                str(iss.object_id)[:50] if iss.object_id is not None else "",
                str(iss.related_object_id)[:50] if iss.related_object_id is not None else "",
                iss.property_name[:50] if iss.property_name else "",
                str(iss.expected_value)[:100] if iss.expected_value is not None else "",
                str(iss.actual_value)[:100] if iss.actual_value is not None else "",
                iss.measurement if iss.measurement is not None else 0.0,
                iss.unit[:20] if iss.unit else "",
                iss.details[:500] if iss.details else "",
            ]
            cursor.insertRow(row)

    notify("Issue feature class created successfully.")
    return output_feature_class

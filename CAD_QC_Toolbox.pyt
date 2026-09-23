# -*- coding: utf-8 -*-
"""
CAD Standards & Layer QC Toolbox.
ArcGIS Pro Python Toolbox (.pyt) integrating:
1. CADReferenceComparisonQCTool (Reference-vs-Received CAD Comparison QC)
2. GeometryQCTool (Port of 10 geometry & topology checks from Geometry QC Analyzer)
"""

import sys
import os
from datetime import datetime

# Ensure helpers can be imported from current toolbox directory
toolbox_dir = os.path.dirname(os.path.abspath(__file__))
if toolbox_dir not in sys.path:
    sys.path.insert(0, toolbox_dir)

import arcpy

from helpers.models import QCResult, QCIssue, Severity, CheckID
from helpers.comparison import (
    build_reference_profile,
    run_cad_comparison,
    ComparisonConfig,
)
from helpers.geometry import (
    run_geometry_qc,
    GeometryQCConfig,
)
from helpers.reporting import (
    create_excel_report,
    create_html_report,
    create_text_report,
)
from helpers.issue_writer import (
    write_issues_to_feature_class,
    export_qc_errors_to_geodatabase_dataset,
    get_default_geodatabase,
)
from helpers.utilities import (
    auto_detect_layer_field,
    get_dataset_spatial_reference,
    extract_features_by_layer,
    get_dataset_cad_layers,
)


class Toolbox(object):
    def __init__(self):
        self.label = "CAD Standards & Layer QC Toolbox"
        self.alias = "cad_qc"
        self.description = (
            "Production-ready QA/QC toolbox for CAD-based urban planning & land subdivision. "
            "Includes Reference-Based CAD Comparison QC and standalone 10-check Geometry & Topology QC."
        )
        self.tools = [CADReferenceComparisonQCTool, GeometryQCTool]


class CADReferenceComparisonQCTool(object):
    def __init__(self):
        self.label = "CAD Reference-Based Comparison QC"
        self.description = (
            "Compares a Received CAD dataset against an Original/Reference CAD dataset. "
            "Learns the expected standards dynamically from the Reference CAD (layers, geometry composition, "
            "closure, colors, lineweights, linetypes) and detects discrepancies. 100% read-only."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        # 0: Reference Source
        p_ref = arcpy.Parameter(
            displayName="Reference CAD / Approved Dataset",
            name="reference_source",
            datatype=["GPFeatureLayer", "DEFeatureClass", "DECADDrawingDataset"],
            parameterType="Required",
            direction="Input",
        )

        # 1: Reference Layer Field
        p_ref_field = arcpy.Parameter(
            displayName="Reference Layer Field",
            name="reference_layer_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input",
        )
        p_ref_field.parameterDependencies = ["reference_source"]

        # 2: Received Source
        p_rec = arcpy.Parameter(
            displayName="Received CAD / Client Dataset",
            name="received_source",
            datatype=["GPFeatureLayer", "DEFeatureClass", "DECADDrawingDataset"],
            parameterType="Required",
            direction="Input",
        )

        # 3: Received Layer Field
        p_rec_field = arcpy.Parameter(
            displayName="Received Layer Field",
            name="received_layer_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input",
        )
        p_rec_field.parameterDependencies = ["received_source"]

        # 4: Scope
        p_scope = arcpy.Parameter(
            displayName="Comparison Scope",
            name="scope",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        p_scope.filter.type = "ValueList"
        p_scope.filter.list = ["All Layers", "Polygon / Closed-Geometry Layers", "Custom Layer Selection"]
        p_scope.value = "All Layers"

        # 5: Dominant Geometry Threshold
        p_dom = arcpy.Parameter(
            displayName="Dominant Geometry Threshold (0.1 - 1.0)",
            name="dominant_threshold",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_dom.value = 0.50

        # 6: Closure Tolerance
        p_clos = arcpy.Parameter(
            displayName="Closure Tolerance (Map Units)",
            name="closure_tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_clos.value = 0.01

        # 7: Output Folder
        p_out = arcpy.Parameter(
            displayName="Output Folder for Reports",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input",
        )

        # 8: Options Category (Toggles)
        p_opt_counts = arcpy.Parameter(
            displayName="Compare Feature Counts",
            name="compare_feature_counts",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_opt_counts.value = True
        p_opt_counts.category = "Comparison Options"

        p_opt_geoms = arcpy.Parameter(
            displayName="Compare Geometry Composition & Detect Unexpected Types",
            name="compare_geometries",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_opt_geoms.value = True
        p_opt_geoms.category = "Comparison Options"

        p_opt_clos = arcpy.Parameter(
            displayName="Compare Polyline Closure",
            name="compare_closure",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_opt_clos.value = True
        p_opt_clos.category = "Comparison Options"

        p_opt_color = arcpy.Parameter(
            displayName="Compare CAD Colors",
            name="compare_color",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_opt_color.value = True
        p_opt_color.category = "Comparison Options"

        p_opt_lw = arcpy.Parameter(
            displayName="Compare CAD Lineweights",
            name="compare_lineweight",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_opt_lw.value = True
        p_opt_lw.category = "Comparison Options"

        p_opt_lt = arcpy.Parameter(
            displayName="Compare CAD Linetypes",
            name="compare_linetype",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_opt_lt.value = True
        p_opt_lt.category = "Comparison Options"

        p_opt_case = arcpy.Parameter(
            displayName="Case-Sensitive Layer Names",
            name="case_sensitive",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_opt_case.value = False
        p_opt_case.category = "Layer Name Normalization"

        p_opt_trim = arcpy.Parameter(
            displayName="Trim Layer Name Whitespace",
            name="trim_whitespace",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_opt_trim.value = True
        p_opt_trim.category = "Layer Name Normalization"

        # 16: Combined Workflow (Run Geometry QC on Received CAD)
        p_run_gqc = arcpy.Parameter(
            displayName="Run Geometry QC on Received CAD (Combined Workflow)",
            name="run_geometry_qc",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_run_gqc.value = False
        p_run_gqc.category = "Advanced / Combined Workflow"

        # 17: Reports Toggles
        p_rep_excel = arcpy.Parameter(
            displayName="Generate Excel Report (.xlsx)",
            name="generate_excel",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_rep_excel.value = True
        p_rep_excel.category = "Report Outputs"

        p_rep_html = arcpy.Parameter(
            displayName="Generate HTML Report (.html)",
            name="generate_html",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_rep_html.value = True
        p_rep_html.category = "Report Outputs"

        p_rep_txt = arcpy.Parameter(
            displayName="Generate Text Summary (.txt)",
            name="generate_text",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_rep_txt.value = True
        p_rep_txt.category = "Report Outputs"

        # 20: Optional Issue Feature Class
        p_out_fc = arcpy.Parameter(
            displayName="Output Issue Feature Class (Optional)",
            name="output_issue_fc",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Output",
        )
        p_out_fc.category = "Report Outputs"

        return [
            p_ref, p_ref_field, p_rec, p_rec_field, p_scope, p_dom, p_clos, p_out,
            p_opt_counts, p_opt_geoms, p_opt_clos, p_opt_color, p_opt_lw, p_opt_lt,
            p_opt_case, p_opt_trim, p_run_gqc, p_rep_excel, p_rep_html, p_rep_txt,
            p_out_fc
        ]

    def updateParameters(self, parameters):
        # Auto-detect layer field when reference dataset is selected
        if parameters[0].altered and parameters[0].value:
            if not parameters[1].value:
                parameters[1].value = auto_detect_layer_field(parameters[0].valueAsText)

        # Auto-detect layer field when received dataset is selected
        if parameters[2].altered and parameters[2].value:
            if not parameters[3].value:
                parameters[3].value = auto_detect_layer_field(parameters[2].valueAsText)

    def updateMessages(self, parameters):
        from helpers.validation import validate_cad_comparison_parameters
        validate_cad_comparison_parameters(parameters)

    def execute(self, parameters, messages):
        ref_source = parameters[0].valueAsText
        ref_layer_field = parameters[1].valueAsText or "Layer"
        rec_source = parameters[2].valueAsText
        rec_layer_field = parameters[3].valueAsText or "Layer"
        scope = parameters[4].valueAsText or "All Layers"
        dom_threshold = float(parameters[5].value or 0.50)
        closure_tol = float(parameters[6].value or 0.01)
        out_folder = parameters[7].valueAsText

        cmp_counts = bool(parameters[8].value)
        cmp_geoms = bool(parameters[9].value)
        cmp_closure = bool(parameters[10].value)
        cmp_color = bool(parameters[11].value)
        cmp_lw = bool(parameters[12].value)
        cmp_lt = bool(parameters[13].value)
        case_sensitive = bool(parameters[14].value)
        trim_ws = bool(parameters[15].value)
        run_gqc_on_rec = bool(parameters[16].value)

        gen_excel = bool(parameters[17].value)
        gen_html = bool(parameters[18].value)
        gen_txt = bool(parameters[19].value)
        out_issue_fc = parameters[20].valueAsText

        arcpy.AddMessage("=" * 60)
        arcpy.AddMessage("Starting CAD Reference-Based QC Analysis...")
        arcpy.AddMessage("=" * 60)

        config = ComparisonConfig(
            compare_layer_names=True,
            compare_feature_counts=cmp_counts,
            compare_geometry_types=cmp_geoms,
            compare_geometry_distribution=cmp_geoms,
            compare_closure=cmp_closure,
            compare_color=cmp_color,
            compare_linetype=cmp_lt,
            compare_lineweight=cmp_lw,
            detect_unexpected_features=cmp_geoms,
            closure_tolerance=closure_tol,
            dominant_threshold=dom_threshold,
            case_sensitive=case_sensitive,
            trim_whitespace=trim_ws,
            scope=scope,
        )

        def progress_notify(msg):
            arcpy.AddMessage(f"[QC] {msg}")

        # 1. Build Reference Profile
        ref_profile = build_reference_profile(
            reference_source=ref_source,
            layer_field_name=ref_layer_field,
            closure_tolerance=closure_tol,
            dominant_threshold=dom_threshold,
            case_sensitive=case_sensitive,
            trim_whitespace=trim_ws,
            progress_callback=progress_notify,
        )

        # 2. Run CAD Comparison
        qc_result = run_cad_comparison(
            reference_profile=ref_profile,
            received_source=rec_source,
            received_layer_field=rec_layer_field,
            config=config,
            progress_callback=progress_notify,
        )

        # 3. Optional Combined Workflow (Mode C): Run Geometry QC on Received dataset
        if run_gqc_on_rec:
            arcpy.AddMessage("[Combined Workflow] Running per-layer Geometry QC on Received dataset...")
            f_by_layer, _, _ = extract_features_by_layer(rec_source, rec_layer_field)
            qc_result.geometry_qc_run = True
            combined_summary = {}

            for lname, l_features in f_by_layer.items():
                arcpy.AddMessage(f"[Combined Workflow] Analyzing CAD Layer: {lname} ({len(l_features)} features)...")
                g_issues, g_summary = run_geometry_qc(
                    features=l_features,
                    layer_name=lname,
                    source="RECEIVED",
                    progress_callback=progress_notify,
                )
                for gi in g_issues:
                    gi.issue_id = len(qc_result.issues) + 1
                    qc_result.add_issue(gi)

                err_count = sum(1 for gi in g_issues if gi.severity == Severity.ERROR)
                warn_count = sum(1 for gi in g_issues if gi.severity == Severity.WARNING)
                qc_result.layer_geometry_qc_summaries[lname] = {
                    "feature_count": len(l_features),
                    "total_issues": len(g_issues),
                    "errors": err_count,
                    "warnings": warn_count,
                    "checks": {chk: info["count"] for chk, info in g_summary.items() if info["count"] > 0},
                }

                for chk, info in g_summary.items():
                    if chk not in combined_summary:
                        combined_summary[chk] = dict(info)
                    else:
                        combined_summary[chk]["count"] += info["count"]
                        if info["status"] == "ERROR":
                            combined_summary[chk]["status"] = "ERROR"
                        elif info["status"] == "WARNING" and combined_summary[chk]["status"] != "ERROR":
                            combined_summary[chk]["status"] = "WARNING"

            qc_result.geometry_qc_summary = combined_summary

        # 4. Generate Reports
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(out_folder, exist_ok=True)

        if gen_excel:
            excel_path = os.path.join(out_folder, f"CAD_QC_Report_{timestamp}.xlsx")
            create_excel_report(qc_result, excel_path)
            arcpy.AddMessage(f"[Report] Excel report generated: {excel_path}")

        if gen_html:
            html_path = os.path.join(out_folder, f"CAD_QC_Report_{timestamp}.html")
            create_html_report(qc_result, html_path)
            arcpy.AddMessage(f"[Report] HTML dashboard generated: {html_path}")

        if gen_txt:
            txt_path = os.path.join(out_folder, f"CAD_QC_Report_{timestamp}.txt")
            create_text_report(qc_result, txt_path)
            arcpy.AddMessage(f"[Report] Text summary generated: {txt_path}")

        # 5. Output Issue Feature Class
        if out_issue_fc:
            sr = get_dataset_spatial_reference(rec_source) or get_dataset_spatial_reference(ref_source)
            write_issues_to_feature_class(
                issues=qc_result.issues,
                output_feature_class=out_issue_fc,
                spatial_reference=sr,
                progress_callback=progress_notify,
            )
            arcpy.AddMessage(f"[Issues] Issue Feature Class created: {out_issue_fc}")

        if qc_result.geometry_qc_run and qc_result.issues:
            sr = get_dataset_spatial_reference(rec_source) or get_dataset_spatial_reference(ref_source)
            arcpy.AddMessage("[GDB Export] Exporting detected issues into Default Geodatabase Dataset 'CAD_QC_Errors'...")
            export_qc_errors_to_geodatabase_dataset(
                issues=qc_result.issues,
                gdb_path=None,
                dataset_name="CAD_QC_Errors",
                spatial_reference=sr,
                create_all_ten=True,
                add_to_map=True,
                progress_callback=progress_notify,
            )

        # Final Summary Notification
        n_errors = len(qc_result.issues_by_severity(Severity.ERROR))
        n_warnings = len(qc_result.issues_by_severity(Severity.WARNING))

        arcpy.AddMessage("=" * 60)
        arcpy.AddMessage(f"QC Completed. Total Issues: {len(qc_result.issues)} ({n_errors} Errors, {n_warnings} Warnings).")
        arcpy.AddMessage(f"Passed Layers: {qc_result.passed_layers_count()} / {len(qc_result.layer_statuses)}")
        arcpy.AddMessage("=" * 60)


class GeometryQCTool(object):
    def __init__(self):
        self.label = "Geometry & Topology QC Analyzer"
        self.description = (
            "Runs the complete suite of 10 geometry & topology checks ported from Geometry QC Analyzer: "
            "Invalid Geometries, Overlaps, Duplicates, Enclosed Gaps, Multipart, Short Segments, Angle Issues, "
            "Snap Issues, Redundant Vertices, and Missing Junctions. 100% read-only."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        # 0: Input Features
        p_in = arcpy.Parameter(
            displayName="Input Feature Class / CAD Drawing",
            name="input_features",
            datatype=["GPFeatureLayer", "DEFeatureClass", "DECADDrawingDataset"],
            parameterType="Required",
            direction="Input",
        )

        # 1: Layer Field
        p_layer_field = arcpy.Parameter(
            displayName="CAD Layer Field (Optional)",
            name="layer_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input",
        )
        p_layer_field.parameterDependencies = ["input_features"]

        # 2: Target CAD Layer
        p_target_layer = arcpy.Parameter(
            displayName="Target CAD Layer",
            name="target_layer",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        p_target_layer.filter.type = "ValueList"
        p_target_layer.filter.list = ["All Layers"]
        p_target_layer.value = "All Layers"

        # 3: Layer Display Name Label
        p_layer_name = arcpy.Parameter(
            displayName="Layer Display Name / Label",
            name="layer_name",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        p_layer_name.value = "GeometryQC"

        # 4: Short Segment Tolerance
        p_short = arcpy.Parameter(
            displayName="Short Segment Threshold (meters)",
            name="short_seg_tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_short.value = 0.10
        p_short.category = "Tolerances & Thresholds"

        # 5: Sharp Angle Threshold
        p_angle = arcpy.Parameter(
            displayName="Sharp Angle Threshold (degrees)",
            name="angle_tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_angle.value = 5.0
        p_angle.category = "Tolerances & Thresholds"

        # 6: Snap Tolerance
        p_snap = arcpy.Parameter(
            displayName="Snap Issue Threshold (meters)",
            name="snap_tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_snap.value = 0.01
        p_snap.category = "Tolerances & Thresholds"

        # 7: Redundant Vertex Threshold
        p_red = arcpy.Parameter(
            displayName="Redundant Vertex Angle Threshold (degrees)",
            name="redundant_vertex_tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_red.value = 179.9
        p_red.category = "Tolerances & Thresholds"

        # 8: Missing Junction Tolerance
        p_junc = arcpy.Parameter(
            displayName="Missing Junction Threshold (meters)",
            name="junction_tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_junc.value = 0.01
        p_junc.category = "Tolerances & Thresholds"

        # 9: Overlap Tolerance (Area)
        p_ov = arcpy.Parameter(
            displayName="Overlap Area Tolerance (m²)",
            name="overlap_tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_ov.value = 0.0001
        p_ov.category = "Tolerances & Thresholds"

        # 10: Enclosed Gap Tolerance (Area)
        p_gap = arcpy.Parameter(
            displayName="Enclosed Gap Area Tolerance (m²)",
            name="gap_tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        p_gap.value = 0.001
        p_gap.category = "Tolerances & Thresholds"

        # 11: Output Folder
        p_out = arcpy.Parameter(
            displayName="Output Folder for Reports",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input",
        )

        # 12-21: Individual Check Toggles
        chk_names = [
            ("check_invalid", "Check Invalid Geometries", True),
            ("check_overlap", "Check Overlaps", True),
            ("check_duplicate", "Check Duplicate Geometries", True),
            ("check_gap", "Check Enclosed Gaps", True),
            ("check_multipart", "Check Multipart Geometries", True),
            ("check_short_seg", "Check Short Segments", True),
            ("check_angle", "Check Sharp Angles", True),
            ("check_snap", "Check Snap Issues", True),
            ("check_redundant", "Check Redundant Vertices", True),
            ("check_junction", "Check Missing Junctions", True),
        ]
        toggles = []
        for name, disp, def_val in chk_names:
            p_chk = arcpy.Parameter(
                displayName=disp,
                name=name,
                datatype="GPBoolean",
                parameterType="Optional",
                direction="Input",
            )
            p_chk.value = def_val
            p_chk.category = "Enabled Checks (10 Checks)"
            toggles.append(p_chk)

        # 22-25: Reports and Output FC
        p_excel = arcpy.Parameter(
            displayName="Generate Excel Report",
            name="generate_excel",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_excel.value = True
        p_excel.category = "Report Outputs"

        p_html = arcpy.Parameter(
            displayName="Generate HTML Report",
            name="generate_html",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_html.value = True
        p_html.category = "Report Outputs"

        p_txt = arcpy.Parameter(
            displayName="Generate Text Summary",
            name="generate_text",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_txt.value = True
        p_txt.category = "Report Outputs"

        p_out_fc = arcpy.Parameter(
            displayName="Output Issue Feature Class (Optional)",
            name="output_issue_fc",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Output",
        )
        p_out_fc.category = "Report Outputs"

        # 26: Export 10 Error Types to Default GDB Dataset
        p_export_gdb = arcpy.Parameter(
            displayName="Export 10 Error Types to Default GDB Dataset",
            name="export_to_gdb",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_export_gdb.value = True
        p_export_gdb.category = "Geodatabase Dataset Export"

        # 27: Target Geodatabase
        p_target_gdb = arcpy.Parameter(
            displayName="Target Geodatabase (Leave empty for Default.gdb)",
            name="target_gdb",
            datatype="DEWorkspace",
            parameterType="Optional",
            direction="Input",
        )
        p_target_gdb.category = "Geodatabase Dataset Export"

        # 28: Feature Dataset Name
        p_ds_name = arcpy.Parameter(
            displayName="Feature Dataset Name",
            name="dataset_name",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        p_ds_name.value = "CAD_Geometry_QC_Errors"
        p_ds_name.category = "Geodatabase Dataset Export"

        # 29: Add Error Layers to Map
        p_add_map = arcpy.Parameter(
            displayName="Add Error Layers to Active Pro Map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p_add_map.value = True
        p_add_map.category = "Geodatabase Dataset Export"

        return [
            p_in, p_layer_field, p_target_layer, p_layer_name,
            p_short, p_angle, p_snap, p_red, p_junc, p_ov, p_gap, p_out,
            *toggles,
            p_excel, p_html, p_txt, p_out_fc,
            p_export_gdb, p_target_gdb, p_ds_name, p_add_map
        ]

    def updateParameters(self, parameters):
        if parameters[0].altered and parameters[0].value:
            in_ds = parameters[0].valueAsText
            if not parameters[1].value:
                det = auto_detect_layer_field(in_ds)
                if det:
                    parameters[1].value = det

            try:
                cad_lyrs = get_dataset_cad_layers(in_ds, parameters[1].valueAsText)
                if cad_lyrs:
                    parameters[2].filter.list = ["All Layers"] + cad_lyrs
                else:
                    parameters[2].filter.list = ["All Layers"]
            except Exception:
                parameters[2].filter.list = ["All Layers"]

    def updateMessages(self, parameters):
        from helpers.validation import validate_geometry_qc_parameters
        validate_geometry_qc_parameters(parameters)

    def execute(self, parameters, messages):
        in_fc = parameters[0].valueAsText
        layer_field = parameters[1].valueAsText
        target_layer = parameters[2].valueAsText or "All Layers"
        layer_label = parameters[3].valueAsText or os.path.basename(in_fc)

        short_seg_m = float(parameters[4].value or 0.10)
        angle_deg = float(parameters[5].value or 5.0)
        snap_m = float(parameters[6].value or 0.01)
        red_deg = float(parameters[7].value or 179.9)
        junc_m = float(parameters[8].value or 0.01)
        ov_sqm = float(parameters[9].value or 0.0001)
        gap_sqm = float(parameters[10].value or 0.001)
        out_folder = parameters[11].valueAsText

        # Toggles indices: 12 to 21
        chk_inv = bool(parameters[12].value)
        chk_ov = bool(parameters[13].value)
        chk_dup = bool(parameters[14].value)
        chk_gap = bool(parameters[15].value)
        chk_mp = bool(parameters[16].value)
        chk_seg = bool(parameters[17].value)
        chk_ang = bool(parameters[18].value)
        chk_snap = bool(parameters[19].value)
        chk_red = bool(parameters[20].value)
        chk_junc = bool(parameters[21].value)

        gen_excel = bool(parameters[22].value)
        gen_html = bool(parameters[23].value)
        gen_txt = bool(parameters[24].value)
        out_issue_fc = parameters[25].valueAsText
        export_to_gdb = bool(parameters[26].value) if len(parameters) > 26 and parameters[26].value is not None else True
        target_gdb = parameters[27].valueAsText if len(parameters) > 27 and parameters[27].valueAsText else None
        dataset_name = parameters[28].valueAsText if len(parameters) > 28 and parameters[28].valueAsText else "CAD_Geometry_QC_Errors"
        add_to_map = bool(parameters[29].value) if len(parameters) > 29 and parameters[29].value is not None else True

        config = GeometryQCConfig(
            check_invalid=chk_inv,
            check_overlap=chk_ov,
            check_duplicate=chk_dup,
            check_gap=chk_gap,
            check_multipart=chk_mp,
            check_short_seg=chk_seg,
            check_angle=chk_ang,
            check_snap=chk_snap,
            check_redundant=chk_red,
            check_junction=chk_junc,
            overlap_tolerance_sqm=ov_sqm,
            gap_tolerance_sqm=gap_sqm,
            short_seg_tolerance_m=short_seg_m,
            angle_tolerance_deg=angle_deg,
            snap_tolerance_m=snap_m,
            redundant_vertex_deg=red_deg,
            junction_tolerance_m=junc_m,
        )

        def progress_notify(msg):
            arcpy.AddMessage(f"[GeometryQC] {msg}")

        # Extract features grouped by CAD layer
        features_by_layer, actual_field, sr = extract_features_by_layer(
            dataset=in_fc,
            layer_field=layer_field,
            target_layer=target_layer,
        )

        total_features = sum(len(f_dict) for f_dict in features_by_layer.values())
        if not features_by_layer or total_features == 0:
            arcpy.AddWarning(f"No geometric features found in '{in_fc}' for target layer '{target_layer}'.")
            return

        arcpy.AddMessage("=" * 60)
        arcpy.AddMessage(f"Starting Geometry & Topology QC on {len(features_by_layer)} CAD layer(s) ({total_features} features)...")
        arcpy.AddMessage(f"Dataset: {in_fc} | Target: {target_layer}")
        arcpy.AddMessage("=" * 60)

        all_issues = []
        combined_summary = {}
        layer_summaries = {}

        for lname, layer_features in sorted(features_by_layer.items()):
            arcpy.AddMessage("-" * 40)
            arcpy.AddMessage(f"[CAD Layer: {lname}] Analyzing {len(layer_features)} features...")
            l_issues, l_summary = run_geometry_qc(
                features=layer_features,
                layer_name=lname,
                source="INPUT",
                config=config,
                progress_callback=progress_notify,
            )

            # Check if layer is reserved CAD system layer '0'
            if lname.strip() in ("0", "Defpoints", "DEFPOINTS") and len(layer_features) > 0:
                iss_zero = QCIssue(
                    issue_id=len(all_issues) + len(l_issues) + 1,
                    check_id=CheckID.CHK_RESERVED_LAYER,
                    issue_type="RESERVED_LAYER_CONTAINS_DATA",
                    severity=Severity.WARNING,
                    layer_name=lname,
                    source="INPUT",
                    expected_value="Empty (0 features)",
                    actual_value=f"{len(layer_features)} features",
                    details=(
                        f"Reserved CAD system layer '{lname}' contains {len(layer_features)} features. "
                        f"CAD drafting standards require layer '0' to remain empty without drawing entities."
                    ),
                )
                l_issues.append(iss_zero)
                l_summary[CheckID.CHK_RESERVED_LAYER] = {
                    "name": "Reserved System Layer (0)",
                    "count": 1,
                    "status": "WARNING",
                }
                arcpy.AddWarning(
                    f"[CAD Layer: {lname}] Warning: Reserved system layer '{lname}' contains {len(layer_features)} features. "
                    f"CAD drafting standards require layer '0' to remain empty."
                )

            # Re-index issues sequentially
            for iss in l_issues:
                iss.issue_id = len(all_issues) + 1
                all_issues.append(iss)

            err_count = sum(1 for iss in l_issues if iss.severity == Severity.ERROR)
            warn_count = sum(1 for iss in l_issues if iss.severity == Severity.WARNING)

            layer_summaries[lname] = {
                "feature_count": len(layer_features),
                "total_issues": len(l_issues),
                "errors": err_count,
                "warnings": warn_count,
                "checks": {chk: info["count"] for chk, info in l_summary.items() if info["count"] > 0},
            }

            status_str = "ERROR" if err_count > 0 else ("WARNING" if warn_count > 0 else "PASS")
            arcpy.AddMessage(f"--> [Layer: {lname}] {len(l_issues)} Issues ({err_count} Errors, {warn_count} Warnings) [{status_str}]")

            # Merge into global check summary
            for chk, info in l_summary.items():
                if chk not in combined_summary:
                    combined_summary[chk] = dict(info)
                else:
                    combined_summary[chk]["count"] += info["count"]
                    if info["status"] == "ERROR":
                        combined_summary[chk]["status"] = "ERROR"
                    elif info["status"] == "WARNING" and combined_summary[chk]["status"] != "ERROR":
                        combined_summary[chk]["status"] = "WARNING"

        # Wrap in QCResult for unified reporting
        qc_result = QCResult(
            reference_source=in_fc,
            received_source="N/A (Standalone Geometry QC)",
            execution_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            issues=all_issues,
            geometry_qc_run=True,
            geometry_qc_summary=combined_summary,
            layer_geometry_qc_summaries=layer_summaries,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(out_folder, exist_ok=True)

        if gen_excel:
            excel_path = os.path.join(out_folder, f"Geometry_QC_Report_{timestamp}.xlsx")
            create_excel_report(qc_result, excel_path)
            arcpy.AddMessage(f"[Report] Excel report generated: {excel_path}")

        if gen_html:
            html_path = os.path.join(out_folder, f"Geometry_QC_Report_{timestamp}.html")
            create_html_report(qc_result, html_path)
            arcpy.AddMessage(f"[Report] HTML dashboard generated: {html_path}")

        if gen_txt:
            txt_path = os.path.join(out_folder, f"Geometry_QC_Report_{timestamp}.txt")
            create_text_report(qc_result, txt_path)
            arcpy.AddMessage(f"[Report] Text summary generated: {txt_path}")

        if out_issue_fc:
            final_sr = sr or get_dataset_spatial_reference(in_fc)
            write_issues_to_feature_class(
                issues=qc_result.issues,
                output_feature_class=out_issue_fc,
                spatial_reference=final_sr,
                progress_callback=progress_notify,
            )
            arcpy.AddMessage(f"[Issues] Issue Feature Class created: {out_issue_fc}")

        if export_to_gdb:
            final_sr = sr or get_dataset_spatial_reference(in_fc)
            arcpy.AddMessage("=" * 60)
            arcpy.AddMessage("Exporting 10 QC Error Types into Geodatabase Feature Dataset...")
            resolved_gdb = target_gdb or get_default_geodatabase()
            arcpy.AddMessage(f"[GDB Export] Geodatabase: {resolved_gdb}")
            arcpy.AddMessage(f"[GDB Export] Feature Dataset: {dataset_name}")
            gdb_results = export_qc_errors_to_geodatabase_dataset(
                issues=all_issues,
                gdb_path=target_gdb,
                dataset_name=dataset_name,
                spatial_reference=final_sr,
                create_all_ten=True,
                add_to_map=add_to_map,
                progress_callback=progress_notify,
            )
            arcpy.AddMessage(f"[GDB Export] Successfully created {len(gdb_results)} feature classes inside dataset '{dataset_name}'.")
            arcpy.AddMessage("=" * 60)

        total_errors = sum(1 for iss in all_issues if iss.severity == Severity.ERROR)
        total_warnings = sum(1 for iss in all_issues if iss.severity == Severity.WARNING)

        arcpy.AddMessage("=" * 60)
        arcpy.AddMessage(f"Geometry QC Completed across {len(layer_summaries)} CAD layers.")
        arcpy.AddMessage(f"Total Issues Detected: {len(all_issues)} ({total_errors} Errors, {total_warnings} Warnings).")
        for lname, linfo in layer_summaries.items():
            arcpy.AddMessage(f"  • CAD Layer '{lname}': {linfo['total_issues']} issues ({linfo['errors']} Errors, {linfo['warnings']} Warnings)")
        arcpy.AddMessage("=" * 60)

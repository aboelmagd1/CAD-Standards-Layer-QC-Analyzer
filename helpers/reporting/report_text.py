# -*- coding: utf-8 -*-
"""
Plain Text Report Generator.
Generates a concise, structured ASCII log of the QC outcomes.
"""

import os
from ..models.qc_result import QCResult, LayerStatus
from ..models.qc_issue import Severity, CheckID


def create_text_report(qc_result: QCResult, output_path: str) -> str:
    """
    Generates a concise plain text QC summary report.
    Returns the absolute path to the generated text file.
    """
    lines = []
    lines.append("CAD REFERENCE-BASED QC & GEOMETRY QUALITY REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"REFERENCE: {qc_result.reference_source}")
    lines.append(f"RECEIVED:  {qc_result.received_source}")
    lines.append(f"DATE:      {qc_result.execution_date}")
    lines.append("")
    lines.append(f"Reference Layers: {qc_result.total_reference_layers()}")
    lines.append(f"Received Layers:  {qc_result.total_received_layers()}")
    lines.append(f"Missing Layers:   {len(qc_result.missing_layers)}")
    lines.append(f"Extra Layers:     {len(qc_result.extra_layers)}")
    lines.append("")

    geom_diffs = len(qc_result.issues_by_check(CheckID.CHK_GEOMETRY_TYPE))
    unexp_types = len(qc_result.issues_by_check(CheckID.CHK_UNEXPECTED_FEATURE))
    color_diffs = len(qc_result.issues_by_check(CheckID.CHK_COLOR))
    lw_diffs = len(qc_result.issues_by_check(CheckID.CHK_LINEWEIGHT))
    lt_diffs = len(qc_result.issues_by_check(CheckID.CHK_LINETYPE))
    clos_diffs = len(qc_result.issues_by_check(CheckID.CHK_CLOSURE))
    cnt_diffs = len(qc_result.issues_by_check(CheckID.CHK_FEATURE_COUNT))
    res_diffs = len(qc_result.issues_by_check(CheckID.CHK_RESERVED_LAYER))

    lines.append(f"Geometry Differences:     {geom_diffs}")
    lines.append(f"Unexpected Feature Types: {unexp_types}")
    lines.append(f"Color Differences:        {color_diffs}")
    lines.append(f"Lineweight Differences:   {lw_diffs}")
    lines.append(f"Linetype Differences:     {lt_diffs}")
    lines.append(f"Closure Issues:           {clos_diffs}")
    lines.append(f"Feature Count Differences:{cnt_diffs}")
    ref_cmp_issues = qc_result.reference_comparison_issues()
    geom_qc_issues = qc_result.geometry_qc_issues()

    lines.append(f"Reference Comparison Issues: {len(ref_cmp_issues)}")
    lines.append(f"  Geometry Differences:     {geom_diffs}")
    lines.append(f"  Unexpected Feature Types: {unexp_types}")
    lines.append(f"  Color Differences:        {color_diffs}")
    lines.append(f"  Lineweight Differences:   {lw_diffs}")
    lines.append(f"  Linetype Differences:     {lt_diffs}")
    lines.append(f"  Closure Issues:           {clos_diffs}")
    lines.append(f"  Feature Count Differences:{cnt_diffs}")
    if res_diffs > 0:
        lines.append(f"  Reserved Layer (0) Issues:{res_diffs}")
    lines.append("")
    lines.append(f"Geometry QC Issues:         {len(geom_qc_issues)}")
    lines.append(f"Total QC Issues:            {len(qc_result.issues)}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("")

    # Detailed layer findings
    for l_name, ls in sorted(qc_result.layer_statuses.items()):
        if ls.status != LayerStatus.PASS:
            lines.append(f"[{ls.status}] {ls.layer_name}")
            lines.append(f"  Received Count: {ls.rec_count:,}")
            lines.append(f"  Expected: {ls.expected_geom} | Received: {ls.received_geom}")
            for r in ls.reasons:
                lines.append(f"  • {r}")
            lines.append("")

    # Geometry-Aware QC Profile findings (if any)
    if qc_result.layer_geometry_qc_summaries:
        lines.append("=" * 60)
        lines.append("GEOMETRY-AWARE QC PROFILE & ISSUES BREAKDOWN")
        lines.append("-" * 60)
        header_fmt = "{:<24} {:<12} {:<14} {:>8}"
        lines.append(header_fmt.format("Layer", "Geometry", "QC Profile", "Issues"))
        lines.append("-" * 60)
        for lname, linfo in sorted(qc_result.layer_geometry_qc_summaries.items()):
            g_type = str(linfo.get("geometry_type") or linfo.get("expected_geom", "Unknown"))
            qc_prof = str(linfo.get("qc_profile") or "Generic QC")
            tot = linfo.get("total_issues", 0)
            lines.append(header_fmt.format(lname[:23], g_type[:11], qc_prof[:13], tot))
        lines.append("-" * 60)
        lines.append("")

        for lname, linfo in sorted(qc_result.layer_geometry_qc_summaries.items()):
            errs = linfo.get("errors", 0)
            warns = linfo.get("warnings", 0)
            tot = linfo.get("total_issues", errs + warns)
            st = "ERROR" if errs > 0 else ("WARNING" if warns > 0 else "PASS")
            g_type = linfo.get("geometry_type", "Unknown")
            qc_prof = linfo.get("qc_profile", "Generic QC")
            lines.append(f"[{st}] CAD Layer: {lname} ({linfo.get('feature_count', '—')} features) | Type: {g_type} | Profile: {qc_prof}")
            lines.append(f"  Total Issues: {tot} ({errs} Errors, {warns} Warnings)")
            chks = linfo.get("checks", {})
            for chk_name, cnt in chks.items():
                if cnt > 0:
                    lines.append(f"    • {chk_name}: {cnt}")
            lines.append("")

    if qc_result.geometry_qc_summary:
        lines.append("=" * 60)
        lines.append("GEOMETRY & TOPOLOGY QC SUMMARY (10 CHECKS)")
        lines.append("-" * 60)
        for chk_id, s_info in qc_result.geometry_qc_summary.items():
            lines.append(f"  {s_info.get('name', chk_id):<24}: {s_info.get('count', 0):>4} issues [{s_info.get('status', 'PASS')}]")
        lines.append("")

    lines.append("=" * 60)
    lines.append("END OF REPORT")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return os.path.abspath(output_path)

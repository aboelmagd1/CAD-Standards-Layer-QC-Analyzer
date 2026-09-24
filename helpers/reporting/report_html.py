# -*- coding: utf-8 -*-
"""
HTML Report Generator.
Generates a self-contained, responsive, professional HTML dashboard
with KPI cards, interactive layer filters, accordions, and clean visual typography.
Supports dual-language: English (default/primary) and Arabic (with RTL layout),
both via an instant client-side toggle and pre-rendered standalone .html and _ar.html files.
"""

import os
import html
import json
from ..models.qc_result import QCResult, LayerStatus
from ..models.qc_issue import Severity, CheckID


TRANSLATIONS = {
    "en": {
        "title": "CAD Standards & Geometry Quality Control Report",
        "meta_ref": "Reference",
        "meta_rec": "Received",
        "meta_date": "Date",
        "kpi_ref_layers": "Ref Layers",
        "kpi_passed": "Passed Layers",
        "kpi_errors": "Layers with Errors",
        "kpi_missing": "Missing Layers",
        "kpi_ref_cmp": "Ref Comparison Issues",
        "kpi_geom_qc": "Geometry QC Issues",
        "kpi_total": "Total Issues",
        "sec_layer_overview": "Layer Compliance Overview",
        "btn_all": "All",
        "btn_error": "Errors",
        "btn_warning": "Warnings",
        "btn_pass": "Passed",
        "th_layer_name": "Layer Name",
        "th_rec_count": "Received Count",
        "th_exp_geom": "Expected Geometry",
        "th_rec_geom": "Received Geometry",
        "th_status": "Status",
        "th_findings": "Findings / Reasons",
        "sec_ref_profile": "Learned Reference Profile (Authoritative CAD Standard)",
        "th_feat_count": "Feature Count",
        "th_dom_geom": "Dominant Geometry",
        "th_dom_pct": "Dominant %",
        "th_comp": "Composition",
        "th_clos_req": "Closure Required",
        "th_clos_pct": "Closure %",
        "th_color": "Dominant Color",
        "th_ltype": "Dominant Linetype",
        "th_lweight": "Dominant Lineweight",
        "sec_layer_gqc": "Geometry-Aware QC — Issues Breakdown by CAD Layer",
        "th_gqc_layer": "CAD Layer Name",
        "th_gqc_geom": "Geometry",
        "th_gqc_profile": "QC Profile",
        "th_gqc_app_checks": "Applicable Checks",
        "th_gqc_analyzed": "Features Analyzed",
        "th_gqc_issues": "Issues Found",
        "th_gqc_errors": "Errors",
        "th_gqc_warnings": "Warnings",
        "th_gqc_status": "Status",
        "sec_gqc_summary": "Geometry & Topology QC Summary (10 Global Checks)",
        "th_chk_id": "Check ID",
        "th_chk_name": "Check Name",
        "th_chk_issues": "Issues Count",
        "sec_issues_registry": "Detailed QC Issues Registry",
        "no_issues": "No QC Issues Detected. All checks passed!",
        "th_issue_id": "ID",
        "th_issue_sev": "Severity",
        "th_issue_layer": "Layer Name",
        "th_issue_oid": "Feature OID",
        "th_issue_loc": "Location (X, Y)",
        "th_issue_details": "Details",
        "matches_ref": "Matches Reference standard",
        "toggle_btn": "🌐 العربية",
    },
    "ar": {
        "title": "تقرير ضبط الجودة ومعايير الكاد والمطابقة الهندسية",
        "meta_ref": "الملف المرجعي المعتمد",
        "meta_rec": "الملف المستلم",
        "meta_date": "تاريخ الفحص",
        "kpi_ref_layers": "طبقات المرجع",
        "kpi_passed": "الطبقات المطابقة",
        "kpi_errors": "طبقات بها أخطاء",
        "kpi_missing": "طبقات مفقودة",
        "kpi_ref_cmp": "ملاحظات مقارنة المعايير",
        "kpi_geom_qc": "أخطاء الجيوميتري والتوبولوجي",
        "kpi_total": "إجمالي الملاحظات",
        "sec_layer_overview": "نظرة عامة على مطابقة الطبقات",
        "btn_all": "الكل",
        "btn_error": "الأخطاء",
        "btn_warning": "التحذيرات",
        "btn_pass": "المطابقة",
        "th_layer_name": "اسم الطبقة",
        "th_rec_count": "عدد العناصر المستلمة",
        "th_exp_geom": "الجيوميتري المتوقع",
        "th_rec_geom": "الجيوميتري المستلم",
        "th_status": "الحالة",
        "th_findings": "الملاحظات والأسباب",
        "sec_ref_profile": "بروفايل معيار الكاد المعتمد (الملف المرجعي)",
        "th_feat_count": "عدد العناصر",
        "th_dom_geom": "الجيوميتري السائد",
        "th_dom_pct": "نسبة السيادة",
        "th_comp": "التركيبة",
        "th_clos_req": "الإغلاق مطلوب",
        "th_clos_pct": "نسبة الإغلاق",
        "th_color": "اللون السائد",
        "th_ltype": "نوع الخط السائد",
        "th_lweight": "سماكة الخط السائدة",
        "sec_layer_gqc": "تدقيق الجيوميتري حسب طبقات الكاد",
        "th_gqc_layer": "اسم طبقة الكاد",
        "th_gqc_geom": "نوع الجيوميتري",
        "th_gqc_profile": "بروفايل التدقيق",
        "th_gqc_app_checks": "الفحوصات المطبقة",
        "th_gqc_analyzed": "العناصر المفحوصة",
        "th_gqc_issues": "الملاحظات المكتشفة",
        "th_gqc_errors": "الأخطاء",
        "th_gqc_warnings": "التحذيرات",
        "th_gqc_status": "الحالة",
        "sec_gqc_summary": "ملخص فحوصات الجيوميتري والتوبولوجي (10 فحوصات)",
        "th_chk_id": "رمز الفحص",
        "th_chk_name": "اسم الفحص",
        "th_chk_issues": "عدد الملاحظات",
        "sec_issues_registry": "السجل التفصيلي لملاحظات الجودة",
        "no_issues": "لم يتم رصد أي ملاحظات جودة. جميع الفحوصات مطابقة بنجاح!",
        "th_issue_id": "الرقم",
        "th_issue_sev": "مستوى الخطورة",
        "th_issue_layer": "اسم الطبقة",
        "th_issue_oid": "رقم العنصر (OID)",
        "th_issue_loc": "الإحداثيات (X, Y)",
        "th_issue_details": "التفاصيل",
        "matches_ref": "مطابق لمعيار الكاد المرجعي",
        "toggle_btn": "🌐 English",
    }
}


def _build_html_content(qc_result: QCResult, initial_lang: str = "en") -> str:
    lang = initial_lang if initial_lang in ("en", "ar") else "en"
    t = TRANSLATIONS[lang]
    is_rtl = (lang == "ar")
    html_dir = "rtl" if is_rtl else "ltr"

    total_issues = len(qc_result.issues)
    total_errors = len(qc_result.issues_by_severity(Severity.ERROR))
    total_warnings = len(qc_result.issues_by_severity(Severity.WARNING))
    passed_layers = qc_result.passed_layers_count()
    error_layers = qc_result.error_layers_count()
    missing_layers_cnt = len(qc_result.missing_layers)
    ref_cmp_issues_cnt = len(qc_result.reference_comparison_issues())
    geom_qc_issues_cnt = len(qc_result.geometry_qc_issues())

    # Reference profile rows
    ref_rows_html = ""
    if qc_result.reference_profile:
        for l_name, lp in sorted(qc_result.reference_profile.layers.items()):
            comp_txt = "MIXED" if lp.is_mixed_geometry else "CONSISTENT"
            comp_badge = "badge-warning" if lp.is_mixed_geometry else "badge-success"
            clos_req_txt = "Yes" if lp.closure_required else "No"
            ref_rows_html += f"""
            <tr>
                <td><strong>{html.escape(lp.layer_name)}</strong></td>
                <td>{lp.feature_count:,}</td>
                <td><span class="badge badge-info">{html.escape(lp.dominant_geometry or "None")}</span></td>
                <td>{lp.dominant_percentage * 100:.1f}%</td>
                <td><span class="badge {comp_badge}" data-term="{comp_txt}">{comp_txt}</span></td>
                <td><span data-term="{clos_req_txt}">{clos_req_txt}</span></td>
                <td>{f"{lp.closure_percentage * 100:.1f}%" if lp.closure_required else "N/A"}</td>
                <td>{html.escape(lp.dominant_color() or "N/A")}</td>
                <td>{html.escape(lp.dominant_linetype() or "N/A")}</td>
                <td>{html.escape(lp.dominant_lineweight() or "N/A")}</td>
            </tr>
            """

    # Layer overview rows
    layer_rows_html = ""
    for l_name, ls in sorted(qc_result.layer_statuses.items()):
        status_badge = "badge-success"
        if ls.status in (LayerStatus.ERROR, LayerStatus.MISSING):
            status_badge = "badge-danger"
        elif ls.status in (LayerStatus.WARNING, LayerStatus.REVIEW):
            status_badge = "badge-warning"
        elif ls.status == LayerStatus.EXTRA:
            status_badge = "badge-info"

        reasons_html = "<br>".join([f"<small>• {html.escape(r)}</small>" for r in ls.reasons])
        default_finding = f"<small class='text-muted' data-term='Matches Reference standard'>{t['matches_ref'] if is_rtl else 'Matches Reference standard'}</small>"

        layer_rows_html += f"""
        <tr data-status="{ls.status.lower()}">
            <td><strong>{html.escape(ls.layer_name)}</strong></td>
            <td>{ls.rec_count:,}</td>
            <td>{html.escape(ls.expected_geom)}</td>
            <td>{html.escape(ls.received_geom)}</td>
            <td><span class="badge {status_badge}" data-term="{ls.status}">{ls.status}</span></td>
            <td>{reasons_html if reasons_html else default_finding}</td>
        </tr>
        """

    # Geometry QC rows (if run)
    gqc_html = ""
    if qc_result.geometry_qc_summary:
        gqc_rows = ""
        for chk_id, s_info in qc_result.geometry_qc_summary.items():
            st = s_info.get("status", "PASS")
            b_class = "badge-success" if st == "PASS" else "badge-danger"
            gqc_rows += f"""
            <tr>
                <td><code>{chk_id}</code></td>
                <td><strong>{html.escape(s_info.get('name', chk_id))}</strong></td>
                <td>{s_info.get('count', 0)}</td>
                <td><span class="badge {b_class}" data-term="{st}">{st}</span></td>
            </tr>
            """

        layer_gqc_card = ""
        if qc_result.layer_geometry_qc_summaries:
            layer_gqc_rows = ""
            for lname, linfo in sorted(qc_result.layer_geometry_qc_summaries.items()):
                errs = linfo.get("errors", 0)
                warns = linfo.get("warnings", 0)
                tot = linfo.get("total_issues", errs + warns)
                st = "ERROR" if errs > 0 else ("WARNING" if warns > 0 else "PASS")
                b_class = "badge-danger" if st == "ERROR" else ("badge-warning" if st == "WARNING" else "badge-success")
                g_type = linfo.get("geometry_type") or linfo.get("expected_geom", "—")
                qc_prof = linfo.get("qc_profile") or (
                    "Polygon QC" if g_type.lower() == "polygon" else (
                        "Line QC" if "line" in g_type.lower() else (
                            "Point QC" if "point" in g_type.lower() else "Generic QC"
                        )
                    )
                )
                app_checks = linfo.get("applicable_checks", [])
                app_str = f"{len(app_checks)} checks" if app_checks else "All Type Checks"

                layer_gqc_rows += f"""
                <tr>
                    <td><strong>{html.escape(lname)}</strong></td>
                    <td><span class="badge badge-info">{html.escape(g_type)}</span></td>
                    <td><strong>{html.escape(qc_prof)}</strong></td>
                    <td><small>{html.escape(app_str)}</small></td>
                    <td>{linfo.get('feature_count', '—')}</td>
                    <td><strong>{tot}</strong></td>
                    <td><span class="text-danger font-weight-bold">{errs}</span></td>
                    <td><span class="text-warning font-weight-bold">{warns}</span></td>
                    <td><span class="badge {b_class}" data-term="{st}">{st}</span></td>
                </tr>
                """
            layer_gqc_card = f"""
            <div class="card mb-4">
                <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">
                    <h2 data-i18n="sec_layer_gqc">{t['sec_layer_gqc']}</h2>
                    <small class="text-muted" id="sub_layers_eval">{len(qc_result.layer_geometry_qc_summaries)} CAD layers evaluated</small>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th data-i18n="th_gqc_layer">{t['th_gqc_layer']}</th>
                                    <th data-i18n="th_gqc_geom">{t['th_gqc_geom']}</th>
                                    <th data-i18n="th_gqc_profile">{t['th_gqc_profile']}</th>
                                    <th data-i18n="th_gqc_app_checks">{t['th_gqc_app_checks']}</th>
                                    <th data-i18n="th_gqc_analyzed">{t['th_gqc_analyzed']}</th>
                                    <th data-i18n="th_gqc_issues">{t['th_gqc_issues']}</th>
                                    <th data-i18n="th_gqc_errors">{t['th_gqc_errors']}</th>
                                    <th data-i18n="th_gqc_warnings">{t['th_gqc_warnings']}</th>
                                    <th data-i18n="th_gqc_status">{t['th_gqc_status']}</th>
                                </tr>
                            </thead>
                            <tbody>{layer_gqc_rows}</tbody>
                        </table>
                    </div>
                </div>
            </div>
            """

        gqc_html = f"""
        {layer_gqc_card}
        <div class="card mb-4">
            <div class="card-header bg-dark text-white">
                <h2 data-i18n="sec_gqc_summary">{t['sec_gqc_summary']}</h2>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th data-i18n="th_chk_id">{t['th_chk_id']}</th>
                                <th data-i18n="th_chk_name">{t['th_chk_name']}</th>
                                <th data-i18n="th_chk_issues">{t['th_chk_issues']}</th>
                                <th data-i18n="th_status">{t['th_status']}</th>
                            </tr>
                        </thead>
                        <tbody>{gqc_rows}</tbody>
                    </table>
                </div>
            </div>
        </div>
        """

    # Detailed issues rows
    issue_rows_html = ""
    for iss in qc_result.issues[:500]:
        sev_badge = "badge-danger" if iss.severity == Severity.ERROR else ("badge-warning" if iss.severity == Severity.WARNING else "badge-info")
        loc_str = f"({iss.location[0]:.2f}, {iss.location[1]:.2f})" if iss.location else "—"
        issue_rows_html += f"""
        <tr>
            <td>#{iss.issue_id}</td>
            <td><code>{iss.check_id}</code></td>
            <td><span class="badge {sev_badge}" data-term="{iss.severity}">{iss.severity}</span></td>
            <td>{html.escape(iss.layer_name)}</td>
            <td>{iss.object_id or "—"}</td>
            <td>{loc_str}</td>
            <td>{html.escape(iss.details)}</td>
        </tr>
        """

    translations_json = json.dumps(TRANSLATIONS, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="{lang}" dir="{html_dir}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CAD QC & Comparison Analysis Report</title>
    <style>
        :root {{
            --primary: #1F4E79;
            --primary-light: #2c6da7;
            --success: #28a745;
            --warning: #ffc107;
            --danger: #dc3545;
            --info: #17a2b8;
            --bg: #f8f9fa;
            --card-bg: #ffffff;
            --text: #212529;
            --border: #e9ecef;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
        }}
        [dir="rtl"] body, [dir="rtl"] {{
            font-family: 'Segoe UI', Tahoma, 'Cairo', Arial, sans-serif;
            text-align: right;
        }}
        .container {{
            max-width: 1300px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, #0d233a 100%);
            color: white;
            padding: 28px 32px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 16px;
        }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 24px; font-weight: 700; }}
        .header p {{ margin: 0; opacity: 0.88; font-size: 13px; line-height: 1.5; }}
        .lang-toggle-btn {{
            background: rgba(255, 255, 255, 0.18);
            border: 1px solid rgba(255, 255, 255, 0.45);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            white-space: nowrap;
            transition: all 0.2s ease;
            backdrop-filter: blur(4px);
        }}
        .lang-toggle-btn:hover {{
            background: rgba(255, 255, 255, 0.32);
            transform: translateY(-1px);
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--card-bg);
            padding: 16px 8px;
            border-radius: 10px;
            border: 1px solid var(--border);
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-width: 0;
        }}
        .kpi-value {{
            font-size: 26px;
            font-weight: 700;
            margin-bottom: 4px;
            line-height: 1.1;
        }}
        .kpi-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            color: #6c757d;
            font-weight: 600;
            line-height: 1.3;
        }}
        .card {{
            background: var(--card-bg);
            border-radius: 10px;
            border: 1px solid var(--border);
            margin-bottom: 24px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
            overflow: hidden;
        }}
        .card-header {{
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            background: #fafbfc;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .card-header h2 {{
            margin: 0;
            font-size: 18px;
            color: var(--primary);
        }}
        .table-responsive {{
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background: #f1f4f8;
            color: #495057;
            font-weight: 600;
            padding: 12px 14px;
            text-align: left;
            border-bottom: 2px solid var(--border);
        }}
        [dir="rtl"] th, [dir="rtl"] td {{
            text-align: right;
        }}
        td {{
            padding: 12px 14px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}
        tr:hover td {{
            background-color: #fbfcfd;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: 700;
            border-radius: 4px;
            text-transform: uppercase;
        }}
        .badge-success {{ background-color: #d4edda; color: #155724; }}
        .badge-danger {{ background-color: #f8d7da; color: #721c24; }}
        .badge-warning {{ background-color: #fff3cd; color: #856404; }}
        .badge-info {{ background-color: #d1ecf1; color: #0c5460; }}
        .filter-btn {{
            background: #ffffff;
            border: 1px solid #ced4da;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            margin-left: 6px;
            font-weight: 500;
        }}
        [dir="rtl"] .filter-btn {{
            margin-left: 0;
            margin-right: 6px;
        }}
        .filter-btn.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-top">
                <div>
                    <h1 data-i18n="title">{t['title']}</h1>
                    <p><span data-i18n="meta_ref">{t['meta_ref']}</span>: {html.escape(qc_result.reference_source or "N/A")} | <span data-i18n="meta_rec">{t['meta_rec']}</span>: {html.escape(qc_result.received_source or "N/A")} | <span data-i18n="meta_date">{t['meta_date']}</span>: {qc_result.execution_date}</p>
                </div>
                <button id="langToggleBtn" class="lang-toggle-btn" onclick="toggleLanguage()">{t['toggle_btn']}</button>
            </div>
        </div>

        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-value" style="color: var(--primary);">{qc_result.total_reference_layers()}</div>
                <div class="kpi-label" data-i18n="kpi_ref_layers">{t['kpi_ref_layers']}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: var(--success);">{passed_layers}</div>
                <div class="kpi-label" data-i18n="kpi_passed">{t['kpi_passed']}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: var(--danger);">{error_layers}</div>
                <div class="kpi-label" data-i18n="kpi_errors">{t['kpi_errors']}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: var(--danger);">{missing_layers_cnt}</div>
                <div class="kpi-label" data-i18n="kpi_missing">{t['kpi_missing']}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: var(--info);">{ref_cmp_issues_cnt}</div>
                <div class="kpi-label" data-i18n="kpi_ref_cmp">{t['kpi_ref_cmp']}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: { 'var(--danger)' if geom_qc_issues_cnt > 0 else 'var(--success)' };">{geom_qc_issues_cnt}</div>
                <div class="kpi-label" data-i18n="kpi_geom_qc">{t['kpi_geom_qc']}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: { 'var(--danger)' if total_errors > 0 else 'var(--success)' };">{total_issues}</div>
                <div class="kpi-label" data-i18n="kpi_total">{t['kpi_total']}</div>
            </div>
        </div>

        <!-- Layer Overview -->
        <div class="card">
            <div class="card-header">
                <h2 data-i18n="sec_layer_overview">{t['sec_layer_overview']}</h2>
                <div>
                    <button class="filter-btn active" data-i18n="btn_all" onclick="filterLayers('all', this)">{t['btn_all']}</button>
                    <button class="filter-btn" data-i18n="btn_error" onclick="filterLayers('error', this)">{t['btn_error']}</button>
                    <button class="filter-btn" data-i18n="btn_warning" onclick="filterLayers('warning', this)">{t['btn_warning']}</button>
                    <button class="filter-btn" data-i18n="btn_pass" onclick="filterLayers('pass', this)">{t['btn_pass']}</button>
                </div>
            </div>
            <div class="table-responsive">
                <table id="layerTable">
                    <thead>
                        <tr>
                            <th data-i18n="th_layer_name">{t['th_layer_name']}</th>
                            <th data-i18n="th_rec_count">{t['th_rec_count']}</th>
                            <th data-i18n="th_exp_geom">{t['th_exp_geom']}</th>
                            <th data-i18n="th_rec_geom">{t['th_rec_geom']}</th>
                            <th data-i18n="th_status">{t['th_status']}</th>
                            <th data-i18n="th_findings">{t['th_findings']}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {layer_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Reference Profile -->
        <div class="card">
            <div class="card-header">
                <h2 data-i18n="sec_ref_profile">{t['sec_ref_profile']}</h2>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th data-i18n="th_layer_name">{t['th_layer_name']}</th>
                            <th data-i18n="th_feat_count">{t['th_feat_count']}</th>
                            <th data-i18n="th_dom_geom">{t['th_dom_geom']}</th>
                            <th data-i18n="th_dom_pct">{t['th_dom_pct']}</th>
                            <th data-i18n="th_comp">{t['th_comp']}</th>
                            <th data-i18n="th_clos_req">{t['th_clos_req']}</th>
                            <th data-i18n="th_clos_pct">{t['th_clos_pct']}</th>
                            <th data-i18n="th_color">{t['th_color']}</th>
                            <th data-i18n="th_ltype">{t['th_ltype']}</th>
                            <th data-i18n="th_lweight">{t['th_lweight']}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {ref_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Geometry QC Summary (if present) -->
        {gqc_html}

        <!-- Issue Details -->
        <div class="card">
            <div class="card-header">
                <h2 data-i18n="sec_issues_registry">{t['sec_issues_registry']}</h2>
                <small class="text-muted" id="sub_issues_showing">Displaying {min(len(qc_result.issues), 500)} of {len(qc_result.issues)} issues</small>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th data-i18n="th_issue_id">{t['th_issue_id']}</th>
                            <th data-i18n="th_chk_id">{t['th_chk_id']}</th>
                            <th data-i18n="th_issue_sev">{t['th_issue_sev']}</th>
                            <th data-i18n="th_issue_layer">{t['th_issue_layer']}</th>
                            <th data-i18n="th_issue_oid">{t['th_issue_oid']}</th>
                            <th data-i18n="th_issue_loc">{t['th_issue_loc']}</th>
                            <th data-i18n="th_issue_details">{t['th_issue_details']}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {issue_rows_html if issue_rows_html else f"<tr><td colspan='7' style='text-align:center; padding:20px; color:#28a745;'><strong data-i18n='no_issues'>{t['no_issues']}</strong></td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const TRANSLATIONS = {translations_json};
        let currentLang = '{lang}';

        const TERM_MAP = {{
            ar: {{
                'PASS': 'مطابق',
                'ERROR': 'خطأ',
                'WARNING': 'تحذير',
                'EXTRA': 'إضافي',
                'MISSING': 'مفقود',
                'REVIEW': 'مراجعة',
                'CONSISTENT': 'متناسق',
                'MIXED': 'مختلط',
                'Yes': 'نعم',
                'No': 'لا',
                'Matches Reference standard': 'مطابق لمعيار الكاد المرجعي'
            }},
            en: {{
                'PASS': 'PASS',
                'ERROR': 'ERROR',
                'WARNING': 'WARNING',
                'EXTRA': 'EXTRA',
                'MISSING': 'MISSING',
                'REVIEW': 'REVIEW',
                'CONSISTENT': 'CONSISTENT',
                'MIXED': 'MIXED',
                'Yes': 'Yes',
                'No': 'No',
                'Matches Reference standard': 'Matches Reference standard'
            }}
        }};

        function setLanguage(lang) {{
            currentLang = (lang === 'ar') ? 'ar' : 'en';
            const t = TRANSLATIONS[currentLang];
            document.documentElement.lang = currentLang;
            document.documentElement.dir = (currentLang === 'ar') ? 'rtl' : 'ltr';

            // Update text for all elements with data-i18n
            document.querySelectorAll('[data-i18n]').forEach(el => {{
                const key = el.getAttribute('data-i18n');
                if (t[key]) {{
                    el.textContent = t[key];
                }}
            }});

            // Update terms (badges, Yes/No, etc.)
            document.querySelectorAll('[data-term]').forEach(el => {{
                const termKey = el.getAttribute('data-term');
                if (TERM_MAP[currentLang] && TERM_MAP[currentLang][termKey]) {{
                    el.textContent = TERM_MAP[currentLang][termKey];
                }}
            }});

            // Update toggle button text
            const btn = document.getElementById('langToggleBtn');
            if (btn) {{
                btn.textContent = (currentLang === 'ar') ? '🌐 English' : '🌐 العربية';
            }}
        }}

        function toggleLanguage() {{
            const newLang = (currentLang === 'en') ? 'ar' : 'en';
            setLanguage(newLang);
        }}

        function filterLayers(status, btn) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const rows = document.querySelectorAll('#layerTable tbody tr');
            rows.forEach(r => {{
                if (status === 'all') {{
                    r.style.display = '';
                }} else {{
                    const s = r.getAttribute('data-status');
                    r.style.display = (s === status) ? '' : 'none';
                }}
            }});
        }}

        // If initially Arabic, apply term replacements
        if (currentLang === 'ar') {{
            setLanguage('ar');
        }}
    </script>
</body>
</html>"""
    return html_content


def create_html_report(qc_result: QCResult, output_path: str) -> str:
    """
    Generates a standalone, beautiful HTML dashboard report.
    - Generates primary English version at output_path (default/primary).
    - Generates dedicated Arabic version at {root}_ar.html (with RTL).
    - Both versions feature an interactive language switcher to toggle instantly in browser.
    Returns the absolute path to the primary English HTML file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # 1. Primary English version
    en_content = _build_html_content(qc_result, initial_lang="en")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(en_content)

    # 2. Arabic version
    root, ext = os.path.splitext(output_path)
    ar_output_path = f"{root}_ar{ext}"
    ar_content = _build_html_content(qc_result, initial_lang="ar")
    with open(ar_output_path, "w", encoding="utf-8") as f:
        f.write(ar_content)

    return os.path.abspath(output_path)

# -*- coding: utf-8 -*-
"""
HTML Report Generator.
Generates a self-contained, responsive, professional HTML dashboard
with KPI cards, interactive layer filters, accordions, and clean visual typography.
"""

import os
import html
from ..models.qc_result import QCResult, LayerStatus
from ..models.qc_issue import Severity, CheckID


def create_html_report(qc_result: QCResult, output_path: str) -> str:
    """
    Generates a standalone, beautiful HTML dashboard report.
    Returns the absolute path to the generated HTML file.
    """
    total_issues = len(qc_result.issues)
    total_errors = len(qc_result.issues_by_severity(Severity.ERROR))
    total_warnings = len(qc_result.issues_by_severity(Severity.WARNING))
    passed_layers = qc_result.passed_layers_count()
    error_layers = qc_result.error_layers_count()
    missing_layers_cnt = len(qc_result.missing_layers)
    extra_layers_cnt = len(qc_result.extra_layers)

    # Reference profile rows
    ref_rows_html = ""
    if qc_result.reference_profile:
        for l_name, lp in sorted(qc_result.reference_profile.layers.items()):
            ref_rows_html += f"""
            <tr>
                <td><strong>{html.escape(lp.layer_name)}</strong></td>
                <td>{lp.feature_count:,}</td>
                <td><span class="badge badge-info">{html.escape(lp.dominant_geometry or "None")}</span></td>
                <td>{lp.dominant_percentage * 100:.1f}%</td>
                <td>{"<span class='badge badge-warning'>MIXED</span>" if lp.is_mixed_geometry else "<span class='badge badge-success'>CONSISTENT</span>"}</td>
                <td>{"Yes" if lp.closure_required else "No"}</td>
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

        layer_rows_html += f"""
        <tr data-status="{ls.status.lower()}">
            <td><strong>{html.escape(ls.layer_name)}</strong></td>
            <td>{ls.ref_count:,}</td>
            <td>{ls.rec_count:,}</td>
            <td>{html.escape(ls.expected_geom)}</td>
            <td>{html.escape(ls.received_geom)}</td>
            <td><span class="badge {status_badge}">{ls.status}</span></td>
            <td>{reasons_html if reasons_html else "<small class='text-muted'>Matches Reference standard</small>"}</td>
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
                <td><span class="badge {b_class}">{st}</span></td>
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
                layer_gqc_rows += f"""
                <tr>
                    <td><strong>{html.escape(lname)}</strong></td>
                    <td>{linfo.get('feature_count', '—')}</td>
                    <td><strong>{tot}</strong></td>
                    <td><span class="text-danger font-weight-bold">{errs}</span></td>
                    <td><span class="text-warning font-weight-bold">{warns}</span></td>
                    <td><span class="badge {b_class}">{st}</span></td>
                </tr>
                """
            layer_gqc_card = f"""
            <div class="card mb-4">
                <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">Geometry QC — Issues Breakdown by CAD Layer</h5>
                    <small class="text-light">{len(qc_result.layer_geometry_qc_summaries)} CAD layers evaluated</small>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover table-striped mb-0">
                            <thead>
                                <tr>
                                    <th>CAD Layer Name</th>
                                    <th>Features Analyzed</th>
                                    <th>Total Issues</th>
                                    <th>Errors</th>
                                    <th>Warnings</th>
                                    <th>Status</th>
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
                <h5 class="mb-0">Geometry & Topology QC Summary (10 Global Checks)</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover table-striped mb-0">
                        <thead>
                            <tr>
                                <th>Check ID</th>
                                <th>Check Name</th>
                                <th>Issues Count</th>
                                <th>Status</th>
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
    for iss in qc_result.issues[:500]:  # Limit top 500 in HTML table for performance
        sev_badge = "badge-danger" if iss.severity == Severity.ERROR else ("badge-warning" if iss.severity == Severity.WARNING else "badge-info")
        loc_str = f"({iss.location[0]:.2f}, {iss.location[1]:.2f})" if iss.location else "—"
        issue_rows_html += f"""
        <tr>
            <td>#{iss.issue_id}</td>
            <td><code>{iss.check_id}</code></td>
            <td><span class="badge {sev_badge}">{iss.severity}</span></td>
            <td>{html.escape(iss.layer_name)}</td>
            <td>{iss.object_id or "—"}</td>
            <td>{loc_str}</td>
            <td>{html.escape(iss.details)}</td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
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
        .container {{
            max-width: 1300px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, #0d233a 100%);
            color: white;
            padding: 32px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 26px; }}
        .header p {{ margin: 0; opacity: 0.85; font-size: 14px; }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 10px;
            border: 1px solid var(--border);
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
            text-align: center;
        }}
        .kpi-value {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .kpi-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #6c757d;
            font-weight: 600;
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
            <h1>CAD Standards & Geometry Quality Control Report</h1>
            <p>Reference: {html.escape(qc_result.reference_source or "N/A")} | Received: {html.escape(qc_result.received_source or "N/A")} | Date: {qc_result.execution_date}</p>
        </div>

        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-value" style="color: var(--primary);">{qc_result.total_reference_layers()}</div>
                <div class="kpi-label">Ref Layers</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: var(--success);">{passed_layers}</div>
                <div class="kpi-label">Passed Layers</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: var(--danger);">{error_layers}</div>
                <div class="kpi-label">Layers with Errors</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: var(--danger);">{missing_layers_cnt}</div>
                <div class="kpi-label">Missing Layers</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: var(--info);">{extra_layers_cnt}</div>
                <div class="kpi-label">Extra Layers</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value" style="color: { 'var(--danger)' if total_errors > 0 else 'var(--success)' };">{total_issues}</div>
                <div class="kpi-label">Total QC Issues</div>
            </div>
        </div>

        <!-- Layer Overview -->
        <div class="card">
            <div class="card-header">
                <h2>Layer Compliance Overview</h2>
                <div>
                    <button class="filter-btn active" onclick="filterLayers('all', this)">All</button>
                    <button class="filter-btn" onclick="filterLayers('error', this)">Errors</button>
                    <button class="filter-btn" onclick="filterLayers('warning', this)">Warnings</button>
                    <button class="filter-btn" onclick="filterLayers('pass', this)">Passed</button>
                </div>
            </div>
            <div class="table-responsive">
                <table id="layerTable">
                    <thead>
                        <tr>
                            <th>Layer Name</th>
                            <th>Reference Count</th>
                            <th>Received Count</th>
                            <th>Expected Geometry</th>
                            <th>Received Geometry</th>
                            <th>Status</th>
                            <th>Findings / Reasons</th>
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
                <h2>Learned Reference Profile (Authoritative CAD Standard)</h2>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Layer Name</th>
                            <th>Feature Count</th>
                            <th>Dominant Geometry</th>
                            <th>Dominant %</th>
                            <th>Composition</th>
                            <th>Closure Required</th>
                            <th>Closure %</th>
                            <th>Dominant Color</th>
                            <th>Dominant Linetype</th>
                            <th>Dominant Lineweight</th>
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
                <h2>Detailed QC Issues Registry</h2>
                <small class="text-muted">Displaying {min(len(qc_result.issues), 500)} of {len(qc_result.issues)} issues</small>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Check ID</th>
                            <th>Severity</th>
                            <th>Layer Name</th>
                            <th>Feature OID</th>
                            <th>Location (X, Y)</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {issue_rows_html if issue_rows_html else "<tr><td colspan='7' style='text-align:center; padding:20px; color:#28a745;'><strong>No QC Issues Detected. All checks passed!</strong></td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
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
    </script>
</body>
</html>"""

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return os.path.abspath(output_path)

# CAD Standards & Geometry Quality Analyzer

> **ArcGIS Pro Python Toolbox (`.pyt`)** combining **Reference-Based CAD Comparison QC** and **Geometry-Aware Quality Control** for urban planning, land subdivision, and engineering CAD submissions.  
> 📖 **للاطلاع على الدليل الشامل والمفصل باللغتين العربية والإنجليزية، يرجى مراجعة [DOCUMENTATION.md](DOCUMENTATION.md)**  
> 📖 **For the comprehensive bilingual user manual & architecture guide, see [DOCUMENTATION.md](DOCUMENTATION.md)**

---

## 1. Overview & Philosophy

This toolbox addresses two fundamental, independent Quality Control questions in a single, high-performance, strictly **100% read-only** solution:

1. **Reference-Based CAD Comparison**:
   > *"What changed between my approved Original CAD and the Received/Client CAD?"*
   - **No hardcoded rules**: The system inspects the Reference CAD dynamically, learns the authoritative baseline (**Reference Profile**), and validates the Received CAD against what was learned (layers, geometry composition, closure rates, colors, linetypes, lineweights).
   - First-class support for **`Closed Polyline` vs `Polygon` vs `Open Polyline`**, ensuring parcel boundaries stored as polylines are verified without forcing conversion to polygons.
   - **Pure Quality Focus**: Comparison evaluates layer compliance, geometry integrity, and CAD visual properties without flagging artificial errors for intentional entity count differences.

2. **Geometry-Aware QC Profiles (Combined Workflow)**:
   > *"What is geometrically or topologically defective in the dataset itself?"*
   - **Type-Aware Profile Dispatching**: Automatically runs the appropriate QC profile based on expected layer geometry:
     - **Polygon QC Profile**: Invalid Geometries, Duplicates, Overlaps, Enclosed Gaps, Multipart, Short Segments, Sharp Angles, Snap Issues, Redundant Vertices, Missing Junctions, and Unclosed Rings (`UNCLOSED_RING`).
     - **Line QC Profile**: L01 Invalid, L02 Duplicate, L03 Overlap, L04 Self-Intersection, L05 Dangle, L06 Disconnected, L07 Short Segment, L08 Sharp Angle, L09 Redundant Vertex, L10 Snap, L11 Missing Junction, L12 Open/Closed Behavior.
     - **Point QC Profile**: P01 Invalid, P02 Duplicate, P03 Near Duplicate, P04 Point Density, P05 Cross-Layer Coincidence.
   - **Enforces Reference Standards on Mismatches**: When a received layer has a geometry type mismatch (e.g. `parcel` is polyline instead of polygon), the tool does **not** skip QC; it enforces the Reference-expected Polygon profile and identifies boundary defects.

---

## 2. Requirements & Installation

- **ArcGIS Pro**: ArcGIS Pro 3.0 or higher (tested on ArcGIS Pro 3.3).
- **Python Environment**: ArcGIS Pro Default `arcgispro-py3` environment.
- **Dependencies**: `arcpy`, `openpyxl` (pre-installed in ArcGIS Pro conda environment).

### Adding the Toolbox in ArcGIS Pro
1. In ArcGIS Pro, open the **Catalog** pane.
2. Expand **Toolboxes**, right-click and select **Add Toolbox**.
3. Browse to this directory and select `CAD_QC_Toolbox.pyt`.
4. The toolbox `CAD Standards & Layer QC Toolbox` (`cad_qc`) will now be available with two tools:
   - **`CAD Reference-Based Comparison QC`** (`CADReferenceComparisonQCTool`)
   - **`Geometry & Topology QC Analyzer`** (`GeometryQCTool`)

---

## 3. Tool Reference

### Tool 1: `CADReferenceComparisonQCTool`
Compares a Received CAD dataset against an Original/Reference CAD dataset and optionally runs Geometry QC.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **Reference CAD / Approved Dataset** | Feature Class / CAD Layer | *Required* | Approved baseline dataset. |
| **Reference Layer Field** | Field | `Layer` (auto-detected) | Attribute field containing layer names. |
| **Received CAD / Client Dataset** | Feature Class / CAD Layer | *Required* | Submitted client dataset. |
| **Received Layer Field** | Field | `Layer` (auto-detected) | Attribute field containing layer names. |
| **Comparison Scope** | String | `All Layers` | `All Layers`, `Polygon / Closed-Geometry Layers`, or `Custom Layer Selection`. |
| **Dominant Geometry Threshold** | Double | `0.50` (50%) | Threshold above which a geometry type is considered dominant (0.10 to 1.0). |
| **Closure Tolerance** | Double | `0.01` (1 cm) | Max endpoint distance for polylines to be classified as closed. |
| **Output Folder for Reports** | Folder | *Required* | Target directory for generated reports & results GDB. |
| **Compare Feature Counts** | Boolean | `False` | Optional entity count delta comparison (disabled by default). |
| **Compare Geometries** | Boolean | `True` | Detects unexpected entity types and distribution shifts. |
| **Compare Closure** | Boolean | `True` | Identifies open polylines where closed polylines were expected. |
| **Compare Colors / Weights / Types** | Boolean | `True` | Evaluates CAD visual property distributions. |
| **Run Geometry QC on Received CAD** | Boolean | `False` | Enables Combined Workflow: runs Geometry-Aware QC on the Received dataset. |
| **Generate Excel / HTML / TXT** | Boolean | `True` | Generates formatted reports. |
| **Output Standalone Issues Table** | DETable | *Optional* | Standalone descriptive table (no dummy Shape column). |

---

### Tool 2: `GeometryQCTool`
Executes geometry & topology checks across CAD layers with automated profile dispatching.

| Check Category | Checks Included | Description |
| :--- | :--- | :--- |
| **Polygon QC Suite** | 10 Checks + Closure | Invalid Geometries, Overlaps, Duplicates, Gaps, Multipart, Short Segments, Sharp Angles, Snap, Redundant Vertices, Missing Junctions. |
| **Line QC Suite** | 12 Checks (L01–L12) | Line Self-Intersections, Dangles, Disconnected Lines, Cutbacks, Overlaps, Open/Closed behavior. |
| **Point QC Suite** | 5 Checks (P01–P05) | Null Points, Exact Duplicates, Near Coincidences, Clustering / Distribution. |

---

## 4. Reports & Deliverables

Every run produces clean, organized deliverables stored together in the selected output folder:

### 1. Dual-Language Interactive HTML Dashboard (`.html`)
- **Primary English Dashboard**: `CAD_QC_Report_<timestamp>.html`.
- **Dedicated Arabic Dashboard**: `CAD_QC_Report_<timestamp>_ar.html` (RTL layout with professional Arabic CAD terminology).
- **Instant Language Switcher**: `🌐 العربية` / `🌐 English` toggle button in the header switches between languages on the fly without page reload.
- **Responsive Single-Row / Auto-Fit KPI Grid**: Cards adapt cleanly to screen widths without wrapping awkward margins.
- **Filter Tabs**: `All`, `Errors`, `Warnings`, `Passed`.

### 2. Formatted Excel Workbook (`.xlsx`) via `openpyxl`
- Styled worksheets covering: `Summary`, `Reference Profile`, `Layer Overview`, `Layer Differences`, `Geometry Comparison`, `Property Comparison`, `Unexpected Features`, `Closure Issues`, `Geometry QC Summary`, `Geometry QC Issues`, and `Issue Details`.
- Color-coded badges (`PASS`, `WARNING`, `ERROR`, `MISSING`, `EXTRA`).
- Pure standards focus without irrelevant count comparison columns.

### 3. Plain Text Summary (`.txt`)
- Lightweight ASCII summary suitable for automation logs and quick inspection.

### 4. Self-Contained Output Geodatabase (`CAD_QC_Results.gdb`)
- Created directly in the reports output folder alongside the reports.
- **Feature Dataset (`CAD_Geometry_QC_Errors`)**: Individual Feature Classes for each error check (`QC01_Invalid_Geometries`, `QC02_Overlaps`, etc.). Only created for checks that actually have defects!
- **Standalone Table (`CAD_QC_All_Issues_Table`)**: Complete descriptive table of all issues with full attribute traceability and **no dummy Shape coordinates**.
- **Group Layer in Map**: When layers are added to the active map in ArcGIS Pro, all QC feature classes are automatically grouped under a single clean `CAD Geometry QC Errors` Group Layer, with the descriptive table under Standalone Tables.
- **GDB Conflict Resolution**: Automatically clears stale or legacy feature classes across the GDB to prevent Esri `ERROR 002851`.

---

## 5. Architecture & Code Structure

```
CAD Standards & Layer QC Analyzer/
├── CAD_QC_Toolbox.pyt                  # ArcGIS Pro Python Toolbox
│
├── helpers/
│   ├── __init__.py                     # Package exports
│   │
│   ├── models/                         # Shared Data Models
│   │   ├── qc_issue.py                 # Standardized QCIssue dataclass
│   │   ├── qc_result.py                # QCResult and LayerQCStatus containers
│   │   └── reference_profile.py        # ReferenceProfile & LayerProfile models
│   │
│   ├── geometry/                       # Geometry QC Engines & Profiles
│   │   ├── geometry_types.py           # GeometryType enum & classifier
│   │   ├── qc_profiles.py              # Profile dispatcher (Polygon, Line, Point)
│   │   ├── line_qc.py                  # 12 Line QC check algorithms (L01–L12)
│   │   ├── point_qc.py                 # 5 Point QC check algorithms (P01–P05)
│   │   ├── spatial_index.py            # 2D Bounding box spatial grid index
│   │   ├── vertex_index.py             # Spatial hash grid for vertices
│   │   ├── invalid_geometry.py         # CHK_INVALID_GEOM
│   │   ├── overlap.py                  # CHK_OVERLAP
│   │   ├── duplicate.py                # CHK_DUPLICATE
│   │   ├── gap.py                      # CHK_GAP
│   │   ├── multipart.py                # CHK_MULTIPART
│   │   ├── short_segment.py            # CHK_SHORT_SEG
│   │   ├── angle.py                    # CHK_ANGLE
│   │   ├── snap.py                     # CHK_SNAP
│   │   ├── redundant_vertex.py         # CHK_REDUNDANT
│   │   ├── junction.py                 # CHK_JUNCTION
│   │   └── geometry_qc_runner.py       # Geometry QC orchestrator
│   │
│   ├── comparison/                     # CAD Reference Comparison Engine
│   │   ├── reference_profiler.py       # Reference CAD dynamic profile builder
│   │   ├── layer_analyzer.py           # Streaming cursor scanner
│   │   ├── property_comparator.py      # Property comparison without count bias
│   │   ├── geometry_comparator.py      # Unexpected feature & distribution checker
│   │   ├── closure_checker.py          # Euclidean polyline closure checker
│   │   └── comparison_engine.py        # Master comparison orchestrator
│   │
│   ├── reporting/                      # Unified Report Generation
│   │   ├── report_excel.py             # Multi-sheet styled openpyxl workbook
│   │   ├── report_html.py              # Bilingual (EN/AR) interactive HTML dashboard
│   │   └── report_text.py              # Structured plain-text summary
│   │
│   ├── issue_writer.py                 # GDB export, Group Layer, & Standalone Table writer
│   ├── utilities.py                    # Spatial reference & field utilities
│   └── validation.py                   # Parameter validation & pre-execution checks
│
├── tests/
│   ├── mock_arcpy.py                   # Complete ArcPy emulator for offline CI/CD
│   ├── test_geometry_qc.py             # 10 geometry QC unit tests
│   ├── test_geometry_aware_qc.py       # Geometry QC profile unit tests
│   ├── test_cad_comparison.py          # CAD comparison unit tests
│   ├── test_combined_workflow.py       # End-to-end report generation tests (EN & AR)
│   ├── test_gdb_dataset_export.py      # GDB export, Group Layer & conflict resolution tests
│   ├── test_issue_writer_table.py      # Standalone table & reports GDB tests
│   ├── test_layer_zero.py              # Reserved layer 0 validation tests
│   └── run_tests.py                    # Automated test runner
│
├── prompt.md                           # Specification document
├── USER_GUIDE.md                       # Comprehensive User Guide (Arabic & English)
├── DOCUMENTATION.md                    # Technical Reference Manual
└── README.md                           # Documentation
```

---

## 6. Running the Automated Tests

To run the automated test suite offline or in ArcGIS Pro:

```powershell
python -m unittest discover tests
```

All **61 unit and integration tests** pass cleanly, validating:
- All Geometry QC Profiles (Polygon, Line, Point).
- Mismatch profile enforcement on received polylines.
- GDB creation inside the reports directory and conflict resolution.
- Group Layer creation and layer grouping in ArcGIS Pro.
- Dual-language HTML generation (English primary and Arabic RTL).
- Clean standalone table exports without dummy coordinates.

---

## 7. Data Safety

This tool is strictly:
$$\text{READ} \longrightarrow \text{ANALYZE} \longrightarrow \text{COMPARE} \longrightarrow \text{REPORT}$$

It will **never** edit, rename, move, delete, repair, merge, or split source CAD files or feature classes.

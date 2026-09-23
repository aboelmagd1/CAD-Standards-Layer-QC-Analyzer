# CAD Standards & Geometry Quality Analyzer

> **ArcGIS Pro Python Toolbox (`.pyt`)** combining **Reference-Based CAD Comparison QC** and **Geometry & Topology QC** for urban planning, land subdivision, and engineering CAD submissions.  
> 📖 **للاطلاع على الدليل الشامل والمفصل باللغتين العربية والإنجليزية، يرجى مراجعة [DOCUMENTATION.md](DOCUMENTATION.md)**  
> 📖 **For the comprehensive bilingual user manual & architecture guide, see [DOCUMENTATION.md](DOCUMENTATION.md)**

---

## 1. Overview & Philosophy

This toolbox addresses two fundamental, independent Quality Control questions in a single, high-performance, strictly **100% read-only** solution:

1. **Reference-Based CAD Comparison**:
   > *"What changed between my approved Original CAD and the Received/Client CAD?"*
   - **No hardcoded rules**: The system inspects the Reference CAD dynamically, learns the authoritative baseline (**Reference Profile**), and validates the Received CAD against what was learned (layers, geometry composition, closure rates, colors, linetypes, lineweights).
   - First-class support for **`Closed Polyline` vs `Polygon` vs `Open Polyline`**, ensuring parcel boundaries stored as polylines are verified without forcing conversion to polygons.

2. **Geometry & Topology QC**:
   > *"What is geometrically or topologically defective in the dataset itself?"*
   - Direct Python/ArcPy port of the **10 checks** from the [`Geometry-QC-Analyzer`](https://github.com/aboelmagd1/Geometry-QC-Analyzer).
   - Designed around in-memory spatial grid and vertex hash indexing ($O(N \log N)$) instead of naive $O(N^2)$ comparisons.

3. **Combined Workflow**:
   - Run Reference Comparison + Geometry QC on the Received dataset in a single execution.

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
Compares a Received CAD dataset against an Original/Reference CAD dataset.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **Reference CAD / Approved Dataset** | Feature Class / CAD Layer | *Required* | Approved baseline dataset. |
| **Reference Layer Field** | Field | `Layer` (auto-detected) | Attribute field containing layer names. |
| **Received CAD / Client Dataset** | Feature Class / CAD Layer | *Required* | Submitted client dataset. |
| **Received Layer Field** | Field | `Layer` (auto-detected) | Attribute field containing layer names. |
| **Comparison Scope** | String | `All Layers` | `All Layers`, `Polygon / Closed-Geometry Layers`, or `Custom Layer Selection`. |
| **Dominant Geometry Threshold** | Double | `0.50` (50%) | Threshold above which a geometry type is considered dominant (0.10 to 1.0). |
| **Closure Tolerance** | Double | `0.01` (1 cm) | Max endpoint distance for polylines to be classified as closed. |
| **Output Folder** | Folder | *Required* | Target directory for generated reports. |
| **Compare Feature Counts** | Boolean | `True` | Flags count discrepancies between matching layers. |
| **Compare Geometries** | Boolean | `True` | Detects unexpected entity types and distribution shifts. |
| **Compare Closure** | Boolean | `True` | Identifies open polylines where closed polylines were expected. |
| **Compare Colors / Weights / Types** | Boolean | `True` | Evaluates CAD property distributions. |
| **Run Geometry QC on Received CAD** | Boolean | `False` | Enables Mode C: runs the full 10-check geometry QC suite on the Received dataset. |
| **Generate Excel / HTML / TXT** | Boolean | `True` | Generates formatted reports. |
| **Output Issue Feature Class** | Feature Class | *Optional* | Writes spatial points for all issues for ArcGIS Pro inspection. |

---

### Tool 2: `GeometryQCTool`
Executes all 10 geometry & topology checks against a single dataset.

| Check ID | Check Name | Default Threshold | Description |
| :--- | :--- | :--- | :--- |
| `CHK_INVALID_GEOM` | Invalid Geometries | N/A | Self-intersections, bow-ties, NaN coordinates, zero-area polygons. |
| `CHK_OVERLAP` | Polygon Overlaps | `0.0001 m²` | Overlapping polygon areas decomposed; excludes duplicates. |
| `CHK_DUPLICATE` | Duplicate Geometries | $\ge 99.9\%$ coincidence | 100% coincident polygon detection. |
| `CHK_GAP` | Enclosed Gaps | `0.001 m²` | Slivers and hidden interior holes between adjacent polygons. |
| `CHK_MULTIPART` | Multipart Geometries | Parts $> 1$ | Flags multipart polygons where singlepart geometry is expected. |
| `CHK_SHORT_SEG` | Short Segments | `0.10 m` (10 cm) | Edges shorter than threshold (sub-millimeter precision reporting). |
| `CHK_ANGLE` | Sharp Angles | `5.0°` | Acute needle spikes and digitizing artifacts. |
| `CHK_SNAP` | Snap Issues | `0.01 m` (1 cm) | Near-coincident vertices within tolerance (excludes identical points). |
| `CHK_REDUNDANT` | Redundant Vertices | `179.9°` | Unnecessary collinear vertices that do not change direction. |
| `CHK_JUNCTION` | Missing Junctions | `0.01 m` (1 cm) | T-junction vertices touching neighbor edges without matching nodes. |

---

## 4. Reports & Deliverables

Every run produces three standardized, professional report formats in the selected output folder:

### 1. Excel Workbook (`.xlsx`) via `openpyxl`
Contains up to 12 styled worksheets:
- `Summary`: Executive KPIs, layer counts, error totals, coordinate system status.
- `Reference Profile`: What the tool learned from the Original CAD (dominant type, closure rates, colors, lineweights).
- `Layer Overview`: High-level matrix with status badges (`PASS`, `WARNING`, `ERROR`, `MISSING`, `EXTRA`, `REVIEW`).
- `Layer Differences`: Detailed missing and extra layers inventory.
- `Geometry Comparison`: Side-by-side distribution breakdown for all matching layers.
- `Property Comparison`: Color, linetype, and lineweight differences.
- `Unexpected Features`: Unexpected entity types found inside layers.
- `Closure Issues`: Coordinate locations, endpoint gaps, and tolerances for unclosed features.
- `Feature Count Differences`: Feature count deltas and percentage differences.
- `Geometry QC Summary`: 10-check summary table with status indicators.
- `Geometry QC Issues`: Feature-level geometry defect records with measurements.
- `Issue Details`: Complete registry of all detected issues with OID traceability.

### 2. Interactive HTML Dashboard (`.html`)
- Self-contained, responsive modern dashboard usable by non-GIS stakeholders.
- KPI summary cards (Total Layers, Passed, Errors, Missing, Extra, Total Issues).
- Filter tabs (`All`, `Errors`, `Warnings`, `Passed`).
- Collapsible accordions for fast issue inspection.

### 3. Plain Text Summary (`.txt`)
- Clean ASCII summary suitable for automation logs and quick email updates.

### 4. Optional ArcGIS Pro Issue Feature Class
- Point feature class created at issue locations (`FEATURE_OID`, `RELATED_OID`, `CHECK_ID`, `ISSUE_TYPE`, `SEVERITY`, `MEASURE`, `DETAIL`).
- Enables `Select Issue → Zoom to Feature → Inspect` directly inside ArcGIS Pro.

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
│   ├── geometry/                       # High-Performance Geometry QC Engine
│   │   ├── geometry_classifier.py      # CLOSED_POLYLINE vs OPEN_POLYLINE vs POLYGON
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
│   │   ├── layer_analyzer.py           # Streaming cursor scanner (O(N) passes)
│   │   ├── property_comparator.py      # Distribution-based property comparisons
│   │   ├── geometry_comparator.py      # Unexpected feature & distribution checker
│   │   ├── closure_checker.py          # Euclidean polyline closure checker
│   │   └── comparison_engine.py        # Master comparison orchestrator
│   │
│   ├── reporting/                      # Unified Report Generation
│   │   ├── report_excel.py             # 12-sheet styled openpyxl workbook
│   │   ├── report_html.py              # Modern interactive HTML dashboard
│   │   └── report_text.py              # Structured plain-text summary
│   │
│   ├── issue_writer.py                 # Feature class writer for ArcGIS Pro
│   ├── utilities.py                    # Spatial reference & field utilities
│   └── validation.py                   # Parameter validation & pre-execution checks
│
├── tests/
│   ├── test_geometry_qc.py             # 10 geometry QC unit tests
│   ├── test_cad_comparison.py          # CAD comparison unit tests
│   ├── test_combined_workflow.py       # End-to-end report generation tests
│   └── run_tests.py                    # Automated test runner
│
├── prompt.md                           # Specification document
└── README.md                           # Documentation
```

---

## 6. Running the Automated Tests

To run the automated test suite using the ArcGIS Pro Python environment:

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" tests/run_tests.py
```

All 22 unit and integration tests validate:
- All 10 geometry & topology QC checks against synthetic geometries.
- All Reference Comparison categories (identical layers, unexpected features, closure gaps, color/weight/type diffs, mixed profiles, graceful missing property handling).
- Multi-sheet Excel, HTML dashboard, and text report generation.

---

## 7. Data Safety

This tool is strictly:
$$\text{READ} \longrightarrow \text{ANALYZE} \longrightarrow \text{COMPARE} \longrightarrow \text{REPORT}$$

It will **never** edit, rename, move, delete, repair, merge, or split source CAD files or feature classes.

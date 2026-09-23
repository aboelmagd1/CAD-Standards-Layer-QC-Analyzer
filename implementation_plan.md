# Implementation Plan — CAD Reference-Based QC & Geometry Quality Analyzer

A production-ready **ArcGIS Pro Python Toolbox (`.pyt`)** integrating two complementary Quality Control systems:
1. **Reference-Based CAD Comparison QC** (`CADReferenceComparisonQCTool`): Dynamically builds a Reference Profile from the Original CAD and compares Received CAD.
2. **Geometry & Topology QC** (`GeometryQCTool`): Implements the full 10 geometry/topology checks ported from `Geometry-QC-Analyzer` using high-performance spatial and vertex indexing.
3. **Combined QC Workflow**: Option to run Reference Comparison + Geometry QC on Received CAD with unified Excel, HTML, Text reporting and ArcGIS Issue Layer.

---

## User Review Required

> [!IMPORTANT]
> **Strictly 100% Read-Only**: Neither tool will ever edit, repair, delete, move, merge, split, or rename source CAD/GIS features. All outputs are written to reports or a dedicated optional issue feature class.

> [!IMPORTANT]
> **No Hard-Coded Standards**: The Reference CAD defines the expected standard dynamically. The tool never assumes rules like `PARCEL = Closed Polyline` or hard-coded colors.

---

## Architecture & Directory Layout

Directly following Section 38 of the specification:

```
CAD Standards & Layer QC Analyzer/
├── CAD_QC_Toolbox.pyt                  # ArcGIS Pro Python Toolbox (.pyt)
│
├── helpers/
│   ├── __init__.py
│   │
│   ├── models/                         # Shared Data Models
│   │   ├── __init__.py
│   │   ├── qc_issue.py                 # QCIssue dataclass (shared by both QC dimensions)
│   │   ├── qc_result.py                # Combined and individual QC results container
│   │   └── reference_profile.py        # ReferenceProfile model (layers, distributions, properties)
│   │
│   ├── geometry/                       # High-Performance Geometry QC Engine (10 Checks)
│   │   ├── __init__.py
│   │   ├── geometry_classifier.py      # CLOSED_POLYLINE vs OPEN_POLYLINE vs POLYGON vs POINT vs TEXT, etc.
│   │   ├── spatial_index.py            # In-memory bounding box / R-tree grid index for O(1) candidate filtering
│   │   ├── vertex_index.py             # Spatial hash grid for vertex proximity, snap, and junction tests
│   │   ├── invalid_geometry.py         # CHK_INVALID_GEOM: self-intersections, bow-ties, NaN coords, non-simple
│   │   ├── overlap.py                  # CHK_OVERLAP: true polygon overlap areas decomposed, excluding duplicates
│   │   ├── duplicate.py                # CHK_DUPLICATE: 100% coincident geometry detection
│   │   ├── gap.py                      # CHK_GAP: enclosed sliver holes / gaps between adjacent polygons
│   │   ├── multipart.py                # CHK_MULTIPART: multipart polygons detection
│   │   ├── short_segment.py            # CHK_SHORT_SEG: polygon edges shorter than threshold (default 10 cm, mm-precision)
│   │   ├── angle.py                    # CHK_ANGLE: sharp spikes / needle angles (< 5.0°)
│   │   ├── snap.py                     # CHK_SNAP: near-coincident vertices within tolerance (default 1.0 cm)
│   │   ├── redundant_vertex.py         # CHK_REDUNDANT: collinear / redundant vertices (~179.9°)
│   │   ├── junction.py                 # CHK_JUNCTION: T-junction vertices touching edges without matching node (1.0 cm)
│   │   └── geometry_qc_runner.py       # Orchestrator running all enabled checks with progress reporting
│   │
│   ├── comparison/                     # Reference-Based CAD Comparison Engine
│   │   ├── __init__.py
│   │   ├── reference_profiler.py       # Builds ReferenceProfile from Original CAD (layers, properties, distributions)
│   │   ├── layer_analyzer.py           # Fast single-pass cursor scanner extracting CAD fields and geometries
│   │   ├── property_comparator.py      # Color, Linetype, Lineweight, Text, and custom property comparators
│   │   ├── geometry_comparator.py      # Expected vs Received geometry type & distribution comparison
│   │   ├── closure_checker.py          # Polyline start/end Euclidean distance tolerance & closure statistics
│   │   └── comparison_engine.py        # Master comparison orchestrator producing CAD QC issues
│   │
│   ├── reporting/                      # Unified Reporting Engine
│   │   ├── __init__.py
│   │   ├── report_excel.py             # Multi-sheet openpyxl workbook (Reference Profile, Layer Overview, Diffs, Geometry QC, Issue Details)
│   │   ├── report_html.py              # Self-contained modern interactive HTML dashboard with KPI cards & filter tabs
│   │   └── report_text.py              # Structured plain-text summary log
│   │
│   ├── issue_writer.py                 # Exports QCIssue objects into an ArcGIS Feature Class with categorized symbology
│   └── validation.py                   # Parameter info, defaults, updateMessages validation, and coordinate system checks
│
├── tests/
│   ├── __init__.py
│   ├── test_geometry_qc.py             # Unit tests for all 10 geometry QC checks
│   ├── test_cad_comparison.py          # Unit tests for all reference comparison categories
│   ├── test_combined_workflow.py       # Integration test: Reference Comparison + Geometry QC + Reports
│   └── run_tests.py                    # Automated test runner using arcgispro-py3
│
├── prompt.md                           # Specification document
└── README.md                           # Documentation, installation, parameter guidance, workflows
```

---

## Proposed Changes

### 1. Data Models (`helpers/models/`)
- `qc_issue.py`:
  - `QCIssue`: `issue_id`, `check_id`, `issue_type`, `severity` (`ERROR`, `WARNING`, `INFO`, `PASS`), `source`, `layer_name`, `object_id`, `related_object_id`, `property_name`, `expected_value`, `actual_value`, `measurement`, `threshold`, `geometry`, `location` (X, Y), `details`.
- `reference_profile.py`:
  - `LayerProfile`: `layer_name`, `feature_count`, `geometry_distribution`, `dominant_geometry`, `dominant_percentage`, `closure_required`, `closure_percentage`, `color_distribution`, `linetype_distribution`, `lineweight_distribution`, `text_properties`, `available_properties`.
  - `ReferenceProfile`: dictionary of `LayerProfile` objects + dataset metadata (spatial reference, path).
- `qc_result.py`:
  - `QCResult`: holds CAD comparison summary, geometry QC summary, layer statuses, and list of `QCIssue` items.

### 2. Geometry QC Engine (`helpers/geometry/`)
- High performance $O(N \log N)$ or grid-based instead of naive $O(N^2)$:
  - `spatial_index.py`: Grid-based spatial index bucketizing bounding boxes to query candidate neighbors.
  - `vertex_index.py`: Hash grid index bucketizing $(x, y)$ quantized to cell size for sub-millimeter proximity queries.
- Implementation of all 10 checks:
  1. `invalid_geometry.py` (`CHK_INVALID_GEOM`)
  2. `overlap.py` (`CHK_OVERLAP`, default $0.0001\text{ m}^2$, separates true overlaps from duplicates)
  3. `duplicate.py` (`CHK_DUPLICATE`, 100% coincident area detection)
  4. `gap.py` (`CHK_GAP`, enclosed silver gaps between polygons, default $0.001\text{ m}^2$)
  5. `multipart.py` (`CHK_MULTIPART`, flags multipart polygons)
  6. `short_segment.py` (`CHK_SHORT_SEG`, default 10 cm, mm-precision reporting)
  7. `angle.py` (`CHK_ANGLE`, sharp angles $< 5.0^\circ$)
  8. `snap.py` (`CHK_SNAP`, vertices close but not identical, default 1.0 cm)
  9. `redundant_vertex.py` (`CHK_REDUNDANT`, collinear vertices near $179.9^\circ$)
  10. `junction.py` (`CHK_JUNCTION`, T-junction vertex touching adjacent polygon edge without node, default 1.0 cm)
- `geometry_classifier.py`: Standardizes `POINT`, `MULTIPOINT`, `OPEN_POLYLINE`, `CLOSED_POLYLINE`, `POLYGON`, `TEXT`, `ANNOTATION`, `MULTIPATCH`, `OTHER`.

### 3. Comparison Engine (`helpers/comparison/`)
- `reference_profiler.py`: Scans Reference CAD, aggregates layer distributions, closure rates, and CAD properties.
- `layer_analyzer.py`: Streams through Received CAD using single-pass `arcpy.da.SearchCursor`.
- `property_comparator.py`: Compares property distributions gracefully without false errors for unexposed properties.
- `geometry_comparator.py`: Identifies missing layers, extra layers, unexpected feature types inside layers, and geometry distribution shifts.
- `closure_checker.py`: Detects unclosed polylines where closed polylines were expected, reporting gap distances and endpoint coordinates.
- `comparison_engine.py`: Coordinates the full comparison workflow.

### 4. Reporting Engine (`helpers/reporting/`)
- `report_excel.py`: Generates the complete 12-sheet Excel workbook (`openpyxl`) with headers, colors, auto-fit widths, and clean number formatting.
- `report_html.py`: Generates a modern responsive HTML dashboard with KPI summary cards, filter tabs, collapsible issue accordions, and issue inspection tables.
- `report_text.py`: Clean ASCII log output.
- `issue_writer.py`: Creates an ArcGIS Pro Issue Feature Class (point or problem geometry) with fields: `ISSUE_ID`, `CHECK_ID`, `ISSUE_TYPE`, `SEVERITY`, `LAYER_NAME`, `OBJECT_ID`, `RELATED_OID`, `PROPERTY`, `EXPECTED`, `ACTUAL`, `DETAIL`, `MEASURE`.

### 5. Toolbox & Validation (`CAD_QC_Toolbox.pyt`, `helpers/validation.py`)
- `Toolbox`: Contains `GeometryQCTool` and `CADReferenceComparisonQCTool`.
- `GeometryQCTool`: Inputs for feature class/layer, selection scope, 10 independent check toggles and threshold parameters, output folder, report choices, and issue feature class output.
- `CADReferenceComparisonQCTool`: Reference Source & Field, Received Source & Field, Scope, Comparison option toggles, Dominant threshold, Closure tolerance, Optional "Run Geometry QC on Received CAD" toggle, Output folder, report choices, and issue feature class output.
- `updateMessages()`: Validates inputs, paths, parameters, tolerances, and warns if spatial references differ.

### 6. Verification & Automated Tests (`tests/`)
- Unit and integration tests covering:
  - All 10 Geometry QC checks with synthetic geometries creating exact test conditions.
  - All CAD Comparison categories: Identical CAD, Missing Layer, Extra Layer, Unexpected Feature Type, Closure Difference, Color Difference, Lineweight Difference, Linetype Difference, Count Difference, Mixed Reference Layer, Multiple Colors, Different ObjectIDs, Spatial Reference Difference.
  - Verification of Excel, HTML, and TXT report outputs.

---

## Verification Plan

### Automated Execution
Run:
```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" tests/run_tests.py
```
- Validates all 10 Geometry QC checks.
- Validates all Reference Comparison tests.
- Validates combined workflow and report generation.

### Geoprocessing Validation
Verify that `CAD_QC_Toolbox.pyt` loads into ArcGIS Pro without syntax or schema errors:
```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -c "import arcpy; arcpy.ImportToolbox('CAD_QC_Toolbox.pyt'); print('Toolbox loaded successfully')"
```

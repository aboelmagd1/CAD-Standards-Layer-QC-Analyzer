# AI Build Prompt — CAD Reference-Based QC & Geometry Quality Analyzer

### ArcGIS Pro Python Toolbox (.pyt) — Python / ArcPy

---

# 1. Project Objective

Build a production-ready **ArcGIS Pro Python Toolbox (.pyt)** that combines two complementary Quality Control systems:

## A. Reference-Based CAD Comparison QC

Compare:

```text
Original / Correct CAD
        VS
Received / Client CAD
```

The **Original CAD is the source of truth**.

The system must automatically inspect the Original CAD, extract its observed Layer and Feature characteristics, build a **Reference Profile**, and then compare the Received CAD against that profile.

Do NOT hard-code assumptions such as:

```text
PARCEL = Closed Polyline
ROAD = Open Polyline
TEXT = Text
```

Instead:

```text
Original CAD
     ↓
Analyze
     ↓
Reference Profile
     ↓
Received CAD
     ↓
Compare
     ↓
QC Issues
```

---

## B. Geometry & Topology QC

The toolbox must also include the full geometry QC functionality of the existing:

**Geometry QC Analyzer**

Repository:

`https://github.com/aboelmagd1/Geometry-QC-Analyzer`

The Python implementation must preserve the existing QC concepts and check set rather than replacing them with a simplified geometry validation system.

The existing analyzer performs 10 critical geometry/topology checks and is designed as a read-only, high-performance QC workflow.

---

# 2. Overall Architecture

The final toolbox should contain:

```text
CAD_QC_Toolbox.pyt

Tool 1:
GeometryQCTool

Tool 2:
CADReferenceComparisonQCTool
```

Architecture:

```text
                    CAD QC TOOLBOX
                          │
             ┌────────────┴────────────┐
             │                         │
             ▼                         ▼
       GEOMETRY QC             CAD COMPARISON QC
             │                         │
             │                         ▼
             │                Reference CAD
             │                         │
             │                         ▼
             │                Reference Profile
             │                         │
             │                         ▼
             │                Received CAD
             │                         │
             │                         ▼
             │                    Comparison
             │                         │
             └────────────┬────────────┘
                          ▼
                     QC Results
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
          Excel         HTML          TXT
                          │
                          ▼
                Optional Issue Layer
```

---

# 3. Fundamental Design Principle

The system must distinguish between two questions.

### Question 1 — Reference Comparison

> Is the Received CAD different from the Original CAD?

### Question 2 — Geometry QC

> Does the geometry itself contain spatial/topological problems?

These are different QC dimensions and must not be mixed.

Example:

```text
Original:
PARCEL = Closed Polyline

Received:
PARCEL = Closed Polyline
```

The layer comparison may PASS.

But the Received polygons could still have:

```text
Overlaps
Gaps
Short Segments
Snap Issues
Redundant Vertices
Missing Junctions
```

Therefore:

**A layer can match the Reference and still fail Geometry QC.**

---

# 4. Tool 1 — GeometryQCTool

Implement a Python/ArcPy equivalent of the existing Geometry QC Analyzer.

The tool must support:

```text
Feature Class
Feature Layer
Current Selection
Visible/selected features where applicable
```

The tool must remain:

```text
100% Read-Only
No source edits
No automatic repair
No schema modification
```

---

# 5. Geometry QC — Required 10 Checks

Implement all 10 checks.

Do not remove, merge, or simplify them.

---

## 5.1 Invalid Geometry

Check ID:

```text
CHK_INVALID_GEOM
```

Detect invalid polygon geometry including:

```text
Self-intersections
Bow-ties
Unclosed loops
NaN coordinates
Non-simple geometry
Invalid OGC/Esri polygon geometry
```

The check must report:

```text
Layer
Feature/Object ID
Issue Type
Diagnostic
Location
```

The existing analyzer explicitly includes invalid geometry detection.

---

# 6. Overlap Check

Check ID:

```text
CHK_OVERLAP
```

Detect polygon areas that overlap other polygons.

Default tolerance:

```text
0.0001 m²
```

The implementation must distinguish:

```text
True overlap
```

from:

```text
Duplicate geometry
```

because 100% coincident polygons should be reported as duplicates rather than generating redundant overlap issues.

The existing analyzer decomposes multipart intersections and reports accurate overlap areas.

Report:

```text
Feature A
Feature B
Overlap Area
Unit
Location
Severity
```

---

# 7. Duplicate Geometry

Check ID:

```text
CHK_DUPLICATE
```

Detect polygons that are 100% geometrically coincident.

Example:

```text
Parcel 101
Parcel 102

Same geometry
```

Report:

```text
DUPLICATE GEOMETRY

OID 101
OID 102

Coincident Area:
...
```

Do not report the same pair again as an ordinary overlap.

The existing analyzer explicitly separates duplicate geometry from overlap.

---

# 8. Enclosed Gap

Check ID:

```text
CHK_GAP
```

Default tolerance:

```text
0.001 m²
```

Detect enclosed gaps/sliver holes between adjacent polygons.

Example:

```text
Polygon A
     │
     │
   GAP
     │
     │
Polygon B
```

Report:

```text
Gap Area
Gap Geometry
Neighbor Features
Location
```

The existing analyzer specifically detects enclosed hidden gaps/sliver holes.

---

# 9. Multipart Feature

Check ID:

```text
CHK_MULTIPART
```

Detect multipart polygon features.

Example:

```text
One feature
   ├── Polygon Part 1
   └── Polygon Part 2
```

Report:

```text
Layer
OID
Part Count
Geometry
```

This check should be configurable because some datasets may legitimately allow multipart features.

The default behavior should match the existing Geometry QC Analyzer concept: flag multipart features when the QC expects singlepart polygons.

---

# 10. Short Segment

Check ID:

```text
CHK_SHORT_SEG
```

Default:

```text
10.0 cm
```

Detect polygon edges shorter than the configured tolerance.

Report:

```text
OID
Segment Index
Segment Length
Configured Threshold
Location
```

Use appropriate units.

If the value is below 1 cm, report using millimeters where practical rather than displaying misleading values such as:

```text
0.00 cm
```

The existing analyzer specifically supports sub-millimeter precision for small distances.

---

# 11. Angle Issue

Check ID:

```text
CHK_ANGLE
```

Default:

```text
5.0°
```

Detect abnormal sharp angles associated with:

```text
Spikes
Needles
Digitizing artifacts
Very narrow geometry
```

Report:

```text
OID
Vertex Index
Angle
Threshold
Location
```

The existing analyzer uses a 5° default threshold.

---

# 12. Snap Issue

Check ID:

```text
CHK_SNAP
```

Default:

```text
1.0 cm
```

Detect vertices that are extremely close but not coincident.

Example:

```text
Vertex A
     •
      \
       • Vertex B

Distance = 0.003 m
```

Report:

```text
Feature A
Vertex A
Feature B
Vertex B
Distance
Tolerance
Location
```

Important:

Do not flag truly identical coordinates as snap issues.

The existing analyzer specifically excludes true identical points and reports very small distances with high precision.

---

# 13. Redundant Vertex

Check ID:

```text
CHK_REDUNDANT
```

Default:

```text
179.9°
```

Detect unnecessary collinear vertices.

Example:

```text
A ───── B ───── C
```

where B does not meaningfully change the direction.

Report:

```text
OID
Vertex Index
Angle
Adjacent Segment Lengths
Location
```

If coincident/redundant vertices occur together, flag the relevant vertices according to the existing analyzer behavior.

The existing analyzer uses approximately 179.9° for this check.

---

# 14. Missing Junction

Check ID:

```text
CHK_JUNCTION
```

Default:

```text
1.0 cm
```

Detect T-junction conditions where:

```text
Polygon A vertex
       ↓
       •──────── Polygon B edge
```

but the neighboring geometry does not contain a matching snapped node.

Report:

```text
Source Feature
Source Vertex
Neighbor Feature
Nearest Edge
Distance
Location
```

The existing analyzer specifically describes this as detecting polygon vertices touching neighboring polygon edges without a matching snapped node.

---

# 15. Geometry QC Parameters

All 10 checks must be independently configurable.

Example:

```text
☑ Invalid Geometry
☑ Overlap
☑ Duplicate Geometry
☑ Enclosed Gap
☑ Multipart
☑ Short Segment
☑ Angle Issue
☑ Snap Issue
☑ Redundant Vertex
☑ Missing Junction
```

Defaults:

```text
Short Segment = 10 cm
Angle = 5°
Snap = 1 cm
Redundant Vertex = 179.9°
Junction = 1 cm
Overlap = 0.0001 m²
Gap = 0.001 m²
```

These defaults are based on the existing Geometry QC Analyzer specification.

---

# 16. High-Performance Geometry Engine

Do NOT implement the geometry QC using naive O(n²) comparisons.

The existing Geometry QC Analyzer is designed around:

```text
In-Memory Spatial Index
+
Vertex Grid Index
```

The Python implementation should follow the same architectural principle where practical.

Use:

```text
Spatial indexing
Bounding-box filtering
Vertex grid / hash
Candidate pair reduction
Prepared geometry where available
```

Avoid comparing every polygon against every other polygon.

---

# 17. Geometry QC Result Model

Every issue should have a standardized object:

```python
QCIssue(
    issue_id,
    check_id,
    issue_type,
    severity,
    layer_name,
    object_id,
    related_object_id,
    geometry,
    location,
    measurement,
    threshold,
    details
)
```

This model must be shared by:

```text
Geometry QC
CAD Comparison QC
```

---

# 18. CAD Reference Comparison Tool

Tool name:

```text
CADReferenceComparisonQCTool
```

Inputs:

```text
Reference / Original CAD
Received CAD
```

The Original CAD must be analyzed first.

---

# 19. Reference Profile

Generate:

```text
ReferenceProfile
```

for every layer.

Store:

```text
Layer Name
Feature Count
Geometry Types
Geometry Distribution
Open/Closed Distribution
Color Distribution
Linetype Distribution
Lineweight Distribution
Text/Annotation properties
Available CAD properties
```

The Reference Profile is generated automatically.

No manual Layer rules should be required for the basic workflow.

---

# 20. Layer Comparison

Compare:

```text
Missing Layers
Extra Layers
Matching Layers
```

Example:

```text
Reference:
PARCEL
ROAD
BUILDING
TEXT

Received:
PARCEL
ROAD
TEXT
TEMP
```

Results:

```text
Missing:
BUILDING

Extra:
TEMP
```

---

# 21. Geometry Type Comparison

For every layer compare:

```text
POINT
MULTIPOINT
OPEN_POLYLINE
CLOSED_POLYLINE
POLYGON
TEXT
ANNOTATION
OTHER
```

Example:

Reference:

```text
PARCEL
Closed Polyline = 1000
```

Received:

```text
PARCEL
Closed Polyline = 980
Open Polyline = 20
```

Result:

```text
UNEXPECTED FEATURE TYPE

Layer:
PARCEL

Expected:
Closed Polyline

Unexpected:
Open Polyline

Affected:
20
```

---

# 22. Feature Property Comparison

Compare available properties:

```text
Color
Linetype
Lineweight
Transparency
Text Style
Font
Text Size
Rotation
Other CAD properties
```

Do not assume all properties are available.

Return:

```text
MATCH
DIFFERENT
NOT AVAILABLE
NOT APPLICABLE
```

---

# 23. Property Distribution

If the Reference contains multiple values inside one Layer, preserve the distribution.

Example:

```text
PARCEL

Color:
7 = 980
1 = 20

Lineweight:
0.25 = 1000

Linetype:
Continuous = 1000
```

Compare the Received distribution against it.

---

# 24. Unexpected Features

Explicitly detect features whose type/properties are not represented in the corresponding Reference Layer.

Example:

```text
Reference PARCEL:
Closed Polyline

Received PARCEL:
Closed Polyline
Open Polyline
Text
Point
```

Report:

```text
Open Polyline → Unexpected
Text → Unexpected
Point → Unexpected
```

This is a key CAD QC requirement.

---

# 25. Closure Comparison

Analyze closure in the Reference and Received datasets.

Compare:

```text
Closed count
Open count
Closure percentage
```

If Reference:

```text
Closed = 100%
```

and Received:

```text
Closed = 98%
Open = 2%
```

report the affected features.

Use configurable closure tolerance.

---

# 26. Feature Count Comparison

For each Layer:

```text
Reference Count
Received Count
Difference
Percentage Difference
```

Do not automatically treat every count difference as an error.

Classify it separately.

---

# 27. Feature Identity

Do not match features by ObjectID unless the user explicitly provides a reliable identity field.

Possible identity field:

```text
Parcel Number
Block Number
CAD Handle
Feature ID
Custom Key
```

Without a reliable identity field, perform:

```text
Layer-level statistical comparison
+
Feature-level issue detection
```

rather than false feature-to-feature matching.

---

# 28. Combined QC Workflow

The user should be able to run:

## Option A

```text
Geometry QC only
```

## Option B

```text
Reference CAD Comparison only
```

## Option C

```text
Reference CAD Comparison
+
Geometry QC on Received CAD
```

Option C should be especially useful for client-submitted CAD.

Workflow:

```text
Original CAD
     ↓
Reference Profile
     ↓
Compare Received CAD
     ↓
Layer / Property QC
     ↓
Geometry QC on Received
     ↓
Combined QC Report
```

---

# 29. Important Example

Suppose:

### Original CAD

```text
Layer: PARCEL

1000 Closed Polylines
Color = 7
Lineweight = 0.25
Linetype = Continuous
```

### Received CAD

```text
Layer: PARCEL

980 Closed Polylines
20 Open Polylines
Color = 1
Lineweight = 0.50
Linetype = Continuous
```

The Comparison QC reports:

```text
❌ Unexpected Open Polylines: 20
❌ Color Difference
❌ Lineweight Difference
✓ Linetype Match
⚠ Feature Count Difference
```

Then Geometry QC additionally finds:

```text
❌ 3 Overlaps
❌ 2 Gaps
❌ 8 Snap Issues
❌ 5 Short Segments
❌ 1 Missing Junction
```

The final report must show both groups separately.

---

# 30. Reporting

Use `openpyxl` for Excel.

Excel sheets:

```text
Summary
Reference Profile
Layer Overview
Layer Differences
Geometry Comparison
Property Comparison
Unexpected Features
Closure Issues
Feature Count Differences
Geometry QC Summary
Geometry QC Issues
Issue Details
```

---

# 31. Geometry QC Summary

Example:

| Check            | Issues | Status  |
| ---------------- | -----: | ------- |
| Invalid Geometry |      0 | PASS    |
| Overlap          |      3 | ERROR   |
| Duplicate        |      0 | PASS    |
| Enclosed Gap     |      2 | ERROR   |
| Multipart        |      1 | WARNING |
| Short Segment    |      5 | WARNING |
| Angle            |      0 | PASS    |
| Snap             |      8 | ERROR   |
| Redundant Vertex |     12 | WARNING |
| Missing Junction |      1 | ERROR   |

---

# 32. CAD Comparison Summary

Example:

| Check                  | Issues |
| ---------------------- | -----: |
| Missing Layers         |      1 |
| Extra Layers           |      2 |
| Geometry Differences   |     20 |
| Unexpected Features    |     20 |
| Color Differences      |      5 |
| Lineweight Differences |      4 |
| Linetype Differences   |      0 |
| Closure Differences    |      8 |
| Count Differences      |      3 |

---

# 33. HTML Report

Generate a self-contained HTML report containing:

```text
Executive Summary
Reference Profile
CAD Comparison
Layer Differences
Property Differences
Unexpected Features
Closure Issues
Geometry QC
Detailed Issues
```

---

# 34. ArcGIS Pro Issue Visualization

Provide optional temporary graphics / output issue Feature Class.

The existing Geometry QC Analyzer uses categorized visual overlays and allows users to inspect issues spatially. Preserve this concept in the Python implementation where feasible.

Each issue type should have a distinct visual category.

For example:

```text
Overlap
Gap
Snap
Short Segment
Angle
Redundant Vertex
Junction
Invalid Geometry
```

The exact colors should be configurable.

Do not modify the source geometry.

---

# 35. Issue Navigation

Where possible, issue records should retain:

```text
Layer
Object ID
Related Object ID
Issue Type
Geometry
Location
```

so the user can:

```text
Select Issue
→ Zoom to Issue
→ Inspect Feature
```

This follows the workflow of the existing Geometry QC Analyzer, which provides categorized results, OID tracking, and zoom-to-issue behavior.

---

# 36. Read-Only Requirement

Both tools must be strictly:

```text
READ
ANALYZE
REPORT
```

Never:

```text
EDIT
REPAIR
DELETE
MOVE
MERGE
SPLIT
RENAME
```

source features.

The existing Geometry QC Analyzer is explicitly read-only; preserve this behavior.

---

# 37. Performance Requirements

Target:

```text
Up to approximately 10,000,000 features
```

Requirements:

```text
No O(n²) brute-force comparisons
Use spatial indexing
Use vertex indexing
Use bounding-box filtering
Use arcpy.da cursors
Avoid loading unnecessary geometry into memory
```

For the CAD comparison:

```text
One efficient Reference analysis
One efficient Received analysis
Compare aggregated profiles
```

For Geometry QC:

```text
Candidate filtering first
Detailed geometry testing second
```

---

# 38. Project Architecture

Recommended structure:

```text
CAD_QC_Toolbox.pyt

helpers/
│
├── geometry/
│   ├── geometry_classifier.py
│   ├── spatial_index.py
│   ├── vertex_index.py
│   ├── invalid_geometry.py
│   ├── overlap.py
│   ├── duplicate.py
│   ├── gap.py
│   ├── multipart.py
│   ├── short_segment.py
│   ├── angle.py
│   ├── snap.py
│   ├── redundant_vertex.py
│   └── junction.py
│
├── comparison/
│   ├── reference_profiler.py
│   ├── layer_analyzer.py
│   ├── property_comparator.py
│   ├── geometry_comparator.py
│   ├── closure_checker.py
│   └── comparison_engine.py
│
├── reporting/
│   ├── report_excel.py
│   ├── report_html.py
│   └── report_text.py
│
├── models/
│   ├── qc_issue.py
│   ├── qc_result.py
│   └── reference_profile.py
│
└── validation.py
```

---

# 39. Shared QC Issue Model

Both systems must produce the same issue structure.

```python
QCIssue(
    issue_id,
    check_id,
    issue_type,
    severity,
    source,
    layer_name,
    object_id,
    related_object_id,
    property_name,
    expected_value,
    actual_value,
    measurement,
    threshold,
    geometry,
    details
)
```

This allows one reporting engine to handle:

```text
Geometry QC
+
CAD Comparison QC
```

---

# 40. No Hard-Coded CAD Standards

Never write logic such as:

```python
if layer == "PARCEL":
```

or:

```python
if color != 7:
```

or:

```python
if lineweight != 0.25:
```

unless those values came from the Reference Profile.

Correct:

```python
reference = build_reference_profile(reference_source)

result = compare(
    reference,
    received
)
```

The Reference CAD determines the expected state.

---

# 41. Validation

`updateMessages()` must validate:

```text
Reference exists
Received exists
Layer fields exist
Sources are readable
Spatial references can be inspected
Output folder exists
Tolerance values are valid
At least one QC check is enabled
```

---

# 42. Coordinate System

Compare spatial references.

If different:

```text
WARNING:
Reference and Received spatial references differ.
```

Do not automatically transform either dataset.

---

# 43. Testing Requirements

Create tests for every Geometry QC check:

```text
Invalid Geometry
Overlap
Duplicate
Gap
Multipart
Short Segment
Angle
Snap
Redundant Vertex
Missing Junction
```

And every Reference Comparison category:

```text
Missing Layer
Extra Layer
Geometry Type
Unexpected Feature
Color
Lineweight
Linetype
Closure
Feature Count
Mixed Geometry
```

Also test:

```text
Different ObjectIDs
Different layer case
Whitespace
Unavailable properties
Mixed Reference properties
Large datasets
Empty layers
```

---

# 44. Final Acceptance Criteria

The final toolbox must allow the user to select:

```text
REFERENCE / ORIGINAL CAD
+
RECEIVED / CLIENT CAD
```

and produce:

### CAD Comparison QC

```text
✓ Missing Layers
✓ Extra Layers
✓ Feature Count Differences
✓ Geometry Type Differences
✓ Unexpected Features
✓ Open/Closed Differences
✓ Color Differences
✓ Lineweight Differences
✓ Linetype Differences
✓ Text/Annotation Differences
✓ Property Distribution Differences
```

### Geometry QC

```text
✓ Invalid Geometry
✓ Overlap
✓ Duplicate Geometry
✓ Enclosed Gap
✓ Multipart
✓ Short Segment
✓ Angle Issue
✓ Snap Issue
✓ Redundant Vertex
✓ Missing Junction
```

### Outputs

```text
✓ Reference Profile
✓ Excel Report
✓ HTML Report
✓ TXT Report
✓ Optional Issue Feature Class
✓ Spatial Issue Visualization
✓ Feature/Object ID traceability
```

---

# 45. Final Product Philosophy

The tool should answer two fundamental questions:

### Reference QC

> **"What changed between my correct Original CAD and the Received CAD?"**

### Geometry QC

> **"What is geometrically or topologically wrong with the CAD?"**

These must remain independent but integrated.

The final architecture is therefore:

```text
                  ORIGINAL CAD
                       │
                       ▼
              REFERENCE PROFILER
                       │
                       ▼
              REFERENCE PROFILE
                       │
                       ▼
                  RECEIVED CAD
                       │
                       ▼
             ┌──────────────────┐
             │ COMPARISON ENGINE│
             └──────────────────┘
                       │
                       ▼
               CAD COMPARISON QC
                       │
                       │
                       ▼
              GEOMETRY QC ENGINE
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
    CAD QC RESULTS          GEOMETRY QC RESULTS
          │                         │
          └────────────┬────────────┘
                       ▼
                  FINAL QC REPORT
```

The Reference CAD defines **what should be there**.

The Geometry QC engine determines **whether the geometry itself is valid and topologically clean**.

Both results must be available independently and in one combined QC report.

# -*- coding: utf-8 -*-
"""
Mock ArcPy implementation for offline unit testing without ArcGIS Pro / ArcPy binaries.
Provides minimal emulation of ArcPy geometry types (Point, Array, Polygon, Polyline, Extent, SpatialReference)
and basic environment/management functions so the entire test suite can run in any Python environment.
"""

import os
import sys
import math
from typing import List, Tuple, Any, Optional


class SpatialReference:
    def __init__(self, item: Any = 3857):
        self.factoryCode = int(item) if str(item).isdigit() else 3857
        self.name = "WGS_1984_Web_Mercator_Auxiliary_Sphere" if self.factoryCode == 3857 else str(item)


class Point:
    def __init__(self, x: float = 0.0, y: float = 0.0, z: Optional[float] = None, m: Optional[float] = None):
        self.X = float(x) if x is not None else 0.0
        self.Y = float(y) if y is not None else 0.0
        self.Z = float(z) if z is not None else None
        self.M = float(m) if m is not None else None

    def __repr__(self):
        return f"Point({self.X}, {self.Y})"


class Array(list):
    def __init__(self, seq=()):
        super().__init__(seq)

    def add(self, item):
        self.append(item)

    def removeAll(self):
        self.clear()


class Extent:
    def __init__(self, xmin: float = 0.0, ymin: float = 0.0, xmax: float = 0.0, ymax: float = 0.0):
        self.XMin = float(xmin)
        self.YMin = float(ymin)
        self.XMax = float(xmax)
        self.YMax = float(ymax)

    @property
    def trueCentroid(self):
        return Point((self.XMin + self.XMax) / 2.0, (self.YMin + self.YMax) / 2.0)


class Geometry:
    def __init__(self, geom_type: str = "geometry", spatial_reference: Optional[SpatialReference] = None):
        self.type = geom_type
        self.spatialReference = spatial_reference or SpatialReference(3857)
        self.parts: List[List[Point]] = []

    @property
    def partCount(self) -> int:
        return len(self.parts)

    def getPart(self, index: int = 0) -> Array:
        if 0 <= index < len(self.parts):
            return Array(self.parts[index])
        return Array()

    @property
    def pointCount(self) -> int:
        return sum(len(p) for p in self.parts)

    @property
    def isMultipart(self) -> bool:
        return len(self.parts) > 1

    @property
    def extent(self) -> Extent:
        all_pts = [pt for part in self.parts for pt in part]
        if not all_pts:
            return Extent(0, 0, 0, 0)
        minx = min(pt.X for pt in all_pts)
        miny = min(pt.Y for pt in all_pts)
        maxx = max(pt.X for pt in all_pts)
        maxy = max(pt.Y for pt in all_pts)
        return Extent(minx, miny, maxx, maxy)

    @property
    def trueCentroid(self) -> Point:
        return self.extent.trueCentroid

    @property
    def firstPoint(self) -> Optional[Point]:
        if self.parts and self.parts[0]:
            return self.parts[0][0]
        return None

    @property
    def lastPoint(self) -> Optional[Point]:
        if self.parts and self.parts[-1]:
            return self.parts[-1][-1]
        return None


class Polyline(Geometry):
    def __init__(self, inputs: Any, spatial_reference: Optional[SpatialReference] = None):
        super().__init__(geom_type="polyline", spatial_reference=spatial_reference)
        self._load_inputs(inputs)

    def _load_inputs(self, inputs: Any):
        if not inputs:
            return
        if isinstance(inputs, Array) or isinstance(inputs, list):
            if len(inputs) > 0 and (isinstance(inputs[0], Array) or isinstance(inputs[0], list)):
                for part in inputs:
                    self.parts.append([pt if isinstance(pt, Point) else Point(pt[0], pt[1]) for pt in part])
            else:
                self.parts.append([pt if isinstance(pt, Point) else Point(pt[0], pt[1]) for pt in inputs])

    @property
    def length(self) -> float:
        tot = 0.0
        for part in self.parts:
            for i in range(len(part) - 1):
                tot += math.hypot(part[i + 1].X - part[i].X, part[i + 1].Y - part[i].Y)
        return tot


class Polygon(Geometry):
    def __init__(self, inputs: Any, spatial_reference: Optional[SpatialReference] = None):
        super().__init__(geom_type="polygon", spatial_reference=spatial_reference)
        self._load_inputs(inputs)

    def _load_inputs(self, inputs: Any):
        if not inputs:
            return
        if isinstance(inputs, Array) or isinstance(inputs, list):
            if len(inputs) > 0 and (isinstance(inputs[0], Array) or isinstance(inputs[0], list)):
                for part in inputs:
                    self.parts.append([pt if isinstance(pt, Point) else Point(pt[0], pt[1]) for pt in part])
            else:
                self.parts.append([pt if isinstance(pt, Point) else Point(pt[0], pt[1]) for pt in inputs])

    @property
    def area(self) -> float:
        tot_area = 0.0
        for part in self.parts:
            n = len(part)
            if n < 3:
                continue
            ring_area = 0.0
            for i in range(n):
                j = (i + 1) % n
                ring_area += part[i].X * part[j].Y
                ring_area -= part[j].X * part[i].Y
            tot_area += abs(ring_area) / 2.0
        return tot_area

    @property
    def length(self) -> float:
        tot = 0.0
        for part in self.parts:
            for i in range(len(part) - 1):
                tot += math.hypot(part[i + 1].X - part[i].X, part[i + 1].Y - part[i].Y)
        return tot

    def equals(self, other: Any) -> bool:
        if not isinstance(other, Polygon):
            return False
        if abs(self.area - other.area) > 1e-4:
            return False
        ext1, ext2 = self.extent, other.extent
        return (
            abs(ext1.XMin - ext2.XMin) < 1e-4
            and abs(ext1.YMin - ext2.YMin) < 1e-4
            and abs(ext1.XMax - ext2.XMax) < 1e-4
            and abs(ext1.YMax - ext2.YMax) < 1e-4
        )

    def intersect(self, other: Any, dimension: int = 4) -> "Polygon":
        """Approximates 2D polygon intersection area using bbox overlap."""
        if not isinstance(other, Polygon):
            return Polygon(Array())
        e1 = self.extent
        e2 = other.extent
        ixmin = max(e1.XMin, e2.XMin)
        iymin = max(e1.YMin, e2.YMin)
        ixmax = min(e1.XMax, e2.XMax)
        iymax = min(e1.YMax, e2.YMax)

        if ixmin < ixmax and iymin < iymax:
            arr = Array([
                Point(ixmin, iymin),
                Point(ixmax, iymin),
                Point(ixmax, iymax),
                Point(ixmin, iymax),
                Point(ixmin, iymin),
            ])
            return Polygon(arr, self.spatialReference)
        return Polygon(Array())


class PointGeometry(Geometry):
    def __init__(self, point: Point, spatial_reference: Optional[SpatialReference] = None):
        super().__init__(geom_type="point", spatial_reference=spatial_reference)
        self.parts = [[point]]

    @property
    def X(self) -> float:
        return self.parts[0][0].X

    @property
    def Y(self) -> float:
        return self.parts[0][0].Y


# Mock da cursors
class da:
    _counts = {}

    class SearchCursor:
        def __init__(self, target, fields):
            self.target = target
            self.fields = fields

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def __iter__(self):
            return iter([])

    class InsertCursor:
        def __init__(self, target, fields):
            self.target = target
            self.fields = fields
            da._counts[target] = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def insertRow(self, row):
            da._counts[self.target] = da._counts.get(self.target, 0) + 1

    @staticmethod
    def Walk(top, **kwargs):
        import os
        if os.path.exists(top):
            for dirpath, dirnames, filenames in os.walk(top):
                yield dirpath, dirnames, filenames


# Mock Parameter for toolbox testing
class Parameter:
    def __init__(
        self,
        displayName: str = "",
        name: str = "",
        datatype: Any = "GPString",
        parameterType: str = "Required",
        direction: str = "Input",
    ):
        self.displayName = displayName
        self.name = name
        self.datatype = datatype
        self.parameterType = parameterType
        self.direction = direction
        self.value = None
        self.valueAsText = ""
        self.altered = False
        self.category = ""
        self.filter = type("Filter", (), {"type": "ValueList", "list": []})()
        self.parameterDependencies = []


def AddMessage(msg: str):
    pass


def AddWarning(msg: str):
    pass


def AddError(msg: str):
    pass


def Exists(path: str) -> bool:
    import os
    return os.path.exists(path)


class Describe:
    def __init__(self, target: Any):
        self.name = str(target)
        self.dataType = "FeatureClass"
        self.spatialReference = SpatialReference(3857)
        self.children = []
        self.catalogPath = str(target)


class Env:
    def __init__(self):
        import tempfile, os
        self.workspace = os.path.join(tempfile.gettempdir(), "test_mock.gdb")
        self.scratchGDB = self.workspace


env = Env()


class Management:
    @staticmethod
    def CreateFileGDB(out_folder_path, out_name):
        import os
        path = os.path.join(out_folder_path, out_name)
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def CreateFeatureDataset(out_dataset_path, out_name, spatial_reference=None):
        import os
        path = os.path.join(out_dataset_path, out_name)
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def CreateFeatureclass(out_path, out_name, geometry_type="POINT", spatial_reference=None):
        import os
        os.makedirs(out_path, exist_ok=True)
        path = os.path.join(out_path, out_name)
        with open(path, "w") as f:
            f.write("")
        return path

    @staticmethod
    def CreateTable(out_path, out_name):
        import os
        os.makedirs(out_path, exist_ok=True)
        path = os.path.join(out_path, out_name)
        with open(path, "w") as f:
            f.write("")
        return path

    @staticmethod
    def AddFields(in_table, fields):
        pass

    @staticmethod
    def AddField(in_table, field_name, field_type, **kwargs):
        pass

    @staticmethod
    def Delete(target):
        import os, shutil
        if os.path.isfile(target):
            try:
                os.remove(target)
            except Exception:
                pass
        elif os.path.isdir(target):
            try:
                shutil.rmtree(target)
            except Exception:
                pass

    @staticmethod
    def GetCount(target):
        return [str(da._counts.get(target, 0))]


management = Management()


def ValidateTableName(name: str, workspace: Any = None) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(name))


class MockLayer:
    def __init__(self, name: str = "", is_group: bool = False, data_source: str = ""):
        self.name = name
        self.isGroupLayer = is_group
        self.dataSource = data_source
        self.layers = []


class MockMap:
    def __init__(self, name: str = "Map"):
        self.name = name
        self._layers = []
        self._tables = []

    def listLayers(self, wildcard=None):
        return list(self._layers)

    def listTables(self, wildcard=None):
        return list(self._tables)

    def createGroupLayer(self, name: str):
        grp = MockLayer(name=name, is_group=True)
        self._layers.append(grp)
        return grp

    def addDataFromPath(self, path: str):
        lyr = MockLayer(name=os.path.basename(path), data_source=path)
        self._layers.append(lyr)
        return lyr

    def addLayerToGroup(self, target_group_layer, add_layer, add_position="BOTTOM"):
        target_group_layer.layers.append(add_layer)

    def removeLayer(self, layer):
        if layer in self._layers:
            self._layers.remove(layer)


class MockArcGISProject:
    _current = None

    def __new__(cls, path: str = "CURRENT"):
        if path == "CURRENT":
            if cls._current is None:
                obj = super().__new__(cls)
                obj.activeMap = MockMap("Map")
                obj.defaultGeodatabase = ""
                cls._current = obj
            return cls._current
        obj = super().__new__(cls)
        obj.activeMap = MockMap("Map")
        obj.defaultGeodatabase = ""
        return obj


class mp:
    ArcGISProject = MockArcGISProject


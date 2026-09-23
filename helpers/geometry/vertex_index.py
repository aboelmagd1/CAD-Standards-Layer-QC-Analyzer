# -*- coding: utf-8 -*-
"""
Vertex Grid Index.
Spatial hash grid for vertices to perform fast proximity queries,
sub-millimeter snapping tests, and junction/node matching without O(V^2) comparisons.
"""

import math
from typing import Dict, List, Tuple, Any, Optional


class VertexRecord:
    __slots__ = ("x", "y", "feature_id", "part_idx", "vertex_idx")

    def __init__(self, x: float, y: float, feature_id: Any, part_idx: int, vertex_idx: int):
        self.x = x
        self.y = y
        self.feature_id = feature_id
        self.part_idx = part_idx
        self.vertex_idx = vertex_idx


class VertexGridIndex:
    """
    Spatial hash grid for vertices.
    Bucket size is set according to snap or search tolerance.
    """

    def __init__(self, tolerance: float = 0.05):
        self.cell_size = max(tolerance * 2.0, 0.001)
        self.grid: Dict[Tuple[int, int], List[VertexRecord]] = {}
        self.records: List[VertexRecord] = []

    def insert(self, x: float, y: float, feature_id: Any, part_idx: int = 0, vertex_idx: int = 0) -> VertexRecord:
        rec = VertexRecord(x, y, feature_id, part_idx, vertex_idx)
        self.records.append(rec)
        cx = int(math.floor(x / self.cell_size))
        cy = int(math.floor(y / self.cell_size))
        cell = (cx, cy)
        if cell not in self.grid:
            self.grid[cell] = []
        self.grid[cell].append(rec)
        return rec

    def query_radius(self, x: float, y: float, radius: float) -> List[Tuple[VertexRecord, float]]:
        """
        Finds all vertices within radius of (x, y) with their euclidean distances.
        """
        min_cx = int(math.floor((x - radius) / self.cell_size))
        max_cx = int(math.floor((x + radius) / self.cell_size))
        min_cy = int(math.floor((y - radius) / self.cell_size))
        max_cy = int(math.floor((y + radius) / self.cell_size))

        results = []
        r2 = radius * radius
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                cell_recs = self.grid.get((cx, cy))
                if cell_recs:
                    for rec in cell_recs:
                        dx = rec.x - x
                        dy = rec.y - y
                        d2 = dx * dx + dy * dy
                        if d2 <= r2:
                            results.append((rec, math.sqrt(d2)))
        return results

    def find_nearest(self, x: float, y: float, max_radius: float) -> Optional[Tuple[VertexRecord, float]]:
        """Finds the nearest vertex within max_radius."""
        nearby = self.query_radius(x, y, max_radius)
        if not nearby:
            return None
        return min(nearby, key=lambda item: item[1])

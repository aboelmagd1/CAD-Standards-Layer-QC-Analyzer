# -*- coding: utf-8 -*-
"""
Spatial Index.
High-performance in-memory 2D grid/bucket index for bounding boxes to enable
fast candidate pair reduction (O(N log N) / O(N)) instead of naive O(N^2).
"""

import math
from typing import Dict, List, Tuple, Set, Any


class SpatialGridIndex:
    """
    A 2D spatial grid index for features with bounding boxes.
    Buckets feature IDs into grid cells based on their bounding extent.
    """

    def __init__(self, cell_size: float = 100.0):
        self.cell_size = max(cell_size, 0.001)
        self.grid: Dict[Tuple[int, int], List[Any]] = {}
        self.bboxes: Dict[Any, Tuple[float, float, float, float]] = {}

    def insert(self, feature_id: Any, extent_or_bbox: Any):
        """
        Insert feature by extent or bbox (minx, miny, maxx, maxy).
        """
        if hasattr(extent_or_bbox, "XMin"):
            minx = extent_or_bbox.XMin
            miny = extent_or_bbox.YMin
            maxx = extent_or_bbox.XMax
            maxy = extent_or_bbox.YMax
        elif isinstance(extent_or_bbox, (list, tuple)) and len(extent_or_bbox) >= 4:
            minx, miny, maxx, maxy = extent_or_bbox[:4]
        else:
            return

        self.bboxes[feature_id] = (minx, miny, maxx, maxy)

        c_min_x = int(math.floor(minx / self.cell_size))
        c_min_y = int(math.floor(miny / self.cell_size))
        c_max_x = int(math.floor(maxx / self.cell_size))
        c_max_y = int(math.floor(maxy / self.cell_size))

        for cx in range(c_min_x, c_max_x + 1):
            for cy in range(c_min_y, c_max_y + 1):
                cell = (cx, cy)
                if cell not in self.grid:
                    self.grid[cell] = []
                self.grid[cell].append(feature_id)

    def query(self, extent_or_bbox: Any) -> Set[Any]:
        """Query all feature IDs whose grid cells overlap the given bbox."""
        if hasattr(extent_or_bbox, "XMin"):
            minx = extent_or_bbox.XMin
            miny = extent_or_bbox.YMin
            maxx = extent_or_bbox.XMax
            maxy = extent_or_bbox.YMax
        elif isinstance(extent_or_bbox, (list, tuple)) and len(extent_or_bbox) >= 4:
            minx, miny, maxx, maxy = extent_or_bbox[:4]
        else:
            return set()

        c_min_x = int(math.floor(minx / self.cell_size))
        c_min_y = int(math.floor(miny / self.cell_size))
        c_max_x = int(math.floor(maxx / self.cell_size))
        c_max_y = int(math.floor(maxy / self.cell_size))

        candidates: Set[Any] = set()
        for cx in range(c_min_x, c_max_x + 1):
            for cy in range(c_min_y, c_max_y + 1):
                cell_feats = self.grid.get((cx, cy))
                if cell_feats:
                    candidates.update(cell_feats)

        # Precise bounding-box intersection filter
        results = set()
        for fid in candidates:
            fb = self.bboxes[fid]
            if not (minx > fb[2] or maxx < fb[0] or miny > fb[3] or maxy < fb[1]):
                results.add(fid)

        return results

    def get_candidate_pairs(self) -> Set[Tuple[Any, Any]]:
        """
        Returns all unique pairs (fid1, fid2) with fid1 < fid2 whose bounding boxes overlap.
        """
        pairs: Set[Tuple[Any, Any]] = set()
        for cell_feats in self.grid.values():
            n = len(cell_feats)
            if n < 2:
                continue
            for i in range(n):
                f1 = cell_feats[i]
                b1 = self.bboxes[f1]
                for j in range(i + 1, n):
                    f2 = cell_feats[j]
                    if f1 == f2:
                        continue
                    b2 = self.bboxes[f2]
                    # Check bbox overlap
                    if not (b1[0] > b2[2] or b1[2] < b2[0] or b1[1] > b2[3] or b1[3] < b2[1]):
                        pair = (f1, f2) if f1 < f2 else (f2, f1)
                        pairs.add(pair)
        return pairs

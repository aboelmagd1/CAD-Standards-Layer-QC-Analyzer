# -*- coding: utf-8 -*-
"""
Reference Profile Data Model.
Captures the expected CAD standards extracted dynamically from the Original CAD dataset.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class LayerProfile:
    layer_name: str
    normalized_layer_name: str = ""
    geometry_type: str = "Unknown"  # Polygon, Polyline, Point, Multipoint, Unknown
    feature_count: int = 0
    geometry_distribution: Dict[str, int] = field(default_factory=dict)
    dominant_geometry: Optional[str] = None
    dominant_percentage: float = 0.0
    is_mixed_geometry: bool = False
    closure_required: bool = False
    closed_count: int = 0
    open_count: int = 0
    closure_percentage: float = 0.0
    open_closed_distribution: Dict[str, int] = field(default_factory=dict)
    multipart_distribution: Dict[str, int] = field(default_factory=dict)
    vertex_count_distribution: Dict[str, Any] = field(default_factory=dict)
    zm_availability: Dict[str, bool] = field(default_factory=dict)
    color_distribution: Dict[str, int] = field(default_factory=dict)
    linetype_distribution: Dict[str, int] = field(default_factory=dict)
    lineweight_distribution: Dict[str, int] = field(default_factory=dict)
    text_properties: Dict[str, Any] = field(default_factory=dict)
    available_properties: List[str] = field(default_factory=list)
    sample_attributes: Dict[str, Any] = field(default_factory=dict)

    def dominant_color(self) -> Optional[str]:
        if not self.color_distribution:
            return None
        return max(self.color_distribution.items(), key=lambda x: x[1])[0]

    def dominant_linetype(self) -> Optional[str]:
        if not self.linetype_distribution:
            return None
        return max(self.linetype_distribution.items(), key=lambda x: x[1])[0]

    def dominant_lineweight(self) -> Optional[str]:
        if not self.lineweight_distribution:
            return None
        return max(self.lineweight_distribution.items(), key=lambda x: x[1])[0]


@dataclass
class ReferenceProfile:
    source_path: str
    spatial_reference_name: str = "Unknown"
    spatial_reference_wkid: Optional[int] = None
    total_features: int = 0
    layers: Dict[str, LayerProfile] = field(default_factory=dict)
    available_cad_fields: List[str] = field(default_factory=list)
    analysis_date: str = ""

    def get_layer(self, layer_name: str) -> Optional[LayerProfile]:
        return self.layers.get(layer_name)

    def layer_names(self) -> List[str]:
        return list(self.layers.keys())

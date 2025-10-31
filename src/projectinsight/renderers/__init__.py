# src/projectinsight/renderers/__init__.py
"""
渲染器套件，負責將圖形資料結構視覺化為圖檔。
"""

from .component_renderer import generate_component_dot_source, render_component_graph
from .concept_flow_renderer import generate_concept_flow_dot_source, render_concept_flow_graph
from .dynamic_behavior_renderer import generate_dynamic_behavior_dot_source, render_dynamic_behavior_graph

__all__ = [
    "generate_component_dot_source",
    "generate_concept_flow_dot_source",
    "generate_dynamic_behavior_dot_source",
    "render_component_graph",
    "render_concept_flow_graph",
    "render_dynamic_behavior_graph",
]

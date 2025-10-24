# src/projectinsight/renderers/__init__.py
"""
渲染器套件，負責將圖形資料結構視覺化為圖檔。
"""

from .component_renderer import render_component_graph

__all__ = [
    "render_component_graph",
]

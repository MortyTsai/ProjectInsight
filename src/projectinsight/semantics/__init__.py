# src/projectinsight/semantics/__init__.py
"""
語義分析器套件。

此套件包含用於理解超越純語法呼叫的「架構意圖」的分析器。
- dynamic_behavior_analyzer: 分析由設定檔驅動的動態模式。
- semantic_link_analyzer: 分析靜態 IoC 模式（如註冊、繼承）。
"""

from .dynamic_behavior_analyzer import analyze_dynamic_behavior
from .semantic_link_analyzer import analyze_semantic_links

__all__ = [
    "analyze_dynamic_behavior",
    "analyze_semantic_links",
]

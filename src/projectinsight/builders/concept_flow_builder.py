# src/projectinsight/builders/concept_flow_builder.py
"""
提供概念流動圖的建構邏輯。
"""

# 1. 標準庫導入
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


def build_concept_flow_graph_data(analysis_results: dict[str, Any]) -> dict[str, Any]:
    """
    將概念流動分析器的結果轉換為圖形資料結構。

    Args:
        analysis_results: 來自 concept_flow_parser 的分析結果。

    Returns:
        一個包含節點和邊的圖形資料字典。
    """
    edges = analysis_results.get("edges", [])
    nodes: set[str] = set()

    for source, target in edges:
        nodes.add(source)
        nodes.add(target)

    return {
        "nodes": sorted(nodes),
        "edges": sorted(edges),
    }

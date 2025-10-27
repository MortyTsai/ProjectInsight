# src/projectinsight/builders/dynamic_behavior_builder.py
"""
提供動態行為圖的建構邏輯。
"""

# 1. 標準庫導入
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


def build_dynamic_behavior_graph_data(analysis_results: dict[str, Any]) -> dict[str, Any]:
    """
    將動態行為分析器的結果轉換為圖形資料結構。

    Args:
        analysis_results: 來自 dynamic_behavior_analyzer 的分析結果。

    Returns:
        一個包含節點和邊的圖形資料字典。
    """
    links = analysis_results.get("links", [])
    nodes: dict[str, Any] = {}

    for link in links:
        p_info = link["producer_info"]
        c_info = link["consumer_info"]

        nodes[p_info["caller_fqn"]] = p_info
        nodes[c_info["caller_fqn"]] = c_info

    edges = links

    return {
        "nodes": nodes,
        "edges": sorted(edges, key=lambda x: (x["source"], x["target"])),
    }
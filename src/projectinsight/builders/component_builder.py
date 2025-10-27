# src/projectinsight/builders/component_builder.py
"""
提供高階組件互動圖的建構邏輯。
"""

# 1. 標準庫導入
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


def _get_node_for_path(full_path: str, all_components: set[str]) -> str:
    """
    確定一個完整路徑應該對應到哪個圖節點。
    如果路徑是某個組件的成員，則返回組件路徑。
    否則，返回其自身路徑（即它是一個模組級函式）。
    """
    parts = full_path.split(".")
    for i in range(len(parts) - 1, 0, -1):
        potential_component = ".".join(parts[:i])
        if potential_component in all_components:
            return potential_component
    return full_path


def build_component_graph_data(
    call_graph: set[tuple[str, str]],
    all_components: set[str],
    show_internal_calls: bool = True,
) -> dict[str, list[Any]]:
    """
    將函式級的呼叫圖抽象提升為組件級/模組函式級的互動圖。
    """
    component_edges: set[tuple[str, str]] = set()

    for caller, callee in call_graph:
        caller_node = _get_node_for_path(caller, all_components)
        callee_node = _get_node_for_path(callee, all_components)

        if caller_node and callee_node and caller_node != callee_node:
            component_edges.add((caller_node, callee_node))

    edges = component_edges
    if not show_internal_calls:
        filtered_edges = set()
        for caller, callee in component_edges:
            caller_module = ".".join(caller.split(".")[:-1])
            callee_module = ".".join(callee.split(".")[:-1])
            if caller_module != callee_module:
                filtered_edges.add((caller, callee))
        edges = filtered_edges

    nodes: set[str] = set()
    for caller, callee in edges:
        nodes.add(caller)
        nodes.add(callee)

    return {
        "nodes": sorted(nodes),
        "edges": sorted(edges),
    }

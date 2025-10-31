# src/projectinsight/builders/component_builder.py
"""
提供高階組件互動圖的建構邏輯。
"""

# 1. 標準庫導入
from collections import defaultdict
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


def _get_component_for_path(full_path: str, all_components: set[str], all_definitions: set[str]) -> str | None:
    """
    [最終修正] 確定一個 FQN 應歸屬到的高階組件（類別或公開的模組級函式）。
    """
    # 優先判斷是否為某個已知類別的成員
    parts = full_path.split(".")
    for i in range(len(parts) - 1, 0, -1):
        potential_component = ".".join(parts[:i])
        if potential_component in all_components:
            return potential_component

    # 如果不是類別成員，檢查它自身是否就是一個已知的頂層定義（模組級函式）
    if full_path in all_definitions:
        return full_path

    # 如果以上都不是（例如，它是一個巢狀的私有函式），則不返回任何組件
    return None


def build_component_graph_data(
    call_graph: set[tuple[str, str]],
    all_components: set[str],
    definition_to_module_map: dict[str, str],
    docstring_map: dict[str, str],
    show_internal_calls: bool = True,
) -> dict[str, Any]:
    """
    [最終修正] 將函式級的呼叫圖抽象提升為組件級（類別或公開函式）的互動圖。
    """
    component_edges: set[tuple[str, str]] = set()
    all_definitions = set(definition_to_module_map.keys())

    for caller, callee in call_graph:
        caller_component = _get_component_for_path(caller, all_components, all_definitions)
        callee_component = _get_component_for_path(callee, all_components, all_definitions)

        if caller_component and callee_component and caller_component != callee_component:
            component_edges.add((caller_component, callee_component))

    edges = component_edges
    if not show_internal_calls:
        filtered_edges = set()
        for caller, callee in component_edges:
            caller_module = definition_to_module_map.get(caller, ".".join(caller.split(".")[:-1]))
            callee_module = definition_to_module_map.get(callee, ".".join(callee.split(".")[:-1]))
            if caller_module != callee_module:
                filtered_edges.add((caller, callee))
        edges = filtered_edges

    nodes: set[str] = set()
    for caller, callee in edges:
        nodes.add(caller)
        nodes.add(callee)

    nodes_by_module: dict[str, list[str]] = defaultdict(list)
    for node in sorted(nodes):
        module_path = definition_to_module_map.get(node)
        if module_path:
            nodes_by_module[module_path].append(node)

    return {
        "nodes": sorted(nodes),
        "edges": sorted(edges),
        "nodes_by_module": nodes_by_module,
        "docstrings": docstring_map,
    }

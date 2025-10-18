# src/projectinsight/builders/flow_builder.py
"""
提供控制流圖的建構邏輯。
"""
# 1. 標準庫導入
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


def _get_module_path_from_func_path(full_path: str, all_modules: set[str]) -> str:
    """從完整的函式/方法路徑中穩健地提取出其所屬的模組路徑。"""
    parts = full_path.split('.')
    for i in range(len(parts) - 1, 0, -1):
        potential_module = ".".join(parts[:i])
        if potential_module in all_modules:
            return potential_module
    return ""


def build_flow_graph_data(
    call_graph: set[tuple[str, str]],
    show_internal_calls: bool = True,
    all_modules: set[str] | None = None
) -> dict[str, list[Any]]:
    """
    將函式呼叫關係轉換為標準的圖形資料格式。
    """
    if all_modules is None:
        all_modules = set()

    edges = call_graph
    if not show_internal_calls:
        filtered_edges = set()
        for caller, callee in call_graph:
            caller_module = _get_module_path_from_func_path(caller, all_modules)
            callee_module = _get_module_path_from_func_path(callee, all_modules)
            if caller_module and callee_module and caller_module != callee_module:
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

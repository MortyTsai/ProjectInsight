# src/projectinsight/builders/dependency_builder.py
"""
提供詳細模組依賴圖的建構邏輯。
"""

# 1. 標準庫導入
import logging
from collections import defaultdict


def build_graph_data(
    all_dependencies: dict[str, list[str]],
    root_package: str
) -> dict[str, dict[str, list[str]] | list[tuple[str, str]]]:
    """
    將解析出的依賴關係轉換為按目錄分組的圖形資料格式，並過濾孤立節點。

    Args:
        all_dependencies: 一個字典，key 是模組名，value 是其依賴的模組列表。
        root_package: 專案的根套件名稱，用於過濾外部依賴。

    Returns:
        一個字典，包含 'nodes_by_dir' (按目錄分組的節點) 和 'edges' (邊列表)。
    """
    edges: set[tuple[str, str]] = set()
    nodes_with_edges: set[str] = set()

    internal_modules = {
        module for module in all_dependencies if module.startswith(root_package)
    }

    for module in internal_modules:
        for dep in all_dependencies.get(module, []):
            if dep in internal_modules:
                edge = (module, dep)
                edges.add(edge)
                nodes_with_edges.add(module)
                nodes_with_edges.add(dep)

    nodes_by_dir: dict[str, list[str]] = defaultdict(list)
    for module in nodes_with_edges:
        parent_dir = ".".join(module.split('.')[:-1])
        if not parent_dir:
            parent_dir = root_package
        nodes_by_dir[parent_dir].append(module)

    logging.info(f"圖表建構完成：共 {len(nodes_with_edges)} 個內部模組節點 (已過濾孤立點)，{len(edges)} 條內部依賴邊。")

    return {
        "nodes_by_dir": dict(nodes_by_dir),
        "edges": sorted(edges)
    }

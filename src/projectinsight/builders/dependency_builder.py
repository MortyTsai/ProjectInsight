# src/projectinsight/builders/dependency_builder.py
"""
提供詳細模組依賴圖的建構邏輯。
"""
# 1. 標準庫導入
import logging
from collections import defaultdict
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


def build_graph_data(
    all_module_details: dict[str, dict[str, list[Any]]],
    root_package: str
) -> dict[str, Any]:
    """
    將解析出的依賴關係和模組細節轉換為渲染器所需的圖形資料格式。
    """
    edges: set[tuple[str, str]] = set()
    internal_modules = set(all_module_details.keys())

    for module, details in all_module_details.items():
        for imp in details.get("imports", []):
            if imp['type'] == 'direct':
                if imp['module'] in internal_modules:
                    edges.add((module, imp['module']))
            elif imp['type'] == 'from':
                base_module = imp['module']
                level = imp['level']

                if level > 0:  # Relative import
                    source_parts = module.split('.')
                    if level >= len(source_parts):
                        continue
                    base_parts = source_parts[:-level]
                    base_module = ".".join(base_parts) + "." + base_module if base_module else ".".join(base_parts)

                for symbol in imp['symbols']:
                    potential_module = f"{base_module}.{symbol}"
                    if potential_module in internal_modules:
                        edges.add((module, potential_module))
                    elif base_module in internal_modules:
                        edges.add((module, base_module))

    nodes_by_dir: dict[str, list[str]] = defaultdict(list)
    for module in internal_modules:
        parent_dir = ".".join(module.split('.')[:-1]) or root_package
        nodes_by_dir[parent_dir].append(module)

    logging.info(f"依賴圖建構完成：共 {len(internal_modules)} 個內部模組節點，{len(edges)} 條內部依賴邊。")
    return {
        "nodes_by_dir": {k: sorted(v) for k, v in nodes_by_dir.items()},
        "edges": sorted(edges),
        "module_details": all_module_details,
    }

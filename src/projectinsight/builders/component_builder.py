# src/projectinsight/builders/component_builder.py
"""
提供高階組件互動圖的建構邏輯。
"""

# 1. 標準庫導入
import fnmatch
from collections import defaultdict, deque
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


def _get_component_for_path(full_path: str, all_components: set[str], all_definitions: set[str]) -> str | None:
    """
    確定一個 FQN 應歸屬到的高階組件（類別或公開的模組級函式）。
    """
    parts = full_path.split(".")
    for i in range(len(parts) - 1, 0, -1):
        potential_component = ".".join(parts[:i])
        if potential_component in all_components:
            return potential_component

    if full_path in all_definitions:
        return full_path

    return None


def _perform_focus_analysis(
    all_nodes: set[str], all_edges: set[tuple[str, str]], focus_config: dict[str, Any]
) -> tuple[set[str], set[tuple[str, str]]]:
    """
    根據聚焦設定，在有向圖上執行雙向 BFS 以縮小圖的規模。
    """
    entrypoints = focus_config.get("entrypoints", [])
    max_depth = focus_config.get("max_depth", 3)

    if not entrypoints:
        return all_nodes, all_edges

    successors: dict[str, list[str]] = defaultdict(list)
    predecessors: dict[str, list[str]] = defaultdict(list)
    for u, v in all_edges:
        successors[u].append(v)
        predecessors[v].append(u)

    focused_nodes: set[str] = set()
    queue = deque([(ep, 0) for ep in entrypoints if ep in all_nodes])
    visited_successors = {ep for ep in entrypoints if ep in all_nodes}
    visited_predecessors = {ep for ep in entrypoints if ep in all_nodes}

    while queue:
        node, depth = queue.popleft()
        focused_nodes.add(node)
        if depth < max_depth:
            for neighbor in successors.get(node, []):
                if neighbor not in visited_successors:
                    visited_successors.add(neighbor)
                    queue.append((neighbor, depth + 1))

    queue = deque([(ep, 0) for ep in entrypoints if ep in all_nodes])
    while queue:
        node, depth = queue.popleft()
        focused_nodes.add(node)
        if depth < max_depth:
            for neighbor in predecessors.get(node, []):
                if neighbor not in visited_predecessors:
                    visited_predecessors.add(neighbor)
                    queue.append((neighbor, depth + 1))

    focused_edges = {(u, v) for u, v in all_edges if u in focused_nodes and v in focused_nodes}

    return focused_nodes, focused_edges


def build_component_graph_data(
    call_graph: set[tuple[str, str]],
    all_components: set[str],
    definition_to_module_map: dict[str, str],
    docstring_map: dict[str, str],
    show_internal_calls: bool = True,
    filtering_config: dict[str, Any] | None = None,
    focus_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    調整邊過濾邏輯，確保小專案的內部呼叫能正確顯示。
    """
    component_edges: set[tuple[str, str]] = set()
    all_definitions = set(definition_to_module_map.keys())

    for caller, callee in call_graph:
        caller_component = _get_component_for_path(caller, all_components, all_definitions)
        callee_component = _get_component_for_path(callee, all_components, all_definitions)

        if not (caller_component and callee_component):
            continue

        if caller_component != callee_component or show_internal_calls:
            component_edges.add((caller_component, callee_component))

    initial_nodes: set[str] = set()
    for caller, callee in component_edges:
        initial_nodes.add(caller)
        initial_nodes.add(callee)

    if focus_config and focus_config.get("entrypoints"):
        current_nodes, current_edges = _perform_focus_analysis(initial_nodes, component_edges, focus_config)
    else:
        current_nodes, current_edges = initial_nodes, component_edges

    exclude_patterns = filtering_config.get("exclude_nodes", []) if filtering_config else []
    if exclude_patterns:
        final_nodes = set()
        for node in current_nodes:
            is_excluded = any(fnmatch.fnmatch(node, pattern) for pattern in exclude_patterns)
            if not is_excluded:
                final_nodes.add(node)
    else:
        final_nodes = current_nodes

    final_edges = {
        (caller, callee) for caller, callee in current_edges if caller in final_nodes and callee in final_nodes
    }

    nodes_by_module: dict[str, list[str]] = defaultdict(list)
    for node in sorted(final_nodes):
        module_path = definition_to_module_map.get(node)
        if module_path:
            nodes_by_module[module_path].append(node)

    return {
        "nodes": sorted(final_nodes),
        "edges": sorted(final_edges),
        "nodes_by_module": nodes_by_module,
        "docstrings": docstring_map,
    }

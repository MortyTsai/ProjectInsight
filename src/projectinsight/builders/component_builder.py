# src/projectinsight/builders/component_builder.py
"""
提供高階組件互動圖的建構邏輯。
"""

# 1. 標準庫導入
import fnmatch
import logging
from collections import defaultdict, deque
from typing import Any


# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


def _get_component_for_path(full_path: str, all_components: set[str],
                            definition_to_module_map: dict[str, str]) -> str | None:
    """
    確定一個 FQN 應歸屬到的高階組件（類別或公開的模組級函式）。
    [降噪] 新增了對 '<locals>' 的處理，將內部函式呼叫歸屬回其父組件。
    """
    if not full_path:
        return None

    # [新增] 處理 <locals> 雜訊
    # 如果一個 FQN 包含 'locals' (例如 A.B.<locals>.C)，
    # 我們將其歸屬回其父組件 (A.B)，以消除低層次雜訊。
    if ".<locals>." in full_path:
        full_path = full_path.split(".<locals>.", 1)[0]

    if full_path in all_components:
        return full_path

    parts = full_path.split(".")
    # [修正] 修正 range() 的第三個參數 (來自上次開發)
    for i in range(len(parts) - 1, 0, -1):
        potential_component = ".".join(parts[:i])
        if potential_component in all_components:
            return potential_component

    if full_path in definition_to_module_map:
        return full_path

    return full_path


def _perform_focus_analysis(
        all_nodes: set[str], all_edges: set[tuple[str, str]], focus_config: dict[str, Any], current_depth: int
) -> tuple[set[str], set[tuple[str, str]]]:
    """
    根據聚焦設定，在有向圖上執行雙向 BFS 以縮小圖的規模。
    """
    entrypoints = focus_config.get("entrypoints", [])
    if not entrypoints:
        return all_nodes, all_edges

    logging.debug(f"--- FOCUS ANALYSIS (depth={current_depth}) ---")
    logging.debug(f"Entrypoints: {entrypoints}")
    logging.debug(f"Received all_edges count: {len(all_edges)}")

    successors: dict[str, list[str]] = defaultdict(list)
    predecessors: dict[str, list[str]] = defaultdict(list)
    for u, v in all_edges:
        successors[u].append(v)
        predecessors[v].append(u)

    entrypoint_node = entrypoints[0]
    if entrypoint_node in successors:
        logging.debug(f"Successors of '{entrypoint_node}': {successors[entrypoint_node]}")
    else:
        logging.debug(f"'{entrypoint_node}' has NO successors in the graph.")
    if entrypoint_node in predecessors:
        logging.debug(f"Predecessors of '{entrypoint_node}': {predecessors[entrypoint_node]}")
    else:
        logging.debug(f"'{entrypoint_node}' has NO predecessors in the graph.")

    # [修正] 修正 BFS 演算法的實現，使其更標準和健壯
    visited_successors = set()
    queue = deque([(ep, 0) for ep in entrypoints if ep in all_nodes])
    for ep in entrypoints:
        if ep in all_nodes:
            visited_successors.add(ep)

    while queue:
        node, depth = queue.popleft()
        if depth >= current_depth:
            continue
        for neighbor in successors.get(node, []):
            if neighbor not in visited_successors:
                visited_successors.add(neighbor)
                queue.append((neighbor, depth + 1))

    visited_predecessors = set()
    queue = deque([(ep, 0) for ep in entrypoints if ep in all_nodes])
    for ep in entrypoints:
        if ep in all_nodes:
            visited_predecessors.add(ep)

    while queue:
        node, depth = queue.popleft()
        if depth >= current_depth:
            continue
        for neighbor in predecessors.get(node, []):
            if neighbor not in visited_predecessors:
                visited_predecessors.add(neighbor)
                queue.append((neighbor, depth + 1))

    final_focused_nodes = visited_successors.union(visited_predecessors)
    logging.debug(f"Visited successors: {len(visited_successors)}")
    logging.debug(f"Visited predecessors: {len(visited_predecessors)}")
    logging.debug(f"Final focused nodes count: {len(final_focused_nodes)}")

    focused_edges = {(u, v) for u, v in all_edges if u in final_focused_nodes and v in final_focused_nodes}

    return final_focused_nodes, focused_edges


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
    調整邊過濾邏輯，並實現智慧化深度調整。
    """
    component_edges: set[tuple[str, str]] = set()

    logging.debug(f"--- BUILDER: 開始建構組件圖 ---")
    logging.debug(f"接收到 call_graph 邊數: {len(call_graph)}")
    logging.debug(f"接收到 all_components 節點數: {len(all_components)}")
    logging.debug(f"接收到 definition_to_module_map 條目數: {len(definition_to_module_map)}")

    for i, (caller, callee) in enumerate(call_graph):
        if i < 10:
            logging.debug(f"  - 樣本邊 #{i + 1}: {caller} -> {callee}")

    for caller, callee in call_graph:
        caller_component = _get_component_for_path(caller, all_components, definition_to_module_map)
        callee_component = _get_component_for_path(callee, all_components, definition_to_module_map)

        if not (caller_component and callee_component):
            logging.debug(f"  - [丟棄的邊] 原因: 元件解析失敗")
            logging.debug(f"    - Caller: '{caller}' -> '{caller_component}'")
            logging.debug(f"    - Callee: '{callee}' -> '{callee_component}'")
            continue

        if caller_component != callee_component or show_internal_calls:
            component_edges.add((caller_component, callee_component))

    logging.debug(f"轉換後 component_edges 邊數: {len(component_edges)}")

    initial_nodes: set[str] = set()
    for caller, callee in component_edges:
        initial_nodes.add(caller)
        initial_nodes.add(callee)

    current_nodes, current_edges = initial_nodes, component_edges

    if focus_config and focus_config.get("entrypoints"):
        enable_dynamic_depth = focus_config.get("enable_dynamic_depth", True)
        if enable_dynamic_depth:
            initial_depth = focus_config.get("initial_depth", 2)
            min_nodes = focus_config.get("min_nodes", 10)
            max_search_depth = focus_config.get("max_search_depth", 7)

            current_depth = initial_depth
            while current_depth <= max_search_depth:
                logging.info(f"執行聚焦分析，當前深度: {current_depth}...")
                temp_nodes, temp_edges = _perform_focus_analysis(
                    initial_nodes, component_edges, focus_config, current_depth
                )

                if len(temp_nodes) >= min_nodes:
                    logging.info(f"找到 {len(temp_nodes)} 個節點 (>= {min_nodes})，停止增加深度。")
                    current_nodes, current_edges = temp_nodes, temp_edges
                    break

                current_nodes, current_edges = temp_nodes, temp_edges
                if current_depth == max_search_depth:
                    logging.warning(f"已達到最大搜索深度 ({max_search_depth})，但仍只有 {len(current_nodes)} 個節點。")
                    break

                logging.info(f"只找到 {len(temp_nodes)} 個節點 (< {min_nodes})，自動增加深度...")
                current_depth += 1
        else:
            fixed_depth = focus_config.get("initial_depth", 2)
            current_nodes, current_edges = _perform_focus_analysis(
                initial_nodes, component_edges, focus_config, fixed_depth
            )

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
        if not module_path and "." in node:
            module_path = node.rsplit(".", 1)[0]

        if module_path:
            nodes_by_module[module_path].append(node)

    return {
        "nodes": sorted(final_nodes),
        "edges": sorted(final_edges),
        "nodes_by_module": nodes_by_module,
        "docstrings": docstring_map,
    }
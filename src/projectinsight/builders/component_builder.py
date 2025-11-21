# src/projectinsight/builders/component_builder.py
"""
提供高階組件互動圖的建構邏輯。
實作智慧自動降級 (Smart Fallback)：當雙向分析導致節點爆炸時，自動切換至單向模式。
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


def _perform_focus_analysis(
    all_nodes: set[str],
    all_edges: set[tuple[str, str]],
    focus_config: dict[str, Any],
    current_depth: int,
) -> tuple[set[str], set[tuple[str, str]]]:
    """
    根據聚焦設定，在有向圖上執行 BFS 以縮小圖的規模。
    支援方向控制：'both', 'upstream' (predecessors), 'downstream' (successors)。
    """
    entrypoints = focus_config.get("entrypoints", [])
    direction = focus_config.get("direction", "both")

    if not entrypoints:
        return all_nodes, all_edges

    logging.debug(f"--- FOCUS ANALYSIS (depth={current_depth}, direction={direction}) ---")
    logging.debug(f"Entrypoints: {entrypoints}")

    successors: dict[str, list[str]] = defaultdict(list)
    predecessors: dict[str, list[str]] = defaultdict(list)
    for u, v in all_edges:
        successors[u].append(v)
        predecessors[v].append(u)

    final_nodes = set()
    for ep in entrypoints:
        if ep in all_nodes:
            final_nodes.add(ep)

    if direction in ("both", "downstream"):
        visited_successors = set(final_nodes)
        queue_succ = deque([(ep, 0) for ep in final_nodes])

        while queue_succ:
            node, depth = queue_succ.popleft()
            if depth >= current_depth:
                continue
            for neighbor in successors.get(node, []):
                if neighbor not in visited_successors:
                    visited_successors.add(neighbor)
                    queue_succ.append((neighbor, depth + 1))

        final_nodes.update(visited_successors)
        logging.debug(f"Collected {len(visited_successors)} nodes from downstream analysis.")

    if direction in ("both", "upstream"):
        visited_predecessors = set(final_nodes)
        queue_pred = deque([(ep, 0) for ep in final_nodes])

        while queue_pred:
            node, depth = queue_pred.popleft()
            if depth >= current_depth:
                continue
            for neighbor in predecessors.get(node, []):
                if neighbor not in visited_predecessors:
                    visited_predecessors.add(neighbor)
                    queue_pred.append((neighbor, depth + 1))

        final_nodes.update(visited_predecessors)
        logging.debug(f"Collected {len(visited_predecessors)} nodes from upstream analysis.")

    logging.debug(f"Final focused nodes count: {len(final_nodes)}")

    focused_edges = {(u, v) for u, v in all_edges if u in final_nodes and v in final_nodes}

    return final_nodes, focused_edges


def build_component_graph_data(
    call_graph: set[tuple[str, str]],
    all_components: set[str],
    definition_to_module_map: dict[str, str],
    docstring_map: dict[str, str],
    show_internal_calls: bool = True,
    filtering_config: dict[str, Any] | None = None,
    focus_config: dict[str, Any] | None = None,
    semantic_edges: set[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    """
    接收由 Parser 產出的、已經被完全抽象的呼叫圖和語義連結，
    並對其進行過濾和資料結構轉換。
    """
    logging.debug("--- BUILDER: 開始建構組件圖 (職責簡化版) ---")

    if show_internal_calls:
        component_edges = call_graph
    else:
        component_edges = {(caller, callee) for caller, callee in call_graph if caller != callee}

    initial_nodes: set[str] = set()
    for caller, callee in component_edges:
        initial_nodes.add(caller)
        initial_nodes.add(callee)
    if semantic_edges:
        for u, v, _ in semantic_edges:
            initial_nodes.add(u)
            initial_nodes.add(v)
    initial_nodes.update(all_components)

    current_nodes, current_edges = initial_nodes, component_edges
    current_semantic_edges = semantic_edges or set()

    if focus_config and focus_config.get("entrypoints"):
        enable_dynamic_depth = focus_config.get("enable_dynamic_depth", True)

        current_direction = focus_config.get("direction", "both")
        max_nodes_bidirectional = focus_config.get("max_nodes_for_bidirectional", 500)
        auto_fallback = focus_config.get("auto_downstream_fallback", True)

        if enable_dynamic_depth:
            initial_depth = focus_config.get("initial_depth", 2)
            min_nodes = focus_config.get("min_nodes", 10)
            max_search_depth = focus_config.get("max_search_depth", 7)

            current_depth = initial_depth
            while current_depth <= max_search_depth:
                logging.info(f"執行聚焦分析，當前深度: {current_depth} (模式: {current_direction})...")

                current_iter_config = focus_config.copy()
                current_iter_config["direction"] = current_direction

                temp_nodes, temp_edges = _perform_focus_analysis(
                    initial_nodes, component_edges, current_iter_config, current_depth
                )

                if current_direction == "both" and len(temp_nodes) > max_nodes_bidirectional and auto_fallback:
                    logging.warning(
                        f"聚焦分析節點數 ({len(temp_nodes)}) 超過雙向分析安全閾值 ({max_nodes_bidirectional})。"
                    )
                    logging.warning("正在自動切換至 'downstream' (單向) 模式以防止圖表爆炸...")

                    current_direction = "downstream"
                    current_iter_config["direction"] = "downstream"

                    temp_nodes, temp_edges = _perform_focus_analysis(
                        initial_nodes, component_edges, current_iter_config, current_depth
                    )
                    logging.info(f"切換至單向模式後，節點數降至: {len(temp_nodes)}")

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
            current_iter_config = focus_config.copy()
            current_iter_config["direction"] = current_direction

            current_nodes, current_edges = _perform_focus_analysis(
                initial_nodes, component_edges, current_iter_config, fixed_depth
            )

            if current_direction == "both" and len(current_nodes) > max_nodes_bidirectional and auto_fallback:
                logging.warning(f"固定深度分析節點數 ({len(current_nodes)}) 超過閾值，自動切換至 'downstream'。")
                current_iter_config["direction"] = "downstream"
                current_nodes, current_edges = _perform_focus_analysis(
                    initial_nodes, component_edges, current_iter_config, fixed_depth
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
    final_semantic_edges = {
        (u, v, label) for u, v, label in current_semantic_edges if u in final_nodes and v in final_nodes
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
        "semantic_edges": sorted(final_semantic_edges),
        "high_level_components": all_components,
    }

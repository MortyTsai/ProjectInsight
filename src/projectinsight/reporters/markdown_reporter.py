# src/projectinsight/reporters/markdown_reporter.py
"""
提供將分析結果匯總為單一 Markdown 報告的功能。
"""

# 1. 標準庫導入
import datetime
import fnmatch
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
# (無)
# 3. 本專案導入
from projectinsight.utils.file_system_utils import generate_tree_structure


def _collect_source_files(target_project_root: Path, report_settings: dict[str, Any]) -> list[Path]:
    """收集專案中所有應被納入報告的原始碼檔案。"""
    source_code_settings = report_settings.get("source_code", {})
    included_extensions = set(source_code_settings.get("included_extensions", []))
    exclude_dirs = set(report_settings.get("tree_view", {}).get("exclude_dirs", []))

    collected = []
    all_files = sorted([p for p in target_project_root.rglob("*") if p.is_file()])

    for file_path in all_files:
        is_excluded = False
        for part in file_path.parts:
            for pattern in exclude_dirs:
                if fnmatch.fnmatch(part, pattern):
                    is_excluded = True
                    break
            if is_excluded:
                break
        if is_excluded:
            continue

        if file_path.suffix in included_extensions:
            collected.append(file_path)
    return collected


def _write_debug_log(output_path: Path, project_name: str, filtered_components: list[str]):
    """將除錯資訊寫入一個單獨的日誌檔案。"""
    debug_log_path = output_path.with_name(f"{project_name}_InsightDebug.log")
    log_parts = [
        f"# ProjectInsight 除錯日誌: {project_name}",
        f"生成時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n" + "=" * 50,
        "附錄 A: 潛在的分析盲點或獨立組件",
        "=" * 50,
        "說明: 以下列表包含所有在「高階組件互動圖」中被過濾掉的、",
        "尺寸過小的連通分量中的節點 (通常是孤立節點)。",
        "如果在此列表中發現了您認為是核心的組件，這可能表示靜態分析存在盲點，",
        "導致該組件未能被正確連接到主架構圖中。",
        "\n",
    ]
    log_parts.extend(f"- {fqn}" for fqn in filtered_components)

    try:
        debug_log_path.write_text("\n".join(log_parts), encoding="utf-8")
        logging.info(f"除錯日誌已成功儲存至: {debug_log_path}")
    except Exception as e:
        logging.error(f"寫入除錯日誌時發生錯誤: {e}")


def _generate_adjacency_list_text(graph_data: dict[str, Any], context_packages: list[str]) -> list[str]:
    """
    將圖形資料轉換為最高效的、帶有節點類型標籤的鄰接串列 Markdown 格式。
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    semantic_edges = graph_data.get("semantic_edges", [])
    high_level_components = graph_data.get("high_level_components", set())

    adjacency_list = defaultdict(list)
    all_nodes = set(nodes)

    def get_node_tag(fqn: str) -> str:
        """根據節點 FQN 返回其類型標籤。"""
        if fqn in high_level_components:
            return ""
        is_external = not any(fqn.startswith(pkg) for pkg in context_packages)
        if is_external:
            return " (external)"
        return " (private)"

    for u, v, label in semantic_edges:
        all_nodes.add(u)
        all_nodes.add(v)
        adjacency_list[u].append(f"- {label.upper()}: {v}")

    for caller, callee in edges:
        all_nodes.add(caller)
        all_nodes.add(callee)
        adjacency_list[caller].append(f"- CALLS: {callee}")

    if not all_nodes:
        return []

    tagged_node_map = {node: f"{node}{get_node_tag(node)}" for node in all_nodes}

    text_parts = ["<details>\n<summary>點擊展開/摺疊鄰接串列</summary>\n"]
    text_parts.append("```markdown")
    for node in sorted(all_nodes):
        text_parts.append(f"- **{tagged_node_map[node]}**:")
        if node in adjacency_list:
            for edge_str in sorted(adjacency_list[node]):
                parts = edge_str.split(": ", 1)
                if len(parts) == 2:
                    relation, target_node = parts
                    tagged_target = tagged_node_map.get(target_node, target_node)
                    text_parts.append(f"  {relation}: {tagged_target}")
                else:
                    text_parts.append(f"  {edge_str}")
        else:
            pass

    text_parts.append("```\n</details>\n")
    return text_parts


def generate_markdown_report(
    project_name: str,
    target_project_root: Path,
    output_path: Path,
    analysis_results: dict[str, Any],
    report_settings: dict[str, Any],
    context_packages: list[str],
):
    """
    生成一份為 LLM 優化的 Markdown 分析報告，並將除錯資訊寫入單獨的日誌檔案。
    """
    report_parts = []
    analysis_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_parts.append(f"# ProjectInsight 分析報告: {project_name}")
    report_parts.append(f"**分析時間**: {analysis_time}")

    tree_settings = report_settings.get("tree_view", {})
    report_parts.append("\n## 1. 專案結構總覽")
    report_parts.append("<details>\n<summary>點擊展開/摺疊專案檔案樹</summary>\n")
    report_parts.append("```")
    tree_lines = generate_tree_structure(target_project_root, tree_settings=tree_settings)
    report_parts.extend(tree_lines)
    report_parts.append("```\n</details>\n")

    component_graph_data = analysis_results.get("component_graph_data")
    if component_graph_data:
        report_parts.append("## 2. 高階組件關係圖 (鄰接串列)")
        report_parts.extend(_generate_adjacency_list_text(component_graph_data, context_packages))

    concept_dot = analysis_results.get("concept_flow_dot_source")
    if concept_dot:
        report_parts.append("## 3. 概念流動圖")
        report_parts.append("<details>\n<summary>點擊展開/摺疊 DOT 原始碼</summary>\n")
        report_parts.append("```dot")
        report_parts.append(concept_dot)
        report_parts.append("```\n</details>\n")

    dynamic_dot = analysis_results.get("dynamic_behavior_dot_source")
    if dynamic_dot:
        report_parts.append("## 4. 動態行為圖")
        report_parts.append("<details>\n<summary>點擊展開/摺疊 DOT 原始碼</summary>\n")
        report_parts.append("```dot")
        report_parts.append(dynamic_dot)
        report_parts.append("```\n</details>\n")

    report_parts.append("## 5. 專案完整原始碼")
    source_files = _collect_source_files(target_project_root, report_settings)
    for file_path in source_files:
        relative_path = file_path.relative_to(target_project_root).as_posix()
        report_parts.append(f"<details>\n<summary><code>{relative_path}</code></summary>\n")
        file_extension = file_path.suffix.lstrip(".")
        report_parts.append(f"```{file_extension}")
        try:
            content = file_path.read_text(encoding="utf-8")
            report_parts.append(content)
        except Exception as e:
            report_parts.append(f"無法讀取檔案: {e}")
        report_parts.append("```\n</details>\n")

    try:
        final_report = "\n".join(report_parts)
        output_path.write_text(final_report, encoding="utf-8")
        logging.info(f"Markdown 報告已成功儲存至: {output_path}")
    except Exception as e:
        logging.error(f"寫入 Markdown 報告時發生錯誤: {e}")

    filtered_components = analysis_results.get("filtered_components")
    if filtered_components:
        _write_debug_log(output_path, project_name, filtered_components)

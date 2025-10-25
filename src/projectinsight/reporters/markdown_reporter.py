# src/projectinsight/reporters/markdown_reporter.py
"""
提供將分析結果匯總為單一 Markdown 報告的功能。
"""

# 1. 標準庫導入
import datetime
import fnmatch
import logging
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


def generate_markdown_report(
    project_name: str,
    target_project_root: Path,
    output_path: Path,
    analysis_results: dict[str, Any],
    report_settings: dict[str, Any],
):
    """
    生成一份完整的 Markdown 分析報告。

    Args:
        project_name: 專案名稱 (用於報告標題)。
        target_project_root: 被分析專案的根目錄。
        output_path: Markdown 報告的儲存路徑。
        analysis_results: 一個包含所有分析結果的字典。
        report_settings: 包含報告生成規則的字典。
    """
    report_parts = []
    analysis_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- 1. 報告標頭 ---
    report_parts.append(f"# ProjectInsight 分析報告: {project_name}")
    report_parts.append(f"**分析時間**: {analysis_time}")

    # --- 2. 專案結構總覽 ---
    tree_settings = report_settings.get("tree_view", {})
    exclude_dirs = set(tree_settings.get("exclude_dirs", []))
    report_parts.append("\n## 1. 專案結構總覽")
    report_parts.append("<details>\n<summary>點擊展開/摺疊專案檔案樹</summary>\n")
    report_parts.append("```")
    tree_lines = generate_tree_structure(target_project_root, exclude_dirs=exclude_dirs)
    report_parts.extend(tree_lines)
    report_parts.append("```\n</details>\n")

    # --- 3. 組件互動圖 ---
    component_dot = analysis_results.get("component_dot_source")
    if component_dot:
        report_parts.append("## 2. 高階組件互動圖")
        report_parts.append("<details>\n<summary>點擊展開/摺疊 DOT 原始碼</summary>\n")
        report_parts.append("```dot")
        report_parts.append(component_dot)
        report_parts.append("```\n</details>\n")

    # --- 4. 概念流動圖 ---
    concept_dot = analysis_results.get("concept_flow_dot_source")
    if concept_dot:
        report_parts.append("## 3. 概念流動圖")
        report_parts.append("<details>\n<summary>點擊展開/摺疊 DOT 原始碼</summary>\n")
        report_parts.append("```dot")
        report_parts.append(concept_dot)
        report_parts.append("```\n</details>\n")

    # --- 5. 所有原始碼 ---
    report_parts.append("## 4. 專案完整原始碼")
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

    # --- 寫入檔案 ---
    try:
        final_report = "\n".join(report_parts)
        output_path.write_text(final_report, encoding="utf-8")
        logging.info(f"Markdown 報告已成功儲存至: {output_path}")
    except Exception as e:
        logging.error(f"寫入 Markdown 報告時發生錯誤: {e}")

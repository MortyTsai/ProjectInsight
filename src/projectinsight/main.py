# src/projectinsight/main.py
"""
ProjectInsight 主執行入口。
"""

# 1. 標準庫導入
import logging
import os
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import yaml

# 3. 本專案導入
from projectinsight import builders, parsers, renderers, reporters


def process_project(config_path: Path):
    """根據單一設定檔處理一個專案的分析與渲染。"""
    if not config_path.is_file():
        logging.error(f"指定的專案設定檔不存在: {config_path}")
        return

    project_name = config_path.stem
    logging.info(f"========== 開始處理專案: {project_name} ==========")
    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logging.error(f"解析設定檔 '{config_path.name}' 時發生錯誤: {e}")
        return

    target_project_path_str = config.get("target_project_path", "")
    root_package_name = config.get("root_package_name", "")
    output_dir_str = config.get("output_dir", "output")
    analysis_types = config.get("analysis_types", [])
    report_settings = config.get("report_settings", {})
    architecture_layers = config.get("architecture_layers", {})
    vis_config = config.get("visualization", {})

    if not target_project_path_str or not root_package_name:
        logging.error(f"設定檔 '{config_path.name}' 中缺少 'target_project_path' 或 'root_package_name'。")
        return

    if not isinstance(analysis_types, list) or not analysis_types:
        logging.warning(f"設定檔 '{config_path.name}' 中 'analysis_types' 為空或格式不正確，已跳過。")
        return

    config_dir = config_path.parent
    target_project_root = (config_dir / target_project_path_str).resolve()
    output_dir = (config_dir / output_dir_str).resolve()
    os.makedirs(output_dir, exist_ok=True)

    # --- 智慧偵測 Python 原始碼根目錄 (支援 'src' 和非 'src' 佈局) ---
    potential_src_dir = target_project_root / "src"
    if potential_src_dir.is_dir():
        python_source_root = potential_src_dir
        logging.info("偵測到 'src' 佈局。")
    else:
        python_source_root = target_project_root
        logging.info("未偵測到 'src' 佈局，將使用專案根目錄作為 Python 原始碼路徑。")

    logging.info(f"專案報告根目錄: {target_project_root}")
    logging.info(f"Python 原始碼分析根目錄: {python_source_root}")
    logging.info(f"將執行以下分析: {', '.join(analysis_types)}")

    py_files = sorted(python_source_root.rglob("*.py"))
    report_analysis_results: dict[str, Any] = {}

    for analysis_type in analysis_types:
        logging.info(f"--- 開始執行分析: '{analysis_type}' ---")
        if analysis_type == "component_interaction":
            comp_graph_config = vis_config.get("component_interaction_graph", {})
            layout_engine = comp_graph_config.get("layout_engine", "dot")
            show_internal_calls = comp_graph_config.get("show_internal_calls", True)

            analysis_results = parsers.component_parser.analyze_code(python_source_root, root_package_name, py_files)
            graph_data = builders.build_component_graph_data(
                call_graph=analysis_results["call_graph"],
                all_components=analysis_results.get("components", set()),
                show_internal_calls=show_internal_calls,
            )
            dot_source = renderers.generate_component_dot_source(
                graph_data, root_package_name, architecture_layers, layout_engine
            )
            report_analysis_results["component_dot_source"] = dot_source
            png_output_path = output_dir / f"{project_name}_component_interaction_{layout_engine}.png"
            renderers.render_component_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                root_package=root_package_name,
                layer_info=architecture_layers,
                layout_engine=layout_engine,
            )

        elif analysis_type in ("concept_flow", "auto_concept_flow"):
            track_groups: list[dict[str, Any]]

            if analysis_type == "auto_concept_flow":
                auto_concept_config = config.get("auto_concept_flow", {})
                exclude_patterns = auto_concept_config.get("exclude_patterns", [])
                track_groups = parsers.seed_discoverer.discover_seeds(
                    root_pkg=root_package_name,
                    py_files=py_files,
                    project_root=python_source_root,
                    exclude_patterns=exclude_patterns,
                )
            else:  # concept_flow
                concept_flow_config = config.get("concept_flow", {})
                track_groups = concept_flow_config.get("track_groups", [])

            if not track_groups:
                logging.warning(f"在 '{analysis_type}' 分析中未找到任何要追蹤的概念種子，已跳過。")
                continue

            concept_flow_graph_config = vis_config.get("concept_flow_graph", {})
            layout_engine = concept_flow_graph_config.get("layout_engine", "dot")

            analysis_results = parsers.concept_flow_analyzer.analyze_concept_flow(
                root_pkg=root_package_name,
                py_files=py_files,
                track_groups=track_groups,
                project_root=python_source_root,
            )
            graph_data = builders.build_concept_flow_graph_data(analysis_results)
            dot_source = renderers.generate_concept_flow_dot_source(graph_data, root_package_name, layout_engine)
            report_analysis_results["concept_flow_dot_source"] = dot_source
            png_output_path = output_dir / f"{project_name}_concept_flow_{layout_engine}.png"
            renderers.render_concept_flow_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                root_package=root_package_name,
                layout_engine=layout_engine,
            )
        else:
            logging.error(f"未知的分析類型: '{analysis_type}'。")

    # --- 生成最終的 Markdown 報告 ---
    if report_analysis_results:
        report_output_path = output_dir / f"{project_name}_InsightReport.md"
        reporters.generate_markdown_report(
            project_name=project_name,
            target_project_root=target_project_root,
            output_path=report_output_path,
            analysis_results=report_analysis_results,
            report_settings=report_settings,
        )

    logging.info(f"========== 專案 '{project_name}' 處理完成 ==========\n")


def main():
    """主函式，讀取工作區設定，並為每個指定的專案執行處理流程。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    project_root = Path(__file__).resolve().parent.parent.parent

    configs_dir = project_root / "configs"
    workspace_path = configs_dir / "workspace.yaml"
    projects_dir = configs_dir / "projects"

    if not workspace_path.is_file():
        logging.error("工作區設定檔 'workspace.yaml' 不存在。")
        logging.info("請從 'workspace.template.yaml' 複製一份並進行設定。")
        return

    try:
        with open(workspace_path, encoding="utf-8") as f:
            workspace_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logging.error(f"解析工作區設定檔時發生錯誤: {e}")
        return

    active_projects = workspace_config.get("active_projects", [])
    if not active_projects:
        logging.warning("工作區設定檔中沒有指定任何 'active_projects'。")
        return

    logging.info(f"ProjectInsight 工具啟動，在工作區中找到 {len(active_projects)} 個活躍專案。")
    for project_config_name in active_projects:
        config_path = projects_dir / project_config_name
        process_project(config_path)


if __name__ == "__main__":
    main()

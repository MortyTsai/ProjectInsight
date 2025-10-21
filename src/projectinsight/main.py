# src/projectinsight/main.py
"""
ProjectInsight 主執行入口。
"""

# 1. 標準庫導入
import logging
import os
from pathlib import Path

# 2. 第三方庫導入
import yaml

# 3. 本專案導入
from projectinsight import builders, parsers, renderers


def process_project(config_path: Path):
    """根據單一設定檔處理一個專案的分析與渲染。"""
    if not config_path.is_file():
        logging.error(f"指定的專案設定檔不存在: {config_path}")
        return

    logging.info(f"========== 開始處理專案: {config_path.stem} ==========")
    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logging.error(f"解析設定檔 '{config_path.name}' 時發生錯誤: {e}")
        return

    target_src_path_str = config.get("target_src_path", "")
    root_package_name = config.get("root_package_name", "")
    output_dir_str = config.get("output_dir", "output")
    analysis_type = config.get("analysis_type", "component_interaction")
    architecture_layers = config.get("architecture_layers", {})
    vis_config = config.get("visualization", {})
    comp_graph_config = vis_config.get("component_interaction_graph", {})

    if not target_src_path_str or not root_package_name:
        logging.error(f"設定檔 '{config_path.name}' 中缺少 'target_src_path' 或 'root_package_name'。")
        return

    config_dir = config_path.parent
    target_project_src = (config_dir / target_src_path_str).resolve()
    output_dir = (config_dir / output_dir_str).resolve()
    os.makedirs(output_dir, exist_ok=True)

    logging.info(f"分析類型: '{analysis_type}'")

    py_files = sorted(target_project_src.rglob("*.py"))

    if analysis_type == "component_interaction":
        layout_engine = comp_graph_config.get("layout_engine", "dot")
        show_internal_calls = comp_graph_config.get("show_internal_calls", True)
        internal_calls_status = "顯示" if show_internal_calls else "隱藏"
        logging.info(f"生成組件互動圖，使用佈局引擎 '{layout_engine}'... (內部互動: {internal_calls_status})")
        output_path = output_dir / f"{config_path.stem}_component_interaction_{layout_engine}.png"

        analysis_results = parsers.component_parser.analyze_code(target_project_src, root_package_name, py_files)
        all_components = analysis_results.get("components", set())

        graph_data = builders.build_component_graph_data(
            call_graph=analysis_results["call_graph"],
            all_components=all_components,
            show_internal_calls=show_internal_calls,
        )
        renderers.render_component_graph(
            graph_data=graph_data,
            output_path=output_path,
            root_package=root_package_name,
            save_source_file=True,
            layer_info=architecture_layers,
            layout_engine=layout_engine,
        )
    else:
        logging.error(f"未知的分析類型: '{analysis_type}'。目前僅支援 'component_interaction'。")

    logging.info(f"========== 專案 '{config_path.stem}' 處理完成 ==========\n")


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

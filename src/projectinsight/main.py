# src/projectinsight/main.py
"""
ProjectInsight 主執行入口。
"""

import colorsys
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from projectinsight import builders, renderers, reporters
from projectinsight.parsers import component_parser, concept_flow_analyzer, seed_discoverer
from projectinsight.semantics import dynamic_behavior_analyzer

# 定義所有視覺化選項的最佳實踐預設值
DEFAULT_VIS_CONFIG: dict[str, Any] = {
    "component_interaction_graph": {
        "layout_engine": "dot",
        "dpi": 200,
        "layout": {
            "show_internal_calls": True,
            "aspect_ratio": "auto",
        },
        "node_styles": {
            "show_docstrings": True,
            "title": {"font_size": 11, "path_color": "#555555", "main_color": "#000000"},
            "docstring": {"font_size": 9, "color": "#333333", "spacing": 8},
        },
    },
    "dynamic_behavior_graph": {
        "layout_engine": "dot",
        "dpi": 200,
        "node_styles": {
            "show_docstrings": True,
            "title": {"font_size": 11, "path_color": "#555555", "main_color": "#000000"},
            "docstring": {"font_size": 9, "color": "#333333", "spacing": 8},
        },
    },
}


def _merge_configs(default: dict, user: dict) -> dict:
    """遞迴地合併使用者設定到預設設定中。"""
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(default.get(key), dict):
            default[key] = _merge_configs(default[key], value)
        else:
            default[key] = value
    return default


def _generate_color_palette(num_colors: int) -> list[str]:
    """
    [新增] 使用黃金比例演算法生成一個視覺上可區分的、和諧的調色盤。
    """
    palette = []
    # 使用黃金比例的共軛數
    golden_ratio_conjugate = 0.61803398875
    # 從一個隨機的起始色相開始，以增加每次運行的變化性
    hue = 0.7
    for _ in range(num_colors):
        hue += golden_ratio_conjugate
        hue %= 1
        # [核心修正] 降低亮度，提高飽和度，以獲得更鮮豔的顏色
        rgb_float = colorsys.hls_to_rgb(hue, 0.9, 0.9)
        # 將 0-1 的浮點數轉換為 0-255 的整數，並格式化為 HEX 字串
        rgb_int = tuple(int(c * 255) for c in rgb_float)
        palette.append(f"#{rgb_int[0]:02x}{rgb_int[1]:02x}{rgb_int[2]:02x}")
    return palette


def _discover_architecture_layers(root_package_path: Path) -> dict[str, Any]:
    """
    [升級] 自動掃描根套件目錄，並使用演算法調色盤為其分配顏色。
    """
    if not root_package_path.is_dir():
        return {}

    auto_layers = {}
    try:
        sub_packages = [
            item.name
            for item in sorted(root_package_path.iterdir())
            if item.is_dir() and (item / "__init__.py").exists()
        ]

        if not sub_packages:
            return {}

        palette = _generate_color_palette(len(sub_packages))
        for i, layer_key in enumerate(sub_packages):
            auto_layers[layer_key] = {"color": palette[i]}

        logging.info(f"自動發現 {len(auto_layers)} 個架構層級: {', '.join(auto_layers.keys())}")
    except OSError as e:
        logging.warning(f"自動發現架構層級時發生錯誤: {e}")

    return auto_layers


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

    user_vis_config = config.get("visualization", {})
    vis_config = _merge_configs(DEFAULT_VIS_CONFIG.copy(), user_vis_config)

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

    potential_src_dir = target_project_root / "src"
    if potential_src_dir.is_dir():
        python_source_root = potential_src_dir
        logging.info("偵測到 'src' 佈局。")
    else:
        python_source_root = target_project_root
        logging.info("未偵測到 'src' 佈局，將使用專案根目錄作為 Python 原始碼路徑。")

    root_package_path = python_source_root / root_package_name
    auto_discovered_layers = _discover_architecture_layers(root_package_path)
    user_provided_layers = config.get("architecture_layers", {})
    architecture_layers = {**auto_discovered_layers, **user_provided_layers}

    # [核心修正] 為根層級注入一個明確的、中性的定義
    if "(root)" not in architecture_layers:
        architecture_layers["(root)"] = {
            "name": f"{root_package_name} (root)",
            "color": "#EAEAEA",  # 一個清晰、中性的淺灰色
        }

    logging.info(f"專案報告根目錄: {target_project_root}")
    logging.info(f"Python 原始碼分析根目錄: {python_source_root}")
    logging.info(f"將執行以下分析: {', '.join(analysis_types)}")

    py_files = sorted(python_source_root.rglob("*.py"))
    report_analysis_results: dict[str, Any] = {}

    parser_results: dict[str, Any] = {}
    graph_analysis_types = {
        "component_interaction",
        "auto_concept_flow",
        "dynamic_behavior",
    }
    if any(at in analysis_types for at in graph_analysis_types):
        logging.info("--- 預執行程式碼解析以獲取共享資訊 (Docstrings, etc.) ---")
        parser_results = component_parser.analyze_code(python_source_root, root_package_name, py_files)

    docstring_map = parser_results.get("docstring_map", {})

    for analysis_type in analysis_types:
        logging.info(f"--- 開始執行分析: '{analysis_type}' ---")
        if analysis_type == "component_interaction":
            comp_graph_config = vis_config["component_interaction_graph"]
            layout_config = comp_graph_config.get("layout", {})
            show_internal_calls = layout_config.get("show_internal_calls", True)

            graph_data = builders.build_component_graph_data(
                call_graph=parser_results.get("call_graph", set()),
                all_components=parser_results.get("components", set()),
                definition_to_module_map=parser_results.get("definition_to_module_map", {}),
                docstring_map=docstring_map,
                show_internal_calls=show_internal_calls,
            )
            dot_source = renderers.generate_component_dot_source(
                graph_data, root_package_name, architecture_layers, comp_graph_config
            )
            report_analysis_results["component_dot_source"] = dot_source
            layout_engine = comp_graph_config.get("layout_engine", "dot")
            png_output_path = output_dir / f"{project_name}_component_interaction_{layout_engine}.png"
            renderers.render_component_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                root_package=root_package_name,
                layer_info=architecture_layers,
                comp_graph_config=comp_graph_config,
            )

        elif analysis_type == "auto_concept_flow":
            auto_concept_config = config.get("auto_concept_flow", {})
            exclude_patterns = auto_concept_config.get("exclude_patterns", [])
            track_groups = seed_discoverer.discover_seeds(
                root_pkg=root_package_name,
                py_files=py_files,
                project_root=python_source_root,
                exclude_patterns=exclude_patterns,
            )

            if not track_groups:
                logging.warning(f"在 '{analysis_type}' 分析中未找到任何要追蹤的概念種子，已跳過。")
                continue

            layout_engine = "sfdp"
            dpi = "200"

            analysis_results = concept_flow_analyzer.analyze_concept_flow(
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
                dpi=dpi,
            )

        elif analysis_type == "dynamic_behavior":
            dynamic_behavior_config = config.get("dynamic_behavior_analysis", {})
            rules = dynamic_behavior_config.get("rules", [])
            roles = dynamic_behavior_config.get("roles", {})
            if not rules:
                logging.warning("在 'dynamic_behavior' 分析中未找到任何規則，已跳過。")
                continue

            db_graph_config = vis_config["dynamic_behavior_graph"]

            analysis_results = dynamic_behavior_analyzer.analyze_dynamic_behavior(
                py_files=py_files,
                rules=rules,
                project_root=python_source_root,
            )
            graph_data = builders.build_dynamic_behavior_graph_data(analysis_results)
            dot_source = renderers.generate_dynamic_behavior_dot_source(
                graph_data, root_package_name, db_graph_config, roles, docstring_map
            )
            report_analysis_results["dynamic_behavior_dot_source"] = dot_source
            layout_engine = db_graph_config.get("layout_engine", "dot")
            png_output_path = output_dir / f"{project_name}_dynamic_behavior_{layout_engine}.png"
            renderers.render_dynamic_behavior_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                root_package=root_package_name,
                db_graph_config=db_graph_config,
                roles_config=roles,
                docstring_map=docstring_map,
            )

        else:
            logging.warning(f"未知的分析類型: '{analysis_type}'。")

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

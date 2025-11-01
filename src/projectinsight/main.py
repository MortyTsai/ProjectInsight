# src/projectinsight/main.py
"""
ProjectInsight 主執行入口。
"""

# 1. 標準庫導入
import colorsys
import importlib.resources
import logging
import os
import sys
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import yaml
from ruamel.yaml import YAML

# 3. 本專案導入
from projectinsight import builders, renderers, reporters
from projectinsight.parsers import component_parser

ASSESSMENT_THRESHOLDS = {
    "warn_definitions": 3000,
}

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
        "filtering": {
            "exclude_nodes": [],
        },
        "focus": {
            "entrypoints": [],
            "max_depth": 3,
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


def find_project_root(marker: str = "pyproject.toml") -> Path:
    """
    [最終修正] 使用 importlib.resources 定位套件位置，然後向上遍歷尋找標記檔案。
    這是解決 `python -m` 執行模式下路徑問題的最健壯方法。
    """
    try:
        anchor = importlib.resources.files("projectinsight")
    except ModuleNotFoundError:
        anchor = Path(__file__).resolve().parent

    current_path = Path(str(anchor))
    while current_path != current_path.parent:
        if (current_path / marker).exists():
            return current_path
        current_path = current_path.parent
    raise FileNotFoundError(f"無法從 '{anchor}' 向上找到專案根目錄標記檔案: {marker}")


def _update_config_file(config_path: Path, updates: dict[str, Any]):
    """使用 ruamel.yaml 安全地更新設定檔，保留註解和格式。"""
    yaml_loader = YAML()
    try:
        with open(config_path, encoding="utf-8") as f:
            config_data = yaml_loader.load(f)

        for key, value in updates.items():
            keys = key.split(".")
            d = config_data
            for k in keys[:-1]:
                d = d.setdefault(k, {})
            d[keys[-1]] = value

        with open(config_path, "w", encoding="utf-8") as f:
            yaml_loader.dump(config_data, f)
        logging.info(f"已自動更新設定檔: {config_path.name}")
    except Exception as e:
        logging.error(f"自動更新設定檔 '{config_path.name}' 時失敗: {e}")


def _interactive_wizard(config_path: Path, definition_count: int) -> str:
    """處理大型專案的互動式配置精靈。"""
    print("\n" + "=" * 60)
    logging.info(f"ProjectInsight 偵測到這是一個大型專案 (約 {definition_count} 個組件)。")
    logging.warning("直接進行完整分析可能會非常緩慢或失敗。")
    print("-" * 60)
    print("我們建議您選擇一種策略來縮小分析範圍：")
    print("  1. [聚焦分析] 手動指定您想分析的核心模組 (例如: my_package.main)。")
    print("  2. [過濾分析] 手動指定您想排除的無關模組 (例如: *tests*)。")
    print("  3. [強制執行] 忽略建議，繼續執行完整分析 (不推薦)。")
    print("  4. [退出] 終止分析。")
    print("=" * 60)

    while True:
        choice = input("請輸入您的選擇 (1-4): ").strip()
        if choice in ("1", "2", "3", "4"):
            break
        else:
            print("無效的輸入，請重新輸入。")

    updates = {}
    action = "proceed"

    if choice == "1":
        print("\n請輸入您想聚焦的一個或多個模組 FQN (完整路徑)，用逗號分隔。")
        entrypoints_str = input("> ").strip()
        entrypoints = [ep.strip() for ep in entrypoints_str.split(",") if ep.strip()]
        if entrypoints:
            updates = {
                "visualization.component_interaction_graph.focus": {
                    "entrypoints": entrypoints,
                    "max_depth": 3,
                }
            }
            logging.info("將啟用「聚焦分析」模式。")
    elif choice == "2":
        print("\n請輸入您想排除的一個或多個模組模式 (支援 * 萬用字元)，用逗號分隔。")
        patterns_str = input("> ").strip()
        patterns = [p.strip() for p in patterns_str.split(",") if p.strip()]
        if patterns:
            updates = {"visualization.component_interaction_graph.filtering": {"exclude_nodes": patterns}}
            logging.info("將啟用「過濾分析」模式。")
    elif choice == "3":
        updates = {"force_analysis": True}
        logging.warning("將強制執行完整分析。")
    elif choice == "4":
        action = "exit"

    if updates:
        _update_config_file(config_path, updates)

    return action


def _merge_configs(default: dict, user: dict) -> dict:
    """遞迴地合併使用者設定到預設設定中。"""
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(default.get(key), dict):
            default[key] = _merge_configs(default[key], value)
        else:
            default[key] = value
    return default


def _generate_color_palette(num_colors: int) -> list[str]:
    """使用黃金比例演算法生成一個視覺上可區分的、和諧的調色盤。"""
    palette = []
    golden_ratio_conjugate = 0.61803398875
    hue = 0.7
    for _ in range(num_colors):
        hue += golden_ratio_conjugate
        hue %= 1
        rgb_float = colorsys.hls_to_rgb(hue, 0.9, 0.9)
        rgb_int = tuple(int(c * 255) for c in rgb_float)
        palette.append(f"#{rgb_int[0]:02x}{rgb_int[1]:02x}{rgb_int[2]:02x}")
    return palette


def _discover_architecture_layers(root_package_path: Path) -> dict[str, Any]:
    """自動掃描根套件目錄，並使用演算法調色盤為其分配顏色。"""
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

    if "(root)" not in architecture_layers:
        architecture_layers["(root)"] = {
            "name": f"{root_package_name} (root)",
            "color": "#EAEAEA",
        }

    logging.info(f"專案報告根目錄: {target_project_root}")
    logging.info(f"Python 原始碼分析根目錄: {python_source_root}")
    logging.info(f"將執行以下分析: {', '.join(analysis_types)}")

    py_files = sorted(python_source_root.rglob("*.py"))
    report_analysis_results: dict[str, Any] = {}

    logging.info("--- 開始執行專案體量預評估 ---")
    scan_results = component_parser.quick_ast_scan(python_source_root, py_files)
    definition_count = scan_results["definition_count"]

    comp_vis_config = vis_config.get("component_interaction_graph", {})
    has_focus = comp_vis_config.get("focus", {}).get("entrypoints")
    has_filter = comp_vis_config.get("filtering", {}).get("exclude_nodes")
    is_forced = config.get("force_analysis", False)

    if (
        definition_count > ASSESSMENT_THRESHOLDS["warn_definitions"]
        and not has_focus
        and not has_filter
        and not is_forced
        and sys.stdout.isatty()
    ):
        action = _interactive_wizard(config_path, definition_count)
        if action == "exit":
            logging.info("使用者選擇退出。")
            return
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            user_vis_config = config.get("visualization", {})
            vis_config = _merge_configs(DEFAULT_VIS_CONFIG.copy(), user_vis_config)

    logging.info("--- 開始執行完整程式碼解析 ---")
    parser_results = component_parser.full_jedi_analysis(
        python_source_root, root_package_name, scan_results["pre_scan_results"]
    )
    docstring_map = parser_results.get("docstring_map", {})

    for analysis_type in analysis_types:
        logging.info(f"--- 開始執行分析: '{analysis_type}' ---")
        if analysis_type == "component_interaction":
            comp_graph_config = vis_config["component_interaction_graph"]
            layout_config = comp_graph_config.get("layout", {})
            show_internal_calls = layout_config.get("show_internal_calls", True)
            filtering_config = comp_graph_config.get("filtering")
            focus_config = comp_graph_config.get("focus")  # [修改] 讀取聚焦設定

            graph_data = builders.build_component_graph_data(
                call_graph=parser_results.get("call_graph", set()),
                all_components=parser_results.get("components", set()),
                definition_to_module_map=parser_results.get("definition_to_module_map", {}),
                docstring_map=docstring_map,
                show_internal_calls=show_internal_calls,
                filtering_config=filtering_config,
                focus_config=focus_config,  # [修改] 傳遞聚焦設定
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

    try:
        project_root = find_project_root()
    except FileNotFoundError as e:
        logging.error(f"初始化失敗: {e}")
        return

    configs_dir = project_root / "configs"
    workspace_path = configs_dir / "workspace.yaml"
    projects_dir = configs_dir / "projects"

    if not workspace_path.is_file():
        logging.error(f"工作區設定檔 '{workspace_path}' 不存在。")
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

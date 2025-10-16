# src/projectinsight/main.py
"""
ProjectInsight 主執行入口。

此腳本負責協調檔案解析、圖表建構與最終渲染的完整流程。
"""

# 1. 標準庫導入
import argparse
import logging
import os
from pathlib import Path

import yaml

# 3. 本專案導入
from projectinsight.builders import dependency_builder
from projectinsight.parsers import py_parser
from projectinsight.renderer import render_graph


def main():
    """
    主函式。
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # --- 1. 設定命令列參數解析 ---
    project_root = Path(__file__).resolve().parent.parent.parent
    default_config_path = project_root / "configs" / "default.yaml"

    parser = argparse.ArgumentParser(description="ProjectInsight: 自動化專案視覺化工具。")
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=default_config_path,
        help=f"要使用的設定檔路徑 (預設: {default_config_path})"
    )
    args = parser.parse_args()

    config_path = args.config.resolve()

    logging.info(f"ProjectInsight 工具啟動，使用設定檔: {config_path}")

    # --- 2. 讀取設定檔 ---
    try:
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        template_path = project_root / "configs" / "config.template.yaml"
        logging.error(f"設定檔不存在: {config_path}")
        logging.info(f"您可以從 '{template_path}' 複製一份並修改後使用。")
        logging.info(f"範例指令: python -m projectinsight.main -c {project_root / 'configs' / 'my_project.yaml'}")
        return
    except yaml.YAMLError as e:
        logging.error(f"解析設定檔時發生錯誤: {e}")
        return

    target_src_path_str = config.get("target_src_path", "")
    root_package_name = config.get("root_package_name", "")
    output_dir_str = config.get("output_dir", "output")
    architecture_layers = config.get("architecture_layers", {})

    config_dir = config_path.parent
    target_project_src = (config_dir / target_src_path_str).resolve()
    output_dir = (config_dir / output_dir_str).resolve()
    output_path = output_dir / f"{root_package_name}_dependencies.png"

    os.makedirs(output_dir, exist_ok=True)

    # --- 3. 解析 ---
    logging.info(f"開始掃描目標目錄: {target_project_src}")
    py_files = sorted(target_project_src.rglob("*.py"))
    logging.info(f"共找到 {len(py_files)} 個 Python 檔案。")

    all_dependencies = {}
    for file_path in py_files:
        relative_parts = file_path.relative_to(target_project_src.parent).with_suffix("").parts
        module_name = ".".join(relative_parts)

        dependencies = py_parser.analyze_dependencies(file_path)
        all_dependencies[module_name] = dependencies

    # --- 4. 建構 ---
    graph_data = dependency_builder.build_graph_data(all_dependencies, root_package_name)

    # --- 5. 渲染 ---
    render_graph(
        graph_data=graph_data,
        output_path=output_path,
        root_package=root_package_name,
        save_source_file=True,
        layer_info=architecture_layers
    )


if __name__ == "__main__":
    main()

# src/projectinsight/core/project_processor.py
"""
負責處理單一專案的完整分析、建構、渲染和報告生成流程。
"""

# 1. 標準庫導入
import logging
import os
import sys
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
from projectinsight import builders, renderers, reporters
from projectinsight.core.config_loader import ConfigLoader
from projectinsight.core.interactive_wizard import InteractiveWizard
from projectinsight.parsers import component_parser, concept_flow_analyzer, seed_discoverer
from projectinsight.semantics import dynamic_behavior_analyzer

ASSESSMENT_THRESHOLDS = {
    "warn_definitions": 3000,
}


class ProjectProcessor:
    """一個處理單一專案完整分析流程的類別。"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.project_name = config_path.stem
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.config

    def run(self):
        """執行完整的專案處理流程。"""
        if not self.config:
            logging.error(f"因設定檔 '{self.config_path.name}' 載入失敗，終止處理。")
            return

        logging.info(f"========== 開始處理專案: {self.project_name} ==========")

        target_project_root, python_source_root, output_dir = self._prepare_paths()
        if not target_project_root:
            return

        root_package_name = self.config["root_package_name"]
        analysis_types = self.config.get("analysis_types", [])
        if not isinstance(analysis_types, list) or not analysis_types:
            logging.warning(f"設定檔 '{self.config_path.name}' 中 'analysis_types' 為空或格式不正確，已跳過。")
            return

        logging.info(f"專案報告根目錄: {target_project_root}")
        logging.info(f"Python 原始碼分析根目錄: {python_source_root}")
        logging.info(f"將執行以下分析: {', '.join(analysis_types)}")

        root_package_dir = python_source_root / root_package_name
        if not root_package_dir.is_dir():
            logging.error(f"根套件目錄不存在: {root_package_dir}")
            return
        py_files = sorted(root_package_dir.rglob("*.py"))
        logging.info(f"在根套件 '{root_package_name}' 中找到 {len(py_files)} 個 Python 檔案進行分析。")

        logging.info("--- 開始執行專案體量預評估 ---")
        scan_results = component_parser.quick_ast_scan(python_source_root, py_files, root_package_name)

        if self._needs_wizard(scan_results["definition_count"]):
            wizard = InteractiveWizard(self.config_path, scan_results, target_project_root)
            action = wizard.run()
            if action == "exit":
                logging.info("使用者選擇退出。")
                return
            self.config_loader = ConfigLoader(self.config_path)
            self.config = self.config_loader.config

        logging.info("--- 開始執行完整程式碼解析 ---")
        parser_results = component_parser.full_jedi_analysis(
            python_source_root,
            root_package_name,
            scan_results["pre_scan_results"],
            scan_results["definition_to_module_map"],
        )
        docstring_map = parser_results.get("docstring_map", {})
        report_analysis_results: dict[str, Any] = {}

        for analysis_type in analysis_types:
            self._run_analysis(
                analysis_type,
                py_files,
                python_source_root,
                parser_results,
                docstring_map,
                report_analysis_results,
                output_dir,
            )

        if report_analysis_results:
            report_output_path = output_dir / f"{self.project_name}_InsightReport.md"
            reporters.generate_markdown_report(
                project_name=self.project_name,
                target_project_root=target_project_root,
                output_path=report_output_path,
                analysis_results=report_analysis_results,
                report_settings=self.config.get("report_settings", {}),
            )

        logging.info(f"========== 專案 '{self.project_name}' 處理完成 ==========\n")

    def _prepare_paths(self) -> tuple[Path | None, Path | None, Path | None]:
        """根據設定準備所有需要的路徑。"""
        target_project_path_str = self.config.get("target_project_path")
        output_dir_str = self.config.get("output_dir", "output")

        if not target_project_path_str:
            return None, None, None

        config_dir = self.config_path.parent
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

        return target_project_root, python_source_root, output_dir

    def _needs_wizard(self, definition_count: int) -> bool:
        """判斷是否需要啟動互動式精靈。"""
        vis_config = self.config.get("visualization", {})
        comp_vis_config = vis_config.get("component_interaction_graph", {})
        has_focus = comp_vis_config.get("focus", {}).get("entrypoints")
        has_filter = comp_vis_config.get("filtering", {}).get("exclude_nodes")
        is_forced = self.config.get("force_analysis", False)

        return (
            definition_count > ASSESSMENT_THRESHOLDS["warn_definitions"]
            and not has_focus
            and not has_filter
            and not is_forced
            and sys.stdout.isatty()
        )

    def _run_analysis(
        self,
        analysis_type: str,
        py_files: list[Path],
        python_source_root: Path,
        parser_results: dict[str, Any],
        docstring_map: dict[str, str],
        report_analysis_results: dict[str, Any],
        output_dir: Path,
    ):
        """執行單一類型的分析。"""
        logging.info(f"--- 開始執行分析: '{analysis_type}' ---")
        root_package_name = self.config["root_package_name"]
        vis_config = self.config.get("visualization", {})
        architecture_layers = self.config.get("architecture_layers", {})

        if analysis_type == "component_interaction":
            comp_graph_config = vis_config["component_interaction_graph"]
            layout_config = comp_graph_config.get("layout", {})
            graph_data = builders.build_component_graph_data(
                call_graph=parser_results.get("call_graph", set()),
                all_components=parser_results.get("components", set()),
                definition_to_module_map=parser_results.get("definition_to_module_map", {}),
                docstring_map=docstring_map,
                show_internal_calls=layout_config.get("show_internal_calls", True),
                filtering_config=comp_graph_config.get("filtering"),
                focus_config=comp_graph_config.get("focus"),
            )
            dot_source = renderers.generate_component_dot_source(
                graph_data, root_package_name, architecture_layers, comp_graph_config
            )
            report_analysis_results["component_dot_source"] = dot_source
            layout_engine = comp_graph_config.get("layout_engine", "dot")
            png_output_path = output_dir / f"{self.project_name}_component_interaction_{layout_engine}.png"
            renderers.render_component_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                root_package=root_package_name,
                layer_info=architecture_layers,
                comp_graph_config=comp_graph_config,
            )

        elif analysis_type == "auto_concept_flow":
            auto_concept_config = self.config.get("auto_concept_flow", {})
            track_groups = seed_discoverer.discover_seeds(
                root_pkg=root_package_name,
                py_files=py_files,
                project_root=python_source_root,
                exclude_patterns=auto_concept_config.get("exclude_patterns", []),
            )
            if not track_groups:
                logging.warning(f"在 '{analysis_type}' 分析中未找到任何要追蹤的概念種子，已跳過。")
                return

            analysis_results = concept_flow_analyzer.analyze_concept_flow(
                root_pkg=root_package_name,
                py_files=py_files,
                track_groups=track_groups,
                project_root=python_source_root,
            )
            graph_data = builders.build_concept_flow_graph_data(analysis_results)
            dot_source = renderers.generate_concept_flow_dot_source(graph_data, root_package_name, "sfdp")
            report_analysis_results["concept_flow_dot_source"] = dot_source
            png_output_path = output_dir / f"{self.project_name}_concept_flow_sfdp.png"
            renderers.render_concept_flow_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                root_package=root_package_name,
                layout_engine="sfdp",
                dpi="200",
            )

        elif analysis_type == "dynamic_behavior":
            dynamic_behavior_config = self.config.get("dynamic_behavior_analysis", {})
            rules = dynamic_behavior_config.get("rules", [])
            if not rules:
                logging.warning("在 'dynamic_behavior' 分析中未找到任何規則，已跳過。")
                return

            db_graph_config = vis_config["dynamic_behavior_graph"]
            analysis_results = dynamic_behavior_analyzer.analyze_dynamic_behavior(
                py_files=py_files, rules=rules, project_root=python_source_root
            )
            graph_data = builders.build_dynamic_behavior_graph_data(analysis_results)
            dot_source = renderers.generate_dynamic_behavior_dot_source(
                graph_data,
                root_package_name,
                db_graph_config,
                dynamic_behavior_config.get("roles", {}),
                docstring_map,
            )
            report_analysis_results["dynamic_behavior_dot_source"] = dot_source
            layout_engine = db_graph_config.get("layout_engine", "dot")
            png_output_path = output_dir / f"{self.project_name}_dynamic_behavior_{layout_engine}.png"
            renderers.render_dynamic_behavior_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                root_package=root_package_name,
                db_graph_config=db_graph_config,
                roles_config=dynamic_behavior_config.get("roles", {}),
                docstring_map=docstring_map,
            )
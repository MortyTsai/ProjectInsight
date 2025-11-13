# src/projectinsight/core/project_processor.py
"""
ProjectInsight 的核心處理引擎。

此模組包含 `ProjectProcessor` 類別，作為整個專案分析流程的總指揮。
它負責以下核心職責：
1.  載入並解析專案設定檔。
2.  準備並驗證所有必要的路徑。
3.  協調執行「專案體量預評估」，並在必要時啟動「互動式精靈」。
4.  建立並管理 LibCST 的 `FullRepoManager`，為所有解析器提供統一的語法樹上下文。
5.  根據設定，依次調用 `parsers`, `semantics`, `builders`, `renderers`, 和 `reporters`
    中的各個子系統，完成從原始碼到最終報告的完整轉換流程。
6.  實現了對不同專案結構（如 `src` 佈局和扁平佈局）的健壯適應性。
"""

# 1. 標準庫導入
import logging
import os
import sys
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
from libcst.metadata import (
    FullRepoManager,
    FullyQualifiedNameProvider,
    ParentNodeProvider,
    PositionProvider,
    ScopeProvider,
)

# 3. 本專案導入
from projectinsight.builders.component_builder import build_component_graph_data
from projectinsight.builders.concept_flow_builder import build_concept_flow_graph_data
from projectinsight.builders.dynamic_behavior_builder import build_dynamic_behavior_graph_data
from projectinsight.core.config_loader import ConfigLoader
from projectinsight.core.interactive_wizard import InteractiveWizard
from projectinsight.parsers import component_parser, concept_flow_analyzer, seed_discoverer
from projectinsight.renderers.component_renderer import render_component_graph
from projectinsight.renderers.concept_flow_renderer import (
    generate_concept_flow_dot_source,
    render_concept_flow_graph,
)
from projectinsight.renderers.dynamic_behavior_renderer import (
    generate_dynamic_behavior_dot_source,
    render_dynamic_behavior_graph,
)
from projectinsight.reporters.markdown_reporter import generate_markdown_report
from projectinsight.semantics import dynamic_behavior_analyzer, semantic_link_analyzer
from projectinsight.utils.path_utils import find_top_level_packages

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
        if not target_project_root or not python_source_root:
            logging.error("準備路徑時失敗，終止處理。")
            return

        analysis_types = self.config.get("analysis_types", [])
        if not isinstance(analysis_types, list) or not analysis_types:
            logging.warning(f"設定檔 '{self.config_path.name}' 中 'analysis_types' 為空或格式不正確，已跳過。")
            return

        logging.info(f"專案報告根目錄: {target_project_root}")
        logging.info(f"Python 原始碼分析根目錄: {python_source_root}")

        context_packages: list[str]
        root_package_name_override = self.config.get("root_package_name")
        if root_package_name_override:
            context_packages = [root_package_name_override]
            logging.info(f"使用設定檔中指定的專家覆寫 `root_package_name`: {context_packages}")
        else:
            context_packages = find_top_level_packages(python_source_root)
            logging.info(f"自動偵測到頂層套件/模組: {context_packages}")

        if not context_packages:
            logging.error("無法確定專案的解析上下文。請檢查專案結構，或在設定檔中手動指定 `root_package_name`。")
            return

        logging.info(f"將執行以下分析: {', '.join(analysis_types)}")

        py_files_in_context: set[Path] = set()
        all_py_files_in_root = list(python_source_root.rglob("*.py"))
        context_packages_tuple = tuple(context_packages)

        for py_file in all_py_files_in_root:
            try:
                relative_path_parts = py_file.relative_to(python_source_root).parts
                if not relative_path_parts:
                    continue

                if relative_path_parts[-1] == "__init__.py":
                    module_path = ".".join(relative_path_parts[:-1])
                else:
                    module_path = ".".join(relative_path_parts).removesuffix(".py")

                if module_path.startswith(context_packages_tuple):
                    py_files_in_context.add(py_file)
            except ValueError:
                continue
        py_files = sorted(py_files_in_context)

        py_files_abs_str = [str(p.resolve()) for p in py_files]
        logging.info(f"在解析上下文中找到 {len(py_files)} 個 Python 檔案進行分析。")

        logging.info("--- 開始執行專案體量預評估 ---")
        scan_results = component_parser.quick_ast_scan(python_source_root, py_files, context_packages)

        if self._needs_wizard(scan_results["definition_count"]):
            wizard = InteractiveWizard(self.config_path, scan_results, target_project_root)
            action = wizard.run()
            if action == "exit":
                logging.info("使用者選擇退出。")
                return
            self.config_loader = ConfigLoader(self.config_path)
            self.config = self.config_loader.config

        logging.info("初始化 LibCST FullRepoManager 並解析快取...")
        providers = {FullyQualifiedNameProvider, ScopeProvider, ParentNodeProvider, PositionProvider}
        try:
            repo_manager = FullRepoManager(str(python_source_root.resolve()), py_files_abs_str, providers)
            repo_manager.resolve_cache()
            logging.info("LibCST 快取解析完成。")
        except Exception as e:
            logging.error(f"初始化 LibCST FullRepoManager 時發生嚴重錯誤: {e}", exc_info=True)
            return

        logging.info("--- 開始執行完整程式碼解析 (使用 LibCST 引擎) ---")
        parser_settings = self.config.get("parser_settings", {})
        alias_resolution_settings = parser_settings.get("alias_resolution", {})

        parser_results = component_parser.full_libcst_analysis(
            repo_manager=repo_manager,
            context_packages=context_packages,
            pre_scan_results=scan_results["pre_scan_results"],
            initial_definition_map=scan_results["definition_to_module_map"],
            alias_exclude_patterns=alias_resolution_settings.get("exclude_patterns", []),
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
                scan_results["pre_scan_results"],
                repo_manager,
                context_packages,
            )

        if report_analysis_results:
            report_output_path = output_dir / f"{self.project_name}_InsightReport.md"
            generate_markdown_report(
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
        if not output_dir_str:
            return None, None, None
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
        pre_scan_results: dict[str, Any],
        repo_manager: FullRepoManager,
        context_packages: list[str],
    ):
        """執行單一類型的分析。"""
        logging.info(f"--- 開始執行分析: '{analysis_type}' ---")
        root_package_name = self.config.get("root_package_name")
        vis_config = self.config.get("visualization", {})
        architecture_layers = self.config.get("architecture_layers", {})

        if analysis_type == "component_interaction":
            comp_graph_config = vis_config["component_interaction_graph"]
            layout_config = comp_graph_config.get("layout", {})
            semantic_config = comp_graph_config.get("semantic_analysis", {})

            semantic_edges: set[tuple[str, str, str]] = set()
            if semantic_config.get("enabled", True):
                logging.info("--- 開始執行靜態語義連結分析 ---")
                semantic_results = semantic_link_analyzer.analyze_semantic_links(
                    repo_manager=repo_manager,
                    pre_scan_results=pre_scan_results,
                    context_packages=context_packages,
                    all_components=parser_results.get("components", set()),
                )
                semantic_edges = semantic_results.get("semantic_edges", set())
            else:
                logging.info("--- 靜態語義連結分析已在設定中被禁用 ---")

            graph_data = build_component_graph_data(
                call_graph=parser_results.get("call_graph", set()),
                all_components=parser_results.get("components", set()),
                definition_to_module_map=parser_results.get("definition_to_module_map", {}),
                docstring_map=docstring_map,
                show_internal_calls=layout_config.get("show_internal_calls", False),
                filtering_config=comp_graph_config.get("filtering"),
                focus_config=comp_graph_config.get("focus"),
                semantic_edges=semantic_edges,
            )

            # [最終架構] 將完整的 graph_data 傳遞給 reporter
            report_analysis_results["component_graph_data"] = graph_data

            # 渲染 PNG 僅作為人類除錯的視覺化工具
            layout_engine = comp_graph_config.get("layout_engine", "dot")
            png_output_path = output_dir / f"{self.project_name}_component_interaction_{layout_engine}.png"
            filtered_components = render_component_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                project_name=self.project_name,
                root_package=root_package_name,
                layer_info=architecture_layers,
                comp_graph_config=comp_graph_config,
            )
            report_analysis_results["filtered_components"] = filtered_components

        elif analysis_type == "auto_concept_flow":
            display_package_name = self.config.get("root_package_name", context_packages[0])
            auto_concept_config = self.config.get("auto_concept_flow", {})
            track_groups = seed_discoverer.discover_seeds(
                context_packages=context_packages,
                py_files=py_files,
                project_root=python_source_root,
                exclude_patterns=auto_concept_config.get("exclude_patterns", []),
            )
            if not track_groups:
                logging.warning(f"在 '{analysis_type}' 分析中未找到任何要追蹤的概念種子，已跳過。")
                return

            analysis_results = concept_flow_analyzer.analyze_concept_flow(
                context_packages=context_packages,
                py_files=py_files,
                track_groups=track_groups,
                project_root=python_source_root,
            )
            graph_data = build_concept_flow_graph_data(analysis_results)
            dot_source = generate_concept_flow_dot_source(graph_data, display_package_name, "sfdp")
            report_analysis_results["concept_flow_dot_source"] = dot_source
            png_output_path = output_dir / f"{self.project_name}_concept_flow_sfdp.png"
            render_concept_flow_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                root_package=display_package_name,
                layout_engine="sfdp",
                dpi="200",
            )

        elif analysis_type == "dynamic_behavior":
            display_package_name = self.config.get("root_package_name", context_packages[0])
            dynamic_behavior_config = self.config.get("dynamic_behavior_analysis", {})
            rules = dynamic_behavior_config.get("rules", [])
            if not rules:
                logging.warning("在 'dynamic_behavior' 分析中未找到任何規則，已跳過。")
                return

            db_graph_config = vis_config["dynamic_behavior_graph"]
            analysis_results = dynamic_behavior_analyzer.analyze_dynamic_behavior(
                py_files=py_files, rules=rules, project_root=python_source_root
            )
            graph_data = build_dynamic_behavior_graph_data(analysis_results)
            dot_source = generate_dynamic_behavior_dot_source(
                graph_data,
                display_package_name,
                db_graph_config,
                dynamic_behavior_config.get("roles", {}),
                docstring_map,
            )
            report_analysis_results["dynamic_behavior_dot_source"] = dot_source
            layout_engine = db_graph_config.get("layout_engine", "dot")
            png_output_path = output_dir / f"{self.project_name}_dynamic_behavior_{layout_engine}.png"
            render_dynamic_behavior_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                root_package=display_package_name,
                db_graph_config=db_graph_config,
                roles_config=dynamic_behavior_config.get("roles", {}),
                docstring_map=docstring_map,
            )

# src/projectinsight/core/project_processor.py
"""
ProjectInsight 的核心處理引擎。
"""

# 1. 標準庫導入
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
# (無 - 移除了 libcst 的直接依賴，因為主程序不再負責解析)
# 3. 本專案導入
from projectinsight.builders.component_builder import build_component_graph_data
from projectinsight.builders.concept_flow_builder import build_concept_flow_graph_data
from projectinsight.builders.dynamic_behavior_builder import build_dynamic_behavior_graph_data
from projectinsight.core.cache_manager import CacheManager
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
    "max_nodes_before_wizard": 300,
    "min_meaningful_nodes": 5,
}


class ProjectProcessor:
    """一個處理單一專案完整分析流程的類別。"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.project_name = config_path.stem
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.config

    def _compute_config_fingerprint(self) -> str:
        """
        計算影響解析結果的設定指紋。
        如果這些設定發生變化，快取應視為失效。
        """
        relevant_config = {
            "parser_settings": self.config.get("parser_settings"),
            "root_package_name": self.config.get("root_package_name"),
        }
        try:
            serialized = json.dumps(relevant_config, sort_keys=True, default=str)
            return hashlib.md5(serialized.encode("utf-8")).hexdigest()
        except Exception as e:
            logging.warning(f"計算設定指紋時發生錯誤: {e}，將使用隨機指紋強制快取失效。")
            return os.urandom(8).hex()

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

        config_fingerprint = self._compute_config_fingerprint()
        cache_dir = output_dir / ".cache"
        cache_manager = CacheManager(target_project_root, cache_dir, config_fingerprint)
        cache_manager.load()

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
        logging.info(f"在解析上下文中找到 {len(py_files)} 個 Python 檔案進行分析。")

        logging.info("--- [Phase 1] 執行快速 AST 掃描 ---")
        scan_results = component_parser.quick_ast_scan(python_source_root, py_files, context_packages)

        repo_manager = None

        logging.info("--- [Phase 2 & 3] 執行完整程式碼解析 (Parallel LibCST + Incremental Cache) ---")
        parser_settings = self.config.get("parser_settings", {})
        alias_resolution_settings = parser_settings.get("alias_resolution", {})

        project_root_str = str(python_source_root.resolve())

        parser_results = component_parser.full_libcst_analysis(
            repo_manager=repo_manager,
            context_packages=context_packages,
            pre_scan_results=scan_results["pre_scan_results"],
            initial_definition_map=scan_results["definition_to_module_map"],
            alias_exclude_patterns=alias_resolution_settings.get("exclude_patterns", []),
            cache_manager=cache_manager,
            project_root=project_root_str,
        )

        logging.info("--- [Phase 4] 執行靜態語義連結分析 (Parallel) ---")
        semantic_results = semantic_link_analyzer.analyze_semantic_links(
            repo_manager=repo_manager,
            pre_scan_results=scan_results["pre_scan_results"],
            context_packages=context_packages,
            all_components=parser_results.get("components", set()),
            cache_manager=cache_manager,
            project_root=project_root_str,
        )

        cache_manager.prune(py_files)
        cache_manager.save()

        full_graph_data = build_component_graph_data(
            call_graph=parser_results.get("call_graph", set()),
            all_components=parser_results.get("components", set()),
            definition_to_module_map=parser_results.get("definition_to_module_map", {}),
            docstring_map={},
            show_internal_calls=False,
            filtering_config=None,
            focus_config=None,
            semantic_edges=semantic_results.get("semantic_edges", set()),
        )
        total_nodes = len(full_graph_data.get("nodes", []))
        logging.info(f"--- [評估] 專案全景圖包含 {total_nodes} 個高階組件節點。 ---")

        if self._needs_wizard(total_nodes):
            wizard = InteractiveWizard(self.config_path, target_project_root)

            failed_attempts: list[str] = []
            while True:
                action = wizard.run(full_graph_data, context_packages, failed_attempts)
                if action == "exit":
                    logging.info("使用者選擇退出。")
                    return

                self.config_loader = ConfigLoader(self.config_path)
                self.config = self.config_loader.config

                if self.config.get("force_analysis") or self.config.get("visualization", {}).get(
                    "component_interaction_graph", {}
                ).get("filtering", {}).get("exclude_nodes"):
                    break

                is_meaningful, entrypoint = self._post_analysis_validation(
                    parser_results, semantic_results, self.config
                )
                if is_meaningful:
                    logging.info(f"入口點 '{entrypoint}' 驗證成功，繼續生成報告。")
                    break
                if entrypoint:
                    failed_attempts.append(entrypoint)

        docstring_map = parser_results.get("docstring_map", {})
        report_analysis_results: dict[str, Any] = {}

        for analysis_type in analysis_types:
            self._run_analysis(
                analysis_type,
                py_files,
                python_source_root,
                parser_results,
                semantic_results,
                docstring_map,
                report_analysis_results,
                output_dir,
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
                context_packages=context_packages,
            )

        logging.info(f"========== 專案 '{self.project_name}' 處理完成 ==========\n")

    @staticmethod
    def _post_analysis_validation(
        parser_results: dict[str, Any],
        semantic_results: dict[str, Any],
        config: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """
        使用記憶體中已有的解析結果進行快速驗證，無需重新解析。
        """
        focus_config = config.get("visualization", {}).get("component_interaction_graph", {}).get("focus", {})
        entrypoints = focus_config.get("entrypoints")
        if not entrypoints:
            return True, None

        entrypoint = entrypoints[0]
        logging.info(f"--- [後分析驗證] 正在驗證入口點: {entrypoint} ---")

        try:
            graph_data = build_component_graph_data(
                call_graph=parser_results.get("call_graph", set()),
                all_components=parser_results.get("components", set()),
                definition_to_module_map=parser_results.get("definition_to_module_map", {}),
                docstring_map={},
                show_internal_calls=False,
                filtering_config=None,
                focus_config=focus_config,
                semantic_edges=semantic_results.get("semantic_edges", set()),
            )

            node_count = len(graph_data.get("nodes", []))
            logging.info(f"--- [後分析驗證] 入口點 '{entrypoint}' 生成了 {node_count} 個節點。 ---")
            return node_count >= ASSESSMENT_THRESHOLDS["min_meaningful_nodes"], entrypoint
        except Exception as e:
            logging.error(f"後分析驗證期間發生錯誤: {e}", exc_info=True)
            return False, entrypoint

    def _prepare_paths(self) -> tuple[Path | None, Path | None, Path | None]:
        """
        根據設定準備所有需要的路徑。
        增強路徑偵測邏輯，支援 'lib' 佈局，並優先使用 root_package_name 進行定位。
        """
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

        root_package_name = self.config.get("root_package_name")
        common_layout_dirs = ["src", "lib"]

        if root_package_name:
            for layout_dir in common_layout_dirs:
                potential_root = target_project_root / layout_dir
                if (potential_root / root_package_name).exists():
                    logging.info(f"根據 `root_package_name` 偵測到 '{layout_dir}' 佈局。")
                    return target_project_root, potential_root, output_dir

            if (target_project_root / root_package_name).exists():
                logging.info("根據 `root_package_name` 偵測到扁平佈局 (根目錄)。")
                return target_project_root, target_project_root, output_dir

        potential_src = target_project_root / "src"
        if potential_src.is_dir() and (not root_package_name or (potential_src / root_package_name).exists()):
            logging.info("偵測到 'src' 佈局。")
            return target_project_root, potential_src, output_dir

        potential_lib = target_project_root / "lib"
        if potential_lib.is_dir():
            logging.info("偵測到 'lib' 佈局。")
            return target_project_root, potential_lib, output_dir

        logging.info("未偵測到標準佈局，將使用專案根目錄作為 Python 原始碼路徑。")
        return target_project_root, target_project_root, output_dir

    def _needs_wizard(self, node_count: int) -> bool:
        """判斷是否需要啟動互動式精靈。"""
        vis_config = self.config.get("visualization", {})
        comp_vis_config = vis_config.get("component_interaction_graph", {})
        has_focus = comp_vis_config.get("focus", {}).get("entrypoints")
        has_filter = comp_vis_config.get("filtering", {}).get("exclude_nodes")
        is_forced = self.config.get("force_analysis", False)

        return (
            node_count > ASSESSMENT_THRESHOLDS["max_nodes_before_wizard"]
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
        semantic_results: dict[str, Any],
        docstring_map: dict[str, str],
        report_analysis_results: dict[str, Any],
        output_dir: Path,
        context_packages: list[str],
    ):
        """執行單一類型的分析。"""
        logging.info(f"--- 開始執行分析: '{analysis_type}' ---")
        vis_config = self.config.get("visualization", {})
        architecture_layers = self.config.get("architecture_layers", {})

        if analysis_type == "component_interaction":
            comp_graph_config = vis_config["component_interaction_graph"]
            layout_config = comp_graph_config.get("layout", {})
            semantic_config = comp_graph_config.get("semantic_analysis", {})

            semantic_edges = set()
            if semantic_config.get("enabled", True):
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

            report_analysis_results["component_graph_data"] = graph_data

            layout_engine = comp_graph_config.get("layout_engine", "dot")
            png_output_path = output_dir / f"{self.project_name}_component_interaction_{layout_engine}.png"
            filtered_components = render_component_graph(
                graph_data=graph_data,
                output_path=png_output_path,
                project_name=self.project_name,
                layer_info=architecture_layers,
                comp_graph_config=comp_graph_config,
                context_packages=context_packages,
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

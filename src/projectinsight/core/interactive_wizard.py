# src/projectinsight/core/interactive_wizard.py
"""
負責處理大型專案分析前的所有使用者互動與智慧推薦。
"""

# 1. 標準庫導入
import fnmatch
import logging
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
# (無)
# 3. 本專案導入
from projectinsight.core.config_loader import ConfigLoader
from projectinsight.intelligence.ecosystem_analyzer import EcosystemAnalyzer
from projectinsight.intelligence.graph_analyzer import GraphAnalyzer
from projectinsight.intelligence.heuristics_scorer import HeuristicsScorer


class InteractiveWizard:
    """一個處理大型專案互動式配置的類別。"""

    def __init__(self, config_path: Path, scan_results: dict[str, Any], project_root: Path):
        self.config_path = config_path
        self.scan_results = scan_results
        self.project_root = project_root

    def run(self) -> str:
        """
        執行互動式精靈，並回傳使用者的最終決定 ('proceed' 或 'exit')。
        """
        definition_count = self.scan_results["definition_count"]
        pre_scan_results = self.scan_results["pre_scan_results"]
        module_import_graph = self.scan_results["module_import_graph"]
        definition_to_module_map = self.scan_results["definition_to_module_map"]

        scorer = HeuristicsScorer()
        heuristic_scores = scorer.score(pre_scan_results)
        rules = scorer.rules
        weights = rules.get("weights", {})
        entry_points_bonus = rules.get("entry_points_bonus", 150)

        graph_analyzer = GraphAnalyzer(module_import_graph)
        hits_scores = graph_analyzer.calculate_hits()

        eco_analyzer = EcosystemAnalyzer(self.project_root, module_import_graph, rules.get("frameworks", {}))
        framework_bonus_scores = eco_analyzer.get_framework_bonus_scores()
        standard_entrypoints = eco_analyzer.get_standard_entrypoints()

        combined_scores: dict[str, float] = {}
        all_fqns = set(heuristic_scores.keys()) | set(standard_entrypoints.keys())

        for fqn in all_fqns:
            h_score = heuristic_scores.get(fqn, 0.0)

            module_path = definition_to_module_map.get(fqn)
            if not module_path and fqn in hits_scores:
                module_path = fqn

            hub_score = 0.0
            if module_path and module_path in hits_scores:
                hub_score = hits_scores[module_path].get("hub", 0.0) * 100

            framework_score = 0.0
            for pattern, bonus in framework_bonus_scores.items():
                if fnmatch.fnmatch(fqn, pattern):
                    framework_score += bonus

            entry_point_score = 0.0
            if fqn in standard_entrypoints:
                entry_point_score = entry_points_bonus

            total_score = (
                (h_score * weights.get("heuristic_score", 1.0))
                + (hub_score * weights.get("hub_score", 1.0))
                + (framework_score * weights.get("entry_point_score", 1.0))
                + (entry_point_score * weights.get("entry_point_score", 1.0))
            )
            combined_scores[fqn] = total_score

        sorted_candidates = sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)

        recommendations: list[tuple[str, float]] = []
        seen_modules: set[str] = set()

        for fqn, score in sorted_candidates:
            module_path = definition_to_module_map.get(fqn)
            is_module_itself = False
            if not module_path and fqn in hits_scores:
                module_path = fqn
                is_module_itself = True

            if not module_path:
                continue

            if is_module_itself and not any(def_fqn.startswith(fqn) for def_fqn in definition_to_module_map):
                continue

            if module_path not in seen_modules:
                recommendations.append((fqn, score))
                seen_modules.add(module_path)
            if len(recommendations) >= 5:
                break

        self._display_menu(definition_count, recommendations)
        updates, action = self._get_user_choice(recommendations)
        if updates:
            ConfigLoader.update_config_file(self.config_path, updates)
        return action

    @staticmethod
    def _display_menu(definition_count: int, recommendations: list[tuple[str, float]]):
        """顯示互動式選單給使用者。"""
        print("\n" + "=" * 60)
        logging.info(f"ProjectInsight 偵測到這是一個大型專案 (約 {definition_count} 個組件)。")
        logging.warning("直接進行完整分析可能會非常緩慢或失敗。")
        print("-" * 60)
        print("ProjectInsight 為您推薦了以下幾個可能的分析入口點：")
        for i, (fqn, score) in enumerate(recommendations):
            print(f"  {i + 1}. {fqn} (推薦分數: {score:.0f})")
        print("\n您可以選擇一個推薦的入口點，或選擇其他選項：")
        print(f"  {len(recommendations) + 1}. [手動聚焦] 手動輸入您想分析的核心模組。")
        print(f"  {len(recommendations) + 2}. [過濾分析] 手動指定您想排除的無關模組。")
        print(f"  {len(recommendations) + 3}. [強制執行] 忽略建議，繼續執行完整分析 (不推薦)。")
        print(f"  {len(recommendations) + 4}. [退出] 終止分析。")
        print("=" * 60)

    @staticmethod
    def _get_user_choice(recommendations: list[tuple[str, float]]) -> tuple[dict[str, Any], str]:
        """獲取並處理使用者的選擇。"""
        updates: dict[str, Any] = {}
        action = "proceed"
        while True:
            try:
                choice_str = input(f"請輸入您的選擇 (1-{len(recommendations) + 4}): ").strip()
                choice = int(choice_str)
                if 1 <= choice <= len(recommendations) + 4:
                    break
                else:
                    print("無效的選擇，請重新輸入。")
            except ValueError:
                print("無效的輸入，請輸入數字。")
        if 1 <= choice <= len(recommendations):
            selected_fqn = recommendations[choice - 1][0]
            updates = {
                "visualization.component_interaction_graph.focus": {
                    "entrypoints": [selected_fqn],
                    "max_depth": 3,
                }
            }
            logging.info(f"將啟用「聚焦分析」模式，入口點: {selected_fqn}")
        else:
            option_choice = choice - len(recommendations)
            if option_choice == 1:
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
            elif option_choice == 2:
                print("\n請輸入您想排除的一個或多個模組模式 (支援 * 萬用字元)，用逗號分隔。")
                patterns_str = input("> ").strip()
                patterns = [p.strip() for p in patterns_str.split(",") if p.strip()]
                if patterns:
                    updates = {"visualization.component_interaction_graph.filtering": {"exclude_nodes": patterns}}
                    logging.info("將啟用「過濾分析」模式。")
            elif option_choice == 3:
                updates = {"force_analysis": True}
                logging.warning("將強制執行完整分析。")
            elif option_choice == 4:
                action = "exit"
        return updates, action

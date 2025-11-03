# src/projectinsight/intelligence/heuristics_scorer.py
"""
第一層決策引擎：基於啟發式規則的計分器。
"""

# 1. 標準庫導入
import fnmatch
import importlib.resources
import logging
from typing import Any

# 2. 第三方庫導入
import yaml

# 3. 本專案導入
from projectinsight.parsers.component_parser import CodeVisitor


class HeuristicsScorer:
    """
    根據一組可配置的啟發式規則，為程式碼定義（組件）計算分數。
    """

    def __init__(self):
        self.rules = self._load_rules()

    @staticmethod
    def _load_rules() -> dict[str, Any]:
        """從套件內部載入預設的啟發式規則檔案。"""
        try:
            rules_path = importlib.resources.files("projectinsight.intelligence.defaults").joinpath(
                "default_heuristics.yaml"
            )
            with rules_path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except (FileNotFoundError, yaml.YAMLError) as e:
            logging.error(f"無法載入預設啟發式規則: {e}")
            return {}

    def score(self, pre_scan_results: dict[str, Any]) -> dict[str, float]:
        """
        對 quick_ast_scan 的結果進行計分。

        Args:
            pre_scan_results: 來自 component_parser.quick_ast_scan 的結果。

        Returns:
            一個字典，鍵是定義的 FQN，值是其啟發式分數。
        """
        if not self.rules:
            logging.warning("啟發式規則未載入，跳過計分。")
            return {}

        scores: dict[str, float] = {}
        scoring_rules = self.rules.get("scoring_rules", {})
        module_path_rules = scoring_rules.get("by_module_path", [])
        def_name_rules = scoring_rules.get("by_definition_name", [])
        feature_rules = scoring_rules.get("by_code_feature", [])

        for scan_data in pre_scan_results.values():
            visitor: CodeVisitor = scan_data["visitor"]
            module_path = visitor.module_path

            path_score = 0.0
            for rule in module_path_rules:
                if fnmatch.fnmatch(module_path, rule["pattern"]):
                    path_score += rule["score"]

            feature_score = 0.0
            if visitor.has_main_block:
                for rule in feature_rules:
                    if rule["feature"] == "has___main__block":
                        feature_score += rule["score"]

            for def_fqn in visitor.definitions:
                def_name = def_fqn.split(".")[-1]
                def_name_score = 0.0
                for rule in def_name_rules:
                    if fnmatch.fnmatch(def_name, rule["pattern"]):
                        def_name_score += rule["score"]

                total_score = path_score + feature_score + def_name_score
                scores[def_fqn] = total_score

        logging.info(f"啟發式計分完成，共為 {len(scores)} 個定義計算了分數。")
        return scores

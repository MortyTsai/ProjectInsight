# src/projectinsight/core/interactive_wizard.py
"""
負責處理大型專案分析前的所有使用者互動與智慧推薦。
演算法微調：針對 Pandas 等大型函式庫，新增「私有路徑抑制」與「裝飾器抑制」機制。
"""

# 1. 標準庫導入
import fnmatch
import logging
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import networkx as nx

# 3. 本專案導入
from projectinsight.core.config_loader import ConfigLoader


class InteractiveWizard:
    """
    一個基於圖論事實 (Graph-Based) 的互動式配置精靈。
    它接收完整的組件互動圖資料，透過混合圖論指標識別架構中的核心入口點。
    """

    def __init__(self, config_path: Path, project_root: Path):
        self.config_path = config_path
        self.project_root = project_root
        self.sorted_candidates: list[tuple[str, float]] = []

    def analyze_graph_and_recommend(self, graph_data: dict[str, Any], context_packages: list[str]):
        """
        基於傳入的圖資料構建 NetworkX 圖，並計算混合中心性分數。
        """
        logging.info("--- [Wizard] 正在基於真實呼叫圖進行拓撲分析 (PageRank + Out-Degree) ---")

        G = nx.DiGraph()
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        semantic_edges = graph_data.get("semantic_edges", [])

        if not nodes:
            logging.warning("[Wizard] 圖資料為空，無法進行推薦。")
            return

        G.add_nodes_from(nodes)

        for u, v in edges:
            if u != v:
                G.add_edge(u, v, weight=1.0)

        for u, v, label in semantic_edges:
            if u != v:
                weight = 1.0
                if label in ("registers", "uses_strategy"):
                    weight = 1.5
                elif label == "inherits_from":
                    weight = 1.2
                G.add_edge(u, v, weight=weight)

        try:
            pagerank_scores = nx.pagerank(G, alpha=0.85, weight="weight")
        except nx.PowerIterationFailedConvergence:
            logging.warning("[Wizard] PageRank 未收斂，使用度數中心性代替。")
            pagerank_scores = nx.degree_centrality(G)

        out_degree_scores = nx.out_degree_centrality(G)

        final_scores: dict[str, float] = {}

        max_pr = max(pagerank_scores.values()) if pagerank_scores else 1.0
        max_od = max(out_degree_scores.values()) if out_degree_scores else 1.0

        bonus_patterns = {
            "*main*": 1.5,
            "*app*": 1.5,
            "*application*": 1.5,
            "*api*": 1.3,
            "*router*": 1.3,
            "*server*": 1.3,
            "*cli*": 1.3,
            "*manage*": 1.3,
            "*handler*": 1.3,
            "*wsgi*": 1.3,
            "*asgi*": 1.3,
            "*core*": 1.2,
            "*base*": 1.1,
            "*model*": 1.1,
            "*frame*": 1.2,
            "*index*": 1.1,
            "*session*": 1.1,
            "*engine*": 1.1,
        }

        penalty_patterns = {
            "*test*": 0.05,
            "*docs*": 0.05,
            "*example*": 0.1,
            "*scripts*": 0.1,
            "*utils*": 0.5,
            "*common*": 0.5,
            "*helper*": 0.5,
            "*__init__": 0.2,
            "*types*": 0.3,
            "*exceptions*": 0.3,
            "*error*": 0.3,
            "*property*": 0.5,
            "*filters*": 0.5,
            "*admin*": 0.8,
            "*decorator*": 0.2,
            "*validator*": 0.3,
            "*compat*": 0.3,
        }

        for node in G.nodes():
            is_internal = any(node.startswith(pkg) for pkg in context_packages)
            if not is_internal:
                continue

            parts = node.split(".")
            has_private_part = False
            for part in parts:
                if part.startswith("_") and not part.startswith("__"):
                    has_private_part = True
                    break

            pr_norm = pagerank_scores.get(node, 0) / max_pr
            od_norm = out_degree_scores.get(node, 0) / max_od
            base_score = (pr_norm * 0.4 + od_norm * 0.6) * 100

            multiplier = 1.0
            for pattern, bonus in bonus_patterns.items():
                if fnmatch.fnmatch(node.lower(), pattern):
                    multiplier *= bonus

            for pattern, penalty in penalty_patterns.items():
                if fnmatch.fnmatch(node.lower(), pattern):
                    multiplier *= penalty

            if has_private_part:
                multiplier *= 0.3

            short_name = node.split(".")[-1]
            if short_name and short_name[0].isupper() and "_" not in short_name:
                multiplier *= 1.2

            final_score = base_score * multiplier

            if G.degree(node) == 0:
                final_score *= 0.1

            final_scores[node] = final_score

        self.sorted_candidates = sorted(final_scores.items(), key=lambda item: item[1], reverse=True)

        logging.debug("--- [Wizard] Top 10 推薦候選者 (已過濾外部依賴) ---")
        for i, (fqn, score) in enumerate(self.sorted_candidates[:10]):
            logging.debug(f"  {i + 1}. {fqn} (Score: {score:.2f})")

    def run(
        self,
        graph_data: dict[str, Any],
        context_packages: list[str],
        failed_attempts: list[str] | None = None,
    ) -> str:
        """執行互動式精靈。"""
        self.analyze_graph_and_recommend(graph_data, context_packages)

        if failed_attempts:
            print("\n" + "-" * 60)
            logging.warning(f"您選擇的入口點 '{failed_attempts[-1]}' 未能產生有意義的圖表。")
            logging.info("這通常意味著它是一個代理、孤立的組件或過於簡單。請嘗試其他選項。")
            print("-" * 60)

        filtered_candidates = [cand for cand in self.sorted_candidates if cand[0] not in (failed_attempts or [])]
        recommendations = [cand for cand in filtered_candidates if cand[1] > 0][:5]

        node_count = len(graph_data.get("nodes", []))
        self._display_menu(node_count, recommendations)

        updates, action = self._get_user_choice(recommendations)
        if updates:
            ConfigLoader.update_config_file(self.config_path, updates)
        return action

    @staticmethod
    def _display_menu(node_count: int, recommendations: list[tuple[str, float]]):
        """顯示互動式選單給使用者。"""
        print("\n" + "=" * 60)
        logging.info(f"ProjectInsight 構建了一個包含 {node_count} 個節點的全景圖。")
        logging.warning("圖表過於龐大，直接渲染將導致視覺雜訊。")
        print("-" * 60)
        print("基於混合圖論分析 (PageRank + Out-Degree)，我們推薦以下核心入口點：")

        if not recommendations:
            print("  (無強烈推薦的入口點，請嘗試手動選擇)")

        for i, (fqn, score) in enumerate(recommendations):
            print(f"  {i + 1}. {fqn} (推薦指數: {score:.1f})")

        print("\n您可以選擇一個推薦的入口點，或選擇其他選項：")
        base_idx = len(recommendations)
        print(f"  {base_idx + 1}. [手動聚焦] 手動輸入您想分析的核心模組。")
        print(f"  {base_idx + 2}. [過濾分析] 手動指定您想排除的無關模組。")
        print(f"  {base_idx + 3}. [強制執行] 忽略建議，繼續執行完整分析 (不推薦)。")
        print(f"  {base_idx + 4}. [退出] 終止分析。")
        print("=" * 60)

    @staticmethod
    def _get_user_choice(recommendations: list[tuple[str, float]]) -> tuple[dict[str, Any], str]:
        """獲取並處理使用者的選擇。"""
        updates: dict[str, Any] = {}
        action = "proceed"
        max_choice = len(recommendations) + 4

        while True:
            try:
                choice_str = input(f"請輸入您的選擇 (1-{max_choice}): ").strip()
                choice = int(choice_str)
                if 1 <= choice <= max_choice:
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
                    "initial_depth": 2,
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
                            "initial_depth": 2,
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

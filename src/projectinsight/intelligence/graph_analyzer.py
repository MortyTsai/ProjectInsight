# src/projectinsight/intelligence/graph_analyzer.py
"""
第二層決策引擎：基於圖論的中心性分析器。
"""

# 1. 標準庫導入
import logging

# 2. 第三方庫導入
import networkx as nx

# 3. 本專案導入
# (無)


class GraphAnalyzer:
    """
    分析模組導入圖，以計算圖論指標（如 HITS 中心性）。
    """

    def __init__(self, module_import_graph: dict[str, set[str]]):
        self.graph = self._build_graph(module_import_graph)

    @staticmethod
    def _build_graph(module_import_graph: dict[str, set[str]]) -> nx.DiGraph:
        """將導入關係字典轉換為 NetworkX 有向圖。"""
        graph = nx.DiGraph()
        for module, imports in module_import_graph.items():
            graph.add_node(module)
            for imported_module in imports:
                graph.add_edge(module, imported_module)
        return graph

    def calculate_hits(self) -> dict[str, dict[str, float]]:
        """
        計算圖中每個節點的 HITS (Hyperlink-Induced Topic Search) 分數。

        HITS 演算法計算兩個分數：
        - Hubs: 傾向於指向許多好的 Authorities 的節點。
        - Authorities: 傾向於被許多好的 Hubs 指向的節點。

        在我們的上下文中：
        - 高 Hub 分數的模組：可能是高層次的協調者或入口點（例如 main, app）。
        - 高 Authority 分數的模組：可能是底層的、被廣泛使用的工具或核心庫（例如 utils, models）。

        Returns:
            一個字典，鍵是模組 FQN，值是包含 'hub' 和 'authority' 分數的字典。
        """
        if not self.graph or self.graph.number_of_nodes() == 0:
            logging.warning("無法計算 HITS 分數：圖為空。")
            return {}

        try:
            hubs, authorities = nx.hits(self.graph, max_iter=1000, tol=1e-06)
            logging.info(f"HITS 中心性計算完成，分析了 {self.graph.number_of_nodes()} 個模組節點。")

            scores = {}
            all_nodes = set(hubs.keys()) | set(authorities.keys())
            for node in all_nodes:
                scores[node] = {
                    "hub": hubs.get(node, 0.0),
                    "authority": authorities.get(node, 0.0),
                }
            return scores
        except nx.PowerIterationFailedConvergence:
            logging.error("HITS 演算法未能收斂。可能是圖結構有問題。將回傳空分數。")
            return {}

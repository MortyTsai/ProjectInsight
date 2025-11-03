# src/projectinsight/intelligence/ecosystem_analyzer.py
"""
第三層決策引擎：基於專案標準化入口點定義的分析器。
"""

# 1. 標準庫導入
import logging
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import toml

# 3. 本專案導入
# (無)


class EcosystemAnalyzer:
    """
    分析專案的 pyproject.toml，尋找標準化的 [project.scripts] 和
    [project.entry-points] 入口點定義。
    """

    def __init__(
        self,
        project_root: Path,
        module_import_graph: dict[str, set[str]],
        framework_rules: dict[str, Any],
    ):
        self.project_root = project_root
        self.module_import_graph = module_import_graph
        self.framework_rules = framework_rules
        self.identified_framework: str | None = self._identify_framework()

    def _identify_framework(self) -> str | None:
        """使用雙重策略識別專案框架。"""
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.is_file():
            try:
                data = toml.load(pyproject_path)
                project_name = data.get("project", {}).get("name")
                if project_name:
                    for framework_id, rules in self.framework_rules.items():
                        if rules.get("project_name", "").lower() == project_name.lower():
                            logging.info(f"透過 pyproject.toml [project].name 成功識別出框架: {framework_id}")
                            return framework_id
            except toml.TomlDecodeError:
                pass
        all_imports = {imp.split(".")[0] for imports in self.module_import_graph.values() for imp in imports}
        for framework_id, rules in self.framework_rules.items():
            keyword = rules.get("project_name", "").lower()
            if keyword in all_imports:
                logging.info(f"透過 import 分析成功識別出框架: {framework_id}")
                return framework_id
        return None

    def get_framework_bonus_scores(self) -> dict[str, float]:
        """如果識別出框架，則生成一個基於規則的獎勵分數字典。"""
        if not self.identified_framework:
            return {}
        rules = self.framework_rules.get(self.identified_framework, {})
        bonus_points_rules = rules.get("bonus_points", [])
        bonus_scores = {rule["pattern"]: float(rule["score"]) for rule in bonus_points_rules}
        logging.info(f"為框架 '{self.identified_framework}' 應用了 {len(bonus_scores)} 條獎勵分數規則。")
        return bonus_scores

    def get_standard_entrypoints(self) -> dict[str, float]:
        """
        解析 pyproject.toml，提取 [project.scripts] 和 [project.entry-points]
        中定義的所有 FQN。
        """
        pyproject_path = self.project_root / "pyproject.toml"
        entrypoints: dict[str, float] = {}
        if not pyproject_path.is_file():
            return entrypoints
        try:
            data = toml.load(pyproject_path)
            project_data = data.get("project", {})

            scripts = project_data.get("scripts", {})
            if scripts:
                logging.info(f"在 pyproject.toml 中發現 [project.scripts] 區段，找到 {len(scripts)} 個標準入口點。")
                for _name, entry_str in scripts.items():
                    self._parse_entrypoint_str(entry_str, entrypoints)

            entry_points_groups = project_data.get("entry-points", {})
            if entry_points_groups:
                count = sum(len(group) for group in entry_points_groups.values())
                logging.info(f"在 pyproject.toml 中發現 [project.entry-points] 區段，找到 {count} 個標準入口點。")
                for _group, entries in entry_points_groups.items():
                    for _name, entry_str in entries.items():
                        self._parse_entrypoint_str(entry_str, entrypoints)

        except toml.TomlDecodeError as e:
            logging.warning(f"解析 pyproject.toml 時發生錯誤: {e}")
        return entrypoints

    @staticmethod
    def _parse_entrypoint_str(entry_str: str, entrypoints: dict[str, float]):
        """輔助函式，解析單個入口點字串並更新字典。"""
        if ":" in entry_str:
            module_path, object_path = entry_str.split(":", 1)
            object_path = object_path.split("(")[0].strip()

            fqn = f"{module_path}.{object_path}" if object_path else module_path

            if fqn not in entrypoints:
                entrypoints[fqn] = 1.0
                logging.info(f"  - 發現標準入口點: {fqn}")

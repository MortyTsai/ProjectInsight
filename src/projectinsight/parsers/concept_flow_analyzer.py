# src/projectinsight/parsers/concept_flow_analyzer.py
"""
提供「概念流動」的核心分析邏輯，包括迭代追蹤。
"""

# 1. 標準庫導入
import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import libcst as cst
from libcst.metadata import (
    FullRepoManager,
    FullyQualifiedNameProvider,
    MetadataWrapper,
    ParentNodeProvider,
    PositionProvider,
    ScopeProvider,
)

# 3. 本專案導入
# (無)


@contextmanager
def temporary_cwd(path: Path) -> Generator[None, None, None]:
    """一個上下文管理器，用於安全地、臨時地切換當前工作目錄。"""
    original_cwd = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_cwd)


def _normalize_fqn(name: str, root_pkg: str) -> str:
    """正規化 FQN，使其與使用者定義的格式一致。"""
    if root_pkg in name:
        name = name[name.find(root_pkg) :]
    return name.replace(".<locals>", "")


class ConceptVisitor(cst.CSTVisitor):
    """
    一個 CST 訪問者，用於在整個專案中尋找概念的初始定義和流動。
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider)

    def __init__(self, known_concepts: set[str], wrapper: MetadataWrapper, root_pkg: str):
        super().__init__()
        self.known_concepts = known_concepts
        self.wrapper = wrapper
        self.root_pkg = root_pkg
        self.flow_edges: set[tuple[str, str]] = set()
        self.newly_discovered_concepts: set[str] = set()

    def _find_concept_in_chain(self, node: cst.CSTNode) -> str | None:
        """遞迴地在屬性訪問鏈中尋找一個已知的概念。"""
        try:
            fqns = self.wrapper.resolve(FullyQualifiedNameProvider).get(node)
            if fqns:
                fqn = _normalize_fqn(next(iter(fqns)).name, self.root_pkg)
                if fqn in self.known_concepts:
                    return fqn
        except (KeyError, IndexError):
            pass

        if isinstance(node, cst.Attribute):
            return self._find_concept_in_chain(node.value)

        if isinstance(node, cst.Call):
            return self._find_concept_in_chain(node.func)

        return None

    def _process_usage(self, source_node: cst.CSTNode, usage_context_node: cst.CSTNode):
        """處理一個潛在的概念使用點。"""
        source_concept_fqn = self._find_concept_in_chain(source_node)
        if source_concept_fqn:
            try:
                usage_fqns = self.wrapper.resolve(FullyQualifiedNameProvider)[usage_context_node]
                if usage_fqns:
                    usage_fqn = _normalize_fqn(next(iter(usage_fqns)).name, self.root_pkg)
                    edge = (source_concept_fqn, usage_fqn)
                    if edge[0] != edge[1] and edge not in self.flow_edges:
                        self.flow_edges.add(edge)
                        logging.info(f"    [流動追蹤] 發現流動: {edge[0]} -> {edge[1]}")

                    if (
                        isinstance(usage_context_node, (cst.Name, cst.Attribute))
                        and usage_fqn not in self.known_concepts
                    ):
                        self.newly_discovered_concepts.add(usage_fqn)

            except (KeyError, IndexError):
                pass

    def visit_Assign(self, node: cst.Assign) -> None:
        for target in node.targets:
            self._process_usage(node.value, target.target)

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        if node.value:
            self._process_usage(node.value, node.target)


def analyze_concept_flow(
    root_pkg: str,
    py_files: list[Path],
    track_groups: list[dict[str, Any]],
    project_root: Path,
) -> dict[str, Any]:
    """
    分析整個專案，追蹤指定「概念」的來源、傳遞與使用。
    """
    all_edges: set[tuple[str, str]] = set()

    logging.info(f"準備分析專案: {project_root}")
    with temporary_cwd(project_root):
        logging.info(f"臨時工作目錄已切換至: {Path.cwd()}")

        repo_root = "."
        file_paths_str = [p.relative_to(project_root).as_posix() for p in py_files]
        providers = {FullyQualifiedNameProvider, ScopeProvider, ParentNodeProvider, PositionProvider}

        try:
            repo_manager = FullRepoManager(repo_root, file_paths_str, providers)
            repo_manager.resolve_cache()
            logging.info("LibCST 儲存庫管理器初始化並解析快取完成。")
        except Exception as e:
            logging.error(f"初始化 LibCST FullRepoManager 時發生嚴重錯誤: {e}")
            return {}

        known_concepts: set[str] = {_normalize_fqn(g["from_object"], root_pkg) for g in track_groups}

        iteration = 0
        max_iterations = 10

        while iteration < max_iterations:
            iteration += 1
            logging.info(f"--- 開始第 {iteration} 輪概念流動分析 (已知概念數: {len(known_concepts)}) ---")

            newly_discovered_concepts_this_round: set[str] = set()

            for file_path_str in file_paths_str:
                try:
                    wrapper = repo_manager.get_metadata_wrapper_for_path(file_path_str)
                    visitor = ConceptVisitor(known_concepts, wrapper, root_pkg)
                    wrapper.module.visit(visitor)

                    all_edges.update(visitor.flow_edges)
                    newly_discovered_concepts_this_round.update(visitor.newly_discovered_concepts)
                except Exception as e:
                    logging.error(f"在 '{file_path_str}' 中分析時失敗: {e}")

            new_concepts_to_add = newly_discovered_concepts_this_round - known_concepts
            if not new_concepts_to_add:
                logging.info("--- 分析穩定，未發現新的概念流動，迭代終止。 ---")
                break

            logging.info(f"--- 第 {iteration} 輪結束，發現 {len(new_concepts_to_add)} 個新概念持有者。 ---")
            known_concepts.update(new_concepts_to_add)
        else:
            logging.warning(f"分析達到最大迭代次數 ({max_iterations})，可能存在循環依賴或分析不完全。")

    return {"nodes": [], "edges": list(all_edges)}

# src/projectinsight/parsers/seed_discoverer.py
"""
提供「智慧種子發現」功能，自動識別專案中的核心概念實例。
"""

# 1. 標準庫導入
import fnmatch
import logging
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import libcst as cst
from libcst.metadata import (
    FullRepoManager,
    FullyQualifiedNameProvider,
    GlobalScope,
    MetadataWrapper,
    ParentNodeProvider,
    PositionProvider,
    ScopeProvider,
)

# 3. 本專案導入
from .concept_flow_analyzer import _normalize_fqn, temporary_cwd


class SeedDiscoveryVisitor(cst.CSTVisitor):
    """
    一個 CST 訪問者，用於自動發現潛在的概念種子。
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider)

    def __init__(self, wrapper: MetadataWrapper, root_pkg: str):
        super().__init__()
        self.wrapper = wrapper
        self.root_pkg = root_pkg
        self.discovered_seeds: set[str] = set()

    def visit_Assign(self, node: cst.Assign) -> None:
        scope = self.wrapper.resolve(ScopeProvider).get(node)
        if not isinstance(scope, GlobalScope):
            return

        if isinstance(node.value, cst.Call):
            for target in node.targets:
                try:
                    fqns = self.wrapper.resolve(FullyQualifiedNameProvider).get(target.target)
                    if fqns:
                        fqn = next(iter(fqns)).name
                        normalized_fqn = _normalize_fqn(fqn, self.root_pkg)
                        self.discovered_seeds.add(normalized_fqn)
                except (KeyError, IndexError):
                    continue


def discover_seeds(
    root_pkg: str,
    py_files: list[Path],
    project_root: Path,
    exclude_patterns: list[str],
) -> list[dict[str, Any]]:
    """
    自動分析整個專案，發現潛在的核心概念種子。
    """
    discovered_fqns: set[str] = set()

    logging.info(f"準備自動發現種子: {project_root}")
    with temporary_cwd(project_root):
        repo_root = "."
        file_paths_str = [p.relative_to(project_root).as_posix() for p in py_files]
        providers = {FullyQualifiedNameProvider, ScopeProvider, ParentNodeProvider, PositionProvider}

        try:
            repo_manager = FullRepoManager(repo_root, file_paths_str, providers)
            repo_manager.resolve_cache()
        except Exception as e:
            logging.error(f"初始化 LibCST FullRepoManager 時發生嚴重錯誤: {e}")
            return []

        for file_path_str in file_paths_str:
            try:
                wrapper = repo_manager.get_metadata_wrapper_for_path(file_path_str)
                visitor = SeedDiscoveryVisitor(wrapper, root_pkg)
                wrapper.module.visit(visitor)
                discovered_fqns.update(visitor.discovered_seeds)
            except Exception as e:
                logging.error(f"在 '{file_path_str}' 中發現種子時失敗: {e}")

    logging.info(f"自動發現了 {len(discovered_fqns)} 個潛在的概念種子。")

    filtered_fqns = set()
    for fqn in discovered_fqns:
        is_excluded = False
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(fqn, pattern):
                is_excluded = True
                break
        if not is_excluded:
            filtered_fqns.add(fqn)

    logging.info(f"應用排除規則後，剩餘 {len(filtered_fqns)} 個概念種子。")

    track_groups = [{"group_name": fqn.split(".")[-1], "from_object": fqn} for fqn in sorted(filtered_fqns)]
    return track_groups

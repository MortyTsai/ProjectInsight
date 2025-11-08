# src/projectinsight/semantics/semantic_link_analyzer.py
"""
[第十階段] 靜態語義連結分析器。

此模組負責分析「控制反轉 (IoC)」模式，例如集合註冊、繼承等，
以補充純呼叫圖無法捕捉到的架構意圖。
"""

# 1. 標準庫導入
import logging
from typing import Any

# 2. 第三方庫導入
import libcst as cst
import libcst.matchers as m
from libcst.metadata import (
    FullRepoManager,
    FullyQualifiedNameProvider,
    MetadataWrapper,
    ParentNodeProvider,
    ScopeProvider,
)

# 3. 本專案導入
# (無)

# [!!] 已修復 (P2.2): 輔助函式不應是全域的，它們需要
# 訪問 self.get_metadata()。它們將被複製到每個 Visitor 中
# 作為私有方法。（未來可重構為基底類別）


# --- [P1] 集合註冊分析 ---

class _CollectionRegistrationVisitor(m.MatcherDecoratableVisitor):
    """
    [已驗證 P0.5]
    一個 LibCST 訪問者，用於發現通用的「類別集合聲明」模式。
    匹配:
    class MyRegistrar:
        my_collection = [RegistreeA, RegistreeB]
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider, ParentNodeProvider)

    def __init__(self, wrapper: MetadataWrapper, root_pkg: str, all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.root_pkg = root_pkg
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    # [!!] 已修復 (P2.2): 輔助函式改為內部方法以訪問 self.get_metadata
    def _resolve_to_public_component(self, fqn: str | None) -> str | None:
        if not fqn:
            return None
        path = fqn.split(".<locals>.", 1)[0]
        if path in self.all_components:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            potential_component = ".".join(parts[:i])
            if potential_component in self.all_components:
                return potential_component
        return None

    # [!!] 已修復 (P2.2): 輔助函式改為內部方法以訪問 self.get_metadata
    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            # [!!] 修正: self.get_metadata (NOT self.wrapper.get_metadata)
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception as e:
            logging.debug(f"無法獲取節點 FQN: {e}")
        return None

    # [!!] 已修復 (P2.2): 輔助函式改為內部方法以訪問 self.get_metadata
    def _get_enclosing_class_component(self, node: cst.CSTNode) -> str | None:
        current: cst.CSTNode | None = node
        while current:
            if isinstance(current, cst.ClassDef):
                try:
                    fqn = self._get_fqn_from_node(current)  # [!!] 修正
                    return self._resolve_to_public_component(fqn)
                except Exception:
                    return None
            try:
                # [!!] 修正: self.get_metadata (NOT self.wrapper.get_metadata)
                current = self.get_metadata(ParentNodeProvider, current)
            except (KeyError, Exception):
                break
        return None

    @m.visit(m.Assign(value=m.OneOf(m.List(), m.Tuple())))
    def visit_collection_assign(self, node: cst.Assign):
        """
        處理 class MyRegistrar: my_list = [RegistreeA, RegistreeB] 模式。
        """
        try:
            registrar_component = self._get_enclosing_class_component(node)
            if not registrar_component:
                return

            collection_node = node.value
            if not isinstance(collection_node, (cst.List, cst.Tuple)):
                return

            for element in collection_node.elements:
                registree_node = element.value
                registree_fqn = self._get_fqn_from_node(registree_node)  # [!!] 修正

                if not registree_fqn or not registree_fqn.startswith(self.root_pkg):
                    continue

                registree_component = self._resolve_to_public_component(registree_fqn)

                if registree_component and registrar_component != registree_component:
                    edge = (registrar_component, registree_component, "registers")
                    if edge not in self.semantic_edges:
                        self.semantic_edges.add(edge)
                        logging.debug(
                            f"  [!! 語義連結成功 !!] 發現: {registrar_component} --registers--> {registree_component}"
                        )
        except Exception as e:
            logging.debug(f"處理 'collection assign' 語義連結時出錯: {e}", exc_info=True)


# --- [P2] 繼承分析 ---

class _InheritanceVisitor(m.MatcherDecoratableVisitor):
    """
    [已驗證 P2]
    一個 LibCST 訪問者，用於發現通用的「類別繼承」模式。
    匹配: class Child(Parent1, Parent2): ...
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider)

    def __init__(self, wrapper: MetadataWrapper, root_pkg: str, all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.root_pkg = root_pkg
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    # [!!] 已修復 (P2.2): 輔助函式改為內部方法
    def _resolve_to_public_component(self, fqn: str | None) -> str | None:
        if not fqn:
            return None
        path = fqn.split(".<locals>.", 1)[0]
        if path in self.all_components:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            potential_component = ".".join(parts[:i])
            if potential_component in self.all_components:
                return potential_component
        return None

    # [!!] 已修復 (P2.2): 輔助函式改為內部方法
    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            # [!!] 修正: self.get_metadata
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception as e:
            logging.debug(f"無法獲取節點 FQN: {e}")
        return None

    @m.visit(m.ClassDef())
    def visit_class_def(self, node: cst.ClassDef):
        """
        處理 class Child(Parent1, Parent2): ... 模式。
        """
        try:
            child_fqn = self._get_fqn_from_node(node.name)  # [!!] 修正
            child_component = self._resolve_to_public_component(child_fqn)

            if not child_component or not child_fqn.startswith(self.root_pkg):
                return

            for base in node.bases:
                parent_fqn = self._get_fqn_from_node(base.value)  # [!!] 修正
                if not parent_fqn:
                    continue

                parent_component = self._resolve_to_public_component(parent_fqn)
                if not parent_component:
                    continue

                if child_component != parent_component:
                    edge = (child_component, parent_component, "inherits_from")
                    if edge not in self.semantic_edges:
                        self.semantic_edges.add(edge)
                        logging.debug(
                            f"  [!! 語義連結成功 !!] 發現: {child_component} --inherits_from--> {parent_component}"
                        )
        except Exception as e:
            logging.debug(f"處理 'inherits_from' 語義連結時出錯: {e}", exc_info=True)


# --- [P3] 裝飾器分析 ---

class _DecoratorVisitor(m.MatcherDecoratableVisitor):
    """
    [已驗證 P3]
    一個 LibCST 訪問者，用於發現通用的「裝飾器」模式。
    匹配:
    @Registrar.some_decorator
    def my_registree_func(): ...
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider, ParentNodeProvider)

    def __init__(self, wrapper: MetadataWrapper, root_pkg: str, all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.root_pkg = root_pkg
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    # [!!] 已修復 (P2.2): 輔助函式改為內部方法
    def _resolve_to_public_component(self, fqn: str | None) -> str | None:
        if not fqn:
            return None
        path = fqn.split(".<locals>.", 1)[0]
        if path in self.all_components:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            potential_component = ".".join(parts[:i])
            if potential_component in self.all_components:
                return potential_component
        return None

    # [!!] 已修復 (P2.2): 輔助函式改為內部方法
    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            # [!!] 修正: self.get_metadata
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception as e:
            logging.debug(f"無法獲取節點 FQN: {e}")
        return None

    @m.visit(m.Decorator())
    def visit_decorator(self, node: cst.Decorator):
        """
        處理 @Decorator 模式。
        """
        try:
            # 1. 解析被裝飾的函式 (子節點)
            # [!!] 修正: self.get_metadata
            parent_def = self.get_metadata(ParentNodeProvider, node)
            if not isinstance(parent_def, (cst.FunctionDef, cst.ClassDef)):
                return

            child_fqn = self._get_fqn_from_node(parent_def.name)  # [!!] 修正
            child_component = self._resolve_to_public_component(child_fqn)

            if not child_component or (
                not child_fqn.startswith(self.root_pkg) and not child_fqn.startswith("builtins")
            ):
                return

            # 2. 解析裝飾器本身 (父節點)
            decorator_fqn = self._get_fqn_from_node(node.decorator)  # [!!] 修正
            if not decorator_fqn:
                return

            # 啟發式規則
            if decorator_fqn.split(".")[-1] in ("route", "command", "errorhandler", "before_request"):
                if m.matches(
                    node.decorator, m.Call(func=m.Attribute(value=m.DoNotCare()))
                ):
                    decorator_fqn = self._get_fqn_from_node(
                        node.decorator.func.value
                    )  # [!!] 修正
                elif m.matches(node.decorator, m.Attribute(value=m.DoNotCare())):
                    decorator_fqn = self._get_fqn_from_node(
                        node.decorator.value
                    )  # [!!] 修正

            parent_component = self._resolve_to_public_component(decorator_fqn)

            if not parent_component:
                return

            if child_component != parent_component:
                edge = (parent_component, child_component, "decorates")
                if edge not in self.semantic_edges:
                    self.semantic_edges.add(edge)
                    logging.debug(
                        f"  [!! 語義連結成功 !!] 發現: {parent_component} --decorates--> {child_component}"
                    )

        except Exception as e:
            logging.debug(f"處理 'decorates' 語義連結時出錯: {e}", exc_info=True)


# --- [P4] 代理分析 ---

class _ProxyVisitor(m.MatcherDecoratableVisitor):
    """
    [新增 P4]
    一個 LibCST 訪問者，用於發現通用的「代理」模式。
    匹配: request = LocalProxy(lambda: ...)
    [!!] 已植入日誌探針
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider)

    def __init__(self, wrapper: MetadataWrapper, root_pkg: str, all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.root_pkg = root_pkg
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    # [!!] 已修復 (P2.2): 輔助函式改為內部方法
    def _resolve_to_public_component(self, fqn: str | None) -> str | None:
        if not fqn:
            return None
        path = fqn.split(".<locals>.", 1)[0]
        if path in self.all_components:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            potential_component = ".".join(parts[:i])
            if potential_component in self.all_components:
                return potential_component
        return None

    # [!!] 已修復 (P2.2): 輔助函式改為內部方法
    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            # [!!] 修正: self.get_metadata
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception as e:
            logging.debug(f"無法獲取節點 FQN: {e}")
        return None

    @m.visit(
        m.Assign(
            value=m.Call(
                # [!!] 已修復 (P2.2):
                # 修正了 m.Name(value=m.OneOf(...)) 的 P0 級語法錯誤
                func=m.OneOf(
                    m.Name("LocalProxy"),
                    m.Name("LocalStack")
                ),
                args=[m.Arg(value=m.Lambda())],
            )
        )
    )
    def visit_proxy_assign(self, node: cst.Assign):
        """
        處理 X = LocalProxy(lambda: Y) 模式。
        """
        # [探針 P4-1] 測試 Matcher 是否被觸發
        logging.debug("[PROBE-P4] 'visit_proxy_assign' Matcher 觸發成功。")
        try:
            # 1. 解析代理物件 (Proxy)
            proxy_fqn = self._get_fqn_from_node(node.targets[0].target)  # [!!] 修正
            proxy_component = self._resolve_to_public_component(proxy_fqn)
            logging.debug(f"[PROBE-P4] 代理 (Proxy) 解析為: {proxy_component}")

            if not proxy_component:
                return

            # 2. 解析代理目標 (Target)
            lambda_node = node.value.args[0].value
            if not isinstance(lambda_node, cst.Lambda):
                return

            # 啟發式規則：在 lambda 體中尋找第一個 Name 或 Attribute
            target_node = None
            if m.matches(lambda_node.body, m.Name()):
                target_node = lambda_node.body
            elif m.matches(lambda_node.body, m.Attribute()):
                target_node = lambda_node.body
            elif m.matches(lambda_node.body, m.Call(func=m.Name())):
                target_node = lambda_node.body.func
            elif m.matches(lambda_node.body, m.Call(func=m.Attribute())):
                target_node = lambda_node.body.func

            if not target_node:
                logging.debug("[PROBE-P4] 中止: 找不到 Lambda 內的目標節點。")
                return

            target_fqn = self._get_fqn_from_node(target_node)  # [!!] 修正
            target_component = self._resolve_to_public_component(target_fqn)
            logging.debug(f"[PROBE-P4] 目標 (Target) 原始 FQN: {target_fqn}")
            logging.debug(f"[PROBE-P4] 目標 (Target) 解析為: {target_component}")

            if not target_component:
                logging.debug("[PROBE-P4] 中止: 目標 component 為 None。")
                return

            if proxy_component != target_component:
                # 邊的方向：Proxy -> Target
                edge = (proxy_component, target_component, "proxies")
                if edge not in self.semantic_edges:
                    self.semantic_edges.add(edge)
                    logging.debug(
                        f"  [!! 語義連結成功 !!] 發現: {proxy_component} --proxies--> {target_component}"
                    )
            else:
                logging.debug("[PROBE-P4] 中止: 最終 if 檢查失敗 (自我代理)。")

        except Exception as e:
            logging.debug(f"處理 'proxies' 語義連結時出錯: {e}", exc_info=True)


# --- [協調器] ---

def analyze_semantic_links(
    repo_manager: FullRepoManager,
    pre_scan_results: dict[str, Any],
    root_pkg: str,
    all_components: set[str],
) -> dict[str, Any]:
    """
    [第十階段]
    執行所有靜態語義連結分析。

    Args:
        repo_manager: 已初始化的 LibCST FullRepoManager。
        pre_scan_results: 來自 quick_ast_scan 的結果，用於迭代檔案。
        root_pkg: 根套件名稱。
        all_components: 來自 component_parser 的所有高階組件 FQN 集合。

    Returns:
        一個包含 'semantic_edges' 集合的字典。
    """
    all_semantic_edges: set[tuple[str, str, str]] = set()

    for file_path_str in pre_scan_results:
        try:
            wrapper = repo_manager.get_metadata_wrapper_for_path(file_path_str)

            # 1. [P1] 執行集合註冊分析
            collection_visitor = _CollectionRegistrationVisitor(wrapper, root_pkg, all_components)
            wrapper.visit(collection_visitor)
            all_semantic_edges.update(collection_visitor.semantic_edges)

            # 2. [P2] 執行繼承分析
            inheritance_visitor = _InheritanceVisitor(wrapper, root_pkg, all_components)
            wrapper.visit(inheritance_visitor)
            all_semantic_edges.update(inheritance_visitor.semantic_edges)

            # 3. [P3] 執行裝飾器分析
            decorator_visitor = _DecoratorVisitor(wrapper, root_pkg, all_components)
            wrapper.visit(decorator_visitor)
            all_semantic_edges.update(decorator_visitor.semantic_edges)

            # 4. [P4] 執行代理分析
            proxy_visitor = _ProxyVisitor(wrapper, root_pkg, all_components)
            wrapper.visit(proxy_visitor)
            all_semantic_edges.update(proxy_visitor.semantic_edges)

        except Exception as e:
            logging.warning(f"分析語義連結時無法分析檔案 '{file_path_str}': {e}")

    logging.info(f"--- 語義連結分析完成，發現 {len(all_semantic_edges)} 條連結 ---")

    return {"semantic_edges": all_semantic_edges}
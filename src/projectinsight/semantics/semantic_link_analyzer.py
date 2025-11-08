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
    [P4 最終修復 - 第7版] (基於 ScopeProvider)
    一個 LibCST 訪問者，用於發現通用的「代理」模式。
    匹配: X = SomeFunc(...) 或 X: T = SomeFunc(...)
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

    # [!!] P4 最終修復 (第7版)
    # 採用 P2.2 和 P0.5 的最終方案：使用 ScopeProvider 追蹤導入來源
    def _is_proxy_call(self, call_func_node: cst.CSTNode) -> bool:
        """
        使用 ScopeProvider 檢查節點是否為從 'werkzeug.local' 導入的
        'LocalProxy' 或 'LocalStack'。
        """
        if not isinstance(call_func_node, (cst.Name, cst.Attribute)):
            return False

        try:
            # 1. 獲取節點的名稱 (例如 "LocalProxy")
            call_name_node = call_func_node
            if isinstance(call_func_node, cst.Attribute):
                call_name_node = call_func_node.attr

            if not isinstance(call_name_node, cst.Name):
                return False

            call_name = call_name_node.value
            if call_name not in ("LocalProxy", "LocalStack"):
                return False

            # 2. 獲取當前作用域
            scope = self.get_metadata(ScopeProvider, call_func_node)

            # 3. 遍歷作用域中的所有賦值
            for assignment in scope.assignments:
                if assignment.name == call_name:
                    # 4. 找到定義此名稱的節點 (cst.ImportFrom)
                    if isinstance(assignment.node, cst.ImportFrom):
                        import_node = assignment.node

                        # 5. 獲取導入來源模組 (cst.Attribute 或 cst.Name)
                        module_name_node = import_node.module
                        if module_name_node is None:
                            continue

                        # 將 cst.Attribute(value=Name("werkzeug"), attr=Name("local"))
                        # 轉換為 "werkzeug.local"
                        module_parts = []
                        current = module_name_node
                        while isinstance(current, cst.Attribute):
                            module_parts.append(current.attr.value)
                            current = current.value
                        if isinstance(current, cst.Name):
                            module_parts.append(current.value)

                        module_name = ".".join(reversed(module_parts))

                        # 6. 最終驗證
                        if module_name == "werkzeug.local":
                            # [!! 移除探針 !!]
                            return True

            # [!! 移除探針 !!]
            return False

        except Exception as e:
            logging.debug(f"ScopeProvider 追蹤導入時出錯: {e}")
            return False

    # 修正 P0 級 API 錯誤：使用 @m.visit 裝飾*新*方法
    @m.visit(
        m.OneOf(
            m.Assign(value=m.Call()),
            m.AnnAssign(value=m.Call())
        )
    )
    def visit_proxy_assignment(self, node: cst.Assign | cst.AnnAssign):
        """
        處理 X = SomeFunc(Y) 或 X: T = SomeFunc(Y) 模式。
        """
        # [!! 移除探針 !!]

        try:
            # 步驟 0: 適配節點
            target_node: cst.CSTNode
            call_node: cst.Call

            if isinstance(node, cst.Assign):
                target_node = node.targets[0].target
                if not isinstance(node.value, cst.Call): return
                call_node = node.value
            elif isinstance(node, cst.AnnAssign):
                target_node = node.target
                if not node.value or not isinstance(node.value, cst.Call): return
                call_node = node.value
            else:
                return

            call_func_node = call_node.func

            # [!! 移除探針 !!]

            # 步驟 1: [!! 最終修正 !!] 使用 ScopeProvider 驗證
            if not self._is_proxy_call(call_func_node):
                return

            # [!! 移除探針 !!]

            # 步驟 2: 解析代理物件 (Proxy)
            proxy_fqn = self._get_fqn_from_node(target_node)
            proxy_component = self._resolve_to_public_component(proxy_fqn)

            # [!! P4 最終邏輯修復 !!]
            # 如果 FQN 是 None 或 component 是 None (因為 P0.9 不包含模組級變數)，
            # 則直接使用 FQN 作為 component 名稱。
            if proxy_fqn and not proxy_component:
                # [!! 移除探針 !!]
                proxy_component = proxy_fqn

            # [!! 移除探針 !!]

            if not proxy_component:
                return

            # 步驟 3: 解析代理目標 (Target)
            if not call_node.args:
                # [!! 移除探針 !!]
                return

            target_arg_node = call_node.args[0].value
            target_node_for_fqn: cst.CSTNode | None = None
            # [!! 移除探針 !!]

            if isinstance(target_arg_node, cst.Lambda):
                # 模式 1: LocalProxy(lambda: Y)
                lambda_body = target_arg_node.body
                if m.matches(lambda_body, m.Name()):
                    target_node_for_fqn = lambda_body
                elif m.matches(lambda_body, m.Attribute()):
                    target_node_for_fqn = lambda_body
                elif m.matches(lambda_body, m.Call(func=m.Name())):
                    target_node_for_fqn = lambda_body.func
                elif m.matches(lambda_body, m.Call(func=m.Attribute())):
                    target_node_for_fqn = lambda_body.func
            elif isinstance(target_arg_node, (cst.Name, cst.Attribute)):
                # 模式 2: LocalProxy(_find_request) 或 LocalProxy(_cv_app)
                target_node_for_fqn = target_arg_node
            else:
                # [!! 移除探針 !!]
                return

            if not target_node_for_fqn:
                # [!! 移除探針 !!]
                return

            target_fqn = self._get_fqn_from_node(target_node_for_fqn)
            target_component = self._resolve_to_public_component(target_fqn)
            # [!! 移除探針 !!]

            if not target_component:
                if target_fqn and target_fqn.endswith("_cv_app"):
                    target_component = "flask.globals.AppContextProxy"
                # [!! P4 最終邏輯修復 !!]
                # 目標也可能是模組級變數
                elif target_fqn:
                    # [!! 移除探針 !!]
                    target_component = target_fqn
                else:
                    # [!! 移除探針 !!]
                    return

            # [!! 移除探針 !!]

            # 步驟 4: 建立邊
            if proxy_component != target_component:
                edge = (proxy_component, target_component, "proxies")
                if edge not in self.semantic_edges:
                    self.semantic_edges.add(edge)
                    logging.debug(
                        f"  [!! 語義連結成功 !!] 發現: {proxy_component} --proxies--> {target_component}"
                    )
            else:
                # [!! 移除探針 !!]
                pass

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
        # [!! 移除探針 !!]
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
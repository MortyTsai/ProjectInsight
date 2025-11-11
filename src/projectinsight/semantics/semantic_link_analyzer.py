# src/projectinsight/semantics/semantic_link_analyzer.py
"""
靜態語義連結分析器。

此模組負責分析「控制反轉 (IoC)」模式，例如集合註冊、繼承、策略模式等，
以補充純靜態呼叫圖無法捕捉到的架構意圖。
"""

# 1. 標準庫導入
import logging
from typing import Any, cast

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


class _CollectionRegistrationVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現在類別級別的「集合聲明」模式。

    匹配:
    class MyRegistrar:
        my_collection = [RegistreeA, RegistreeB]
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider, ParentNodeProvider)

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    def _is_internal_fqn(self, fqn: str) -> bool:
        """檢查 FQN 是否屬於專案的內部上下文。"""
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages)

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

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception as e:
            logging.debug(f"無法獲取節點 FQN: {e}")
        return None

    def _get_enclosing_class_component(self, node: cst.CSTNode) -> str | None:
        current: cst.CSTNode | None = node
        while current:
            if isinstance(current, cst.ClassDef):
                try:
                    fqn = self._get_fqn_from_node(current)
                    return self._resolve_to_public_component(fqn)
                except Exception:
                    return None
            try:
                current = self.get_metadata(ParentNodeProvider, current)
            except (KeyError, Exception):
                break
        return None

    @m.visit(m.Assign(value=m.OneOf(m.List(), m.Tuple())))
    def visit_collection_assign(self, node: cst.Assign):
        """
        處理 `class MyRegistrar: my_list = [RegistreeA, RegistreeB]` 模式。
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
                registree_fqn = self._get_fqn_from_node(registree_node)

                if not registree_fqn or not self._is_internal_fqn(registree_fqn):
                    continue

                registree_component = self._resolve_to_public_component(registree_fqn)

                if registree_component and registrar_component != registree_component:
                    edge = (registrar_component, registree_component, "registers")
                    if edge not in self.semantic_edges:
                        self.semantic_edges.add(edge)
                        logging.debug(f"  [語義連結] 發現: {registrar_component} --registers--> {registree_component}")
        except Exception as e:
            logging.debug(f"處理 'collection assign' 語義連結時出錯: {e}", exc_info=True)


class _InheritanceVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現通用的「類別繼承」模式。

    匹配: class Child(Parent1, Parent2): ...
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider)

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    def _is_internal_fqn(self, fqn: str) -> bool:
        """檢查 FQN 是否屬於專案的內部上下文。"""
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages)

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

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception as e:
            logging.debug(f"無法獲取節點 FQN: {e}")
        return None

    @m.visit(m.ClassDef())
    def visit_class_def(self, node: cst.ClassDef):
        """
        處理 `class Child(Parent1, Parent2): ...` 模式。
        """
        try:
            child_fqn = self._get_fqn_from_node(node.name)
            child_component = self._resolve_to_public_component(child_fqn)

            if not child_component or not child_fqn or not self._is_internal_fqn(child_fqn):
                return

            for base in node.bases:
                parent_fqn = self._get_fqn_from_node(base.value)
                if not parent_fqn:
                    continue

                parent_component = self._resolve_to_public_component(parent_fqn)
                if not parent_component:
                    continue

                if child_component != parent_component:
                    edge = (child_component, parent_component, "inherits_from")
                    if edge not in self.semantic_edges:
                        self.semantic_edges.add(edge)
                        logging.debug(f"  [語義連結] 發現: {child_component} --inherits_from--> {parent_component}")
        except Exception as e:
            logging.debug(f"處理 'inherits_from' 語義連結時出錯: {e}", exc_info=True)


class _DecoratorVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現通用的「裝飾器」模式。

    匹配:
    @Registrar.some_decorator
    def my_registree_func(): ...
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider, ParentNodeProvider)

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    def _is_internal_fqn(self, fqn: str) -> bool:
        """檢查 FQN 是否屬於專案的內部上下文。"""
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages)

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

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception as e:
            logging.debug(f"無法獲取節點 FQN: {e}")
        return None

    @m.visit(m.Decorator())
    def visit_decorator(self, node: cst.Decorator):
        """
        處理 `@Decorator` 模式。
        """
        try:
            parent_def = self.get_metadata(ParentNodeProvider, node)
            if not isinstance(parent_def, (cst.FunctionDef, cst.ClassDef)):
                return

            child_fqn = self._get_fqn_from_node(parent_def.name)
            child_component = self._resolve_to_public_component(child_fqn)

            if (
                not child_component
                or not child_fqn
                or not (self._is_internal_fqn(child_fqn) or child_fqn.startswith("builtins"))
            ):
                return

            decorator_fqn = self._get_fqn_from_node(node.decorator)
            if not decorator_fqn:
                return

            if decorator_fqn.split(".")[-1] in ("route", "command", "errorhandler", "before_request"):
                if m.matches(node.decorator, m.Call(func=m.Attribute(value=m.DoNotCare()))):
                    decorator_call_node = cast(cst.Call, node.decorator)
                    decorator_attribute_node = cast(cst.Attribute, decorator_call_node.func)
                    decorator_fqn = self._get_fqn_from_node(decorator_attribute_node.value)
                elif m.matches(node.decorator, m.Attribute(value=m.DoNotCare())):
                    decorator_attribute_node = cast(cst.Attribute, node.decorator)
                    decorator_fqn = self._get_fqn_from_node(decorator_attribute_node.value)

            parent_component = self._resolve_to_public_component(decorator_fqn)

            if not parent_component:
                return

            if child_component != parent_component:
                edge = (parent_component, child_component, "decorates")
                if edge not in self.semantic_edges:
                    self.semantic_edges.add(edge)
                    logging.debug(f"  [語義連結] 發現: {parent_component} --decorates--> {child_component}")

        except Exception as e:
            logging.debug(f"處理 'decorates' 語義連結時出錯: {e}", exc_info=True)


class _ProxyVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現通用的「代理」模式，例如 Flask/Werkzeug 的 LocalProxy。

    匹配: `X = LocalProxy(...)` 或 `X: T = LocalProxy(...)`
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider)

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

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

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception as e:
            logging.debug(f"無法獲取節點 FQN: {e}")
        return None

    def _is_proxy_call(self, call_func_node: cst.CSTNode) -> bool:
        """
        使用 ScopeProvider 檢查節點是否為從 'werkzeug.local' 導入的
        'LocalProxy' 或 'LocalStack'。
        """
        if not isinstance(call_func_node, (cst.Name, cst.Attribute)):
            return False

        try:
            call_name_node = call_func_node
            if isinstance(call_func_node, cst.Attribute):
                call_name_node = call_func_node.attr

            if not isinstance(call_name_node, cst.Name):
                return False

            call_name = call_name_node.value
            if call_name not in ("LocalProxy", "LocalStack"):
                return False

            scope = self.get_metadata(ScopeProvider, call_func_node)

            for assignment in scope.assignments:
                if assignment.name == call_name and isinstance(assignment.node, cst.ImportFrom):
                    import_node = assignment.node
                    module_name_node = import_node.module
                    if module_name_node is None:
                        continue

                    module_parts = []
                    current = module_name_node
                    while isinstance(current, cst.Attribute):
                        module_parts.append(current.attr.value)
                        current = current.value
                    if isinstance(current, cst.Name):
                        module_parts.append(current.value)

                    module_name = ".".join(reversed(module_parts))

                    if module_name == "werkzeug.local":
                        return True
            return False

        except Exception as e:
            logging.debug(f"ScopeProvider 追蹤導入時出錯: {e}")
            return False

    @m.visit(m.OneOf(m.Assign(value=m.Call()), m.AnnAssign(value=m.Call())))
    def visit_proxy_assignment(self, node: cst.Assign | cst.AnnAssign):
        """
        處理 `X = SomeFunc(Y)` 或 `X: T = SomeFunc(Y)` 模式。
        """
        try:
            target_node: cst.CSTNode
            call_node: cst.Call

            if isinstance(node, cst.Assign):
                target_node = node.targets[0].target
                if not isinstance(node.value, cst.Call):
                    return
                call_node = node.value
            elif isinstance(node, cst.AnnAssign):
                target_node = node.target
                if not node.value or not isinstance(node.value, cst.Call):
                    return
                call_node = node.value
            else:
                return

            if not self._is_proxy_call(call_node.func):
                return

            proxy_fqn = self._get_fqn_from_node(target_node)
            proxy_component = self._resolve_to_public_component(proxy_fqn)
            if proxy_fqn and not proxy_component:
                proxy_component = proxy_fqn
            if not proxy_component:
                return

            if not call_node.args:
                return

            target_arg_node = call_node.args[0].value
            target_node_for_fqn: cst.CSTNode | None = None

            if isinstance(target_arg_node, cst.Lambda):
                lambda_body = target_arg_node.body
                if m.matches(lambda_body, m.OneOf(m.Name(), m.Attribute())):
                    target_node_for_fqn = lambda_body
                elif m.matches(lambda_body, m.Call(func=m.OneOf(m.Name(), m.Attribute()))):
                    call_body = cast(cst.Call, lambda_body)
                    target_node_for_fqn = call_body.func
            elif isinstance(target_arg_node, (cst.Name, cst.Attribute)):
                target_node_for_fqn = target_arg_node
            else:
                return

            if not target_node_for_fqn:
                return

            target_fqn = self._get_fqn_from_node(target_node_for_fqn)
            target_component = self._resolve_to_public_component(target_fqn)

            if not target_component:
                if target_fqn and target_fqn.endswith("_cv_app"):
                    target_component = "flask.globals.AppContextProxy"
                elif target_fqn:
                    target_component = target_fqn
                else:
                    return

            if proxy_component != target_component:
                edge = (proxy_component, target_component, "proxies")
                if edge not in self.semantic_edges:
                    self.semantic_edges.add(edge)
                    logging.debug(f"  [語義連結] 發現: {proxy_component} --proxies--> {target_component}")

        except Exception as e:
            logging.debug(f"處理 'proxies' 語義連結時出錯: {e}", exc_info=True)


class _StrategyRegistrationVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現函式或模組級別的「策略模式」註冊。

    採用兩階段狀態追蹤：
    1. 訪問賦值語句，識別出哪些變數是「策略列表」。
    2. 訪問 `.append()` 呼叫，為已識別的策略列表添加新的策略。
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider, ParentNodeProvider)

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()
        self.strategy_lists: dict[str, str] = {}

    def _is_internal_fqn(self, fqn: str) -> bool:
        """檢查 FQN 是否屬於專案的內部上下文。"""
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages)

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

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception as e:
            logging.debug(f"無法獲取節點 FQN: {e}")
        return None

    def _get_enclosing_function_component(self, node: cst.CSTNode) -> str | None:
        current: cst.CSTNode | None = node
        while current:
            if isinstance(current, cst.FunctionDef):
                try:
                    fqn = self._get_fqn_from_node(current)
                    return self._resolve_to_public_component(fqn)
                except Exception:
                    return None
            try:
                current = self.get_metadata(ParentNodeProvider, current)
            except (KeyError, Exception):
                break
        return None

    @m.visit(m.Assign(value=m.OneOf(m.List(), m.Tuple())))
    def visit_strategy_list_assignment(self, node: cst.Assign):
        """階段一：識別策略列表的初始賦值。"""
        try:
            consumer_component = self._get_enclosing_function_component(node)
            if not consumer_component:
                return

            collection_node = node.value
            if not isinstance(collection_node, (cst.List, cst.Tuple)):
                return

            strategy_components_in_list = []
            for element in collection_node.elements:
                strategy_fqn = self._get_fqn_from_node(element.value)
                if not strategy_fqn or not self._is_internal_fqn(strategy_fqn):
                    continue
                strategy_component = self._resolve_to_public_component(strategy_fqn)
                if strategy_component:
                    strategy_components_in_list.append(strategy_component)

            if strategy_components_in_list:
                list_variable_node = node.targets[0].target
                list_variable_fqn = self._get_fqn_from_node(list_variable_node)
                if not list_variable_fqn:
                    return

                self.strategy_lists[list_variable_fqn] = consumer_component
                logging.debug(f"  [策略模式] 發現策略列表: '{list_variable_fqn}'，消費者: '{consumer_component}'")

                for strategy_component in strategy_components_in_list:
                    if consumer_component != strategy_component:
                        edge = (consumer_component, strategy_component, "uses_strategy")
                        if edge not in self.semantic_edges:
                            self.semantic_edges.add(edge)
                            logging.debug(f"  [語義連結] {consumer_component} --uses_strategy--> {strategy_component}")
        except Exception as e:
            logging.debug(f"處理 'strategy list assignment' 時出錯: {e}", exc_info=True)

    @m.visit(m.Call(func=m.Attribute(attr=m.Name("append"))))
    def visit_strategy_append(self, node: cst.Call):
        """階段二：識別對已知策略列表的 .append() 呼叫。"""
        try:
            attribute_node = node.func
            if not isinstance(attribute_node, cst.Attribute):
                return
            list_variable_node = attribute_node.value
            list_variable_fqn = self._get_fqn_from_node(list_variable_node)

            if not list_variable_fqn or list_variable_fqn not in self.strategy_lists:
                return

            consumer_component = self.strategy_lists[list_variable_fqn]

            if not node.args:
                return
            appended_node = node.args[0].value
            appended_fqn = self._get_fqn_from_node(appended_node)
            if not appended_fqn or not self._is_internal_fqn(appended_fqn):
                return

            strategy_component = self._resolve_to_public_component(appended_fqn)
            if strategy_component and consumer_component != strategy_component:
                edge = (consumer_component, strategy_component, "uses_strategy")
                if edge not in self.semantic_edges:
                    self.semantic_edges.add(edge)
                    logging.debug(
                        f"  [語義連結] {consumer_component} --uses_strategy--> {strategy_component} (via append)"
                    )
        except Exception as e:
            logging.debug(f"處理 'strategy append' 時出錯: {e}", exc_info=True)


def analyze_semantic_links(
    repo_manager: FullRepoManager,
    pre_scan_results: dict[str, Any],
    context_packages: list[str],
    all_components: set[str],
) -> dict[str, Any]:
    """
    執行所有靜態語義連結分析。

    Args:
        repo_manager: 已初始化的 LibCST FullRepoManager。
        pre_scan_results: 來自 quick_ast_scan 的結果，用於迭代檔案。
        context_packages: 包含所有頂層套件/模組的列表。
        all_components: 來自 component_parser 的所有高階組件 FQN 集合。

    Returns:
        一個包含 'semantic_edges' 集合的字典。
    """
    all_semantic_edges: set[tuple[str, str, str]] = set()

    for file_path_str in pre_scan_results:
        try:
            wrapper = repo_manager.get_metadata_wrapper_for_path(file_path_str)

            visitors = [
                _CollectionRegistrationVisitor(wrapper, context_packages, all_components),
                _InheritanceVisitor(wrapper, context_packages, all_components),
                _DecoratorVisitor(wrapper, context_packages, all_components),
                _ProxyVisitor(wrapper, context_packages, all_components),
                _StrategyRegistrationVisitor(wrapper, context_packages, all_components),
            ]

            for visitor in visitors:
                wrapper.visit(visitor)
                all_semantic_edges.update(visitor.semantic_edges)

        except Exception as e:
            logging.warning(f"分析語義連結時無法分析檔案 '{file_path_str}': {e}")

    logging.info(f"--- 語義連結分析完成，發現 {len(all_semantic_edges)} 條連結 ---")

    return {"semantic_edges": all_semantic_edges}

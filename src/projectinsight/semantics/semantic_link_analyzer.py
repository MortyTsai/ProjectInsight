# src/projectinsight/semantics/semantic_link_analyzer.py
"""
靜態語義連結分析器。
"""

# 1. 標準庫導入
import logging
import traceback
from pathlib import Path
from typing import Any, ClassVar, cast

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
from projectinsight.core.parallel_manager import ParallelManager
from projectinsight.utils.parser_utils import DECORATOR_IGNORE_PREFIXES, is_noise


class _CollectionRegistrationVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現在類別級別的「集合聲明」模式。
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider, ParentNodeProvider)

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    def _is_internal_fqn(self, fqn: str) -> bool:
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages)

    def _resolve_to_component(self, fqn: str | None) -> str | None:
        if not fqn:
            return None
        if ".<locals>." in fqn:
            return None
        path = fqn.split(".<locals>.", 1)[0]
        if path in self.all_components:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            potential_component = ".".join(parts[:i])
            if potential_component in self.all_components:
                return potential_component
        return fqn

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception:
            pass
        return None

    def _get_enclosing_class_component(self, node: cst.CSTNode) -> str | None:
        current: cst.CSTNode | None = node
        while current:
            if isinstance(current, cst.ClassDef):
                try:
                    fqn = self._get_fqn_from_node(current)
                    return self._resolve_to_component(fqn)
                except Exception:
                    return None
            try:
                current = self.get_metadata(ParentNodeProvider, current)
            except (KeyError, Exception):
                break
        return None

    @m.visit(m.Assign(value=m.OneOf(m.List(), m.Tuple())))
    def visit_collection_assign(self, node: cst.Assign):
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

                registree_component = self._resolve_to_component(registree_fqn)

                if registree_component and registrar_component != registree_component:
                    edge = (registrar_component, registree_component, "registers")
                    if edge not in self.semantic_edges:
                        self.semantic_edges.add(edge)
        except Exception:
            pass


class _InheritanceVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現通用的「類別繼承」模式。
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider)

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    def _is_internal_fqn(self, fqn: str) -> bool:
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages)

    def _resolve_to_component(self, fqn: str | None) -> str | None:
        if not fqn:
            return None
        if ".<locals>." in fqn:
            return None
        path = fqn.split(".<locals>.", 1)[0]
        if path in self.all_components:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            potential_component = ".".join(parts[:i])
            if potential_component in self.all_components:
                return potential_component

        if is_noise(fqn):
            return None

        return fqn

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception:
            pass
        return None

    @m.visit(m.ClassDef())
    def visit_class_def(self, node: cst.ClassDef):
        try:
            child_fqn = self._get_fqn_from_node(node.name)
            child_component = self._resolve_to_component(child_fqn)

            if not child_component:
                return

            for base in node.bases:
                parent_fqn = self._get_fqn_from_node(base.value)
                if not parent_fqn:
                    continue

                parent_component = self._resolve_to_component(parent_fqn)
                if not parent_component:
                    continue

                if child_component != parent_component:
                    edge = (child_component, parent_component, "inherits_from")
                    if edge not in self.semantic_edges:
                        self.semantic_edges.add(edge)
        except Exception:
            pass


class _DecoratorVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現通用的「裝飾器」模式。
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider, ParentNodeProvider)

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    def _is_internal_fqn(self, fqn: str) -> bool:
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages)

    def _resolve_to_component(self, fqn: str | None) -> str | None:
        if not fqn:
            return None
        if ".<locals>." in fqn:
            return None
        path = fqn.split(".<locals>.", 1)[0]
        if path in self.all_components:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            potential_component = ".".join(parts[:i])
            if potential_component in self.all_components:
                return potential_component

        if is_noise(fqn, DECORATOR_IGNORE_PREFIXES):
            return None

        return fqn

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception:
            pass
        return None

    @m.visit(m.Decorator())
    def visit_decorator(self, node: cst.Decorator):
        try:
            parent_def = self.get_metadata(ParentNodeProvider, node)
            if not isinstance(parent_def, (cst.FunctionDef, cst.ClassDef)):
                return

            child_fqn = self._get_fqn_from_node(parent_def.name)
            child_component = self._resolve_to_component(child_fqn)

            if not child_component:
                return

            decorator_fqn = self._get_fqn_from_node(node.decorator)
            if not decorator_fqn:
                return

            if decorator_fqn.split(".")[-1] in ("route", "command", "errorhandler", "before_request", "visit"):
                if m.matches(node.decorator, m.Call(func=m.Attribute(value=m.DoNotCare()))):
                    decorator_call_node = cast(cst.Call, node.decorator)
                    decorator_attribute_node = cast(cst.Attribute, decorator_call_node.func)
                    decorator_fqn = self._get_fqn_from_node(decorator_attribute_node.value)
                elif m.matches(node.decorator, m.Attribute(value=m.DoNotCare())):
                    decorator_attribute_node = cast(cst.Attribute, node.decorator)
                    decorator_fqn = self._get_fqn_from_node(decorator_attribute_node.value)

            parent_component = self._resolve_to_component(decorator_fqn)

            if not parent_component:
                return

            if child_component != parent_component:
                edge = (parent_component, child_component, "decorates")
                if edge not in self.semantic_edges:
                    self.semantic_edges.add(edge)

        except Exception:
            pass


class _ProxyVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現通用的「代理」模式。
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider)

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    def _resolve_to_component(self, fqn: str | None) -> str | None:
        if not fqn:
            return None
        if ".<locals>." in fqn:
            return None
        path = fqn.split(".<locals>.", 1)[0]
        if path in self.all_components:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            potential_component = ".".join(parts[:i])
            if potential_component in self.all_components:
                return potential_component
        return fqn

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception:
            pass
        return None

    def _is_proxy_call(self, call_func_node: cst.CSTNode) -> bool:
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

        except Exception:
            return False

    @m.visit(m.OneOf(m.Assign(value=m.Call()), m.AnnAssign(value=m.Call())))
    def visit_proxy_assignment(self, node: cst.Assign | cst.AnnAssign):
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
            proxy_component = self._resolve_to_component(proxy_fqn)
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
            target_component = self._resolve_to_component(target_fqn)

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

        except Exception:
            pass


class _StrategyRegistrationVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現函式或模組級別的「策略模式」註冊。
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
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages)

    def _resolve_to_component(self, fqn: str | None) -> str | None:
        if not fqn:
            return None
        if ".<locals>." in fqn:
            return None
        path = fqn.split(".<locals>.", 1)[0]
        if path in self.all_components:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            potential_component = ".".join(parts[:i])
            if potential_component in self.all_components:
                return potential_component
        return fqn

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception:
            pass
        return None

    def _get_enclosing_function_component(self, node: cst.CSTNode) -> str | None:
        current: cst.CSTNode | None = node
        while current:
            if isinstance(current, cst.FunctionDef):
                try:
                    fqn = self._get_fqn_from_node(current)
                    return self._resolve_to_component(fqn)
                except Exception:
                    return None
            try:
                current = self.get_metadata(ParentNodeProvider, current)
            except (KeyError, Exception):
                break
        return None

    @m.visit(m.Assign(value=m.OneOf(m.List(), m.Tuple())))
    def visit_strategy_list_assignment(self, node: cst.Assign):
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
                strategy_component = self._resolve_to_component(strategy_fqn)
                if strategy_component:
                    strategy_components_in_list.append(strategy_component)

            if strategy_components_in_list:
                list_variable_node = node.targets[0].target
                list_variable_fqn = self._get_fqn_from_node(list_variable_node)
                if not list_variable_fqn:
                    return

                self.strategy_lists[list_variable_fqn] = consumer_component

                for strategy_component in strategy_components_in_list:
                    if consumer_component != strategy_component:
                        edge = (consumer_component, strategy_component, "uses_strategy")
                        if edge not in self.semantic_edges:
                            self.semantic_edges.add(edge)
        except Exception:
            pass

    @m.visit(m.Call(func=m.Attribute(attr=m.Name("append"))))
    def visit_strategy_append(self, node: cst.Call):
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

            strategy_component = self._resolve_to_component(appended_fqn)
            if strategy_component and consumer_component != strategy_component:
                edge = (consumer_component, strategy_component, "uses_strategy")
                if edge not in self.semantic_edges:
                    self.semantic_edges.add(edge)
        except Exception:
            pass


class _DependencyInjectionVisitor(m.MatcherDecoratableVisitor):
    """
    一個 LibCST 訪問者，用於發現 FastAPI 的 `Depends()` 依賴注入模式。
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider, ParentNodeProvider)
    HTTP_METHODS: ClassVar[set[str]] = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], all_components: set[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.semantic_edges: set[tuple[str, str, str]] = set()

    def _is_internal_fqn(self, fqn: str) -> bool:
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages) or "docs_src" in fqn

    def _resolve_to_component(self, fqn: str | None) -> str | None:
        if not fqn:
            return None
        if ".<locals>." in fqn:
            return None
        path = fqn.split(".<locals>.", 1)[0]
        if path in self.all_components:
            return path
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            potential_component = ".".join(parts[:i])
            if potential_component in self.all_components:
                return potential_component
        if "docs_src" in fqn:
            return fqn
        return fqn

    def _get_fqn_from_node(self, node: cst.CSTNode) -> str | None:
        try:
            fqns = self.get_metadata(FullyQualifiedNameProvider, node)
            if fqns:
                return next(iter(fqns)).name
        except Exception:
            pass
        return None

    def _find_dependency_in_node(self, node: cst.CSTNode) -> cst.Call | None:
        if self.matches(node, m.Call(func=m.Name("Depends"))):
            return cast(cst.Call, node)

        if m.matches(node, m.Subscript()):
            subscript_node = cast(cst.Subscript, node)
            for element in subscript_node.slice:
                dependency = self._find_dependency_in_node(element.slice)
                if dependency:
                    return dependency
        return None

    def _process_dependency(self, depends_call: cst.Call, endpoint_component: str):
        if not depends_call.args:
            return

        dependency_provider_node = depends_call.args[0].value
        provider_fqn = self._get_fqn_from_node(dependency_provider_node)

        if not provider_fqn or not self._is_internal_fqn(provider_fqn):
            return

        provider_component = self._resolve_to_component(provider_fqn)
        if provider_component and endpoint_component != provider_component:
            edge = (endpoint_component, provider_component, "depends_on")
            if edge not in self.semantic_edges:
                self.semantic_edges.add(edge)

    @m.visit(m.FunctionDef())
    def _check_dependency_injection(self, node: cst.FunctionDef):
        try:
            endpoint_fqn = self._get_fqn_from_node(node.name)
            endpoint_component = self._resolve_to_component(endpoint_fqn)
            if not endpoint_component:
                return

            for param in node.params.params:
                if param.default:
                    dependency = self._find_dependency_in_node(param.default)
                    if dependency:
                        self._process_dependency(dependency, endpoint_component)

                if param.annotation:
                    dependency = self._find_dependency_in_node(param.annotation.annotation)
                    if dependency:
                        self._process_dependency(dependency, endpoint_component)

        except Exception:
            pass


def _worker_analyze_semantic_links(args: tuple[str, dict[str, Any]]) -> set[tuple[str, str, str]]:
    """
    [Worker] 執行單一檔案的語義連結分析。
    """
    file_path_str, context = args
    context_packages = context.get("context_packages", [])
    all_components = context.get("all_components", set())
    project_root = context.get("project_root")

    try:
        repo_manager = FullRepoManager(
            project_root,
            [file_path_str],
            {FullyQualifiedNameProvider, ScopeProvider, ParentNodeProvider},
        )
        wrapper = repo_manager.get_metadata_wrapper_for_path(file_path_str)

        visitors = [
            _CollectionRegistrationVisitor(wrapper, context_packages, all_components),
            _InheritanceVisitor(wrapper, context_packages, all_components),
            _DecoratorVisitor(wrapper, context_packages, all_components),
            _ProxyVisitor(wrapper, context_packages, all_components),
            _StrategyRegistrationVisitor(wrapper, context_packages, all_components),
            _DependencyInjectionVisitor(wrapper, context_packages, all_components),
        ]

        file_semantic_edges = set()
        for visitor in visitors:
            wrapper.visit(visitor)
            file_semantic_edges.update(visitor.semantic_edges)

        return file_semantic_edges

    except Exception as e:
        logging.error(f"Worker (Semantic Analysis) 失敗於 {file_path_str}: {e}")
        logging.debug(traceback.format_exc())
        return set()


def analyze_semantic_links(
    repo_manager: FullRepoManager,
    pre_scan_results: dict[str, Any],
    context_packages: list[str],
    all_components: set[str],
    cache_manager: Any | None = None,
    project_root: str | None = None,
) -> dict[str, Any]:
    """
    執行所有靜態語義連結分析。
    """
    all_semantic_edges: set[tuple[str, str, str]] = set()

    files_to_process: list[str] = []
    files_using_cache: list[str] = []

    for file_path_str in pre_scan_results:
        file_path_obj = Path(file_path_str)
        cached_data = cache_manager.get(file_path_obj) if cache_manager else None

        if cached_data and "semantic_edges" in cached_data:
            all_semantic_edges.update(cached_data["semantic_edges"])
            files_using_cache.append(file_path_str)
        else:
            files_to_process.append(file_path_str)

    if files_to_process:
        logging.info(f"  - 快取命中: {len(files_using_cache)} 檔")
        logging.info(f"  - 需解析: {len(files_to_process)} 檔")

        pm = ParallelManager()
        global_context = {
            "context_packages": context_packages,
            "all_components": all_components,
            "project_root": project_root,
        }

        results = pm.execute_map_reduce(
            task_func=_worker_analyze_semantic_links,
            items=files_to_process,
            global_context=global_context,
            chunksize=5,
        )

        for file_path_str, edges in zip(files_to_process, results, strict=False):
            all_semantic_edges.update(edges)

            if cache_manager:
                file_path_obj = Path(file_path_str)
                current_entry = cache_manager.get(file_path_obj) or {}
                current_entry["semantic_edges"] = edges
                cache_manager.update(file_path_obj, current_entry)

    logging.info(f"--- 語義連結分析完成，發現 {len(all_semantic_edges)} 條連結 ---")

    return {"semantic_edges": all_semantic_edges}

# src/projectinsight/parsers/component_parser.py
"""
提供基於 AST 和 LibCST 的 Python 原始碼組件互動解析功能。
"""

# 1. 標準庫導入
import ast
import fnmatch
import logging
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import libcst as cst
import libcst.matchers as m
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


class CodeVisitor(ast.NodeVisitor):
    """一個 AST 訪問者，用於收集程式碼中的各種定義和引用。"""

    def __init__(self, module_path: str, file_path: Path, context_packages: list[str]):
        self.module_path = module_path
        self.file_path = file_path
        self.context_packages = context_packages
        self.current_scope = [self.module_path]
        self.definitions: set[str] = set()
        self.components: set[str] = set()
        self.definition_to_module_map: dict[str, str] = {}
        self.docstring_map: dict[str, str] = {}
        self.definition_count = 0
        self.has_main_block = False
        self.internal_imports: set[str] = set()

    def _is_internal_module(self, module_name: str) -> bool:
        """檢查一個模組名稱是否屬於專案的內部上下文。"""
        return any(module_name.startswith(pkg) for pkg in self.context_packages)

    def visit_Import(self, node: ast.Import):
        """處理 'import a.b.c' 這種形式的導入。"""
        for alias in node.names:
            if self._is_internal_module(alias.name):
                self.internal_imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """處理 'from a.b import c' 這種形式的導入。"""
        if node.level > 0:
            base = self.module_path.split(".")
            if len(base) >= node.level:
                base = base[: -node.level]
            if node.module:
                base.append(node.module)
            import_path = ".".join(base)
            if self._is_internal_module(import_path):
                self.internal_imports.add(import_path)
        elif node.module and self._is_internal_module(node.module):
            self.internal_imports.add(node.module)
        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        """檢查是否存在 if __name__ == '__main__': 區塊。"""
        if isinstance(node.test, ast.Compare):
            left = node.test.left
            comparator = node.test.comparators[0]
            if (
                isinstance(left, ast.Name)
                and left.id == "__name__"
                and isinstance(comparator, ast.Constant)
                and comparator.value == "__main__"
            ):
                self.has_main_block = True
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        is_private = node.name.startswith("_") and not node.name.startswith("__")

        scope_name = ".".join([*self.current_scope, node.name])
        self.definitions.add(scope_name)
        self.definition_to_module_map[scope_name] = self.module_path
        self.definition_count += 1

        if len(self.current_scope) == 1 and not is_private:
            self.components.add(scope_name)

        docstring = ast.get_docstring(node)
        if docstring:
            self.docstring_map[scope_name] = docstring

        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        is_private = node.name.startswith("_") and not node.name.startswith("__")

        scope_name = ".".join([*self.current_scope, node.name])
        self.definitions.add(scope_name)
        if not is_private:
            self.components.add(scope_name)
        self.definition_to_module_map[scope_name] = self.module_path
        self.definition_count += 1
        docstring = ast.get_docstring(node)
        if docstring:
            self.docstring_map[scope_name] = docstring
        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)


def quick_ast_scan(project_path: Path, py_files: list[Path], context_packages: list[str]) -> dict[str, Any]:
    """
    執行一個快速的、無 Jedi 的 AST 掃描，以評估專案體量。
    """
    total_definitions = 0
    total_loc = 0
    pre_scan_results = {}
    module_import_graph: dict[str, set[str]] = {}
    definition_to_module_map: dict[str, str] = {}

    for file_path in py_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            total_loc += len(content.splitlines())
            tree = ast.parse(content, filename=str(file_path))

            relative_path = file_path.relative_to(project_path)
            parts = list(relative_path.parts)

            if parts[-1] == "__init__.py" or parts[-1] == "__main__.py":
                parts.pop()
            else:
                parts[-1] = relative_path.stem
            module_name = ".".join(parts)

            visitor = CodeVisitor(module_name, file_path, context_packages)
            visitor.visit(tree)
            total_definitions += visitor.definition_count
            pre_scan_results[str(file_path)] = {
                "visitor": visitor,
                "content": content,
            }
            if visitor.internal_imports:
                module_import_graph[visitor.module_path] = visitor.internal_imports
            definition_to_module_map.update(visitor.definition_to_module_map)

        except Exception as e:
            logging.debug(f"快速掃描時無法分析檔案 {file_path}: {e}")

    logging.info(f"快速 AST 掃描完成：找到 {len(py_files)} 個檔案, {total_loc} 行程式碼, {total_definitions} 個定義。")
    return {
        "file_count": len(py_files),
        "total_loc": total_loc,
        "definition_count": total_definitions,
        "pre_scan_results": pre_scan_results,
        "module_import_graph": module_import_graph,
        "definition_to_module_map": definition_to_module_map,
    }


def _normalize_call_fqn(callee_fqn: str, alias_map: dict[str, str]) -> str:
    """
    使用別名地圖，將一個潛在的別名 FQN 正規化為其真實的定義 FQN。
    """
    if callee_fqn in alias_map:
        normalized = alias_map[callee_fqn]
        logging.debug(f"  [別名解析] '{callee_fqn}' -> '{normalized}' (直接命中)")
        return normalized

    parts = callee_fqn.split(".")
    for i in range(len(parts), 0, -1):
        potential_alias = ".".join(parts[:i])
        if potential_alias in alias_map:
            real_base = alias_map[potential_alias]
            method_part = ".".join(parts[i:])
            normalized = f"{real_base}.{method_part}" if method_part else real_base
            logging.debug(f"  [別名解析] '{callee_fqn}' -> '{normalized}' (基礎路徑命中)")
            return normalized
    return callee_fqn


class _AliasVisitor(m.MatcherDecoratableVisitor):
    """一個 LibCST 訪問者，用於發現模組級的各種別名模式。"""

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider)

    def __init__(self, wrapper: MetadataWrapper, context_packages: list[str], exclude_patterns: list[str]):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.exclude_patterns = exclude_patterns
        self.alias_map: dict[str, str] = {}

    def _is_internal_fqn(self, fqn: str) -> bool:
        """檢查 FQN 是否屬於專案的內部上下文。"""
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages)

    def _add_alias(self, alias_fqn: str, real_fqn: str):
        is_excluded = any(fnmatch.fnmatch(alias_fqn, pattern) for pattern in self.exclude_patterns)

        if not is_excluded and self._is_internal_fqn(real_fqn) and alias_fqn != real_fqn:
            self.alias_map[alias_fqn] = real_fqn
            logging.debug(f"  [別名發現] {alias_fqn} -> {real_fqn}")

    @m.visit(m.Assign())
    def visit_assign(self, node: cst.Assign) -> None:
        try:
            scope = self.get_metadata(ScopeProvider, node)
            if not isinstance(scope, cst.metadata.GlobalScope):
                return

            alias_target_node = node.targets[0].target
            alias_fqns = self.get_metadata(FullyQualifiedNameProvider, alias_target_node)
            if not alias_fqns:
                return
            alias_fqn = next(iter(alias_fqns)).name

            real_fqns = self.get_metadata(FullyQualifiedNameProvider, node.value)
            if not real_fqns:
                return
            real_fqn = next(iter(real_fqns)).name

            self._add_alias(alias_fqn, real_fqn)

        except Exception as e:
            logging.debug(f"處理賦值別名時出錯: {e}")

    @m.visit(m.ImportFrom())
    def visit_import_from(self, node: cst.ImportFrom) -> None:
        try:
            if isinstance(node.names, cst.ImportStar):
                return

            for import_alias in node.names:
                real_name_node = import_alias.name
                alias_name_node = import_alias.asname.name if import_alias.asname else real_name_node

                real_fqns = self.get_metadata(FullyQualifiedNameProvider, real_name_node)
                if not real_fqns:
                    continue
                real_fqn = next(iter(real_fqns)).name

                alias_fqns = self.get_metadata(FullyQualifiedNameProvider, alias_name_node)
                if not alias_fqns:
                    continue
                alias_fqn = next(iter(alias_fqns)).name

                self._add_alias(alias_fqn, real_fqn)
        except Exception as e:
            logging.debug(f"處理 'from' 導入別名時出錯: {e}")


class _CallGraphVisitor(m.MatcherDecoratableVisitor):
    """一個 LibCST 訪問者，用於解析並建立呼叫圖。"""

    METADATA_DEPENDENCIES = (
        ScopeProvider,
        FullyQualifiedNameProvider,
        ParentNodeProvider,
        PositionProvider,
    )

    def __init__(
        self,
        wrapper: MetadataWrapper,
        context_packages: list[str],
        all_components: set[str],
        module_path: str,
        alias_map: dict[str, str],
        file_path: str,
    ):
        super().__init__()
        self.wrapper = wrapper
        self.context_packages = context_packages
        self.all_components = all_components
        self.module_path = module_path
        self.alias_map = alias_map
        self.file_path = file_path
        self.found_edges: set[tuple[str, str]] = set()

    def _is_internal_fqn(self, fqn: str) -> bool:
        """檢查 FQN 是否屬於專案的內部上下文。"""
        return any(fqn.startswith(f"{pkg}.") or fqn == pkg for pkg in self.context_packages)

    def _resolve_to_public_component(self, fqn: str) -> str | None:
        """
        將任何 FQN（包括私有成員或方法）解析回其所屬的、最近的公開高階組件。
        """
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

    @m.visit(m.Call())
    def _handle_call_node(self, node: cst.Call) -> None:
        """在訪問 cst.Call 節點時被觸發。"""
        try:
            enclosing_fqn = self._get_enclosing_function_fqn(node)
            if not enclosing_fqn:
                return

            caller_component = self._resolve_to_public_component(enclosing_fqn)
            if not caller_component:
                return

            callee_fqns = self.get_metadata(FullyQualifiedNameProvider, node.func)
            if not callee_fqns:
                return

            for fqn_obj in callee_fqns:
                original_callee_fqn = fqn_obj.name
                if not self._is_internal_fqn(original_callee_fqn):
                    continue

                normalized_callee_fqn = _normalize_call_fqn(original_callee_fqn, self.alias_map)
                callee_component = self._resolve_to_public_component(normalized_callee_fqn)
                if not callee_component:
                    continue

                if caller_component and callee_component:
                    self.found_edges.add((caller_component, callee_component))

        except Exception as e:
            logging.debug(f"解析呼叫時出錯: {e}")

    def _get_enclosing_function_fqn(self, node: cst.CSTNode) -> str | None:
        """使用 ParentNodeProvider 向上追溯，找到包裹節點的函式 FQN。"""
        current = node
        while current:
            if isinstance(current, (cst.FunctionDef, cst.ClassDef)):
                try:
                    fqns = self.get_metadata(FullyQualifiedNameProvider, current)
                    if fqns:
                        return next(iter(fqns)).name
                except Exception:
                    return f"{self.module_path}.<resolution.error>"
            try:
                current = self.get_metadata(ParentNodeProvider, current)
            except KeyError:
                break
        return self.module_path


def full_libcst_analysis(
    repo_manager: FullRepoManager,
    context_packages: list[str],
    pre_scan_results: dict[str, Any],
    initial_definition_map: dict[str, str],
    alias_exclude_patterns: list[str],
) -> dict[str, Any]:
    """
    執行 LibCST 分析以建構呼叫圖。
    此函式現在接收一個已初始化的 FullRepoManager。
    """
    all_components: set[str] = set()
    full_docstring_map: dict[str, str] = {}
    call_graph: set[tuple[str, str]] = set()

    for scan_data in pre_scan_results.values():
        visitor: CodeVisitor = scan_data["visitor"]
        all_components.update(visitor.components)
        full_docstring_map.update(visitor.docstring_map)
        try:
            tree = ast.parse(scan_data["content"], filename=str(visitor.file_path))
            module_docstring = ast.get_docstring(tree)
            if module_docstring:
                full_docstring_map[visitor.module_path] = module_docstring
        except Exception as e:
            logging.debug(f"無法為 {visitor.file_path} 解析模組級 docstring: {e}")

    logging.info("--- [階段 1/2] 開始掃描全域別名 (使用 LibCST) ---")
    alias_map: dict[str, str] = {}
    for file_path_str in pre_scan_results:
        try:
            wrapper = repo_manager.get_metadata_wrapper_for_path(file_path_str)
            alias_visitor = _AliasVisitor(wrapper, context_packages, alias_exclude_patterns)
            wrapper.visit(alias_visitor)
            alias_map.update(alias_visitor.alias_map)
        except Exception as e:
            logging.warning(f"掃描別名時無法分析檔案 '{file_path_str}': {e}")
    logging.info(f"--- 別名掃描完成，發現 {len(alias_map)} 個相關的全域別名 ---")

    logging.info("--- [階段 2/2] 開始建立正規化呼叫圖 (使用 LibCST) ---")
    for file_path_str, scan_data in pre_scan_results.items():
        try:
            module_path = scan_data["visitor"].module_path
            wrapper = repo_manager.get_metadata_wrapper_for_path(file_path_str)
            call_visitor = _CallGraphVisitor(
                wrapper,
                context_packages,
                all_components,
                module_path,
                alias_map,
                file_path_str,
            )
            wrapper.visit(call_visitor)
            call_graph.update(call_visitor.found_edges)
        except cst.ParserSyntaxError as e:
            logging.error(f"無法解析檔案 (語法錯誤) '{file_path_str}': {e.message}")
        except Exception as e:
            logging.warning(f"使用 LibCST 分析檔案 '{file_path_str}' 時失敗: {e}", exc_info=True)

    logging.info(f"完整 LibCST 呼叫圖分析完成：找到 {len(all_components)} 個組件，{len(call_graph)} 條呼叫邊。")
    return {
        "call_graph": call_graph,
        "components": all_components,
        "definition_to_module_map": initial_definition_map,
        "docstring_map": full_docstring_map,
    }

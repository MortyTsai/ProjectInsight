# src/projectinsight/parsers/component_parser.py
"""
提供基於 AST 和 LibCST 的 Python 原始碼組件互動解析功能。
"""

# 1. 標準庫導入
import ast
import logging
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
# [重構] 移除 jedi，引入 libcst
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


class CodeVisitor(ast.NodeVisitor):
    """一個 AST 訪問者，用於收集程式碼中的各種定義和引用。"""

    def __init__(self, module_path: str, file_path: Path, root_package_name: str):
        self.module_path = module_path
        self.file_path = file_path
        self.root_package_name = root_package_name
        self.current_scope = [self.module_path]
        # [重構] 不再需要 self.calls，因為 libcst 將處理呼叫
        self.definitions: set[str] = set()
        self.components: set[str] = set()
        self.definition_to_module_map: dict[str, str] = {}
        self.docstring_map: dict[str, str] = {}
        self.definition_count = 0
        self.has_main_block = False
        self.internal_imports: set[str] = set()

    def visit_Import(self, node: ast.Import):
        """處理 'import a.b.c' 這種形式的導入。"""
        for alias in node.names:
            if alias.name.startswith(self.root_package_name):
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
            if import_path.startswith(self.root_package_name):
                self.internal_imports.add(import_path)
        elif node.module and node.module.startswith(self.root_package_name):
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
        scope_name = ".".join([*self.current_scope, node.name])
        self.definitions.add(scope_name)
        self.definition_to_module_map[scope_name] = self.module_path
        self.definition_count += 1

        # [修正]
        # 根據 P0.3 和 P0.9 原則，模組級函式也是高階組件。
        # 檢查 current_scope 的長度，確保這是一個模組級函式（即不在類別或函式內部）。
        if len(self.current_scope) == 1:
            self.components.add(scope_name)

        docstring = ast.get_docstring(node)
        if docstring:
            self.docstring_map[scope_name] = docstring

        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        scope_name = ".".join([*self.current_scope, node.name])
        self.definitions.add(scope_name)
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
        # [重構] quick_ast_scan 不再需要收集呼叫
        self.generic_visit(node)


def quick_ast_scan(project_path: Path, py_files: list[Path], root_package_name: str) -> dict[str, Any]:
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
            if parts[-1] == "__init__.py":
                parts.pop()
            else:
                parts[-1] = relative_path.stem
            module_name = ".".join(parts)

            visitor = CodeVisitor(module_name, file_path, root_package_name)
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


# [重構] 移除 _resolve_call 輔助函式


# [重構] 將 full_jedi_analysis 替換為 full_libcst_analysis
def full_libcst_analysis(
        project_path: Path,
        root_pkg: str,
        pre_scan_results: dict[str, Any],
        initial_definition_map: dict[str, str],
) -> dict[str, Any]:
    """
    執行完整的 LibCST 分析，以建構確定性的呼叫圖。
    """
    call_graph: set[tuple[str, str]] = set()
    all_components: set[str] = set()
    full_definition_map = initial_definition_map.copy()
    full_docstring_map: dict[str, str] = {}

    # [修正]
    # 建立一個集合來儲存 *所有* 的定義，而不僅僅是組件
    all_definitions_set: set[str] = set()

    # --- [步驟 1] 複用 quick_ast_scan 的成果 ---
    for scan_data in pre_scan_results.values():
        visitor: CodeVisitor = scan_data["visitor"]
        all_components.update(visitor.components)
        full_docstring_map.update(visitor.docstring_map)

        # [修正] 聚合所有定義
        all_definitions_set.update(visitor.definitions)

        try:
            tree = ast.parse(scan_data["content"], filename=str(visitor.file_path))
            module_docstring = ast.get_docstring(tree)
            if module_docstring:
                full_docstring_map[visitor.module_path] = module_docstring
        except Exception as e:
            logging.debug(f"無法為 {visitor.file_path} 解析模組級 docstring: {e}")

    # --- [步驟 2] 定義 LibCST 呼叫圖訪問者 ---
    class _CallGraphVisitor(m.MatcherDecoratableVisitor):
        """
        一個 LibCST 訪問者，用於解析並建立呼叫圖。
        """

        METADATA_DEPENDENCIES = (
            ScopeProvider,
            FullyQualifiedNameProvider,
            ParentNodeProvider,
        )

        def __init__(
                self,
                wrapper: MetadataWrapper,
                root_pkg: str,
                all_components: set[str],
                module_path: str,
                # [修正] 接收 all_definitions_set
                all_definitions: set[str],
        ):
            super().__init__()
            self.wrapper = wrapper
            self.root_pkg = root_pkg
            self.all_components = all_components
            self.module_path = module_path
            # [修正] 儲存 all_definitions_set
            self.all_definitions = all_definitions
            self.found_edges: set[tuple[str, str]] = set()

        def _get_enclosing_function_fqn(self, node: cst.CSTNode) -> str:
            """使用 ParentNodeProvider 向上追溯，找到包裹節點的函式 FQN。"""
            current = node
            while current:
                if isinstance(current, (cst.FunctionDef, cst.ClassDef)):
                    try:
                        fqns = self.get_metadata(FullyQualifiedNameProvider, current)
                        if fqns:
                            # 返回第一個找到的 FQN
                            return next(iter(fqns)).name
                    except Exception:
                        # 解析失敗，返回一個已知錯誤
                        return f"{self.module_path}.<resolution.error>"
                try:
                    current = self.get_metadata(ParentNodeProvider, current)
                except KeyError:
                    # 到達樹根
                    break
            # 如果不在任何函式/類別內，則歸屬於模組
            return self.module_path

        # [修正]
        # 將 @m.visit 裝飾器應用於一個 *自訂* 方法
        # 而不是內建的 visit_Call 方法
        @m.visit(m.Call())
        def _handle_call_node(self, node: cst.Call) -> None:
            """
            在訪問 cst.Call 節點時被觸發。
            """
            try:
                # A. 找到呼叫者 (Caller)
                caller_fqn = self._get_enclosing_function_fqn(node)

                # B. 找到被呼叫者 (Callee)
                #    FullyQualifiedNameProvider 會回傳一個集合，以處理多態性
                callee_fqns = self.get_metadata(FullyQualifiedNameProvider, node.func)

                if not callee_fqns:
                    # 無法解析（例如動態呼叫 getattr() 或 lambda）
                    return

                for fqn_obj in callee_fqns:
                    callee_fqn = fqn_obj.name

                    # C. 過濾非本專案的呼叫
                    if not callee_fqn.startswith(self.root_pkg):
                        continue

                    # D. [關鍵] 處理類別實例化
                    # 如果 FQN 指向一個類別（在我們的 all_components 集合中）...
                    # ... 並且 該類別的 __init__ 方法 *確實存在* 於我們的定義中...
                    if callee_fqn in self.all_components and f"{callee_fqn}.__init__" in self.all_definitions:
                        # ...那麼我們將呼叫重新導向到 __init__
                        callee_fqn = f"{callee_fqn}.__init__"

                    # E. 建立邊
                    if caller_fqn != callee_fqn:
                        self.found_edges.add((caller_fqn, callee_fqn))

            except Exception as e:
                logging.debug(f"解析呼叫時出錯: {e}")

    # --- [步驟 3] 初始化 LibCST 管理器並執行分析 ---
    repo_root = str(project_path.resolve())
    file_paths_str = list(pre_scan_results.keys())
    providers = {FullyQualifiedNameProvider, ScopeProvider, ParentNodeProvider}

    try:
        logging.info("初始化 LibCST FullRepoManager 並解析快取...")
        repo_manager = FullRepoManager(repo_root, file_paths_str, providers)
        repo_manager.resolve_cache()
        logging.info("LibCST 快取解析完成。")

        for file_path_str, scan_data in pre_scan_results.items():
            try:
                module_path = scan_data["visitor"].module_path
                wrapper = repo_manager.get_metadata_wrapper_for_path(file_path_str)
                # [修正] 傳遞 all_definitions_set
                visitor = _CallGraphVisitor(
                    wrapper, root_pkg, all_components, module_path, all_definitions_set
                )
                wrapper.visit(visitor)
                call_graph.update(visitor.found_edges)
            except cst.ParserSyntaxError as e:
                logging.error(f"無法解析檔案 (語法錯誤) '{file_path_str}': {e.message}")
            except Exception as e:
                logging.warning(f"使用 LibCST 分析檔案 '{file_path_str}' 時失敗: {e}", exc_info=True)

    except Exception as e:
        logging.error(f"初始化 LibCST FullRepoManager 時發生嚴重錯誤: {e}", exc_info=True)
        logging.error("呼叫圖分析已中止。")

    logging.info(f"完整 LibCST 分析完成：找到 {len(all_components)} 個組件(類別與函式)，{len(call_graph)} 條函式呼叫。")
    return {
        "call_graph": call_graph,
        "components": all_components,
        "definition_to_module_map": full_definition_map,
        "docstring_map": full_docstring_map,
    }
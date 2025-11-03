# src/projectinsight/parsers/component_parser.py
"""
提供基於 AST 和 Jedi 的 Python 原始碼組件互動解析功能。
"""

# 1. 標準庫導入
import ast
import logging
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import jedi

# 3. 本專案導入
# (無)


class CodeVisitor(ast.NodeVisitor):
    """一個 AST 訪問者，用於收集程式碼中的各種定義和引用。"""

    def __init__(self, module_path: str, file_path: Path, root_package_name: str):
        self.module_path = module_path
        self.file_path = file_path
        self.root_package_name = root_package_name
        self.current_scope = [self.module_path]
        self.calls: list[tuple[str, ast.Call]] = []
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
        caller_path = ".".join(self.current_scope)
        self.calls.append((caller_path, node))
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


def _resolve_call(call_node: ast.Call, script: jedi.Script, root_pkg: str) -> set[Any]:
    """使用 Jedi 解析一個 AST Call 節點，找出其定義。"""
    resolved_items: set[Any] = set()
    try:
        func_node = call_node.func
        line, column = func_node.lineno, func_node.col_offset
        if isinstance(func_node, ast.Attribute) and hasattr(func_node, "end_col_offset"):
            column = func_node.end_col_offset - len(func_node.attr)
        definitions = script.infer(line=line, column=column)
        for d in definitions:
            if d.full_name and d.full_name.startswith(root_pkg):
                resolved_items.add(d)
    except Exception:
        pass
    return resolved_items


def full_jedi_analysis(project_path: Path, root_pkg: str, pre_scan_results: dict[str, Any]) -> dict[str, Any]:
    """
    執行完整的 Jedi 分析，以建構呼叫圖。
    此函式現在依賴於 quick_ast_scan 的結果。
    """
    jedi_project = jedi.Project(path=str(project_path.parent))
    call_graph: set[tuple[str, str]] = set()
    all_components: set[str] = set()
    full_definition_map: dict[str, str] = {}
    full_docstring_map: dict[str, str] = {}

    for file_path_str, scan_data in pre_scan_results.items():
        file_path = Path(file_path_str)
        try:
            visitor = scan_data["visitor"]
            content = scan_data["content"]
            all_components.update(visitor.components)
            full_definition_map.update(visitor.definition_to_module_map)
            full_docstring_map.update(visitor.docstring_map)
            tree = ast.parse(content, filename=str(file_path))
            module_docstring = ast.get_docstring(tree)
            if module_docstring:
                full_docstring_map[visitor.module_path] = module_docstring
            script = jedi.Script(code=content, path=str(file_path), project=jedi_project)
            for caller_path, call_node in visitor.calls:
                definitions = _resolve_call(call_node, script, root_pkg)
                for d in definitions:
                    if d.type in ("function", "class"):
                        callee_path = f"{d.full_name}.__init__" if d.type == "class" else d.full_name
                        if callee_path and caller_path != callee_path and caller_path in visitor.definitions:
                            call_graph.add((caller_path, callee_path))
        except Exception as e:
            logging.warning(f"無法分析檔案 {file_path}: {e}")

    logging.info(f"完整 Jedi 分析完成：找到 {len(all_components)} 個組件(類別)，{len(call_graph)} 條函式呼叫。")
    return {
        "call_graph": call_graph,
        "components": all_components,
        "definition_to_module_map": full_definition_map,
        "docstring_map": full_docstring_map,
    }

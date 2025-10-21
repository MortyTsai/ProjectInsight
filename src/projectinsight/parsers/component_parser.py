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

    def __init__(self, module_path: str):
        self.module_path = module_path
        self.current_scope = [self.module_path]
        self.calls: list[tuple[str, ast.Call]] = []
        self.definitions: set[str] = set()
        self.imports: list[ast.AST] = []
        self.components: set[str] = set()  # 新增：用於儲存識別出的組件（類別）

    def visit_Import(self, node: ast.Import):
        self.imports.append(node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module != "__future__":
            self.imports.append(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        scope_name = ".".join([*self.current_scope, node.name])
        self.definitions.add(scope_name)
        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        scope_name = ".".join([*self.current_scope, node.name])
        self.definitions.add(scope_name)
        self.components.add(scope_name)  # 新增：將類別定義視為一個組件
        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_Call(self, node: ast.Call):
        caller_path = ".".join(self.current_scope)
        self.calls.append((caller_path, node))
        self.generic_visit(node)


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


def _resolve_import(import_node: ast.AST, script: jedi.Script, root_pkg: str) -> set[Any]:
    """使用 Jedi 解析一個 AST Import 節點，找出其定義。"""
    resolved_items: set[Any] = set()
    try:
        if isinstance(import_node, (ast.Import, ast.ImportFrom)):
            for alias in import_node.names:
                definitions = script.infer(line=alias.lineno, column=alias.col_offset)
                for d in definitions:
                    if d.full_name and d.full_name.startswith(root_pkg):
                        resolved_items.add(d)
    except Exception:
        pass
    return resolved_items


def analyze_code(project_path: Path, root_pkg: str, py_files: list[Path]) -> dict[str, Any]:
    """分析整個專案，提取模組依賴、函式呼叫和模組細節。"""
    jedi_project = jedi.Project(path=str(project_path.parent))
    call_graph: set[tuple[str, str]] = set()
    all_components: set[str] = set()
    all_module_details: dict[str, dict] = {}

    for file_path in py_files:
        if file_path.name == "__init__.py":
            continue
        try:
            module_name = ".".join(file_path.relative_to(project_path.parent).with_suffix("").parts)
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            visitor = CodeVisitor(module_name)
            visitor.visit(tree)
            all_components.update(visitor.components)

            classes = set()
            functions = set()
            for def_path in visitor.definitions:
                parts = def_path.split(".")
                if len(parts) > 1:
                    is_method = len(parts) > 2 and parts[-2][0].isupper()
                    is_private = parts[-1].startswith("_")

                    if not is_method and not is_private:
                        if parts[-1][0].isupper():
                            classes.add(parts[-1])
                        else:
                            functions.add(parts[-1])

            all_module_details[module_name] = {"classes": sorted(classes), "functions": sorted(functions)}

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

    logging.info(f"程式碼分析完成：找到 {len(all_components)} 個組件(類別)，{len(call_graph)} 條函式呼叫。")
    return {"call_graph": call_graph, "components": all_components, "module_details": all_module_details}

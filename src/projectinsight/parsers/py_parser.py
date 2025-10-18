# src/projectinsight/parsers/py_parser.py
"""
提供基於 AST 的 Python 原始碼依賴解析功能。
"""
# 1. 標準庫導入
import ast
import logging
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


def analyze_dependencies(file_path: Path) -> dict[str, list[Any]]:
    """
    解析單一 Python 檔案，找出其導入語句、公開類別和公開函式。
    """
    logging.debug(f"正在解析依賴: {file_path}")
    imports: list[dict[str, Any]] = []
    classes: list[str] = []
    functions: list[str] = []

    try:
        with open(file_path, encoding="utf-8") as source:
            content = source.read()
            tree = ast.parse(content, filename=file_path.name)
    except Exception as e:
        logging.warning(f"讀取或解析檔案 {file_path} 時發生錯誤: {e}")
        return {"imports": [], "classes": [], "functions": []}

    # 動態地為 AST 節點添加父節點引用
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"type": "direct", "module": alias.name})
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            symbols = [alias.name for alias in node.names]
            imports.append({
                "type": "from", "module": node.module or "",
                "level": node.level, "symbols": symbols
            })
        elif isinstance(node, ast.ClassDef) and not node.name.startswith('_') and \
             hasattr(node, 'parent') and isinstance(node.parent, ast.Module):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith('_') and \
             hasattr(node, 'parent') and isinstance(node.parent, ast.Module):
            functions.append(node.name)

    return {
        "imports": imports,
        "classes": sorted(classes),
        "functions": sorted(functions),
    }

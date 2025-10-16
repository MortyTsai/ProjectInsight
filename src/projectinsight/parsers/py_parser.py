# src/projectinsight/parsers/py_parser.py
"""
提供基於 AST (抽象語法樹) 的 Python 原始碼解析功能。

此模組負責將 .py 檔案轉換為結構化的節點與依賴關係。
"""

# 1. 標準庫導入
import ast
import logging
from pathlib import Path


def analyze_dependencies(file_path: Path) -> list[str]:
    """
    解析單一 Python 檔案，找出其 import 的模組。

    Args:
        file_path: 要分析的 Python 檔案路徑。

    Returns:
        一個包含所有導入模組名稱的字串列表。
    """
    logging.debug(f"正在解析檔案: {file_path}")
    dependencies = set()
    try:
        with open(file_path, encoding="utf-8") as source:
            tree = ast.parse(source.read(), filename=file_path.name)
    except SyntaxError as e:
        logging.warning(f"無法解析檔案 {file_path}，存在語法錯誤: {e}")
        return []
    except Exception as e:
        logging.error(f"讀取或解析檔案 {file_path} 時發生未預期錯誤: {e}")
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                dependencies.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.level > 0:
                relative_prefix = "." * node.level
                dependencies.add(f"{relative_prefix}{node.module}")
            else:
                dependencies.add(node.module)

    return sorted(dependencies)

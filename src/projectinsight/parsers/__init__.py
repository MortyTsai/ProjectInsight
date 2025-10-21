# src/projectinsight/parsers/__init__.py
"""
解析器套件，提供將原始碼轉換為結構化資料的功能。
"""

from . import component_parser

__all__ = [
    "component_parser",
]

# src/projectinsight/reporters/__init__.py
"""
報告生成器套件，負責將分析結果匯總為對 LLM 友善的報告。
"""

from .markdown_reporter import generate_markdown_report

__all__ = ["generate_markdown_report"]

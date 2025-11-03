# src/projectinsight/core/__init__.py
"""
ProjectInsight 的核心協調器套件。

此套件負責將解析、建構、渲染和報告等子系統串連起來，
執行完整的專案分析流程。
"""

from .config_loader import ConfigLoader
from .interactive_wizard import InteractiveWizard
from .project_processor import ProjectProcessor

__all__ = [
    "ConfigLoader",
    "InteractiveWizard",
    "ProjectProcessor",
]

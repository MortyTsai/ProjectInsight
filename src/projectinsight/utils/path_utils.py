# src/projectinsight/utils/path_utils.py
"""
提供與專案路徑解析相關的通用工具函式。
"""

# 1. 標準庫導入
import importlib.resources
from pathlib import Path

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


def find_project_root(marker: str = "pyproject.toml") -> Path:
    """
    使用 importlib.resources 定位套件位置，然後向上遍歷尋找標記檔案。
    這是解決 `python -m` 執行模式下路徑問題的最健壯方法。
    """
    try:
        anchor = importlib.resources.files("projectinsight")
    except ModuleNotFoundError:
        anchor = Path(__file__).resolve().parent

    current_path = Path(str(anchor))
    while current_path != current_path.parent:
        if (current_path / marker).exists():
            return current_path
        current_path = current_path.parent

    current_path = Path.cwd()
    while current_path != current_path.parent:
        if (current_path / marker).exists():
            return current_path
        current_path = current_path.parent

    raise FileNotFoundError(f"無法從 '{anchor}' 或當前工作目錄向上找到專案根目錄標記檔案: {marker}")

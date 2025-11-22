# src/projectinsight/utils/path_utils.py
"""
提供與專案路徑解析相關的通用工具函式。
增強頂層套件偵測：現在支援識別根目錄下的單獨 .py 模組。
"""

# 1. 標準庫導入
import importlib.resources
import logging
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


def find_top_level_packages(source_root: Path) -> list[str]:
    """
    掃描給定的原始碼根目錄，自動偵測所有頂層的 Python 套件或包含 Python 程式碼的目錄。
    修正：現在會包含根目錄下的獨立 .py 檔案 (模組)。

    Args:
        source_root: 要掃描的 Python 原始碼根目錄。

    Returns:
        一個包含所有頂層上下文根名稱的字串列表。
    """
    if not source_root.is_dir():
        logging.warning(f"提供的原始碼路徑不是一個有效目錄: {source_root}")
        return []

    top_level_items = []
    try:
        for item in source_root.iterdir():
            if item.is_dir():
                if next(item.rglob("*.py"), None):
                    top_level_items.append(item.name)

            elif (
                item.is_file() and item.suffix == ".py" and item.name not in ("__init__.py", "setup.py", "conftest.py")
            ):
                top_level_items.append(item.stem)

    except OSError as e:
        logging.error(f"掃描頂層套件時發生檔案系統錯誤: {e}")
        return []

    return sorted(top_level_items)

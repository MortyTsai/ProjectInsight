# src/projectinsight/utils/file_system_utils.py
"""
提供與檔案系統操作相關的公用函式。
"""

# 1. 標準庫導入
import fnmatch
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)

DEFAULT_EXCLUDED_DIRS: set[str] = {
    "__pycache__",
    ".git",
    ".vscode",
    ".idea",
    "venv",
    ".venv",
    "dist",
    "build",
    "output",
    ".ruff_cache",
    "*.egg-info",
}


def generate_tree_structure(
    start_path: Path,
    tree_settings: dict[str, Any],
) -> list[str]:
    """
    生成專案目錄的文字表示結構樹，支援多種過濾規則。

    Args:
        start_path: 要生成目錄樹的起始路徑。
        tree_settings: 包含過濾規則的字典，例如：
                       {
                           "exclude_dirs": ["tests", ...],
                           "exclude_extensions": [".mo", ".po"],
                           "exclude_files": ["README.md", "*.txt"]
                       }

    Returns:
        一個包含目錄樹結構字串的列表。
    """
    exclude_dirs = set(tree_settings.get("exclude_dirs", DEFAULT_EXCLUDED_DIRS))
    exclude_extensions = set(tree_settings.get("exclude_extensions", []))
    exclude_files = set(tree_settings.get("exclude_files", []))

    tree_lines = [f"{start_path.name}/"]

    def recurse(directory: Path, prefix: str = ""):
        """遞迴地建構目錄樹的內部輔助函式."""

        def is_excluded(path: Path) -> bool:
            """檢查路徑是否符合任何排除模式。"""
            if path.is_dir():
                return any(fnmatch.fnmatch(path.name, pattern) for pattern in exclude_dirs)

            if path.suffix in exclude_extensions:
                return True

            return any(fnmatch.fnmatch(path.name, pattern) for pattern in exclude_files)

        try:
            items = sorted(
                [p for p in directory.iterdir() if not is_excluded(p)],
                key=lambda p: (p.is_file(), p.name.lower()),
            )
        except OSError:
            return

        pointers = ["├── "] * (len(items) - 1) + ["└── "]
        for pointer, path in zip(pointers, items, strict=False):
            tree_lines.append(f"{prefix}{pointer}{path.name}")
            if path.is_dir():
                extension = "│   " if pointer == "├── " else "    "
                recurse(path, prefix + extension)

    recurse(start_path)
    return tree_lines

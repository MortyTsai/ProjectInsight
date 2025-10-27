# src/projectinsight/utils/file_system_utils.py
"""
提供與檔案系統操作相關的公用函式。
"""

# 1. 標準庫導入
import fnmatch
from pathlib import Path

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
    exclude_dirs: set[str] | None = None,
) -> list[str]:
    """
    生成專案目錄的文字表示結構樹。

    Args:
        start_path: 要生成目錄樹的起始路徑。
        exclude_dirs: 要忽略的目錄名稱集合 (支援 '*' 萬用字元)。
                      如果為 None，則使用預設值。

    Returns:
        一個包含目錄樹結構字串的列表。
    """
    if exclude_dirs is None:
        exclude_dirs = DEFAULT_EXCLUDED_DIRS

    tree_lines = [f"{start_path.name}/"]

    def recurse(directory: Path, prefix: str = ""):
        """遞迴地建構目錄樹的內部輔助函式."""

        def is_excluded(path_name: str) -> bool:
            """檢查路徑名稱是否符合任何排除模式。"""
            return any(fnmatch.fnmatch(path_name, pattern) for pattern in exclude_dirs)

        try:
            items = sorted([p for p in directory.iterdir() if not is_excluded(p.name)], key=lambda p: p.is_file())
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

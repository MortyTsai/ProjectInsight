# src/projectinsight/utils/parser_utils.py
"""
解析器共用的工具函式與常數定義。
用於解決 component_parser 與 semantic_link_analyzer 之間的循環依賴問題。
"""

# --- 全域雜訊過濾設定 ---

# 1. 適用於所有連結 (Calls, Decorators, etc.) 的通用黑名單
GLOBAL_IGNORE_PREFIXES = (
    # Python 內建
    "builtins.",
    # 標準庫 - 核心與工具
    "typing.",
    "collections.",
    "functools.",
    "itertools.",
    "operator.",
    "contextlib.",
    "enum.",
    "abc.",
    "types.",
    "copy.",
    "weakref.",
    "dataclasses.",
    "colorsys.",
    "importlib.",
    # 標準庫 - 系統與執行時
    "sys.",
    "warnings.",
    "inspect.",
    "traceback.",
    "gc.",
    "atexit.",
    # 標準庫 - 數學與科學
    "math.",
    "cmath.",
    "decimal.",
    "fractions.",
    "random.",
    "statistics.",
    "numbers.",
    # 標準庫 - 文字處理
    "string.",
    "re.",
    "difflib.",
    "textwrap.",
    "unicodedata.",
    "struct.",
    "codecs.",
    # 標準庫 - 時間與日期
    "datetime.",
    "time.",
    "calendar.",
    "zoneinfo.",
    # 標準庫 - 檔案與路徑
    "pathlib.",
    "os.path.",
    "shutil.",
    "glob.",
    "fnmatch.",
    "os.",
    # 標準庫 - 日誌與除錯
    "logging.",
    "pprint.",
    "pdb.",
    # 常見相容性庫
    "six.",
    "typing_extensions.",
    "attr.",
    "attrs.",
    # 特定框架的 DSL 雜訊 (移除結尾點以匹配模組本身)
    "libcst.matchers",
)

# 2. 專用於裝飾器的額外黑名單
DECORATOR_IGNORE_PREFIXES = (
    "click.",
    "pytest.",
    "builtins.staticmethod",
    "builtins.classmethod",
    "builtins.property",
    "property",
)


def is_noise(fqn: str, extra_prefixes: tuple[str, ...] = ()) -> bool:
    """檢查 FQN 是否屬於雜訊。"""
    if not fqn:
        return True

    if fqn.startswith(GLOBAL_IGNORE_PREFIXES):
        return True

    return bool(extra_prefixes and fqn.startswith(extra_prefixes))

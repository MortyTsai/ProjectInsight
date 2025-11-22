# src/projectinsight/core/cache_manager.py
"""
負責管理增量分析的快取機制。
"""

# 1. 標準庫導入
import contextlib
import hashlib
import logging
import os
import pickle
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)

# 快取版本號：當解析邏輯發生重大變更時，應升級此版本號以強制快取失效。
CACHE_VERSION = "1.1.3"
CACHE_FILENAME = "analysis_cache.pkl"


class CacheManager:
    """
    管理專案分析快取的類別。
    """

    def __init__(self, project_root: Path, cache_dir: Path, config_fingerprint: str):
        """
        初始化 CacheManager。

        Args:
            project_root: 專案根目錄。
            cache_dir: 快取存放目錄。
            config_fingerprint: 當前設定檔的雜湊指紋。
        """
        self.project_root_str = str(project_root.resolve())
        self.project_root = project_root.resolve()

        self.cache_dir = cache_dir
        self.config_fingerprint = config_fingerprint
        self.cache_file_path = cache_dir / CACHE_FILENAME
        self.cache_data: dict[str, Any] = {}
        self.dirty = False

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load(self):
        """
        從磁碟載入快取。
        """
        if not self.cache_file_path.exists():
            logging.debug("未發現現有快取，將執行全量分析。")
            self.cache_data = {}
            return

        try:
            with open(self.cache_file_path, "rb") as f:
                loaded_data = pickle.load(f)

            meta = loaded_data.get("_meta", {})
            if meta.get("version") != CACHE_VERSION:
                logging.info(f"快取版本不匹配 (舊: {meta.get('version')}, 新: {CACHE_VERSION})，快取已失效。")
                self.cache_data = {}
                return

            if meta.get("config_fingerprint") != self.config_fingerprint:
                logging.info("設定檔已變更，快取已失效。")
                self.cache_data = {}
                return

            self.cache_data = loaded_data.get("entries", {})
            logging.info(f"成功載入快取，包含 {len(self.cache_data)} 個檔案記錄。")

        except (pickle.UnpicklingError, EOFError, AttributeError, ImportError) as e:
            logging.warning(f"快取檔案損毀或無法讀取，將重置快取: {e}")
            self.cache_data = {}
        except Exception as e:
            logging.error(f"載入快取時發生未預期的錯誤: {e}")
            self.cache_data = {}

    def _get_relative_key(self, file_path: Path) -> str | None:
        """
        使用 os.path.relpath 計算相對路徑鍵，並轉為 POSIX 格式。
        這能解決 Windows 上 pathlib.relative_to 的大小寫敏感問題。
        """
        try:
            resolved_path_str = str(file_path.resolve())
            rel_path = os.path.relpath(resolved_path_str, self.project_root_str)

            if rel_path.startswith(".."):
                return None

            return Path(rel_path).as_posix()
        except ValueError:
            return None

    def get(self, file_path: Path) -> Any | None:
        """
        獲取指定檔案的快取資料。
        """
        relative_path = self._get_relative_key(file_path)
        if not relative_path:
            return None

        entry = self.cache_data.get(relative_path)
        if not entry:
            return None

        current_hash = self._compute_file_hash(file_path.resolve())
        if entry.get("hash") != current_hash:
            return None

        return entry.get("data")

    def update(self, file_path: Path, data: Any):
        """
        更新指定檔案的快取資料。
        """
        relative_path = self._get_relative_key(file_path)
        if not relative_path:
            return

        file_hash = self._compute_file_hash(file_path.resolve())
        self.cache_data[relative_path] = {
            "hash": file_hash,
            "data": data,
        }
        self.dirty = True

    def prune(self, current_files: list[Path]):
        """
        清理已不存在於當前檔案列表中的快取條目。
        """
        current_keys = set()
        for p in current_files:
            key = self._get_relative_key(p)
            if key:
                current_keys.add(key)

        keys_to_remove = [k for k in self.cache_data if k not in current_keys]
        if keys_to_remove:
            for k in keys_to_remove:
                del self.cache_data[k]
            self.dirty = True
            logging.debug(f"已清理 {len(keys_to_remove)} 個過期的快取條目。")

    def save(self):
        """
        將快取寫入磁碟。
        """
        if not self.dirty:
            logging.debug("快取未變更，跳過寫入。")
            return

        payload = {
            "_meta": {
                "version": CACHE_VERSION,
                "config_fingerprint": self.config_fingerprint,
            },
            "entries": self.cache_data,
        }

        temp_path = self.cache_file_path.with_suffix(".tmp")
        try:
            with open(temp_path, "wb") as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

            os.replace(temp_path, self.cache_file_path)
            logging.info(f"快取已更新並儲存至: {self.cache_file_path}")
            self.dirty = False
        except Exception as e:
            logging.error(f"儲存快取時發生錯誤: {e}")
            if temp_path.exists():
                with contextlib.suppress(OSError):
                    os.remove(temp_path)

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        """計算檔案內容的 MD5 雜湊值。"""
        hasher = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError:
            return ""

# src/projectinsight/core/parallel_manager.py
"""
平行化任務管理器。

核心職責：
1. 封裝 ProcessPoolExecutor，提供跨平台 (Windows/Linux) 的多程序支援。
2. 實作 Map-Reduce 模式，負責任務分發與結果聚合。
3. 管理工作程序 (Worker) 的生命週期與錯誤隔離。
"""

# 1. 標準庫導入
import concurrent.futures
import logging
import multiprocessing
import os
from collections.abc import Callable
from typing import Any, TypeVar

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)

T = TypeVar("T")  # 輸入項目類型
R = TypeVar("R")  # 回傳結果類型


class ParallelManager:
    """
    管理平行化解析任務的核心類別。
    """

    def __init__(self, max_workers: int | None = None):
        """
        初始化 ParallelManager。

        Args:
            max_workers: 最大工作程序數。若為 None，則預設為 CPU 核心數。
        """
        self.max_workers = max_workers or os.cpu_count() or 1
        self.mp_context = multiprocessing.get_context("spawn")

    def execute_map_reduce(
        self,
        task_func: Callable[..., R],
        items: list[T],
        global_context: dict[str, Any],
        chunksize: int = 1,
    ) -> list[R]:
        """
        執行 Map-Reduce 模式的平行任務。

        Args:
            task_func: 要在工作程序中執行的純函式 (必須是可序列化的頂層函式)。
                       簽名應為: task_func(item: T, context: dict) -> R
            items: 要處理的項目列表 (通常是檔案路徑列表)。
            global_context: 注入到每個任務的唯讀上下文 (如專案根目錄、設定等)。
            chunksize: 每個工作程序一次領取的任務數量。

        Returns:
            一個包含所有任務結果的列表。
        """
        results: list[R] = []
        total_items = len(items)

        if total_items == 0:
            return results

        logging.info(f"啟動平行處理: {total_items} 個項目, {self.max_workers} 個工作程序 (Chunksize: {chunksize})")

        task_args = ((item, global_context) for item in items)

        try:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers,
                mp_context=self.mp_context,
            ) as executor:
                futures = executor.map(task_func, task_args, chunksize=chunksize)

                for i, result in enumerate(futures):
                    results.append(result)
                    if (i + 1) % 10 == 0 or (i + 1) == total_items:
                        logging.debug(f"平行進度: {i + 1}/{total_items} 完成")

        except Exception as e:
            logging.error(f"平行任務執行期間發生嚴重錯誤: {e}", exc_info=True)
            return results

        return results

# src/projectinsight/utils/logging_utils.py
"""
提供與日誌記錄相關的通用工具和過濾器。
"""

# 1. 標準庫導入
import logging

# 2. 第三方庫導入
# (無)

# 3. 本專案導入
# (無)


class PickleFilter(logging.Filter):
    """
    一個自訂的日誌過濾器，用於攔截包含 'pickle loaded' 的訊息。
    """
    def filter(self, record: logging.LogRecord) -> bool:
        """
        如果日誌訊息不包含 'pickle loaded'，則回傳 True。
        """
        return "pickle loaded" not in record.getMessage()
# src/projectinsight/__main__.py
"""
ProjectInsight 主執行入口。
"""

# 1. 標準庫導入
import logging

# 2. 第三方庫導入
import yaml

# 3. 本專案導入
from projectinsight.core.project_processor import ProjectProcessor
from projectinsight.utils.logging_utils import PickleFilter
from projectinsight.utils.path_utils import find_project_root


def main():
    """主函式，讀取工作區設定，並為每個指定的專案執行處理流程。"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        console_handler.addFilter(PickleFilter())
        root_logger.addHandler(console_handler)

    try:
        project_root = find_project_root()
    except FileNotFoundError as e:
        logging.error(f"初始化失敗: {e}")
        return

    configs_dir = project_root / "configs"
    workspace_path = configs_dir / "workspace.yaml"
    projects_dir = configs_dir / "projects"

    if not workspace_path.is_file():
        logging.error(f"工作區設定檔 '{workspace_path}' 不存在。")
        logging.info("請從 'workspace.template.yaml' 複製一份並進行設定。")
        return

    try:
        with open(workspace_path, encoding="utf-8") as f:
            workspace_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logging.error(f"解析工作區設定檔時發生錯誤: {e}")
        return

    active_projects = workspace_config.get("active_projects", [])
    if not active_projects:
        logging.warning("工作區設定檔中沒有指定任何 'active_projects'。")
        return

    logging.info(f"ProjectInsight 工具啟動，在工作區中找到 {len(active_projects)} 個活躍專案。")
    for project_config_name in active_projects:
        config_path = projects_dir / project_config_name
        try:
            processor = ProjectProcessor(config_path)
            processor.run()
        except Exception as e:
            logging.error(f"處理專案 '{project_config_name}' 時發生未預期的嚴重錯誤: {e}", exc_info=True)


if __name__ == "__main__":
    main()

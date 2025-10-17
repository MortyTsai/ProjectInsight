# scripts/repo_to_text.py
"""專案快照生成工具.

此腳本會自動掃描指定專案目錄，將符合條件的檔案內容合併到單一的文字檔案中，
並在檔案頂部生成專案的目錄結構樹。

主要用於快速打包專案上下文，以提供給大型語言模型 (LLM) 進行分析。
"""

# 1. 標準庫導入
import datetime
from pathlib import Path

# ==============================================================================
# ---                           組態設定                            ---
# ==============================================================================

# 要掃描的專案根目錄路徑 ("auto" 表示自動偵測)
START_PATH: str = "auto"
# 最終輸出的檔案名稱
OUTPUT_FILENAME: str = "ProjectInsight_snapshot.txt"
# 要包含的檔案類型
INCLUDED_EXTENSIONS: set[str] = {
    ".py", ".md", ".yaml", ".toml", ".gitignore"
}
# 要完全忽略的目錄名稱
EXCLUDED_DIRS: set[str] = {
    "__pycache__", ".git", ".vscode", ".idea", "venv", ".venv",
    "dist", "build", "output", ".ruff_cache", "projectinsight.egg-info"
}
# 要完全忽略的特定檔案名稱
EXCLUDED_FILES: set[str] = set()
# 忽略大於此大小的檔案 (KB, 0 表示不限制)
MAX_FILE_SIZE_KB: int = 0
# 檔案標頭與頁尾格式
HEADER_FORMAT: str = "--- START OF FILE {path} ---\n"
FOOTER_FORMAT: str = "\n--- END OF FILE {path} ---\n" + "=" * 80 + "\n\n"

# ==============================================================================
# ---                          腳本主要邏輯                          ---
# ==============================================================================


def get_project_root() -> Path:
    """自動偵測專案根目錄."""
    script_path = Path(__file__).resolve().parent
    if script_path.name.lower() in ["scripts", "script"]:
        return script_path.parent
    return script_path


def generate_tree_structure(start_path: Path, local_excluded_files: set[str]) -> list[str]:
    """生成專案目錄的文字表示結構樹，並尊重排除規則."""
    tree_lines = [f"{start_path.name}/"]

    def recurse(directory: Path, prefix: str = ""):
        """遞迴地建構目錄樹的內部輔助函式."""
        try:
            # 過濾掉不應包含的目錄和檔案
            items = sorted([
                p for p in directory.iterdir()
                if p.name not in EXCLUDED_DIRS
                and p.name not in local_excluded_files
                and (p.is_dir() or p.suffix in INCLUDED_EXTENSIONS or p.name in INCLUDED_EXTENSIONS)
            ], key=lambda p: p.is_file())
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


def create_project_snapshot():
    """主執行函式."""
    project_root = get_project_root() if START_PATH.lower() == "auto" else Path(START_PATH).resolve()
    output_filepath = project_root / OUTPUT_FILENAME

    print(f"專案根目錄已設定為: '{project_root}'")
    print(f"輸出檔案將儲存至: '{output_filepath}'")

    local_excluded_files = EXCLUDED_FILES.copy()
    local_excluded_files.add(OUTPUT_FILENAME)
    local_excluded_files.add(Path(__file__).name)

    files_processed_count = 0
    files_skipped_count = 0

    try:
        with open(output_filepath, "w", encoding="utf-8") as outfile:
            outfile.write(f"# 專案快照: {project_root}\n")
            outfile.write(f"# 生成時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            outfile.write("=" * 80 + "\n\n")

            print("正在生成專案結構樹...")
            tree_lines = generate_tree_structure(project_root, local_excluded_files)
            outfile.write("### Project Directory Tree ###\n\n")
            outfile.write("\n".join(tree_lines))
            outfile.write("\n\n" + "=" * 80 + "\n\n")
            print("結構樹生成完畢。")

            print("正在處理檔案內容...")
            all_files = sorted([p for p in project_root.rglob("*") if p.is_file()])

            for file_path in all_files:
                if (file_path.name in local_excluded_files or
                        any(part in EXCLUDED_DIRS for part in file_path.parts)):
                    continue

                if file_path.suffix not in INCLUDED_EXTENSIONS and file_path.name not in INCLUDED_EXTENSIONS:
                    continue

                relative_path = file_path.relative_to(project_root).as_posix()

                try:
                    if MAX_FILE_SIZE_KB > 0 and file_path.stat().st_size > MAX_FILE_SIZE_KB * 1024:
                        files_skipped_count += 1
                        continue

                    with open(file_path, encoding="utf-8", errors="ignore") as infile:
                        content = infile.read()
                        outfile.write(HEADER_FORMAT.format(path=relative_path))
                        outfile.write(content)
                        outfile.write(FOOTER_FORMAT.format(path=relative_path))
                        files_processed_count += 1
                except OSError as e:
                    print(f"警告：跳過檔案 {relative_path}，原因: {e}")
                    files_skipped_count += 1

            print("檔案內容處理完畢。")

        print(f"\n{'=' * 40}\n處理完成！")
        print(f"總共處理檔案數: {files_processed_count}")
        print(f"總共跳過檔案數: {files_skipped_count}")
        print(f"所有內容已儲存至: '{output_filepath}'\n{'=' * 40}")

    except Exception as e:
        print(f"\n發生嚴重錯誤: {e}")


if __name__ == "__main__":
    create_project_snapshot()

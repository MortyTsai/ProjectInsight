# ProjectInsight: 自動化專案視覺化工具

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue)

ProjectInsight 是一個輕量級的自動化靜態程式碼分析與視覺化工具。它能夠掃描指定的 Python 專案原始碼，解析模組間的依賴關係，並自動生成清晰、分層的架構圖。

這個工具旨在幫助開發者（無論是人類還是 LLM）快速理解一個陌生專案的宏觀結構、模組職責和核心依賴流。

## 核心特性

-   **自動化分析**: 無需任何手動標記或修改原始碼，即可全自動分析。
-   **智慧分層佈局**: 自動將模組按照「策略層」、「應用層」、「基礎設施層」從左到右進行物理佈局，直觀地反映架構設計。
-   **結構化視覺化**: 透過巢狀方框清晰地還原專案的目錄結構。
-   **角色導向著色**: 為不同架構角色的子套件（如 `core`, `services`）賦予不同顏色，並提供圖例說明。
-   **LLM 友善輸出**: 除了生成 PNG 圖檔外，還會輸出一份包含完整圖形結構和語意化註解的 `.txt` 原始檔，極便於大型語言模型進行分析和查詢。
-   **高度可配置**: 所有路徑、架構層級定義和顏色均可透過 YAML 設定檔進行客製化。

## 產出範例

以下是使用 ProjectInsight 分析 [MoshouSapient](https://github.com/MortyTsai/Moshou_Sapient) 專案生成的模組依賴圖：

*(請在 GitHub 編輯器中，將您生成的 PNG 圖片直接拖曳到此處)*

## 環境準備

### 軟體需求
-   Python 3.11 或更高版本
-   Graphviz: 一個開源的圖形視覺化軟體。

### 安裝步驟

1.  **安裝 Graphviz 主程式**
    -   前往 [Graphviz 官方下載頁面](https://graphviz.org/download/)。
    -   下載並安裝適合您作業系統的版本。
    -   **[重要]** 在安裝過程中，務必勾選 **"Add Graphviz to the system PATH"** 相關選項。
    -   安裝完成後，打開一個新的終端機視窗，執行 `dot -V`。如果能成功顯示版本資訊，則表示安裝成功。

2.  **複製本專案**
    ```bash
    git clone https://github.com/your-username/ProjectInsight.git
    cd ProjectInsight
    ```

3.  **設定 Python 虛擬環境並安裝依賴**
    ```bash
    # 建立虛擬環境
    python -m venv .venv
    # 啟用虛擬環境 (Windows)
    .\.venv\Scripts\activate
    # (macOS / Linux)
    # source .venv/bin/activate

    # 安裝 ProjectInsight 及其核心依賴
    pip install .
    ```

## 使用指南

1.  **建立設定檔**
    -   進入 `configs/` 目錄。
    -   將 `config.template.yaml` 複製一份，並重新命名（例如 `my_project.yaml`）。

2.  **修改設定檔**
    -   打開您新建的設定檔 (`my_project.yaml`)。
    -   修改 `target_src_path`，使其指向您想要分析的專案的原始碼目錄。
    -   修改 `root_package_name`，使其與您的專案根套件名一致。
    -   (可選) 根據您專案的架構，調整 `architecture_layers` 中的定義。

3.  **執行分析**
    -   在專案根目錄下，執行以下指令：
    ```bash
    python -m projectinsight.main -c configs/my_project.yaml
    ```

4.  **檢視結果**
    -   分析完成後，生成的 PNG 圖檔和 `.txt` 原始檔將會出現在您設定檔中 `output_dir` 指定的目錄下（預設為 `output/`）。

## 發展藍圖

-   [x] **詳細模組依賴圖**: 實現核心功能，包含巢狀佈局、顏色編碼和分層排列。
-   [ ] **函式/類別級別分析**: 在模組方框內，列出該模組包含的函式與類別定義 (方案 C)。
-   [ ] **邊緣樣式差異化**: 根據依賴類型（跨層、同層）賦予邊不同的樣式。
-   [ ] **支援更多圖表類型**: 如「設定檔流動圖」、「高階組件互動圖」等。
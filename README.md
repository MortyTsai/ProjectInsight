# ProjectInsight: 專為 LLM 設計的專案宏觀分析器

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

ProjectInsight 是一個專為大型語言模型 (LLM) 設計的靜態程式碼分析預處理器。它的核心使命是將一個複雜的 Python 專案原始碼，抽象為一張高層次的、無雜訊的「**高階組件互動圖**」，使 LLM 能夠在幾秒鐘內宏觀地洞察一個陌生專案的核心架構、組件職責與協作關係。

## 核心特性

-   **高階抽象分析**:
    -   **組件互動圖**: 專案的唯一核心功能。它不再關注瑣碎的函式呼叫或模組導入，而是專注於分析類別（組件）之間的實例化與使用關係，以及模組級函式如何與這些組件互動，從而揭示專案的真實架構藍圖。
-   **LLM 友善輸出**:
    -   除了生成 PNG 圖檔供人類除錯外，工具的核心產出是一份包含完整圖形結構（DOT 語言）的 `.txt` 原始檔。這份原始檔專為 LLM 設計，使其能夠輕鬆解析專案的宏觀結構並回答相關問題。
-   **智慧佈局與視覺化**:
    -   **巢狀子圖 (`dot`)**: 自動將組件（類別）節點組織在其所屬的模組框內，清晰地還原專案的結構。
    -   **力導向佈局 (`sfdp`)**: 為大型、複雜的專案提供更優的空間利用率和可讀性。
    -   **架構層級著色**: 透過在設定檔中定義，可為不同架構層級（如 `services`, `processors`, `core`）的組件賦予不同顏色，直觀反映架構意圖。
-   **工作區驅動的高度可配置性**:
    -   透過簡單的 `workspace.yaml` 即可管理和批次執行多個專案分析任務。
    -   所有路徑、佈局引擎、架構層級和顏色均可透過 YAML 進行精細配置。

## 產出範例

以下是使用 ProjectInsight 分析 [MoshouSapient](https://github.com/MortyTsai/Moshou_Sapient) 專案生成的「高階組件互動圖」。

<details>
<summary><b>點擊展開/摺疊：高階組件互動圖 (sfdp 引擎)</b></summary>

*這張圖展示了類別與模組級函式之間的「使用」關係，節點顏色代表其所屬的架構層級。*

<img width="2160" height="1462" alt="moshousapient_component_sfdp_component_interaction_sfdp" src="https://github.com/user-attachments/assets/9906c4f0-574e-4be6-a97f-daa97784c002" />

</details>


## 環境準備

### 軟體需求
-   Python 3.11 或更高版本
-   Graphviz: 一個開源的圖形視覺化軟體。

### 安裝步驟

1.  **安裝 Graphviz 主程式**
    -   前往 [Graphviz 官方下載頁面](https://graphviz.org/download/)。
    -   下載並安裝適合您作業系統的版本。
    -   **[重要]** 在安裝過程中，務必勾選 **"Add Graphviz to the system PATH"** 相關選項。
    -   安裝完成後，打開一個新的終端機視窗，執行 `dot -V` 和 `sfdp -V`。如果都能成功顯示版本資訊，則表示安裝成功。

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

    # 安裝 ProjectInsight 及其所有核心依賴 (包括 jedi)
    pip install .
    ```

## 使用指南 (工作區模式)

ProjectInsight 採用了簡單而強大的「工作區」模式。

1.  **建立您的專案設定檔**
    -   進入 `configs/templates/` 目錄，將 `project.template.yaml` 複製到 `configs/projects/` 目錄下。
    -   將複製的檔案重新命名（例如 `my_project.yaml`）。
    -   打開 `my_project.yaml`，根據檔案內的註解修改 `target_src_path`, `root_package_name`。確認 `analysis_type` 為 `component_interaction`。

2.  **設定工作區**
    -   進入 `configs/` 目錄，將 `workspace.template.yaml` 複製為 `workspace.yaml`。
    -   打開 `workspace.yaml`，在 `active_projects` 列表中，加入您剛剛建立的設定檔名稱（例如 `my_project.yaml`）。

3.  **執行分析**
    -   在專案根目錄下，執行以下簡單的指令：
    ```bash
    python -m projectinsight.main
    ```
    -   工具將會自動讀取 `workspace.yaml` 並處理所有列出的專案。

4.  **檢視結果**
    -   分析完成後，生成的 PNG 圖檔和 `.txt` 原始檔將會出現在您專案設定檔中 `output_dir` 指定的目錄下。

## 發展藍圖

-   [x] **(舊) 詳細模組依賴圖**: 已被移除，確認為對 LLM 的雜訊。
-   [x] **(舊) 函式級控制流圖**: 已被移除，確認為對 LLM 的雜訊。
-   [x] **核心功能：高階組件互動圖**: 成功實現了將原始碼抽象為類別與模組級函式互動關係的核心功能。
-   [ ] **擴展分析維度**:
    -   [ ] **關鍵資料流圖**: 追蹤關鍵資料（如設定值、核心資料結構）的來源與流動路徑。
-   [ ] **視覺化與可用性增強**:
    -   [ ] 允許使用者在設定檔中指定圖表的尺寸 (`size`) 和長寬比 (`ratio`)。

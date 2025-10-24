# ProjectInsight: 專為 LLM 設計的專案宏觀分析器

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

ProjectInsight 是一個專為大型語言模型 (LLM) 設計的靜態程式碼分析預處理器。它的核心使命是將一個複雜的 Python 專案原始碼，抽象為高層次的、無雜訊的宏觀圖表，使 LLM 能夠在幾秒鐘內洞察一個陌生專案的核心架構與關鍵概念的流動路徑。

## 核心特性

-   **多維度高階分析**:
    -   **高階組件互動圖**: 專注於分析類別（組件）之間的實例化與使用關係，以及模組級函式如何與這些組件互動，從而揭示專案的真實架構藍圖。
    -   **概念流動圖 (MVP)**: 追蹤關鍵物件實例（如設定物件、服務單例）在專案中的賦值、傳遞與使用，揭示核心資料的生命週期。

-   **智慧種子發現**:
    -   獨特的 `auto_concept_flow` 模式能夠自動掃描專案，並根據啟發式規則（如模組頂層的類別實例化）識別出潛在的核心「概念」，無需使用者手動指定。

-   **LLM 友善輸出**:
    -   除了生成 PNG 圖檔供人類除錯外，工具的核心產出是一份包含完整圖形結構（DOT 語言）的 `.txt` 原始檔。這份原始檔專為 LLM 設計，使其能夠輕鬆解析專案的宏觀結構並回答相關問題。

-   **智慧佈局與視覺化**:
    -   **巢狀子圖 (`dot`)**: 在組件互動圖中，自動將節點組織在其所屬的模組框內，清晰地還原專案結構。
    -   **力導向佈局 (`sfdp`)**: 為大型、複雜的專案提供更優的空間利用率和可讀性，尤其適用於網狀的「概念流動圖」。
    -   **架構層級著色**: 透過在設定檔中定義，可為不同架構層級的組件賦予不同顏色，直觀反映架構意圖。

-   **工作區驅動的高度可配置性**:
    -   透過簡單的 `workspace.yaml` 即可管理和批次執行多個專案分析任務。
    -   所有路徑、分析類型、佈局引擎等均可透過 YAML 進行精細配置。

## 產出範例

以下是使用 ProjectInsight 分析 [MoshouSapient](https://github.com/MortyTsai/Moshou_Sapient) 專案生成的圖表示例。

<details>
<summary><b>點擊展開/摺疊：1. 高階組件互動圖 (sfdp 引擎)</b></summary>

*這張圖展示了類別與模組級函式之間的「使用」關係，節點顏色代表其所屬的架構層級。*

<img width="2160" height="1462" alt="moshousapient_component_sfdp_component_interaction_sfdp" src="https://github.com/user-attachments/assets/9906c4f0-574e-4be6-a97f-daa97784c002" />

</details>

<details>
<summary><b>點擊展開/摺疊：2. 概念流動圖 (sfdp 引擎, 自動發現模式)</b></summary>

*這張圖展示了工具自動發現的核心概念（如 `settings` 物件）以及它們如何在專案中被賦值和傳遞。*

<img width="4492" height="2384" alt="moshousapient_auto_concept_flow_concept_flow_sfdp" src="https://github.com/user-attachments/assets/338a6ad1-494b-482f-b9ed-036dc10724e3" />

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

    # 安裝 ProjectInsight 及其所有核心依賴 (包括 jedi, libcst)
    pip install .
    ```

## 使用指南 (工作區模式)

ProjectInsight 採用了簡單而強大的「工作區」模式。

1.  **建立您的專案設定檔**
    -   進入 `configs/templates/` 目錄，將 `project.template.yaml` 複製到 `configs/projects/` 目錄下。
    -   將複製的檔案重新命名（例如 `my_project.yaml`）。
    -   打開 `my_project.yaml`，根據檔案內的註解修改 `target_src_path`, `root_package_name` 和 `analysis_type`。

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
-   [x] **核心功能：概念流動圖 (MVP)**: 成功實現了自動發現和追蹤關鍵物件實例在專案中流動路徑的 MVP 功能。
-   [ ] **擴展分析維度**:
    -   [ ] **增強概念流動分析**: 提升分析深度，以追蹤更複雜的概念傳遞模式（如函式回傳、字典賦值等）。
    -   [ ] **YAML 感知分析**: 實現對 `.yaml` 等設定檔的解析，建立從設定源頭到程式碼使用的端到端追蹤鏈。
-   [ ] **視覺化與可用性增強**:
    -   [ ] 允許使用者在設定檔中指定圖表的尺寸 (`size`) 和長寬比 (`ratio`)。

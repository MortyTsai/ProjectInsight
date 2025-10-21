# ProjectInsight: 自動化專案視覺化工具

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

ProjectInsight 是一個輕量級的自動化靜態程式碼分析與視覺化工具。它能夠掃描指定的 Python 專案原始碼，自動生成多種類型、多個層次的架構圖，幫助開發者（無論是人類還是 LLM）在幾秒鐘內洞察一個陌生專案的宏觀結構、核心流程與設計模式。

## 核心特性

-   **多維度分析**:
    -   **模組依賴圖**: 視覺化模組間的 `import` 關係，揭示專案的靜態結構。
    -   **控制流圖**: 視覺化函式/方法間的呼叫關係，追蹤程式碼的執行路徑。
-   **豐富的資訊密度**:
    -   在模組節點內自動列出其包含的公開函式與類別。
    -   透過顏色編碼清晰地標識不同架構層級的組件。
-   **智慧佈局與視覺化**:
    -   **分層佈局 (`dot`)**: 自動將模組按「策略」、「應用」、「基礎設施」等層級從左到右排列，直觀反映架構意圖。
    -   **力導向佈局 (`sfdp`)**: 為大型、複雜的專案提供更優的空間利用率和可讀性。
    -   **結構化呈現**: 透過巢狀方框（在 `dot` 引擎下）清晰地還原專案的目錄結構。
-   **LLM 友善輸出**: 除了生成 PNG 圖檔外，還會輸出一份包含完整圖形結構（DOT 語言）和語意化註解的 `.txt` 原始檔，極便於大型語言模型進行分析和查詢。
-   **工作區驅動的高度可配置性**:
    -   透過簡單的 `workspace.yaml` 即可管理和批次執行多個專案分析任務。
    -   所有路徑、分析類型、佈局引擎、架構層級和顏色均可透過 YAML 進行精細配置。

## 產出範例

以下是使用 ProjectInsight 分析 [MoshouSapient](https://github.com/MortyTsai/Moshou_Sapient) 專案生成的圖表示例。

<details>
<summary><b>點擊展開/摺疊：模組依賴圖 (dot 引擎)</b></summary>

<img width="2238" height="4543" alt="moshousapient_dependency_dot_dependency_dot" src="https://github.com/user-attachments/assets/14ac2c90-e1bf-4597-b6de-e60daef07e11" />
</details>

<details>
<summary><b>點擊展開/摺疊：控制流圖 (sfdp 引擎, 已過濾內部呼叫)</b></summary>

<img width="3991" height="3437" alt="moshousapient_flow_sfdp_filtered_control_flow_sfdp" src="https://github.com/user-attachments/assets/0c8abb3f-6399-4044-9d81-61e63b148326" />
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
    -   打開 `my_project.yaml`，根據檔案內的註解修改 `target_src_path`, `root_package_name` 以及您需要的分析選項 (`analysis_type`, `layout_engine` 等)。

2.  **設定工作區**
    -   進入 `configs/` 目錄，將 `workspace.template.yaml` 複製為 `workspace.yaml`。
    -   打開 `workspace.yaml`，在 `active_projects` 列表中，加入您剛剛建立的設定檔名稱（例如 `my_project.yaml`）。您可以同時管理多個專案。

3.  **執行分析**
    -   在專案根目錄下，執行以下簡單的指令：
    ```bash
    python -m projectinsight.main
    ```
    -   工具將會自動讀取 `workspace.yaml` 並處理所有列出的專案。

4.  **檢視結果**
    -   分析完成後，生成的 PNG 圖檔和 `.txt` 原始檔將會出現在您每個專案設定檔中 `output_dir` 指定的目錄下。檔名會根據您的設定檔名和分析選項自動生成，不會互相覆蓋。

## 發展藍圖

-   [x] **詳細模組依賴圖**: 實現核心功能，包含巢狀佈局、顏色編碼和分層排列。
-   [x] **函式/類別級別列表**: 在模組節點內展示其包含的公開成員。
-   [x] **多維度分析**: 新增了基於 `jedi` 的**控制流圖**分析功能。
-   [x] **靈活佈局**: 支援 `dot` 和 `sfdp` 兩種佈局引擎。
-   [ ] **提升資訊密度**:
    -   [ ] **邊緣樣式差異化**: 根據依賴類型（例如，跨層級 vs. 同層級）賦予邊不同的樣式。
-   [ ] **擴展分析維度**:
    -   [ ] **高階組件互動圖**: 分析類別實例化和交互關係。
    -   [ ] **設定檔流動圖**: 追蹤設定值的來源與使用。
-   [ ] **視覺化與可用性增強**:
    -   [ ] 允許使用者在設定檔中指定圖表的尺寸 (`size`) 和長寬比 (`ratio`)。

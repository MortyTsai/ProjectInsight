# ProjectInsight: 專為 LLM 設計的專案上下文生成器

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

ProjectInsight 是一個為大型語言模型 (LLM) 設計的 Python 專案靜態分析工具。其核心使命是將一個複雜的 Python 專案，轉化為一份單一、完整、高度濃縮的 Markdown 上下文報告，旨在讓 LLM 能夠宏觀地洞察專案的靜態架構與動態行為模式。

## 核心特性

-   **LLM 優先的上下文輸出 (LLM-First Context Output)**:
    -   **語義豐富的鄰接串列**: 將高階組件關係抽象為 Token 極度高效的「鄰接串列」格式。每個節點都帶有明確的類型標籤（高階組件、內部私有、外部依賴），使 LLM 能夠精確理解專案的架構邊界與核心依賴。
    -   **職責分離的產出**: 嚴格區分產出目標，為 LLM 生成純粹的 `.md` 上下文報告，同時為開發者生成用於視覺化除錯的 `.png` 圖檔和 `.log` 除錯日誌。

-   **健壯的解析與渲染引擎 (Robust Parsing & Rendering Engine)**:
    -   **全地形結構自適應**: 無需手動設定，即可自動偵測 `src` 佈局、`lib` 佈局、扁平佈局及包含多個頂層套件的複雜專案結構，並建立正確的解析上下文。
    -   **智慧化佈局與自我保護**: 渲染引擎能夠識別圖的拓撲結構，對「連通分量」進行分組排序。更具備**智慧降級 (Smart Degradation)** 機制，當偵測到「上帝物件 (God Object)」導致圖表過大時，會自動切換至單向聚焦模式或觸發超時保護，防止視覺化崩潰並確保產出可讀性。
    -   **事實驅動的智慧嚮導 (Fact-Driven Intelligent Wizard)**: 在分析大型專案時，內建的互動式嚮導不再依賴猜測，而是基於**全量解析**後的**圖論事實 (PageRank + Out-Degree)** 進行推薦。它具備**上下文感知 (Context-Aware)** 能力，能自動過濾外部依賴、測試代碼、文件雜訊與私有實作，精準識別出真正的架構核心（如 FastAPI 的 App、Django 的 Model、Pandas 的 DataFrame）。

-   **深度語義分析 (Deep Semantic Analysis)**:
    -   **基於 LibCST**: 核心分析引擎基於 `libcst`，實現了確定性的靜態解析。
    -   **通用語義連結 (IoC)**: 能夠識別並視覺化多種「控制反轉 (IoC)」架構模式，揭示專案的真實設計意圖。分析器現在能夠捕捉指向**外部函式庫**和**內部私有實現**的繼承與裝飾關係，極大地豐富了架構的完整性。目前支援：繼承、裝飾器、代理、集合註冊、策略/工廠模式，以及依賴注入 (`Depends`)。

## 環境準備

### 軟體需求
-   Python 3.11 或更高版本
-   Graphviz: 一個開源的圖形視覺化軟體。

### 安裝步驟

1.  **安裝 Graphviz 主程式**
    -   前往 [Graphviz 官方下載頁面](https://graphviz.org/download/)。
    -   下載並安裝適合您作業系統的版本。
    -   **[重要]** 在安裝過程中，務必勾選 **"Add Graphviz to the system PATH"** 相關選項。

2.  **複製本專案並安裝依賴**
    ```bash
    git clone https://github.com/MortyTsai/ProjectInsight.git
    cd ProjectInsight
    python -m venv .venv
    # Windows
    .\.venv\Scripts\activate
    # macOS / Linux
    # source .venv/bin/activate

    # [推薦] 使用可編輯模式安裝，以確保命令列執行的一致性
    pip install -e .
    ```

## 使用指南

1.  **建立您的專案設定檔**
    -   將 `configs/templates/project.template.yaml` 複製到 `configs/projects/` 目錄下，並重新命名（例如 `my_project.yaml`）。
    -   打開 `my_project.yaml`，**只需修改 `target_project_path`** 指向您的專案即可。

2.  **設定工作區**
    -   將 `configs/workspace.template.yaml` 複製為 `workspace.yaml`。
    -   打開 `workspace.yaml`，在 `active_projects` 列表中，加入您剛剛建立的設定檔名稱。

3.  **執行分析**
    -   在專案根目錄下的**終端機 (Terminal)** 中，執行以下指令：
    ```bash
    python -m projectinsight
    ```

4.  **檢視結果**
    -   分析完成後，`_InsightReport.md` 報告、`.png` 圖檔及 `_InsightDebug.log` 除錯日誌將會出現在您專案設定檔中 `output_dir` 指定的目錄下。

## 發展藍圖

-   [x] **第一階段：核心架構與功能完備**
    -   [x] **核心分析能力**: 實現了高階組件互動圖、概念流動圖 (MVP) 和動態行為感知器 (MVP)。
    -   [x] **大型專案適應性**: **[已完成]** 交付了基於 PageRank 與 Out-Degree 的事實驅動推薦引擎，並具備智慧降級保護機制。
    -   [x] **健壯性與語義深度**: 完成了向 `libcst` 的遷移，實現了全地形專案結構自適應 (`src`/`lib`/扁平)，並交付了可擴展的通用語義連結 (IoC) 分析框架。
    -   [x] **渲染健壯性與 LLM 輸出優化**: 實現了基於拓撲的智慧化渲染佈局策略，並為 LLM 設計了語義豐富、Token 高效的「鄰接串列」報告格式。

-   [ ] **第二階段：跨專案壓力測試與功能擴展**
    -   [x] **自我分析與功能健壯性驗證**
    -   [ ] **[下一階段核心]** **增量分析與快取 (Incremental Analysis)**: 設計並實作基於檔案雜湊的快取機制，將大型專案的重複分析時間從分鐘級縮短至秒級。
    -   [ ] **跨專案壓力測試**: 持續驗證在 **FastAPI**, **Flask**, **Django**, **Pandas**, **Matplotlib** 等大型專案上的通用性與準確性。

-   [ ] **第三階段 (長期)：深度語義分析與生態擴展**
    -   [ ] 設計並實作一個外掛系統，允許為特定框架或語言開發專用的解析器。
    -   [ ] 擴展分析器以識別並標記具有副作用（如 I/O、網路請求）的函式。
    -   [ ] 提供 CI/CD 整合（如 GitHub Action）。
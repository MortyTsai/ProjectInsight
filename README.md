# ProjectInsight: 專為 LLM 設計的專案上下文生成器

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

ProjectInsight 是一個為大型語言模型 (LLM) 設計的 Python 專案靜態分析工具。其核心使命是將一個複雜的 Python 專案，轉化為一份單一、完整、高度濃縮的 Markdown 上下文報告，旨在讓 LLM 能夠宏觀地洞察專案的靜態架構與動態行為模式。

## 核心特性

-   **LLM 優先的上下文輸出 (LLM-First Context Output)**:
    -   **語義豐富的鄰接串列**: 將高階組件關係抽象為 Token 極度高效的「鄰接串列」格式。每個節點都帶有明確的類型標籤（高階組件、內部私有、外部依賴），使 LLM 能夠精確理解專案的架構邊界與核心依賴。
    -   **職責分離的產出**: 嚴格區分產出目標，為 LLM 生成純粹的 `.md` 上下文報告，同時為開發者生成用於視覺化除錯的 `.png` 圖檔和 `.log` 除錯日誌。

-   **健壯的解析與渲染引擎 (Robust Parsing & Rendering Engine)**:
    -   **專案結構自適應**: 無需手動設定，即可自動偵測 `src` 佈局、扁平佈局及包含多個頂層套件的複雜專案結構，並建立正確的解析上下文。
    -   **智慧化佈局與視覺化**: 渲染引擎能夠識別圖的拓撲結構，對「連通分量」進行分組排序，並透過「階梯式拓撲分組」技術生成佈局均衡的圖表。同時，它能以不同的視覺樣式清晰地區分「高階組件」、「內部私有實現」與「外部依賴」，並動態生成精確的圖例。
    -   **智慧對話式嚮導 (Intelligent Dialogue Wizard)**: 在分析大型專案時，內建的互動式嚮導不僅能基於**圖論中心性**、啟發式規則和生態位分析，為使用者推薦高品質的分析入口點，更具備「**後分析驗證與自我修正**」能力。如果使用者選擇的入口點未能產生有意義的架構圖（例如，選擇了一個代理模組），系統會自動偵測並引導使用者選擇更高品質的次級推薦，實現了從單向推薦到智慧對話的進化。

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
    -   [x] **大型專案適應性**: **[已增強]** 交付了具備後分析驗證與自我修正能力的「智慧對話式嚮導」，並支援聚焦分析。
    -   [x] **健壯性與語義深度**: 完成了向 `libcst` 的遷移，實現了專案結構自適應，並交付了可擴展的通用語義連結 (IoC) 分析框架。
    -   [x] **渲染健壯性與 LLM 輸出優化**: 實現了基於拓撲的智慧化渲染佈局策略，並為 LLM 設計了語義豐富、Token 高效的「鄰接串列」報告格式。

-   [ ] **第二階段：跨專案壓力測試與功能擴展**
    -   [x] **自我分析與功能健壯性驗證 (進行中)**
    -   [ ] 在更多、更複雜的專案上驗證並持續增強分析器的健壯性與準確性。
    -   [ ] 根據壓力測試的結果，擴展和優化現有的語義連結分析器，以覆蓋更多的框架特性和設計模式。
    -   [ ] **[下一階段核心]** 探索並實作增量分析與快取，以數量級提升對大型專案的重複分析速度。

-   [ ] **第三階段 (長期)：深度語義分析與生態擴展**
    -   [ ] 設計並實作一個外掛系統，允許為特定框架或語言開發專用的解析器。
    -   [ ] 擴展分析器以識別並標記具有副作用（如 I/O、網路請求）的函式。
    -   [ ] 提供 CI/CD 整合（如 GitHub Action）。
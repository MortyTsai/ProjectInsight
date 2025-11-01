# ProjectInsight: 專為 LLM 設計的專案上下文生成器

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

ProjectInsight 是一個專為大型語言模型 (LLM) 設計的混合式程式碼分析預處理器。它的核心使命是**一鍵將一個複雜的 Python 專案，轉化為一份單一、完整、高度濃縮的 Markdown 上下文報告**。這份報告旨在讓 LLM 能夠宏觀地洞察一個陌生專案的靜態架構、動態行為模式與關鍵概念流動，為後續的開發、重構或程式碼審查任務提供堅實的上下文基礎。

## 核心特性

-   **大型專案適應性 (Large-Scale Project Ready)**:
    -   **互動式配置精靈**: 當偵測到大型專案時，ProjectInsight 不會盲目執行，而是會啟動一個互動式精靈，引導使用者選擇最佳的分析策略（如聚焦分析或過濾分析），從根本上避免了因專案過大而導致的分析失敗或長時間等待。
    -   **聚焦分析 (Focus Analysis)**: 允許使用者指定一個或多個核心模組作為「入口點」，工具將只繪製與這些入口點在一定呼叫深度內相關的組件，從而生成規模可控、上下文高度相關的架構圖。
    -   **入口點高亮**: 在聚焦分析模式下，指定的入口點節點將在圖表中以獨特的視覺樣式高亮顯示，方便使用者快速定位分析核心。

-   **零設定，智慧預設 (Zero-Config by Default)**:
    -   **智慧分層與著色**: 無需任何設定，ProjectInsight 會自動掃描您的專案結構，為所有頂層子套件分配獨特的、視覺和諧的顏色，並在圖例中清晰展示。
    -   **智慧佈局**: 對於複雜的專案，系統會自動啟用「單欄垂直佈局」策略，確保生成的架構圖佈局緊湊、清晰。
    -   **最佳實踐**: 所有視覺化選項（如圖片清晰度、字體樣式、Docstring 顯示）均內建了一套最佳實踐的預設值。

-   **高語義密度圖表 (High Semantic Density)**:
    -   **Docstring 即註解**: 所有圖表節點都會自動提取並展示其對應的 Docstring，將圖表從「結構圖」提升為了「帶有註解的架構藍圖」。
    -   **樣式化標題**: 節點標題經過精心設計，通過顏色和字體粗細來區分模組路徑和組件主體，顯著提升了可讀性。

-   **統一上下文報告**:
    -   **單一檔案交付**: 專案的核心產出是一個 `.md` 檔案，整合了專案檔案樹、所有分析圖表的 DOT 原始碼，以及專案中所有核心原始碼的完整內容。

-   **多維度高階分析**:
    -   **高階組件互動圖**: 專注於分析類別與公開模組級函式之間的「使用」關係，揭示專案的真實架構藍圖。
    -   **概念流動圖**: 自動追蹤關鍵物件實例在專案中的賦值與傳遞。
    -   **動態行為圖**: 透過語義規則，識別並視覺化非同步、事件驅動的架構模式。

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
    git clone https://github.com/your-username/ProjectInsight.git
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
    -   打開 `my_project.yaml`，修改 `target_project_path` 和 `root_package_name`。

2.  **設定工作區**
    -   將 `configs/workspace.template.yaml` 複製為 `workspace.yaml`。
    -   打開 `workspace.yaml`，在 `active_projects` 列表中，加入您剛剛建立的設定檔名稱。

3.  **執行分析**
    -   在專案根目錄下的**終端機 (Terminal)** 中，執行以下指令：
    ```bash
    python -m projectinsight.main
    ```

4.  **應對大型專案**
    -   如果您的專案體量較大，互動式精靈將會自動啟動。
    -   **[推薦]** 選擇 **[聚焦分析]**，並輸入您最關心的 1-2 個核心模組的完整路徑（例如 `my_package.main.Application`）。
    -   工具將會自動為您更新 `.yaml` 設定檔，並生成一個規模可控且高度相關的圖表。

5.  **檢視結果**
    -   分析完成後，最終的 `_InsightReport.md` 報告和 `.png` 圖檔將會出現在您專案設定檔中 `output_dir` 指定的目錄下。

## 發展藍圖

-   [x] **(舊) 模組依賴圖與函式級控制流圖**: 已移除。
-   [x] **核心功能：高階組件互動圖**: 實現了將原始碼抽象為類別與公開函式互動關係的核心功能。
-   [x] **核心功能：概念流動圖 (MVP)**: 實現了自動發現和追蹤關鍵物件實例的 MVP 功能。
-   [x] **核心功能：統一 Markdown 報告生成器**: 實現了生成包含多種分析結果和完整原始碼的單一 Markdown 報告。
-   [x] **核心功能：動態行為感知器 (MVP)**: 實現了由設定檔驅動的、識別動態架構模式的語義分析框架。
-   [x] **核心功能：語義豐富化與易用性提升**:
    -   [x] **智慧分層與著色**: 實現了零設定的自動架構分層與顏色分配。
    -   [x] **智慧佈局**: 實現了確保圖表佈局緊湊的自動垂直分層策略。
    -   [x] **Docstring 整合**: 成功將 Docstring 整合到圖表節點中。
-   [x] **核心功能：健壯性與性能強化**:
    -   [x] **互動式精靈**: 實現了對大型專案的預警與互動式配置。
    -   [x] **聚焦分析**: 實現了從入口點進行限定深度分析的核心能力。
    -   [x] **環境穩定性**: 解決了在不同執行模式下的路徑解析問題。

-   [ ] **(下一階段) 核心功能：端到端概念追蹤**:
    -   **目標**: 將「概念流動圖」與「動態行為圖」進行深度融合，實現「超級概念流動圖」。

-   [ ] **(長期) 智慧化與易用性增強**:
    -   [ ] **自主探索外掛**: 為業界主流函式庫（如 Celery, Dramatiq）開發內建的語義分析規則。
    -   [ ] **YAML 感知分析**: 實現對 `.yaml` 等設定檔的解析，將其作為概念的源頭納入分析圖中。
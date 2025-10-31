# ProjectInsight: 專為 LLM 設計的專案上下文生成器

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

ProjectInsight 是一個專為大型語言模型 (LLM) 設計的混合式程式碼分析預處理器。它的核心使命是**一鍵將一個複雜的 Python 專案，轉化為一份單一、完整、高度濃縮的 Markdown 上下文報告**。這份報告旨在讓 LLM 能夠宏觀地洞察一個陌生專案的靜態架構、動態行為模式與關鍵概念流動，為後續的開發、重構或程式碼審查任務提供堅實的上下文基礎。

## 核心特性

-   **零設定，智慧預設 (Zero-Config by Default)**:
    -   **智慧分層與著色**: 無需任何設定，ProjectInsight 會自動掃描您的專案結構，為所有頂層子套件分配獨特的、視覺和諧的顏色，並在圖例中清晰展示。
    -   **智慧佈局**: 對於複雜的專案，系統會自動啟用「單欄垂直佈局」策略，確保生成的架構圖佈局緊湊、清晰，從根本上避免了傳統 `dot` 引擎產生的寬扁問題。
    -   **最佳實踐**: 所有視覺化選項（如圖片清晰度、字體樣式、Docstring 顯示）均內建了一套最佳實踐的預設值，讓使用者可以專注於分析本身，而非繁瑣的配置。

-   **高語義密度圖表 (High Semantic Density)**:
    -   **Docstring 即註解**: 所有圖表節點現在都會自動提取並展示其對應的類別、函式或模組的 Docstring。這將圖表從「結構圖」提升為了「帶有註解的架構藍圖」，極大地豐富了其語義價值。
    -   **樣式化標題**: 節點標題經過精心設計，通過顏色和字體粗細來區分模組路徑和組件主體，顯著提升了可讀性。

-   **統一上下文報告**:
    -   **單一檔案交付**: 專案的核心產出是一個 `.md` 檔案，整合了專案檔案樹、所有分析圖表的 DOT 原始碼，以及專案中所有核心原始碼的完整內容。這份報告被設計為可直接複製貼上給 LLM 的「終極上下文」。

-   **多維度高階分析**:
    -   **高階組件互動圖**: 專注於分析類別與公開模組級函式之間的「使用」關係，揭示專案的真實架構藍圖。
    -   **概念流動圖**: 自動追蹤關鍵物件實例在專案中的賦值與傳遞，揭示核心資料的生命週期。
    -   **動態行為圖**: 透過在設定檔中定義語義規則，識別並視覺化非同步、事件驅動的架構模式（如生產者-消費者模型）。

-   **LLM 友善的圖表抽象**:
    -   **DOT 語言核心**: 所有圖表都首先被抽象為 Graphviz 的 DOT 語言，其結構化的文字表示極易被 LLM 解析和理解。
    -   **高解析度視覺化**: 生成的 `.png` 圖檔預設採用高 DPI 渲染，確保在任何螢幕上都清晰銳利，作為開發過程中的絕佳除錯與驗證工具。

## 產出範例

ProjectInsight 的核心產出是一份結構化的 Markdown 檔案，其結構如下所示：

<details>
<summary><b>點擊展開/摺疊：查看完整的報告結構範例</b></summary>

```markdown
# ProjectInsight 分析報告: moshousapient_full_report

**分析時間**: 2025-10-31 01:00:00

## 1. 專案結構總覽
...

## 2. 高階組件互動圖

<details>
<summary>點擊展開/摺疊 DOT 原始碼</summary>

` ` `dot
digraph ComponentInteractionGraph {
    // 節點現在包含了豐富的 HTML-like Label，帶有樣式化標題和 Docstring
    "moshousapient.core.scheduler.Scheduler" [label=<
        <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">
            <TR><TD ALIGN="LEFT">...</TD></TR> <!-- 樣式化標題 -->
            <TR><TD HEIGHT="8"></TD></TR>
            <TR><TD ALIGN="LEFT">...</TD></TR> <!-- 左對齊的 Docstring -->
        </TABLE>
    >, fillcolor="#FFADAD", shape=plaintext]
    ...
}
` ` `

</details>

...
```

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

2.  **複製本專案並安裝依賴**
    ```bash
    git clone https://github.com/your-username/ProjectInsight.git
    cd ProjectInsight
    python -m venv .venv
    # Windows
    .\.venv\Scripts\activate
    # macOS / Linux
    # source .venv/bin/activate
    pip install .
    ```

## 使用指南

1.  **建立您的專案設定檔**
    -   將 `configs/templates/project.template.yaml` 複製到 `configs/projects/` 目錄下，並重新命名（例如 `my_project.yaml`）。
    -   打開 `my_project.yaml`，**您通常只需修改以下三個核心參數**：
        -   `target_project_path`: 指向您要分析的專案的**根目錄**。
        -   `root_package_name`: 您專案的根套件名稱。
        -   `analysis_types`: 選擇您想執行的所有分析類型。
    -   所有視覺化選項（如佈局、顏色、Docstring 顯示）均有智慧預設值，無需手動配置。

2.  **設定工作區**
    -   將 `configs/workspace.template.yaml` 複製為 `workspace.yaml`。
    -   打開 `workspace.yaml`，在 `active_projects` 列表中，加入您剛剛建立的設定檔名稱。

3.  **執行分析**
    -   在專案根目錄下，執行以下指令：
    ```bash
    python -m projectinsight.main
    ```

4.  **檢視結果**
    -   分析完成後，最終的 `_InsightReport.md` 報告和高解析度的 `.png` 圖檔將會出現在您專案設定檔中 `output_dir` 指定的目錄下。

## 發展藍圖

-   [x] **(舊) 模組依賴圖與函式級控制流圖**: 已移除。
-   [x] **核心功能：高階組件互動圖**: 實現了將原始碼抽象為類別與公開函式互動關係的核心功能。
-   [x] **核心功能：概念流動圖 (MVP)**: 實現了自動發現和追蹤關鍵物件實例的 MVP 功能。
-   [x] **核心功能：統一 Markdown 報告生成器**: 實現了生成包含多種分析結果和完整原始碼的單一 Markdown 報告。
-   [x] **核心功能：動態行為感知器 (MVP)**: 實現了由設定檔驅動的、識別動態架構模式的語義分析框架。
-   [x] **核心功能：語義豐富化與易用性提升**:
    -   [x] **智慧分層與著色**: 實現了零設定的自動架構分層與顏色分配。
    -   [x] **智慧佈局**: 實現了確保圖表佈局緊湊的自動垂直分層策略。
    -   [x] **Docstring 整合**: 成功將 Docstring 整合到圖表節點中，極大提升了圖表的語義密度。
    -   [x] **高解析度渲染**: 預設啟用高 DPI 渲染，確保圖片清晰度。

-   [ ] **(下一階段) 核心功能：端到端概念追蹤**:
    -   **目標**: 將「概念流動圖」與「動態行為圖」進行深度融合，實現一個能夠跨越技術邊界（如資料庫、任務佇列、序列化）的「超級概念流動圖」。

-   [ ] **(長期) 智慧化與易用性增強**:
    -   [ ] **自主探索外掛**: 為業界主流函式庫（如 Celery, Dramatiq）開發內建的語義分析規則，進一步減少使用者配置負擔。
    -   [ ] **YAML 感知分析**: 實現對 `.yaml` 等設定檔的解析，將其作為概念的源頭納入分析圖中。
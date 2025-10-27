# ProjectInsight: 專為 LLM 設計的專案上下文生成器

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

ProjectInsight 是一個專為大型語言模型 (LLM) 設計的混合式程式碼分析預處理器。它的核心使命是**一鍵將一個複雜的 Python 專案，轉化為一份單一、完整、高度濃縮的 Markdown 上下文報告**。這份報告旨在讓 LLM 能夠宏觀地洞察一個陌生專案的靜態架構、動態行為模式與關鍵概念流動，為後續的開發、重構或程式碼審查任務提供堅實的上下文基礎。

## 核心特性

-   **統一上下文報告**:
    -   **單一檔案交付**: 專案的核心產出是一個 `.md` 檔案，整合了專案檔案樹、所有分析圖表的 DOT 原始碼，以及專案中所有核心原始碼的完整內容。這份報告被設計為可直接複製貼上給 LLM 的「終極上下文」。

-   **多維度高階分析**:
    -   **高階組件互動圖**: 專注於分析類別（組件）與模組級函式之間的「使用」關係，揭示專案的真實架構藍圖，而非雜亂的函式呼叫鏈。
    -   **概念流動圖**: 追蹤關鍵物件實例（如設定物件、服務單例）在專案中的賦值與傳遞，揭示核心資料的生命週期。
    -   **(新) 動態行為圖**: 透過在設定檔中定義語義規則，使分析器能夠識別並視覺化非同步、事件驅動的架構模式（如生產者-消費者模型），揭示程式碼的執行「意圖」。

-   **LLM 友善的圖表抽象**:
    -   **DOT 語言核心**: 所有圖表都首先被抽象為 Graphviz 的 DOT 語言。這種結構化的文字表示極易被 LLM 解析和理解，遠勝於直接分析程式碼。
    -   **視覺化為輔**: 生成的 `.png` 圖檔僅作為開發過程中的除錯與驗證工具，是一個獨立且次要的產出。

-   **智慧與靈活的分析能力**:
    -   **設定檔驅動**: 所有分析類型、報告內容、視覺化樣式，乃至複雜的動態行為規則，均可透過 `yaml` 檔案進行精細配置，使工具能適應不同專案的獨特架構。
    -   **自動種子發現**: `auto_concept_flow` 模式能夠自動掃描專案，並根據啟發式規則識別出潛在的核心「概念」，無需使用者手動指定。
    -   **支援主流專案佈局**: 自動偵測專案是採用 `src` 佈局還是扁平佈局，無需額外設定。

-   **高度可配置的工作區**:
    -   透過簡單的 `workspace.yaml` 即可管理和批次執行多個專案分析任務。

## 產出範例

ProjectInsight 的核心產出是一份結構化的 Markdown 檔案，其結構如下所示：

<details>
<summary><b>點擊展開/摺疊：查看完整的報告結構範例</b></summary>

```markdown
# ProjectInsight 分析報告: moshousapient_full_report

**分析時間**: 2025-10-27 01:00:00

## 1. 專案結構總覽

<details>
<summary>點擊展開/摺疊專案檔案樹</summary>

` ` `
moshousapient/
├── configs
│   └── ...
├── src
│   └── moshousapient
│       ├── core
│       │   └── ...
│       └── ...
└── ...
` ` `

</details>

## 2. 高階組件互動圖

<details>
<summary>點擊展開/摺疊 DOT 原始碼</summary>

` ` `dot
digraph ComponentInteractionGraph {
    // ... DOT 原始碼 ...
}
` ` `

</details>

## 3. 概念流動圖

<details>
<summary>點擊展開/摺疊 DOT 原始碼</summary>

` ` `dot
digraph ConceptFlowGraph {
    // ... DOT 原始碼 ...
}
` ` `

</details>

## 4. 動態行為圖

<details>
<summary>點擊展開/摺疊 DOT 原始碼</summary>

` ` `dot
digraph DynamicBehaviorGraph {
    // ... DOT 原始碼 ...
    "moshousapient.services.ingestion_service.IngestionService.handle_new_file" -> "moshousapient.jobs.queue_inference_job.main" [label=file_inference_task];
    // ...
}
` ` `

</details>

## 5. 專案完整原始碼

<details>
<summary><code>src/moshousapient/core/app_orchestrator.py</code></summary>

` ` `python
# src/moshousapient/core/app_orchestrator.py
# ... 檔案內容 ...
` ` `

</details>

<!-- ... 其他所有原始碼檔案 ... -->
```

</details>

## 環境準備

### 軟體需求
-   Python 3.11 或更高版本
-   Graphviz: 一個開源的圖形視覺化軟體（用於生成可選的 `.png` 除錯圖檔）。

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
    -   打開 `my_project.yaml`，根據檔案內的教學式註解，修改以下核心參數：
        -   `target_project_path`: 指向您要分析的專案的**根目錄**。
        -   `root_package_name`: 您專案的根套件名稱。
        -   `analysis_types`: 選擇您想執行的所有分析類型。

2.  **設定工作區**
    -   將 `configs/workspace.template.yaml` 複製為 `workspace.yaml`。
    -   打開 `workspace.yaml`，在 `active_projects` 列表中，加入您剛剛建立的設定檔名稱。

3.  **執行分析**
    -   在專案根目錄下，執行以下指令：
    ```bash
    python -m projectinsight.main
    ```

4.  **檢視結果**
    -   分析完成後，最終的 `_InsightReport.md` 報告和可選的 `.png` 圖檔將會出現在您專案設定檔中 `output_dir` 指定的目錄下。

## 發展藍圖

-   [x] **(舊) 模組依賴圖與函式級控制流圖**: 已被移除，確認為對 LLM 的低層次雜訊。
-   [x] **核心功能：高階組件互動圖**: 實現了將原始碼抽象為類別與模組級函式互動關係的核心功能。
-   [x] **核心功能：概念流動圖 (MVP)**: 實現了自動發現和追蹤關鍵物件實例在專案中流動路徑的 MVP 功能。
-   [x] **核心功能：統一 Markdown 報告生成器**: 重構專案，使其能夠生成包含多種分析結果和完整原始碼的單一 Markdown 報告。
-   [x] **核心功能：動態行為感知器 (MVP)**: 成功實現了一個由設定檔驅動的語義分析框架，能夠識別並視覺化使用者定義的動態架構模式（如生產者-消費者）。

-   [ ] **(下一階段) 核心功能：端到端概念追蹤**:
    -   **目標**: 將「概念流動圖」與「動態行為圖」進行深度融合，實現一個能夠跨越技術邊界（如資料庫、任務佇列、序列化）的「超級概念流動圖」。
    -   **願景**: 讓分析器能夠理解 `pickle.dumps`、`queue.put` 等操作的語義，從而生成從設定檔到最終消費者、真正端到端的完整資料生命週期圖。

-   [ ] **(長期) 智慧化與易用性增強**:
    -   [ ] **自主探索外掛**: 為業界主流函式庫（如 Celery, Dramatiq）開發內建的語義分析規則，減少使用者手動編寫 `dynamic_behavior` 規則的負擔。
    -   [ ] **YAML 感知分析**: 實現對 `.yaml` 等設定檔的解析，將其作為概念的源頭納入分析圖中。
    -   [ ] **規則驗證與除錯模式**: 增加對 `yaml` 規則的預檢查功能，並提供一個「除錯模式」，以幫助使用者快速定位設定錯誤。
# ProjectInsight: 專為 LLM 設計的專案上下文生成器

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

ProjectInsight 是一個為大型語言模型 (LLM) 設計的程式碼分析工具。它的核心使命是將一個複雜的 Python 專案，轉化為一份單一、完整、高度濃縮的 Markdown 上下文報告。這份報告旨在讓 LLM 能夠宏觀地洞察一個陌生專案的靜態架構與動態行為模式，為後續的開發、重構或程式碼審查任務提供堅實的上下文基礎。

## 核心特性

-   **健壯的解析引擎 (Robust Parsing Engine)**:
    -   **專案結構自適應**: 無需手動設定 `root_package_name`，ProjectInsight 能夠自動偵測 `src` 佈局、扁平佈局等多種常見的 Python 專案結構，並建立正確的解析上下文。
    -   **基於 LibCST**: 核心分析引擎基於 `libcst`，實現了確定性的、不依賴虛擬環境的靜態解析，保證了分析結果的可靠性與穩定性。
    -   **通用語義連結分析 (IoC)**: 核心分析器能夠識別並視覺化多種「控制反轉 (IoC)」架構模式，揭示專案的真實設計意圖。目前支援：繼承、裝飾器、代理、集合註冊、策略/工廠模式。

-   **大型專案適應性 (Large-Scale Project Ready)**:
    -   **互動式配置精靈**: 當偵測到大型專案時，會啟動一個互動式精靈，引導使用者選擇最佳的分析策略。
    -   **智慧入口點發現**: 內建一個混合式推薦引擎，綜合啟發式計分、圖論中心性和生態位分析，自動為使用者推薦高品質的分析入口點。
    -   **聚焦分析**: 允許從一個或多個核心組件出發，執行雙向廣度優先搜尋，並支援「智慧化深度調整」，確保總能生成一個規模適中且高度相關的圖表。

-   **零設定與高語義密度圖表 (Zero-Config & High-Density Graph)**:
    -   **智慧預設**: 自動為專案的頂層套件分配顏色、自動選擇佈局策略，實現開箱即用。
    -   **Docstring 即註解**: 所有圖表節點都會自動提取並展示其對應的 Docstring，將圖表從「結構圖」提升為「帶有註解的架構藍圖」。

-   **統一上下文報告**:
    -   **單一檔案交付**: 專案的核心產出是一個 `.md` 檔案，整合了專案檔案樹、所有分析圖表的 DOT 原始碼，以及專案中所有核心原始碼的完整內容。

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
    -   分析完成後，最終的 `_InsightReport.md` 報告和 `.png` 圖檔將會出現在您專案設定檔中 `output_dir` 指定的目錄下。

## 發展藍圖

-   [x] **核心功能：高階組件互動圖**: 實現了將原始碼抽象為類別與公開函式互動關係的核心功能。
-   [x] **核心功能：概念流動圖 (MVP)**: 實現了自動發現和追蹤關鍵物件實例的 MVP 功能。
-   [x] **核心功能：動態行為感知器 (MVP)**: 實現了由設定檔驅動的、識別動態架構模式的語義分析框架。
-   [x] **核心功能：統一 Markdown 報告生成器**: 實現了生成包含多種分析結果和完整原始碼的單一 Markdown 報告。
-   [x] **核心功能：語義豐富化與易用性提升**:
    -   [x] **智慧分層與著色**: 實現了零設定的自動架構分層與顏色分配。
    -   [x] **Docstring 整合**: 成功將 Docstring 整合到圖表節點中。
-   [x] **核心功能：健壯性與大型專案適應性**:
    -   [x] **核心解析引擎遷移**: 成功將核心引擎遷移至 `libcst`，極大提升了分析的可靠性與確定性。
    -   [x] **通用語義連結分析 (IoC)**: 交付了一個可擴展的語義分析框架，能夠識別多種 IoC 模式。
    -   [x] **專案結構自適應**: 實現了對 `src` 佈局和扁平佈局的自動偵測與健壯分析。
    -   [x] **互動式精靈與聚焦分析**: 實現了對大型專案的預警、智慧推薦與互動式配置。

-   [ ] **(下一階段) 核心性能與可維護性**:
    -   [ ] **增量 AST 快取**: 實作基於檔案內容雜湊的快取系統，極大提升重複分析的速度。
    -   [ ] **推薦除錯模式**: 提供一個命令列參數，以詳細報告的形式展示推薦分數的構成。

-   [ ] **(長期) 專家知識庫擴展與深度語義分析**:
    -   [ ] **擴充專家規則**: 系統性地為主流框架（如 Django, Pandas）擴展高品質的專家識別規則。
    -   [ ] **外掛系統**: 設計並實作一個框架專用解析器（如 Django `settings.py`）的外掛系統。
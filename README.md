# ProjectInsight: 專為 LLM 設計的 Python 架構分析與視覺化工具

![Project Status: Active Dev](https://img.shields.io/badge/status-active%20development-green) ![Python Version](https://img.shields.io/badge/python-3.11+-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

ProjectInsight 是一個專為大型語言模型 (LLM) 與軟體架構師設計的 Python 靜態分析工具。它致力於解決大型專案在 AI 輔助開發時面臨的「上下文過載」與「邏輯斷裂」問題，透過深度語義分析與視覺化技術，將龐大的程式碼庫提煉為精簡、高密度的架構圖譜。

## 設計哲學

ProjectInsight 的核心設計圍繞著三個關鍵原則：

1.  **上下文提煉 (Context Distillation)**
    傳統的上下文提供方式往往是將所有原始碼直接提供給 LLM，這容易導致 Context Window 溢出或注意力分散。ProjectInsight 選擇將程式碼抽象為**高階組件 (High-Level Components)** 與 **鄰接串列 (Adjacency List)**，以極低的 Token 消耗提供極高的架構資訊密度。

2.  **深度語義感知 (Deep Semantic Awareness)**
    現代 Python 框架 (如 FastAPI, Django) 大量使用依賴注入、裝飾器與元編程。ProjectInsight 不僅僅分析靜態的 `import` 關係，更深入解析 `Depends()`、`Meta` 繼承與動態分派，還原程式碼背後的真實邏輯流向。

3.  **視覺化思維 (Visual Thinking)**
    我們相信一張清晰的架構圖勝過千言萬語。ProjectInsight 生成的高解析度架構圖 (PNG) 配合智慧佈局演算法，能幫助人類開發者與 LLM 快速掌握專案的宏觀結構。

## 核心特性

-   **深度語義分析 (Deep Semantic Analysis)**:
    -   基於 `LibCST` 構建，具備比傳統 AST 更強的語法理解能力。
    -   **IoC 識別**: 自動偵測並連結隱式的依賴關係，如 FastAPI 的 `Depends()` 注入、Flask 的 `Proxy` 代理、Django 的 `Model` 繼承。
    -   **動態行為**: 支援透過規則設定，捕捉基於字串分派 (String Dispatch) 的生產者/消費者模式。

-   **LLM 優先的上下文 (LLM-First Context)**:
    -   輸出 Token 極度高效的 Markdown 報告，明確標註節點類型（高階/私有/外部）。
    -   提供「黃金上下文」，協助 LLM 回答「修改這個類別會影響哪些下游業務？」這類高階架構問題。

-   **高效能與健壯性**:
    -   **平行化解析**: 採用 Map-Reduce 架構，充分利用多核 CPU，在大型專案 (如 Pandas, Django) 上實現秒級熱啟動。
    -   **智慧降級**: 內建自我保護機制，當分析圖表過大時，自動切換至單向聚焦模式，防止資訊爆炸。
    -   **全地形適應**: 自動偵測並適應 `src`, `lib` 或扁平式專案結構，並具備強大的錯誤隔離機制。

## 安裝與使用

### 1. 安裝
```bash
# 推薦使用 uv 或 pip 安裝
git clone https://github.com/MortyTsai/ProjectInsight.git
cd ProjectInsight
pip install -e .
```
*需預先安裝 [Graphviz](https://graphviz.org/download/) 並加入系統 PATH。*

### 2. 快速開始
1.  複製範本設定檔：
    ```bash
    cp configs/templates/project.template.yaml configs/projects/my_project.yaml
    ```
2.  修改 `my_project.yaml` 中的 `target_project_path` 指向你的專案。
3.  設定工作區 `configs/workspace.yaml`。
4.  執行分析：
    ```bash
    python -m projectinsight
    ```

## 發展藍圖 (Roadmap)

-   [x] **Phase 1: 核心架構 (已完成)**
    -   [x] 高階組件互動圖與概念流動圖。
    -   [x] 事實驅動的智慧推薦引擎 (PageRank)。
    -   [x] 跨平台平行化解析 (Map-Reduce)。
    -   [x] 視覺化優化 (儀表板圖例、像素級對齊)。

-   [ ] **Phase 2: 語義補完 (進行中)**
    -   [ ] **Type-Hint 依賴解析**: 利用 Type Hints 建立函式與資料模型之間的隱式連結，進一步強化依賴圖的完整性。
    -   [ ] **統一依賴模型**: 整合 Call, Inherit, Depends, TypeHint 為統一圖譜。

-   [ ] **Phase 3: 服務化與 MCP (規劃中)**
    -   [ ] **MCP Graph Server**: 實作 Model Context Protocol，提供架構查詢服務 (Graph Query)，支援 IDE 與 AI Agent 主動獲取上下文。
    -   [ ] **變更影響分析 (CIA)**: 提供 CLI 工具，輸入變更檔案，輸出受影響的路徑子圖。
    -   [ ] **自適應剪枝**: 基於 Token 預算的動態上下文生成。

## License

MIT License
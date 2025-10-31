# src/projectinsight/renderers/concept_flow_renderer.py
"""
封裝概念流動圖的 Graphviz 渲染邏輯。
"""

# 1. 標準庫導入
import logging
import subprocess
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import graphviz

# 3. 本專案導入
# (無)


def generate_concept_flow_dot_source(
    graph_data: dict[str, Any],
    root_package: str,
    layout_engine: str,
) -> str:
    """
    生成概念流動圖的 DOT 原始碼字串。

    Args:
        graph_data: 包含節點和邊的圖形資料字典。
        root_package: 專案的根套件名稱。
        layout_engine: Graphviz 佈局引擎 ('dot', 'sfdp', etc.)。

    Returns:
        DOT 格式的圖形描述字串。
    """
    dot = graphviz.Digraph("ConceptFlowGraph")

    font_face = 'FACE="Microsoft YaHei"'
    title = f'<<FONT {font_face} POINT-SIZE="20">{root_package} 概念流動圖 引擎: {layout_engine}</FONT>>'

    dot.attr(fontname="Microsoft YaHei", label=title, charset="UTF-8")
    dot.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fontname="Microsoft YaHei",
        fontsize="11",
        fillcolor="#E6F7FF",
    )
    dot.attr("edge", color="gray50", arrowsize="0.7", fontname="Microsoft YaHei")

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    if not nodes:
        dot.node("empty_graph", "未發現任何概念流動路徑", shape="plaintext")
    else:
        for node_fqn in nodes:
            prefix = f"{root_package}."
            label = node_fqn[len(prefix) :] if node_fqn.startswith(prefix) else node_fqn
            dot.node(node_fqn, label)

        for source, target in edges:
            dot.edge(source, target)

    return dot.source


def render_concept_flow_graph(
    graph_data: dict[str, Any],
    output_path: Path,
    root_package: str,
    layout_engine: str = "sfdp",
    dpi: str = "200",
):
    """
    使用 graphviz 將概念流動圖渲染成圖片檔案。
    """
    dot_source = generate_concept_flow_dot_source(graph_data, root_package, layout_engine)

    logging.info(f"準備將概念流動圖渲染至: {output_path} (DPI: {dpi})")
    # [核心修改] 將 DPI 設定作為圖屬性傳遞給命令列
    command = [layout_engine, f"-T{output_path.suffix[1:]}", f"-Gdpi={dpi}"]
    try:
        process = subprocess.run(
            command, input=dot_source.encode("utf-8"), capture_output=True, check=True, timeout=120
        )
        with open(output_path, "wb") as f:
            f.write(process.stdout)
        logging.info(f"圖表已成功儲存至: {output_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Graphviz ({layout_engine}) 執行時返回錯誤。")
        error_message = e.stderr.decode("utf-8", errors="ignore")
        logging.error(f"Graphviz 錯誤訊息:\n{error_message}")
    except Exception as e:
        logging.error(f"渲染圖表時發生錯誤: {e}")

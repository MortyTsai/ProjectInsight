# src/projectinsight/renderers/component_renderer.py
"""
封裝高階組件互動圖的 Graphviz 渲染邏輯。
"""

# 1. 標準庫導入
import logging
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import graphviz

# 3. 本專案導入
# (無)


def _get_node_color(node_name: str, layer_info: dict[str, dict[str, str]]) -> str:
    """根據節點所屬的頂層套件獲取顏色。"""
    default_color = "#E6F7FF"
    parts = node_name.split(".")
    if len(parts) > 1:
        # projectinsight.parsers.component_parser.CodeVisitor -> parsers
        top_level_pkg = parts[1]
        return layer_info.get(top_level_pkg, {}).get("color", default_color)
    return default_color


def render_component_graph(
    graph_data: dict[str, list[Any]],
    output_path: Path,
    root_package: str,
    save_source_file: bool = False,
    layer_info: dict[str, dict[str, str]] | None = None,
    layout_engine: str = "dot",
):
    """
    使用 graphviz 將組件互動圖渲染成圖片檔案。
    """
    if layer_info is None:
        layer_info = {}

    output_format = output_path.suffix[1:]
    source_filepath = output_path.with_suffix(".txt")
    dot = graphviz.Digraph("ComponentInteractionGraph")

    font_face = 'FACE="Microsoft YaHei"'
    title = (
        f'<<FONT {font_face} POINT-SIZE="20">{root_package} 高階組件互動圖 引擎: {layout_engine}</FONT><BR/>'
        f'<FONT {font_face} POINT-SIZE="12">箭頭 A -&gt; B 表示 A 使用 B</FONT>>'
    )

    dot.attr(fontname="Microsoft YaHei")
    if layout_engine == "dot":
        dot.attr(
            rankdir="TB", splines="ortho", nodesep="0.8", ranksep="1.2", label=title, charset="UTF-8", compound="true"
        )
    else:
        dot.attr(splines="true", nodesep="0.3", label=title, charset="UTF-8", compound="true", overlap="prism")

    dot.attr("node", shape="box", style="rounded,filled", fontname="Arial", fontsize="11")
    dot.attr("edge", color="gray50", arrowsize="0.7")

    with dot.subgraph(name="cluster_legend") as legend:
        legend.attr(label="架構層級圖例", style="rounded", color="gray", fontname="Microsoft YaHei")
        font_tag_start = f'<FONT {font_face} POINT-SIZE="10">'
        font_tag_end = "</FONT>"
        unique_layers = {info["name"]: info["color"] for info in layer_info.values()}
        legend_items = [f"<TR><TD>{font_tag_start}圖例{font_tag_end}</TD></TR>"]
        for name, color in unique_layers.items():
            legend_items.append(f'<TR><TD BGCOLOR="{color}">{font_tag_start}{name}{font_tag_end}</TD></TR>')
        legend.node(
            "legend_table",
            label=f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0'>{''.join(legend_items)}</TABLE>>",
            shape="plaintext",
        )

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    nodes_by_module: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        # projectinsight.parsers.component_parser.CodeVisitor -> projectinsight.parsers.component_parser
        module_path = ".".join(node.split(".")[:-1])
        nodes_by_module[module_path].append(node)

    if layout_engine == "dot":
        for module_path, module_nodes in nodes_by_module.items():
            with dot.subgraph(name=f"cluster_{module_path}") as sg:
                sg.attr(label=module_path, style="rounded", color="gray", fontname="Microsoft YaHei")
                for node in module_nodes:
                    short_name = node.split(".")[-1]  # 簡化節點名稱為類別名
                    color = _get_node_color(node, layer_info)
                    sg.node(node, label=short_name, fillcolor=color)
    else:
        for node in nodes:
            short_name = node.split(".")[-1]
            color = _get_node_color(node, layer_info)
            dot.node(node, label=short_name, fillcolor=color)

    for edge in edges:
        dot.edge(edge[0], edge[1])

    dot_source = dot.source
    if save_source_file:
        with open(source_filepath, "w", encoding="utf-8") as f:
            f.write(dot_source)
        logging.info(f"DOT 原始檔已儲存為 LLM 友善的 .txt 格式: {source_filepath}")

    logging.info(f"準備將圖表渲染至: {output_path}")
    command = [layout_engine, f"-T{output_format}"]
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

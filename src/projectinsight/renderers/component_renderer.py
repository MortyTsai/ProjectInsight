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


def _get_node_color(node_name: str, root_package: str, layer_info: dict[str, dict[str, str]]) -> str:
    """
    根據節點 FQN 所屬的架構層級獲取顏色。
    """
    default_color = "#E6F7FF"
    # 遍歷所有定義的架構層 (例如 'core', 'services')
    for layer_key, info in layer_info.items():
        # 檢查節點名稱是否以 '專案根套件.架構層' 開頭
        # 例如 moshousapient.services.s3_service.S3Service 是否以 moshousapient.services 開頭
        prefix = f"{root_package}.{layer_key}"
        if node_name.startswith(prefix):
            return info.get("color", default_color)
    return default_color


def generate_component_dot_source(
    graph_data: dict[str, list[Any]],
    root_package: str,
    layer_info: dict[str, dict[str, str]],
    layout_engine: str,
) -> str:
    """
    生成高階組件互動圖的 DOT 原始碼字串。

    Args:
        graph_data: 包含節點和邊的圖形資料字典。
        root_package: 專案的根套件名稱。
        layer_info: 架構層級定義。
        layout_engine: Graphviz 佈局引擎 ('dot', 'sfdp', etc.)。

    Returns:
        DOT 格式的圖形描述字串。
    """
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

    if layer_info:
        with dot.subgraph(name="cluster_legend") as legend:
            legend.attr(label="架構層級圖例", style="rounded", color="gray", fontname="Microsoft YaHei")
            font_tag_start = f'<FONT {font_face} POINT-SIZE="10">'
            font_tag_end = "</FONT>"
            unique_layers = {info["name"]: info["color"] for info in layer_info.values()}
            legend_items = [f"<TR><TD>{font_tag_start}圖例{font_tag_end}</TD></TR>"]
            for name, color in sorted(unique_layers.items()):
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
        module_path = ".".join(node.split(".")[:-1])
        nodes_by_module[module_path].append(node)

    prefix_to_strip = f"{root_package}."
    if layout_engine == "dot":
        for module_path, module_nodes in nodes_by_module.items():
            with dot.subgraph(name=f"cluster_{module_path}") as sg:
                sg.attr(label=module_path, style="rounded", color="gray", fontname="Microsoft YaHei")
                for node in module_nodes:
                    label = node[len(prefix_to_strip) :] if node.startswith(prefix_to_strip) else node
                    color = _get_node_color(node, root_package, layer_info)
                    sg.node(node, label=label, fillcolor=color)
    else:
        for node in nodes:
            label = node[len(prefix_to_strip) :] if node.startswith(prefix_to_strip) else node
            color = _get_node_color(node, root_package, layer_info)
            dot.node(node, label=label, fillcolor=color)

    for edge in edges:
        dot.edge(edge[0], edge[1])

    return dot.source


def render_component_graph(
    graph_data: dict[str, list[Any]],
    output_path: Path,
    root_package: str,
    layer_info: dict[str, dict[str, str]] | None = None,
    layout_engine: str = "dot",
):
    """
    使用 graphviz 將組件互動圖渲染成圖片檔案。
    """
    if layer_info is None:
        layer_info = {}

    dot_source = generate_component_dot_source(graph_data, root_package, layer_info, layout_engine)

    logging.info(f"準備將組件互動圖渲染至: {output_path}")
    command = [layout_engine, f"-T{output_path.suffix[1:]}"]
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

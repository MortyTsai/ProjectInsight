# src/projectinsight/renderers/component_renderer.py
"""
封裝高階組件互動圖的 Graphviz 渲染邏輯。
"""

# 1. 標準庫導入
import fnmatch
import html
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import graphviz

# 3. 本專案導入
from projectinsight.utils.color_utils import get_analogous_dark_color


def _get_node_color(node_name: str, root_package: str, layer_info: dict[str, dict[str, str]]) -> str:
    """
    根據節點 FQN 所屬的架構層級（包括根層級）獲取顏色。
    """
    for layer_key, info in layer_info.items():
        if layer_key == "(root)":
            continue
        prefix = f"{root_package}.{layer_key}."
        if node_name.startswith(prefix):
            return info.get("color", "#E6F7FF")

    if "(root)" in layer_info:
        return layer_info["(root)"].get("color", "#E6F7FF")

    return "#E6F7FF"


def _create_html_label(
    node_fqn: str,
    root_package: str,
    docstring: str | None,
    styles: dict[str, Any],
    is_entrypoint: bool,
    bg_color: str,
    border_color: str,
) -> str:
    """
    [最終方案] 使用單一表格、單一儲存格的結構，實現像素完美的、同色系深色邊框高亮。
    """
    title_style = styles.get("title", {})
    title_font_size = title_style.get("font_size", 11)
    path_color = title_style.get("path_color", "#555555")
    main_color = title_style.get("main_color", "#000000")

    prefix_to_strip = f"{root_package}."
    simple_fqn = node_fqn[len(prefix_to_strip) :] if node_fqn.startswith(prefix_to_strip) else node_fqn

    if "." in simple_fqn:
        path_part, main_part = simple_fqn.rsplit(".", 1)
        path_part += "."
    else:
        path_part, main_part = "", simple_fqn

    path_part = html.escape(path_part)
    main_part = html.escape(main_part)

    font_face = 'FACE="Microsoft YaHei"'
    path_html = f'<FONT COLOR="{path_color}" {font_face}>{path_part}</FONT>' if path_part else ""
    main_html = f'<B><FONT COLOR="{main_color}" {font_face}>{main_part}</FONT></B>'
    title_html = f'<FONT POINT-SIZE="{title_font_size}" {font_face}>{path_html}{main_html}</FONT>'

    docstring_html = ""
    if docstring:
        doc_style = styles.get("docstring", {})
        doc_font_size = doc_style.get("font_size", 9)
        doc_color = doc_style.get("color", "#333333")
        spacing = doc_style.get("spacing", 8)

        br_spacing = "<BR/>" * (spacing // 4)

        cleaned_docstring = re.sub(r"^\s+", "", docstring, flags=re.MULTILINE).strip()
        escaped_docstring = html.escape(cleaned_docstring).replace("\n", '<BR ALIGN="LEFT"/>') + '<BR ALIGN="LEFT"/>'

        docstring_html = (
            f'{br_spacing}<FONT POINT-SIZE="{doc_font_size}" COLOR="{doc_color}" {font_face}>{escaped_docstring}</FONT>'
        )

    content = f"{title_html}{docstring_html}"

    if is_entrypoint:
        table_attrs = (
            f'BORDER="3" COLOR="{border_color}" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" BGCOLOR="{bg_color}"'
        )
    else:
        table_attrs = f'BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" BGCOLOR="{bg_color}"'

    return f'<<TABLE {table_attrs}><TR><TD ALIGN="LEFT" VALIGN="TOP">{content}</TD></TR></TABLE>>'


def generate_component_dot_source(
    graph_data: dict[str, Any],
    root_package: str,
    layer_info: dict[str, dict[str, str]],
    comp_graph_config: dict[str, Any],
) -> str:
    """
    生成高階組件互動圖的 DOT 原始碼字串。
    """
    layout_config = comp_graph_config.get("layout", {})
    node_styles = comp_graph_config.get("node_styles", {})
    show_docstrings = node_styles.get("show_docstrings", False)
    focus_config = comp_graph_config.get("focus", {})
    entrypoints = set(focus_config.get("entrypoints", []))

    layout_engine = comp_graph_config.get("layout_engine", "dot")
    aspect_ratio = layout_config.get("aspect_ratio", "auto")
    user_ranking_groups = layout_config.get("ranking_groups")

    dot = graphviz.Digraph("ComponentInteractionGraph")

    font_face = 'FACE="Microsoft YaHei"'
    title = (
        f'<<FONT {font_face} POINT-SIZE="20">{root_package} 高階組件互動圖 引擎: {layout_engine}</FONT><BR/>'
        f'<FONT {font_face} POINT-SIZE="12">箭頭 A -&gt; B 表示 A 使用 B</FONT>>'
    )

    dot.attr(fontname="Microsoft YaHei")
    base_attrs = {"label": title, "charset": "UTF-8"}
    if layout_engine == "dot":
        dot.attr(
            rankdir="TB",
            splines="ortho",
            nodesep="0.8",
            ranksep="1.2",
            concentrate="true",
            **base_attrs,
        )
    else:
        dot.attr(splines="true", nodesep="0.3", overlap="prism", **base_attrs)

    if user_ranking_groups is None and aspect_ratio != "none":
        dot.attr(ratio=str(aspect_ratio))

    dot.attr("node", style="filled", fontname="Arial", fontsize="11")
    dot.attr("edge", color="gray50", arrowsize="0.7")

    if layer_info:
        with dot.subgraph(name="cluster_legend") as legend:
            legend.attr(label="架構層級圖例", style="rounded", color="gray", fontname="Microsoft YaHei")
            font_tag_start = f'<FONT {font_face} POINT-SIZE="10">'
            font_tag_end = "</FONT>"

            legend_data = {}
            for key, info in layer_info.items():
                name = info.get("name", key)
                color = info.get("color")
                if name and color:
                    legend_data[name] = color

            legend_items = [f"<TR><TD>{font_tag_start}圖例{font_tag_end}</TD></TR>"]
            for name, color in sorted(legend_data.items()):
                legend_items.append(f'<TR><TD BGCOLOR="{color}">{font_tag_start}{name}{font_tag_end}</TD></TR>')

            legend.node(
                "legend_table",
                label=f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0'>{''.join(legend_items)}</TABLE>>",
                shape="plaintext",
            )

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    nodes_by_module = graph_data.get("nodes_by_module", {})
    docstrings = graph_data.get("docstrings", {})

    for node_fqn in nodes:
        docstring = docstrings.get(node_fqn) if show_docstrings else None
        color = _get_node_color(node_fqn, root_package, layer_info)
        is_entrypoint = node_fqn in entrypoints

        node_attrs = {"fillcolor": color}

        if show_docstrings:
            border_color = get_analogous_dark_color(color) if is_entrypoint else ""
            label = _create_html_label(
                node_fqn, root_package, docstring, node_styles, is_entrypoint, color, border_color
            )
            dot.node(node_fqn, label=label, shape="plaintext", **node_attrs)
        else:
            if is_entrypoint:
                node_attrs["pencolor"] = get_analogous_dark_color(color)
                node_attrs["penwidth"] = "3.0"
                node_attrs["style"] = "rounded,filled,bold"
            label = node_fqn[len(f"{root_package}.") :] if node_fqn.startswith(f"{root_package}.") else node_fqn
            dot.node(node_fqn, label=label, shape="box", **node_attrs)

    for edge in edges:
        dot.edge(edge[0], edge[1])

    final_ranking_groups = []
    if user_ranking_groups is not None:
        final_ranking_groups = user_ranking_groups
    elif layout_engine == "dot":
        logging.info("未提供手動分層 (ranking_groups)，啟用智慧自動分層策略。")
        sorted_modules = sorted(nodes_by_module.keys())
        final_ranking_groups = [[mod] for mod in sorted_modules]

    if final_ranking_groups:
        module_to_nodes_map = {mod: mod_nodes for mod, mod_nodes in nodes_by_module.items() if mod_nodes}
        for i in range(len(final_ranking_groups) - 1):
            current_row_patterns = final_ranking_groups[i]
            next_row_patterns = final_ranking_groups[i + 1]
            source_node = next(
                (
                    module_to_nodes_map[mod][0]
                    for pat in current_row_patterns
                    for mod in module_to_nodes_map
                    if fnmatch.fnmatch(mod, pat)
                ),
                None,
            )
            target_node = next(
                (
                    module_to_nodes_map[mod][0]
                    for pat in next_row_patterns
                    for mod in module_to_nodes_map
                    if fnmatch.fnmatch(mod, pat)
                ),
                None,
            )
            if source_node and target_node:
                dot.edge(source_node, target_node, style="invis")

    return dot.source


def render_component_graph(
    graph_data: dict[str, Any],
    output_path: Path,
    root_package: str,
    layer_info: dict[str, dict[str, str]],
    comp_graph_config: dict[str, Any],
):
    """
    使用 graphviz 將組件互動圖渲染成圖片檔案。
    """
    layout_engine = comp_graph_config.get("layout_engine", "dot")
    dpi = comp_graph_config.get("dpi", "200")
    dot_source = generate_component_dot_source(graph_data, root_package, layer_info, comp_graph_config)

    logging.info(f"準備將組件互動圖渲染至: {output_path} (DPI: {dpi})")
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

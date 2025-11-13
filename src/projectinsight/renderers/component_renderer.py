# src/projectinsight/renderers/component_renderer.py
"""
封裝高階組件互動圖的 Graphviz 渲染邏輯。
"""

# 1. 標準庫導入
import html
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import graphviz
import networkx as nx

# 3. 本專案導入
from projectinsight.utils.color_utils import get_analogous_dark_color


def _get_node_color(node_name: str, root_package: str | None, layer_info: dict[str, dict[str, str]]) -> str:
    """
    根據節點 FQN 所屬的架構層級獲取顏色。
    此版本能同時處理帶 root_package 和不帶 root_package 的情況。
    """
    best_match_len = 0
    color = "#E6F7FF"

    for layer_key, info in layer_info.items():
        if layer_key == "(root)":
            continue

        prefix = f"{root_package}.{layer_key}." if root_package else f"{layer_key}."
        match_target = layer_key if not root_package else f"{root_package}.{layer_key}"

        if node_name.startswith(prefix) and len(prefix) > best_match_len:
            best_match_len = len(prefix)
            color = info.get("color", color)
        elif node_name.startswith(match_target) and len(match_target) > best_match_len:
            best_match_len = len(match_target)
            color = info.get("color", color)

    if best_match_len == 0 and "(root)" in layer_info:
        if not root_package:
            return layer_info["(root)"].get("color", color)
        if node_name.startswith(f"{root_package}.") and node_name.count(".") == 1:
            return layer_info["(root)"].get("color", color)

    return color


def _create_html_label(
    node_fqn: str,
    docstring: str | None,
    styles: dict[str, Any],
    is_entrypoint: bool,
    bg_color: str,
    border_color: str,
) -> str:
    """
    根據節點資訊和樣式設定，生成三段式 FQN 樣式的 HTML-like Label。
    樣式: package.path.<I>module_name</I>.<B>component_name</B>
    """
    title_style = styles.get("title", {})
    title_font_size = title_style.get("font_size", 11)
    path_color = title_style.get("path_color", "#555555")
    main_color = title_style.get("main_color", "#000000")
    font_face = 'FACE="Microsoft YaHei"'

    parts = node_fqn.split(".")
    if len(parts) > 1:
        main_part = parts[-1]
        module_part = parts[-2]
        package_part = ".".join(parts[:-2])
    else:
        main_part = parts[0]
        module_part = ""
        package_part = ""

    package_html = f'<FONT COLOR="{path_color}" {font_face}>{html.escape(package_part)}.</FONT>' if package_part else ""
    module_html = (
        f'<I><FONT COLOR="{path_color}" {font_face}>{html.escape(module_part)}</FONT></I>.' if module_part else ""
    )
    main_html = f'<B><FONT COLOR="{main_color}" {font_face}>{html.escape(main_part)}</FONT></B>'

    title_html = f'<FONT POINT-SIZE="{title_font_size}" {font_face}>{package_html}{module_html}{main_html}</FONT>'

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


def render_component_graph(
    graph_data: dict[str, Any],
    output_path: Path,
    project_name: str,
    root_package: str | None,
    layer_info: dict[str, dict[str, str]],
    comp_graph_config: dict[str, Any],
) -> list[str]:
    """
    使用 graphviz 將組件互動圖渲染成圖片檔案，並回傳被過濾掉的組件列表。
    """
    node_styles = comp_graph_config.get("node_styles", {})
    show_docstrings = node_styles.get("show_docstrings", True)
    focus_config = comp_graph_config.get("focus", {})
    entrypoints = set(focus_config.get("entrypoints", []))
    semantic_config = comp_graph_config.get("semantic_analysis", {})
    layout_engine = comp_graph_config.get("layout_engine", "dot")
    min_component_size = comp_graph_config.get("layout", {}).get("min_component_size_to_render", 2)
    dpi = comp_graph_config.get("dpi", "200")

    dot = graphviz.Digraph("ComponentInteractionGraph")
    font_face = 'FACE="Microsoft YaHei"'
    title = (
        f'<<FONT {font_face} POINT-SIZE="20">{project_name} 高階組件互動圖 引擎: {layout_engine}</FONT><BR/>'
        f'<FONT {font_face} POINT-SIZE="12">箭頭 A -&gt; B 表示 A 使用 B</FONT>>'
    )

    dot.attr(
        fontname="Microsoft YaHei",
        label=title,
        charset="UTF-8",
        compound="true",
        nodesep="0.8",
        ranksep="1.2",
        splines="ortho",
        concentrate="true",
        packmode="graph",
        pack="true",
    )
    dot.attr("node", style="filled", fontname="Arial", fontsize="11")
    dot.attr("edge", color="gray50", arrowsize="0.7")

    if layer_info:
        with dot.subgraph(name="cluster_legend") as legend:
            legend.attr(label="架構層級圖例", style="rounded", color="gray", fontname="Microsoft YaHei")
            font_tag_start = f'<FONT {font_face} POINT-SIZE="10">'
            font_tag_end = "</FONT>"
            legend_data = {
                info.get("name", key): info.get("color") for key, info in layer_info.items() if info.get("color")
            }
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
    docstrings = graph_data.get("docstrings", {})
    semantic_edges = graph_data.get("semantic_edges", [])

    if not nodes:
        dot.node("empty_graph", "圖中無任何節點", shape="plaintext")
        return []

    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    graph.add_edges_from([(u, v) for u, v, _ in semantic_edges])

    all_components = list(nx.weakly_connected_components(graph))
    filtered_out_components: list[str] = []
    components_to_render = []
    for c in all_components:
        if len(c) >= min_component_size:
            components_to_render.append(c)
        else:
            filtered_out_components.extend(list(c))

    num_filtered = len(filtered_out_components)
    logging.info(
        f"發現 {len(all_components)} 個連通分量，"
        f"已過濾掉 {num_filtered} 個來自微小分量（尺寸<{min_component_size}）的節點。"
    )
    logging.info(f"將為剩餘的 {len(components_to_render)} 個分量進行渲染。")

    for i, component_nodes in enumerate(components_to_render):
        with dot.subgraph(name=f"cluster_{i}") as c:
            c.attr(label=f"Component {i + 1}", style="rounded", color="gray")
            for node_fqn in sorted(component_nodes):
                docstring = docstrings.get(node_fqn) if show_docstrings else None
                color = _get_node_color(node_fqn, root_package, layer_info)
                is_entrypoint = node_fqn in entrypoints
                node_attrs = {"fillcolor": color}

                if show_docstrings:
                    border_color = get_analogous_dark_color(color) if is_entrypoint else ""
                    label = _create_html_label(node_fqn, docstring, node_styles, is_entrypoint, color, border_color)
                    c.node(node_fqn, label=label, shape="plaintext", **node_attrs)
                else:
                    if is_entrypoint:
                        node_attrs["pencolor"] = get_analogous_dark_color(color)
                        node_attrs["penwidth"] = "3.0"
                        node_attrs["style"] = "rounded,filled,bold"
                    c.node(node_fqn, label=node_fqn, shape="box", **node_attrs)

    if semantic_config.get("enabled", True):
        link_styles = semantic_config.get("links", {})
        for u, v, label in semantic_edges:
            style_config = link_styles.get(label, {})
            dot.edge(
                u,
                v,
                style=style_config.get("style", "dashed"),
                color=style_config.get("color", "blue"),
                xlabel=f" {style_config.get('label', label)} " if style_config.get("label") else label,
                fontname="Microsoft YaHei",
                fontsize="9",
            )

    for edge in edges:
        dot.edge(edge[0], edge[1])

    dot_source = dot.source
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

    return sorted(filtered_out_components)
# src/projectinsight/renderers/component_renderer.py
"""
封裝高階組件互動圖的 Graphviz 渲染邏輯。
支援可配置的渲染超時 (render_timeout)。
"""

# 1. 標準庫導入
import html
import logging
import re
import subprocess
from pathlib import Path
from typing import Any, cast

# 2. 第三方庫導入
import graphviz
import networkx as nx

# 3. 本專案導入
from projectinsight.utils.color_utils import get_analogous_dark_color


def _get_node_layer_info(node_name: str, layer_info: dict[str, dict[str, str]]) -> tuple[str, str | None]:
    """
    根據節點 FQN，從 layer_info 中找到最精確匹配的架構層級鍵和顏色。
    """
    best_match_len = 0
    default_color = "#E6F7FF"
    layer_key = "(root)"

    root_info = layer_info.get("(root)", {})
    default_color = root_info.get("color", default_color)

    for key, info in layer_info.items():
        if key == "(root)":
            continue

        prefix = f"{key}."
        if node_name.startswith(prefix) and len(prefix) > best_match_len:
            best_match_len = len(prefix)
            default_color = info.get("color", default_color)
            layer_key = key
        elif node_name == key and len(key) > best_match_len:
            best_match_len = len(key)
            default_color = info.get("color", default_color)
            layer_key = key

    return layer_key, default_color


def _create_html_label(
    node_fqn: str,
    docstring: str | None,
    styles: dict[str, Any],
    is_entrypoint: bool,
    bg_color: str,
    border_color: str,
    node_style: str,
) -> str:
    """
    根據節點資訊和樣式設定，生成三段式 FQN 樣式的 HTML-like Label。
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

    border_style = 'BORDER="3"' if is_entrypoint else 'BORDER="1"'
    color_style = f'COLOR="{border_color}"'
    style_attribute = 'STYLE="dashed"' if node_style != "high_level" else ""

    table_attrs = (
        f"{border_style} {color_style} {style_attribute} "
        f'CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" BGCOLOR="{bg_color}"'
    )

    return f'<<TABLE {table_attrs}><TR><TD ALIGN="LEFT" VALIGN="TOP">{content}</TD></TR></TABLE>>'


def render_component_graph(
    graph_data: dict[str, Any],
    output_path: Path,
    project_name: str,
    layer_info: dict[str, dict[str, str]],
    comp_graph_config: dict[str, Any],
    context_packages: list[str],
) -> list[str]:
    """
    使用 graphviz 將組件互動圖渲染成圖片檔案，並回傳被過濾掉的組件列表。
    """
    node_styles = comp_graph_config.get("node_styles", {})
    show_docstrings = node_styles.get("show_docstrings", True)
    focus_config = comp_graph_config.get("focus", {})
    entrypoints = set(focus_config.get("entrypoints", []))
    semantic_config = comp_graph_config.get("semantic_analysis", {})
    layout_config = comp_graph_config.get("layout", {})
    layout_engine = comp_graph_config.get("layout_engine", "dot")
    min_component_size = layout_config.get("min_component_size_to_render", 2)
    stagger_groups = layout_config.get("stagger_groups", 3)
    dpi = comp_graph_config.get("dpi", "200")

    render_timeout = comp_graph_config.get("render_timeout", 120)

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
        nodesep="1.2",
        ranksep="1.2",
        splines="ortho",
        packmode="graph",
        pack="true",
    )
    dot.attr("node", style="filled", fontname="Arial", fontsize="11")
    dot.attr("edge", color="gray50", arrowsize="0.7")

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    docstrings = graph_data.get("docstrings", {})
    semantic_edges = graph_data.get("semantic_edges", [])
    high_level_components = graph_data.get("high_level_components", set())

    if not nodes:
        dot.node("empty_graph", "圖中無任何節點", shape="plaintext")
        return []

    has_internal_private_nodes = False
    has_external_nodes = False
    for node_fqn in nodes:
        if node_fqn not in high_level_components:
            if any(node_fqn.startswith(pkg) for pkg in context_packages):
                has_internal_private_nodes = True
            else:
                has_external_nodes = True
        if has_internal_private_nodes and has_external_nodes:
            break

    with dot.subgraph(name="cluster_legends") as legends:
        legends.attr(label="", color="none")

        active_nodes_in_graph = set(nodes)
        active_layer_keys = {_get_node_layer_info(node, layer_info)[0] for node in active_nodes_in_graph}

        if layer_info and active_layer_keys:
            with legends.subgraph(name="cluster_layer_legend") as layer_legend:
                layer_legend.attr(label="節點樣式圖例", style="rounded", color="gray", fontname="Microsoft YaHei")
                font_tag_start = f'<FONT {font_face} POINT-SIZE="10">'
                font_tag_end = "</FONT>"
                legend_title = "<b>高階組件 (按層級著色)</b>"
                legend_items = [f'<TR><TD ALIGN="LEFT">{font_tag_start}{legend_title}{font_tag_end}</TD></TR>']
                for key in sorted(active_layer_keys):
                    info = layer_info.get(key, {})
                    name = info.get("name", key)
                    color = info.get("color")
                    if name and color:
                        legend_items.append(
                            f'<TR><TD BGCOLOR="{color}" ALIGN="LEFT">{font_tag_start}{name}{font_tag_end}</TD></TR>'
                        )

                if has_internal_private_nodes:
                    legend_items.append(
                        f'<TR><TD BGCOLOR="#E0E0E0" ALIGN="LEFT" BORDER="1" STYLE="dashed" COLOR="#AAAAAA">'
                        f"{font_tag_start}內部私有組件{font_tag_end}</TD></TR>"
                    )
                if has_external_nodes:
                    legend_items.append(
                        f'<TR><TD BGCOLOR="#FFFFFF" ALIGN="LEFT" BORDER="1" STYLE="dashed" COLOR="#888888">'
                        f"{font_tag_start}外部依賴/契約{font_tag_end}</TD></TR>"
                    )

                layer_legend.node(
                    "layer_legend_table",
                    label=f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='5'>{''.join(legend_items)}</TABLE>>",
                    shape="plaintext",
                )

        active_semantic_labels = {label for _, _, label in semantic_edges}
        if semantic_config.get("enabled", True) and active_semantic_labels:
            with legends.subgraph(name="cluster_semantic_legend") as semantic_legend:
                semantic_legend.attr(label="語義連結圖例", style="rounded", color="gray", fontname="Microsoft YaHei")

                html_rows = []
                link_styles = semantic_config.get("links", {})

                style_map = {
                    "dashed": "- - - &gt;",
                    "dotted": "&middot; &middot; &middot; &gt;",
                    "bold": "&mdash;&mdash;&mdash;&gt;",
                }
                arrow_map = {"tee": "&mdash;|"}

                for key in sorted(active_semantic_labels):
                    style = link_styles.get(key)
                    if not style:
                        continue

                    label_text = style.get("label", key)
                    color = style.get("color", "black")
                    line_style = style.get("style", "solid")
                    arrow = style.get("arrowhead")

                    line_symbol = style_map.get(line_style, "&mdash;&mdash;&gt;")
                    if arrow and arrow in arrow_map:
                        line_symbol = line_symbol.replace("&gt;", arrow_map[arrow])

                    html_rows.append(
                        f'<TR><TD ALIGN="LEFT">{label_text}</TD>'
                        f'<TD ALIGN="LEFT"><FONT COLOR="{color}">{line_symbol}</FONT></TD></TR>'
                    )

                if html_rows:
                    legend_html = (
                        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="5" CELLPADDING="2">'
                        + "".join(html_rows)
                        + "</TABLE>>"
                    )
                    semantic_legend.node("semantic_legend_table", label=legend_html, shape="plaintext")

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

    components_to_render.sort(key=len, reverse=True)

    num_filtered = len(filtered_out_components)
    logging.info(
        f"發現 {len(all_components)} 個連通分量，"
        f"已過濾掉 {num_filtered} 個來自微小分量（尺寸<{min_component_size}）的節點。"
    )
    logging.info(f"將為剩餘的 {len(components_to_render)} 個分量，按尺寸由大到小進行渲染。")

    for i, component_nodes in enumerate(components_to_render):
        with dot.subgraph(name=f"cluster_{i}") as c:
            c.attr(label=f"Component #{i + 1} (size: {len(component_nodes)})", style="rounded", color="gray")
            c.attr(rankdir="TB")

            subgraph = graph.subgraph(component_nodes)
            node_sequence: list[Any]
            try:
                di_subgraph = cast(nx.DiGraph, subgraph)
                node_sequence = list(nx.topological_sort(di_subgraph))
                logging.debug(f"Component {i + 1}: 成功進行拓撲排序。")
            except nx.NetworkXUnfeasible:
                logging.warning(f"Component {i + 1}: 檢測到環，降級為字母排序。")
                node_sequence = sorted(component_nodes)

            if stagger_groups > 0 and len(node_sequence) > 1:
                groups = [node_sequence[j : j + stagger_groups] for j in range(0, len(node_sequence), stagger_groups)]
                for group in groups:
                    quoted_nodes = [f'"{node}"' for node in group]
                    c.body.append(f"{{ rank=same; {' '.join(quoted_nodes)}; }}")

                for j in range(len(groups) - 1):
                    c.edge(groups[j][0], groups[j + 1][0], style="invis")

            for node_fqn in sorted(component_nodes):
                docstring = docstrings.get(node_fqn) if show_docstrings else None
                is_entrypoint = node_fqn in entrypoints

                is_external = not any(node_fqn.startswith(pkg) for pkg in context_packages)
                is_high_level = node_fqn in high_level_components

                node_style_type: str
                if is_high_level:
                    node_style_type = "high_level"
                    _, color = _get_node_layer_info(node_fqn, layer_info)
                    border_color = get_analogous_dark_color(color) if is_entrypoint else color
                elif is_external:
                    node_style_type = "external"
                    color = "#FFFFFF"
                    border_color = "#888888"
                else:
                    node_style_type = "internal_private"
                    color = "#E0E0E0"
                    border_color = "#AAAAAA"

                node_attrs = {"fillcolor": color}

                if show_docstrings:
                    label = _create_html_label(
                        node_fqn, docstring, node_styles, is_entrypoint, color, border_color, node_style_type
                    )
                    c.node(node_fqn, label=label, shape="plaintext", **node_attrs)
                else:
                    if is_entrypoint:
                        node_attrs["pencolor"] = get_analogous_dark_color(color)
                        node_attrs["penwidth"] = "3.0"
                        node_attrs["style"] = "rounded,filled,bold"
                    if node_style_type != "high_level":
                        node_attrs["style"] = "filled,dashed"
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
                arrowhead=style_config.get("arrowhead", "normal"),
                fontname="Microsoft YaHei",
                fontsize="9",
            )

    for edge in edges:
        dot.edge(edge[0], edge[1])

    dot_source = dot.source
    logging.info(f"準備將組件互動圖渲染至: {output_path} (DPI: {dpi}, Timeout: {render_timeout}s)")
    command = [layout_engine, f"-T{output_path.suffix[1:]}", f"-Gdpi={dpi}"]
    try:
        process = subprocess.run(
            command, input=dot_source.encode("utf-8"), capture_output=True, check=True, timeout=render_timeout
        )
        with open(output_path, "wb") as f:
            f.write(process.stdout)
        logging.info(f"圖表已成功儲存至: {output_path}")
    except subprocess.TimeoutExpired:
        logging.error(f"Graphviz 渲染超時 (超過 {render_timeout} 秒)。")
        logging.info(
            "建議：嘗試減少 'initial_depth'，啟用 'auto_downstream_fallback'，或在設定中增加 'render_timeout'。"
        )
    except subprocess.CalledProcessError as e:
        logging.error(f"Graphviz ({layout_engine}) 執行時返回錯誤。")
        error_message = e.stderr.decode("utf-8", errors="ignore")
        logging.error(f"Graphviz 錯誤訊息:\n{error_message}")
    except FileNotFoundError:
        logging.error(f"Graphviz 執行檔 '{layout_engine}' 未找到。請確保 Graphviz 已安裝並已加入系統 PATH。")
    except Exception as e:
        logging.error(f"渲染圖表時發生錯誤: {e}")

    return sorted(filtered_out_components)

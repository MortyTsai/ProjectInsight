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


def _create_legend_html(
    layer_info: dict[str, dict[str, str]],
    active_layer_keys: set[str],
    has_internal_private: bool,
    has_external: bool,
    semantic_config: dict[str, Any],
    active_semantic_labels: set[str],
) -> str:
    """
    生成整合的圖例 HTML 表格。
    """
    font_face = 'FACE="Microsoft YaHei"'
    font_tag_start = f'<FONT {font_face} POINT-SIZE="10">'
    font_tag_end = "</FONT>"
    header_font_start = f'<FONT {font_face} POINT-SIZE="10" COLOR="#333333">'

    node_rows = []
    node_rows.append(
        f'<TR><TD COLSPAN="2" ALIGN="LEFT" VALIGN="TOP"><B>{header_font_start}組件類型{font_tag_end}</B></TD></TR>'
    )

    for key in sorted(active_layer_keys):
        info = layer_info.get(key, {})
        name = info.get("name", key)
        color = info.get("color", "#FFFFFF")
        node_rows.append(
            f'<TR><TD BGCOLOR="{color}" WIDTH="16" HEIGHT="16" BORDER="1" FIXEDSIZE="TRUE"></TD>'
            f'<TD ALIGN="LEFT">{font_tag_start}{name}{font_tag_end}</TD></TR>'
        )

    if has_internal_private:
        node_rows.append(
            f'<TR><TD BGCOLOR="#E0E0E0" WIDTH="16" HEIGHT="16" BORDER="1" STYLE="dashed" FIXEDSIZE="TRUE"></TD>'
            f'<TD ALIGN="LEFT">{font_tag_start}內部私有{font_tag_end}</TD></TR>'
        )
    if has_external:
        node_rows.append(
            f'<TR><TD BGCOLOR="#FFFFFF" WIDTH="16" HEIGHT="16" BORDER="1" STYLE="dashed" FIXEDSIZE="TRUE"></TD>'
            f'<TD ALIGN="LEFT">{font_tag_start}外部依賴{font_tag_end}</TD></TR>'
        )

    left_table = f'<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="4" CELLPADDING="0">{"".join(node_rows)}</TABLE>'

    right_table = ""
    if semantic_config.get("enabled", True) and active_semantic_labels:
        link_rows = []
        link_rows.append(
            f'<TR><TD COLSPAN="2" ALIGN="LEFT" VALIGN="TOP"><B>{header_font_start}關係類型{font_tag_end}</B></TD></TR>'
        )

        link_styles = semantic_config.get("links", {})
        style_map = {
            "dashed": "- - - &gt;",
            "dotted": "&middot; &middot; &gt;",
            "bold": "&mdash;&mdash;&gt;",
            "solid": "&mdash;&mdash;&gt;",
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

            link_rows.append(
                f'<TR><TD ALIGN="RIGHT"><FONT COLOR="{color}">{line_symbol}</FONT></TD>'
                f'<TD ALIGN="LEFT">{font_tag_start}{label_text}{font_tag_end}</TD></TR>'
            )

        right_table = f'<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="4" CELLPADDING="0">{"".join(link_rows)}</TABLE>'

    if right_table:
        combined_content = (
            f"<TR>"
            f'<TD VALIGN="TOP" CELLPADDING="8">{left_table}</TD>'
            f'<TD WIDTH="1" BGCOLOR="#DDDDDD"></TD>'
            f'<TD VALIGN="TOP" CELLPADDING="8">{right_table}</TD>'
            f"</TR>"
        )
    else:
        combined_content = f'<TR><TD VALIGN="TOP" CELLPADDING="8">{left_table}</TD></TR>'

    return (
        f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="0" '
        f'BGCOLOR="#FAFAFA" COLOR="#DDDDDD">{combined_content}</TABLE>'
    )


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
    active_layer_keys = set()
    for node_fqn in nodes:
        layer_key, _ = _get_node_layer_info(node_fqn, layer_info)
        active_layer_keys.add(layer_key)

        if node_fqn not in high_level_components:
            if any(node_fqn.startswith(pkg) for pkg in context_packages):
                has_internal_private_nodes = True
            else:
                has_external_nodes = True

    active_semantic_labels = {label for _, _, label in semantic_edges}

    title_html = (
        f'<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">'
        f'<TR><TD><FONT {font_face} POINT-SIZE="24"><B>{project_name}</B></FONT></TD></TR>'
        f'<TR><TD><FONT {font_face} POINT-SIZE="14">高階組件互動圖 (引擎: {layout_engine})</FONT></TD></TR>'
        f"</TABLE>"
    )

    legend_html = _create_legend_html(
        layer_info,
        active_layer_keys,
        has_internal_private_nodes,
        has_external_nodes,
        semantic_config,
        active_semantic_labels,
    )

    header_html = (
        f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="10">'
        f"<TR><TD>{title_html}</TD></TR>"
        f"<TR><TD>{legend_html}</TD></TR>"
        f"</TABLE>>"
    )

    # 設定全域屬性
    dot.attr(
        label=header_html,
        labelloc="t",
        fontname="Microsoft YaHei",
        charset="UTF-8",
        compound="true",
        nodesep="1",
        ranksep="1",
        splines="ortho",
        packmode="graph",
        pack="true",
    )
    dot.attr("node", style="filled", fontname="Arial", fontsize="11")
    dot.attr("edge", color="gray50", arrowsize="0.7")

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

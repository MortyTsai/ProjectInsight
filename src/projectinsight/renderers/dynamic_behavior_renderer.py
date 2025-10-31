# src/projectinsight/renderers/dynamic_behavior_renderer.py
"""
封裝動態行為圖的 Graphviz 渲染邏輯。
"""

import html
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

import graphviz


def _create_html_label(
    node_fqn: str,
    root_package: str,
    docstring: str | None,
    styles: dict[str, Any],
    context_info: str,
) -> str:
    """
    根據節點資訊和樣式設定，生成 Graphviz 的 HTML-like Label。
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

    context_html = (
        f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="9" COLOR="#555555" {font_face}>  {context_info}</FONT></TD></TR>'
    )

    docstring_html = ""
    spacing_html = ""
    if docstring:
        doc_style = styles.get("docstring", {})
        doc_font_size = doc_style.get("font_size", 9)
        doc_color = doc_style.get("color", "#333333")
        spacing = doc_style.get("spacing", 8)

        cleaned_docstring = re.sub(r"^\s+", "", docstring, flags=re.MULTILINE).strip()
        escaped_docstring = html.escape(cleaned_docstring).replace("\n", '<BR ALIGN="LEFT"/>') + '<BR ALIGN="LEFT"/>'

        spacing_html = f'<TR><TD HEIGHT="{spacing}"></TD></TR>'
        docstring_html = (
            f'<TR><TD ALIGN="LEFT">'
            f'<FONT POINT-SIZE="{doc_font_size}" COLOR="{doc_color}" {font_face}>{escaped_docstring}</FONT>'
            f"</TD></TR>"
        )

    return (
        "<"
        '<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">'
        f'<TR><TD ALIGN="LEFT">{title_html}</TD></TR>'
        f"{context_html}"
        f"{spacing_html}"
        f"{docstring_html}"
        "</TABLE>"
        ">"
    )


def generate_dynamic_behavior_dot_source(
    graph_data: dict[str, Any],
    root_package: str,
    db_graph_config: dict[str, Any],
    roles_config: dict[str, Any],
    docstring_map: dict[str, str],
) -> str:
    """
    生成動態行為圖的 DOT 原始碼字串。
    """
    layout_engine = db_graph_config.get("layout_engine", "dot")
    node_styles = db_graph_config.get("node_styles", {})
    show_docstrings = node_styles.get("show_docstrings", False)

    dot = graphviz.Digraph("DynamicBehaviorGraph")
    font_face = 'FACE="Microsoft YaHei"'
    title = f'<<FONT {font_face} POINT-SIZE="20">{root_package} 動態行為圖 引擎: {layout_engine}</FONT>>'

    dot.attr(fontname="Microsoft YaHei", label=title, charset="UTF-8", compound="true")
    dot.attr("node", shape="box", style="rounded,filled", fontname="Microsoft YaHei", fontsize="11")
    dot.attr("edge", color="gray50", arrowsize="0.7", fontname="Microsoft YaHei", fontsize="10")

    if roles_config:
        with dot.subgraph(name="cluster_legend") as legend:
            legend.attr(label="圖例", style="rounded", color="gray", fontname="Microsoft YaHei")
            for role_id, role_info in roles_config.items():
                legend.node(
                    f"legend_{role_id}",
                    label=role_info.get("name", role_id),
                    shape="box",
                    style="filled",
                    fillcolor=role_info.get("color", "#FFFFFF"),
                    fontname="Microsoft YaHei",
                )

    nodes = graph_data.get("nodes", {})
    edges = graph_data.get("edges", [])

    if not nodes:
        dot.node("empty_graph", "未發現任何動態行為連結", shape="plaintext", fontname="Microsoft YaHei")
    else:
        for fqn, info in nodes.items():
            role = info.get("role", "unknown")
            line = info.get("line_number")
            role_info = roles_config.get(role, {})
            role_name = role_info.get("name", role).split(" ")[0]

            context_info = f"({role_name}"
            if line:
                context_info += f" @ line {line}"
            context_info += ")"

            docstring = docstring_map.get(fqn) if show_docstrings else None
            color = role_info.get("color", "#CCCCCC")

            label = _create_html_label(fqn, root_package, docstring, node_styles, context_info)
            dot.node(fqn, label=label, fillcolor=color, shape="plaintext")

        for edge in edges:
            dot.edge(edge["source"], edge["target"], label=edge["label"])

    return dot.source


def render_dynamic_behavior_graph(
    graph_data: dict[str, Any],
    output_path: Path,
    root_package: str,
    db_graph_config: dict[str, Any],
    roles_config: dict[str, Any],
    docstring_map: dict[str, str],
):
    """
    使用 graphviz 將動態行為圖渲染成圖片檔案。
    """
    layout_engine = db_graph_config.get("layout_engine", "dot")
    dpi = db_graph_config.get("dpi", "96")
    dot_source = generate_dynamic_behavior_dot_source(
        graph_data, root_package, db_graph_config, roles_config, docstring_map
    )

    logging.info(f"準備將動態行為圖渲染至: {output_path} (DPI: {dpi})")
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
    except FileNotFoundError:
        logging.error(f"Graphviz 執行檔 '{layout_engine}' 未找到。請確保 Graphviz 已安裝並已加入系統 PATH。")
    except Exception as e:
        logging.error(f"渲染圖表時發生錯誤: {e}")

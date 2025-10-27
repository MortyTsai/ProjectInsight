# src/projectinsight/renderers/dynamic_behavior_renderer.py
"""
封裝動態行為圖的 Graphviz 渲染邏輯。
"""

import logging
import subprocess
from pathlib import Path
from typing import Any

import graphviz


def generate_dynamic_behavior_dot_source(
    graph_data: dict[str, Any],
    root_package: str,
    layout_engine: str,
    roles_config: dict[str, Any],
) -> str:
    """
    生成動態行為圖的 DOT 原始碼字串。
    """
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
        prefix_to_strip = f"{root_package}."
        for fqn, info in nodes.items():
            simple_fqn = fqn[len(prefix_to_strip) :] if fqn.startswith(prefix_to_strip) else fqn
            role = info.get("role", "unknown")
            line = info.get("line_number")
            role_info = roles_config.get(role, {})
            role_name = role_info.get("name", role).split(" ")[0]

            label_parts = [simple_fqn]
            context_info = f"({role_name}"
            if line:
                context_info += f" @ line {line}"
            context_info += ")"
            label_parts.append(context_info)
            label = r"\n".join(label_parts)

            color = role_info.get("color", "#CCCCCC")

            parts = fqn.split(".")
            module_path = ".".join(parts[:-1])
            if info.get("match_target") == "function_entry":
                module_path = ".".join(parts[:-1])
            elif len(parts) > 2 and parts[-2][0].isupper():
                module_path = ".".join(parts[:-2])

            with dot.subgraph(name=f"cluster_{module_path}") as sg:
                sg.attr(label=module_path, style="rounded", color="gray", fontname="Microsoft YaHei")
                sg.node(fqn, label=label, fillcolor=color)

        for edge in edges:
            dot.edge(edge["source"], edge["target"], label=edge["label"])

    return dot.source


def render_dynamic_behavior_graph(
    graph_data: dict[str, Any],
    output_path: Path,
    root_package: str,
    layout_engine: str = "dot",
    roles_config: dict[str, Any] | None = None,
):
    """
    使用 graphviz 將動態行為圖渲染成圖片檔案。
    """
    if roles_config is None:
        roles_config = {}
    dot_source = generate_dynamic_behavior_dot_source(graph_data, root_package, layout_engine, roles_config)

    logging.info(f"準備將動態行為圖渲染至: {output_path}")
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
    except FileNotFoundError:
        logging.error(f"Graphviz 執行檔 '{layout_engine}' 未找到。請確保 Graphviz 已安裝並已加入系統 PATH。")
    except Exception as e:
        logging.error(f"渲染圖表時發生錯誤: {e}")
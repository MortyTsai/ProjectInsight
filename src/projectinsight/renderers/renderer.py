# src/projectinsight/renderers/renderer.py
import logging
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

import graphviz

MAX_ITEMS_PER_NODE = 15


def _generate_llm_comment(layer_info: dict[str, dict[str, str]]) -> str:
    comment = "// --- Architecture Layers (for LLM Analysis) ---\n"
    comment += "// This graph visualizes architectural layers from left to right.\n"
    layers = defaultdict(list)
    for pkg, info in layer_info.items():
        layers[info['name']].append(pkg)
    for name, pkgs in layers.items():
        comment += f"// Layer: {name}\n"
        for pkg in pkgs:
            comment += f"//   - Package: {pkg}, Color: {layer_info[pkg]['color']}\n"
    comment += "// -------------------------------------------------\n"
    return comment


def _create_module_label(module_name: str, details: dict[str, list[str]], bg_color: str) -> str:
    header = f'<TR><TD BGCOLOR="{bg_color}" ALIGN="CENTER"><B>{module_name}</B></TD></TR>'
    rows = [header]
    classes = sorted(details.get("classes", []))
    functions = sorted(details.get("functions", []))
    total_items = len(classes) + len(functions)
    items_shown = 0
    for class_name in classes:
        if items_shown >= MAX_ITEMS_PER_NODE:
            break
        rows.append(f'<TR><TD ALIGN="LEFT">Ⓒ {class_name}</TD></TR>')
        items_shown += 1
    for func_name in functions:
        if items_shown >= MAX_ITEMS_PER_NODE:
            break
        rows.append(f'<TR><TD ALIGN="LEFT">ƒ {func_name}</TD></TR>')
        items_shown += 1
    if total_items > items_shown:
        rows.append(f'<TR><TD ALIGN="LEFT">... (還有 {total_items - items_shown} 個)</TD></TR>')
    if total_items == 0:
        rows.append('<TR><TD></TD></TR>')
    return f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0' CELLPADDING='4'>{''.join(rows)}</TABLE>>"


def render_graph(
        graph_data: dict[str, Any], output_path: Path, root_package: str,
        save_source_file: bool = False, layer_info: dict[str, dict[str, str]] | None = None,
        layout_engine: str = 'dot'
):
    if layer_info is None:
        layer_info = {}
    output_format = output_path.suffix[1:]
    source_filepath = output_path.with_suffix('.txt')
    dot = graphviz.Digraph('DependencyGraph')

    font_face = 'FACE="Microsoft YaHei"'
    title = (
        f'<<FONT {font_face} POINT-SIZE="20">{root_package} 模組依賴關係圖 引擎: {layout_engine}</FONT><BR/>'
        f'<FONT {font_face} POINT-SIZE="12">箭頭 A -&gt; B 表示 A 依賴 B (A imports B)</FONT>>'
    )

    dot.attr(fontname='Microsoft YaHei')
    if layout_engine == 'dot':
        dot.attr(rankdir='LR', splines='ortho', nodesep='1.0', ranksep='1.5',
                 label=title, compound='true', charset='UTF-8')
    else:
        dot.attr(splines='true', nodesep='0.5', label=title, compound='true',
                 charset='UTF-8', overlap='prism')

    dot.attr('node', shape='plain', style='rounded,filled', fontname='Microsoft YaHei', fontsize='12')
    dot.attr('edge', color='gray50', arrowsize='0.7')
    dot.body.append(_generate_llm_comment(layer_info))

    with dot.subgraph(name='cluster_legend') as legend:
        legend.attr(label='架構層級圖例', style='rounded', color='gray', fontname='Microsoft YaHei')
        font_tag_start = f'<FONT {font_face} POINT-SIZE="10">'
        font_tag_end = '</FONT>'
        legend_items = [f'<TR><TD>{font_tag_start}圖例{font_tag_end}</TD></TR>']
        unique_layers = {info['name']: info['color'] for info in layer_info.values()}
        for name, color in unique_layers.items():
            legend_items.append(f'<TR><TD BGCOLOR="{color}">{font_tag_start}{name}{font_tag_end}</TD></TR>')
        legend.node('legend_table',
                    label=f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0'>{''.join(legend_items)}</TABLE>>",
                    shape='plaintext')

    nodes_by_dir = graph_data.get("nodes_by_dir", {})
    module_details = graph_data.get("module_details", {})
    default_node_color = "#E6F7FF"

    if layout_engine == 'dot':
        with dot.subgraph(name=f'cluster_{root_package}') as root_sg:
            root_sg.attr(label=root_package, style='rounded,filled', fillcolor='#DCDCDC', fontsize='16')
            for dir_name in sorted(nodes_by_dir.keys()):
                if dir_name == root_package:
                    continue
                with root_sg.subgraph(name=f'cluster_{dir_name}') as sg:
                    label = dir_name.split('.')[-1]
                    top_level_pkg = dir_name.split('.')[1] if '.' in dir_name else ''
                    color = layer_info.get(top_level_pkg, {}).get('color', '#F0F0F0')
                    sg.attr(label=label, style='rounded,filled', fillcolor=color, fontsize='14')
                    for module in nodes_by_dir[dir_name]:
                        details = module_details.get(module, {})
                        node_label = _create_module_label(module.split('.')[-1], details, default_node_color)
                        sg.node(module, label=node_label)
            for module in nodes_by_dir.get(root_package, []):
                details = module_details.get(module, {})
                node_label = _create_module_label(module.split('.')[-1], details, default_node_color)
                root_sg.node(module, label=node_label)
    else:
        all_modules = [module for modules in nodes_by_dir.values() for module in modules]
        for module in all_modules:
            top_level_pkg = module.split('.')[1] if '.' in module else ''
            color = layer_info.get(top_level_pkg, {}).get('color', default_node_color)
            details = module_details.get(module, {})
            node_label = _create_module_label(module.split('.')[-1], details, color)
            dot.node(module, label=node_label)

    if layout_engine == 'dot':
        ranks = ['control', 'application', 'infrastructure']
        for rank_name in ranks:
            dot.node(f'rank_anchor_{rank_name}', style='invis', width='0', height='0', label='')
        dot.edge('rank_anchor_control', 'rank_anchor_application', style='invis')
        dot.edge('rank_anchor_application', 'rank_anchor_infrastructure', style='invis')
        for dir_name, modules in nodes_by_dir.items():
            if not modules:
                continue
            top_level_pkg = dir_name.split('.')[1] if len(dir_name.split('.')) > 1 else ""
            rank_info = layer_info.get(top_level_pkg, {})
            if 'rank' in rank_info:
                dot.edge(f"rank_anchor_{rank_info['rank']}", modules[0], style='invis')

    edges = graph_data.get("edges", [])
    for edge in edges:
        dot.edge(edge[0], edge[1])

    dot_source = dot.source
    if save_source_file:
        with open(source_filepath, 'w', encoding='utf-8') as f:
            f.write(dot_source)
        logging.info(f"DOT 原始檔已儲存為 LLM 友善的 .txt 格式: {source_filepath}")

    logging.info(f"準備將圖表渲染至: {output_path}")
    command = [layout_engine, f'-T{output_format}']
    try:
        process = subprocess.run(
            command, input=dot_source.encode('utf-8'),
            capture_output=True, check=True, timeout=120
        )
        with open(output_path, 'wb') as f:
            f.write(process.stdout)
        logging.info(f"圖表已成功儲存至: {output_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Graphviz ({layout_engine}) 執行時返回錯誤。")
        error_message = e.stderr.decode('utf-8', errors='ignore')
        logging.error(f"Graphviz 錯誤訊息:\n{error_message}")
    except FileNotFoundError:
        logging.error(f"指令 '{layout_engine}' 未找到。請確保 Graphviz 已被正確安裝並加入系統 PATH。")
    except subprocess.TimeoutExpired:
        logging.error("Graphviz 執行超時 (超過 120 秒)。專案可能過於複雜。")
    except Exception as e:
        logging.error(f"渲染圖表時發生錯誤: {e}")

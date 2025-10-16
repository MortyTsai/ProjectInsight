# src/projectinsight/renderer.py
"""
封裝 Graphviz 的渲染邏輯。

此模組提供了一個高階介面，用於將結構化的圖形資料轉換為
實際的圖檔 (如 PNG, SVG)。
"""

# 1. 標準庫導入
import logging
import subprocess
from collections import defaultdict
from pathlib import Path

# 2. 第三方庫導入
import graphviz


def _generate_llm_comment(layer_info: dict[str, dict[str, str]]) -> str:
    """生成對 LLM 友善的、描述架構層級的註解。"""
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


def render_graph(
        graph_data: dict,
        output_path: Path,
        root_package: str,
        save_source_file: bool = False,
        layer_info: dict[str, dict[str, str]] | None = None
):
    """
    使用 graphviz 將圖形資料渲染成圖片檔案，支援分層佈局、圖例和語意註解。
    """
    if layer_info is None:
        layer_info = {}

    output_format = output_path.suffix[1:]
    source_filepath = output_path.with_suffix('.txt')

    dot = graphviz.Digraph('DependencyGraph')
    dot.attr(
        rankdir='LR', splines='ortho', nodesep='1.0', ranksep='1.5',
        fontname='Microsoft YaHei', fontsize='20', label=f'{root_package} 模組依賴關係圖',
        compound='true', charset='UTF-8'
    )
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='#E6F7FF', fontname='Arial', fontsize='12')
    dot.attr('edge', color='gray50', arrowsize='0.7')

    dot.body.append(_generate_llm_comment(layer_info))

    with dot.subgraph(name='cluster_legend') as legend:
        legend.attr(label='架構層級圖例', style='rounded', color='gray')
        font_tag_start = '<FONT FACE="Microsoft YaHei" POINT-SIZE="10">'
        font_tag_end = '</FONT>'
        legend_items = [f'<TR><TD>{font_tag_start}圖例{font_tag_end}</TD></TR>']
        unique_layers = {info['name']: info['color'] for info in layer_info.values()}
        for name, color in unique_layers.items():
            legend_items.append(f'<TR><TD BGCOLOR="{color}">{font_tag_start}{name}{font_tag_end}</TD></TR>')
        legend.node('legend_table',
                    label=f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0'>{''.join(legend_items)}</TABLE>>",
                    shape='plaintext')

    nodes_by_dir = graph_data.get("nodes_by_dir", {})

    with dot.subgraph(name=f'cluster_{root_package}') as root_sg:
        root_sg.attr(label=root_package, style='rounded,filled', fillcolor='#DCDCDC', fontname='Microsoft YaHei',
                     fontsize='16')

        for dir_name in sorted(nodes_by_dir.keys()):
            if dir_name == root_package:
                continue
            with root_sg.subgraph(name=f'cluster_{dir_name}') as sg:
                label = dir_name.split('.')[-1]
                top_level_pkg = dir_name.split('.')[1]
                color = layer_info.get(top_level_pkg, {}).get('color', '#F0F0F0')
                sg.attr(label=label, style='rounded,filled', fillcolor=color, fontname='Microsoft YaHei', fontsize='14')
                for module in nodes_by_dir[dir_name]:
                    sg.node(module, module.split('.')[-1])

        for module in nodes_by_dir.get(root_package, []):
            root_sg.node(module, module.split('.')[-1])

    ranks = ['control', 'application', 'infrastructure']
    for rank_name in ranks:
        dot.node(f'rank_anchor_{rank_name}', style='invis', width='0', height='0', label='')

    dot.edge('rank_anchor_control', 'rank_anchor_application', style='invis')
    dot.edge('rank_anchor_application', 'rank_anchor_infrastructure', style='invis')

    for dir_name, modules in nodes_by_dir.items():
        # 修正 E701
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
    command = ['dot', f'-T{output_format}']
    try:
        process = subprocess.run(
            command, input=dot_source.encode('utf-8'),
            capture_output=True, check=True, timeout=30
        )
        with open(output_path, 'wb') as f:
            f.write(process.stdout)
        logging.info(f"圖表已成功儲存至: {output_path}")
    except subprocess.CalledProcessError as e:
        logging.error("Graphviz (dot.exe) 執行時返回錯誤。")
        error_message = e.stderr.decode('utf-8', errors='ignore')
        logging.error(f"Graphviz 錯誤訊息:\n{error_message}")
    except Exception as e:
        logging.error(f"渲染圖表時發生錯誤: {e}")

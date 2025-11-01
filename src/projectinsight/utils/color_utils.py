# src/projectinsight/utils/color_utils.py
"""
提供與顏色處理相關的公用函式。
"""

import colorsys


def get_analogous_dark_color(hex_color: str) -> str:
    """
    根據給定的十六進位背景色，計算一個相似的、更深的、醒目的邊框顏色。

    Args:
        hex_color: 十六進位顏色字串 (例如 "#RRGGBB")。

    Returns:
        一個相似深色的十六進位顏色字串。
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    hue, lightness, saturation = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)

    dark_h = hue
    dark_l = max(0.1, lightness * 0.3)
    dark_s = min(1.0, saturation * 1.2)

    cr, cg, cb = colorsys.hls_to_rgb(dark_h, dark_l, dark_s)

    return f"#{int(cr * 255):02x}{int(cg * 255):02x}{int(cb * 255):02x}"

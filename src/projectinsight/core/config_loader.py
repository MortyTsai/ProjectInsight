# src/projectinsight/core/config_loader.py
"""
負責載入、合併、發現和更新所有與專案分析相關的設定。
"""

# 1. 標準庫導入
import colorsys
import copy
import logging
import random
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import yaml
from ruamel.yaml import YAML

# 3. 本專案導入
from projectinsight.utils.path_utils import find_top_level_packages

DEFAULT_PARSER_CONFIG: dict[str, Any] = {
    "alias_resolution": {
        "exclude_patterns": [
            "*.tests.*",
            "*._*",
        ]
    }
}

DEFAULT_VIS_CONFIG: dict[str, Any] = {
    "component_interaction_graph": {
        "layout_engine": "dot",
        "dpi": 200,
        "render_timeout": 300,
        "layout": {
            "show_internal_calls": False,
            "aspect_ratio": "auto",
            "min_component_size_to_render": 2,
            "stagger_groups": 3,
        },
        "node_styles": {
            "show_docstrings": True,
            "title": {"font_size": 11, "path_color": "#555555", "main_color": "#000000"},
            "docstring": {"font_size": 9, "color": "#333333", "spacing": 8},
        },
        "filtering": {
            "exclude_nodes": [],
        },
        "focus": {
            "entrypoints": [],
            "initial_depth": 2,
            "enable_dynamic_depth": True,
            "min_nodes": 10,
            "max_search_depth": 7,
            "direction": "both",
            "max_nodes_for_bidirectional": 500,
            "auto_downstream_fallback": True,
        },
        "semantic_analysis": {
            "enabled": True,
            "links": {
                "registers": {
                    "style": "dashed",
                    "color": "#1E90FF",
                    "label": "registers",
                },
                "inherits_from": {
                    "style": "dotted",
                    "color": "#32CD32",
                    "label": "inherits",
                },
                "decorates": {
                    "style": "dashed",
                    "color": "#FF8C00",
                    "label": "decorates",
                },
                "proxies": {
                    "style": "dashed",
                    "color": "#9932CC",
                    "label": "proxies",
                    "arrowhead": "tee",
                },
                "uses_strategy": {
                    "style": "bold",
                    "color": "#FF69B4",
                    "label": "uses_strategy",
                },
                "depends_on": {
                    "style": "dashed",
                    "color": "#DAA520",
                    "label": "depends_on",
                },
            },
        },
    },
    "dynamic_behavior_graph": {
        "layout_engine": "dot",
        "dpi": 200,
        "node_styles": {
            "show_docstrings": True,
            "title": {"font_size": 11, "path_color": "#555555", "main_color": "#000000"},
            "docstring": {"font_size": 9, "color": "#333333", "spacing": 8},
        },
    },
}


class ConfigLoader:
    """一個處理設定檔載入、合併與自動發現的類別。"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_yaml(config_path)
        if self.config:
            self._process_config()

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any] | None:
        """安全地載入一個 YAML 檔案。"""
        if not path.is_file():
            logging.error(f"指定的設定檔不存在: {path}")
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logging.error(f"解析設定檔 '{path.name}' 時發生錯誤: {e}")
            return None

    def _process_config(self):
        """處理載入後的設定，進行合併和自動發現。"""
        user_parser_config = self.config.get("parser_settings", {})
        self.config["parser_settings"] = self._merge_configs(copy.deepcopy(DEFAULT_PARSER_CONFIG), user_parser_config)

        user_vis_config = self.config.get("visualization", {})
        self.config["visualization"] = self._merge_configs(copy.deepcopy(DEFAULT_VIS_CONFIG), user_vis_config)

        target_project_path_str = self.config.get("target_project_path")
        if not target_project_path_str:
            return

        config_dir = self.config_path.parent
        target_project_root = (config_dir / target_project_path_str).resolve()
        potential_src_dir = target_project_root / "src"
        python_source_root = potential_src_dir if potential_src_dir.is_dir() else target_project_root

        scan_bases: list[tuple[Path, str | None]] = []
        root_package_name = self.config.get("root_package_name")

        if root_package_name:
            scan_bases.append((python_source_root / root_package_name, root_package_name))
        else:
            top_level_packages = find_top_level_packages(python_source_root)
            for pkg in top_level_packages:
                pkg_path = python_source_root / pkg
                if pkg_path.is_dir():
                    scan_bases.append((pkg_path, pkg))

        all_discovered_layers = {}
        for base_path, prefix in scan_bases:
            all_discovered_layers.update(self._discover_sub_packages(base_path, prefix))

        colored_layers = self._assign_colors_to_layers(list(all_discovered_layers.keys()))
        all_discovered_layers.update(colored_layers)

        user_provided_layers = self.config.get("architecture_layers", {})
        self.config["architecture_layers"] = {**all_discovered_layers, **user_provided_layers}

        root_display_name = root_package_name or self.config_path.stem.replace("_test", "")
        if "(root)" not in self.config["architecture_layers"]:
            self.config["architecture_layers"]["(root)"] = {
                "name": f"{root_display_name} (root)",
                "color": "#EAEAEA",
            }

    @staticmethod
    def _merge_configs(default: dict, user: dict) -> dict:
        """遞迴地合併使用者設定到預設設定中。"""
        for key, value in user.items():
            if isinstance(value, dict) and isinstance(default.get(key), dict):
                default[key] = ConfigLoader._merge_configs(default[key], value)
            else:
                default[key] = value
        return default

    @staticmethod
    def _generate_color_palette(num_colors: int) -> list[str]:
        """
        使用黃金比例演算法，並引入隨機性，生成視覺對比強烈的調色盤。
        """
        palette = []
        golden_ratio_conjugate = 0.61803398875
        hue = random.random()
        for _ in range(num_colors):
            hue += golden_ratio_conjugate
            hue %= 1
            lightness = random.uniform(0.75, 0.95)
            saturation = random.uniform(0.7, 0.9)
            rgb_float = colorsys.hls_to_rgb(hue, lightness, saturation)
            rgb_int = tuple(int(c * 255) for c in rgb_float)
            palette.append(f"#{rgb_int[0]:02x}{rgb_int[1]:02x}{rgb_int[2]:02x}")
        return palette

    def _assign_colors_to_layers(self, layer_keys: list[str]) -> dict[str, Any]:
        """為給定的層級名稱列表分配顏色。"""
        if not layer_keys:
            return {}
        palette = self._generate_color_palette(len(layer_keys))
        auto_layers = {layer_key: {"color": palette[i]} for i, layer_key in enumerate(layer_keys)}
        logging.info(f"自動為 {len(auto_layers)} 個架構層級分配顏色: {', '.join(auto_layers.keys())}")
        return auto_layers

    def _discover_sub_packages(self, base_path: Path, prefix: str | None = None) -> dict[str, Any]:
        """遞迴地掃描給定目錄的所有子套件，並以點分隔的路徑作為鍵。"""
        layers = {}
        if not base_path.is_dir():
            return layers

        if prefix:
            layers[prefix] = {}

        try:
            for item in sorted(base_path.iterdir()):
                if item.is_dir() and (item / "__init__.py").exists():
                    layer_key = f"{prefix}.{item.name}" if prefix else item.name
                    layers.update(self._discover_sub_packages(item, layer_key))
            return layers
        except OSError as e:
            logging.warning(f"自動發現架構層級時發生錯誤: {e}")
            return {}

    @staticmethod
    def update_config_file(config_path: Path, updates: dict[str, Any]):
        """使用 ruamel.yaml 安全地更新設定檔，保留註解和格式。"""
        yaml_loader = YAML()
        try:
            with open(config_path, encoding="utf-8") as f:
                config_data = yaml_loader.load(f)

            for key, value in updates.items():
                keys = key.split(".")
                d = config_data
                for k in keys[:-1]:
                    d = d.setdefault(k, {})
                d[keys[-1]] = value

            with open(config_path, "w", encoding="utf-8") as f:
                yaml_loader.dump(config_data, f)
            logging.info(f"已自動更新設定檔: {config_path.name}")
        except Exception as e:
            logging.error(f"自動更新設定檔 '{config_path.name}' 時失敗: {e}")

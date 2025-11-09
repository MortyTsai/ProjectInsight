# src/projectinsight/core/config_loader.py
"""
負責載入、合併、發現和更新所有與專案分析相關的設定。
"""

# 1. 標準庫導入
import colorsys
import logging
from pathlib import Path
from typing import Any

# 2. 第三方庫導入
import yaml
from ruamel.yaml import YAML

# 3. 本專案導入
# (無)

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
        "layout": {
            "show_internal_calls": False,
            "aspect_ratio": "auto",
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
        self.config["parser_settings"] = self._merge_configs(DEFAULT_PARSER_CONFIG.copy(), user_parser_config)

        user_vis_config = self.config.get("visualization", {})
        self.config["visualization"] = self._merge_configs(DEFAULT_VIS_CONFIG.copy(), user_vis_config)

        root_package_path = self.get_root_package_path()
        if root_package_path:
            auto_discovered_layers = self._discover_architecture_layers(root_package_path)
            user_provided_layers = self.config.get("architecture_layers", {})
            self.config["architecture_layers"] = {**auto_discovered_layers, **user_provided_layers}

            root_package_name = self.config.get("root_package_name", "root")
            if "(root)" not in self.config["architecture_layers"]:
                self.config["architecture_layers"]["(root)"] = {
                    "name": f"{root_package_name} (root)",
                    "color": "#EAEAEA",
                }

    def get_root_package_path(self) -> Path | None:
        """根據設定計算並回傳根套件的絕對路徑。"""
        target_project_path_str = self.config.get("target_project_path")
        root_package_name = self.config.get("root_package_name")

        if not target_project_path_str or not root_package_name:
            logging.error(f"設定檔 '{self.config_path.name}' 中缺少 'target_project_path' 或 'root_package_name'。")
            return None

        config_dir = self.config_path.parent
        target_project_root = (config_dir / target_project_path_str).resolve()

        potential_src_dir = target_project_root / "src"
        python_source_root = potential_src_dir if potential_src_dir.is_dir() else target_project_root

        return python_source_root / root_package_name

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
        """使用黃金比例演算法生成一個視覺上可區分的、和諧的調色盤。"""
        palette = []
        golden_ratio_conjugate = 0.61803398875
        hue = 0.7
        for _ in range(num_colors):
            hue += golden_ratio_conjugate
            hue %= 1
            rgb_float = colorsys.hls_to_rgb(hue, 0.9, 0.9)
            rgb_int = tuple(int(c * 255) for c in rgb_float)
            palette.append(f"#{rgb_int[0]:02x}{rgb_int[1]:02x}{rgb_int[2]:02x}")
        return palette

    def _discover_architecture_layers(self, root_package_path: Path) -> dict[str, Any]:
        """自動掃描根套件目錄，並使用演算法調色盤為其分配顏色。"""
        if not root_package_path.is_dir():
            return {}

        auto_layers = {}
        try:
            sub_packages = [
                item.name
                for item in sorted(root_package_path.iterdir())
                if item.is_dir() and (item / "__init__.py").exists()
            ]

            if not sub_packages:
                return {}

            palette = self._generate_color_palette(len(sub_packages))
            for i, layer_key in enumerate(sub_packages):
                auto_layers[layer_key] = {"color": palette[i]}

            logging.info(f"自動發現 {len(auto_layers)} 個架構層級: {', '.join(auto_layers.keys())}")
        except OSError as e:
            logging.warning(f"自動發現架構層級時發生錯誤: {e}")

        return auto_layers

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

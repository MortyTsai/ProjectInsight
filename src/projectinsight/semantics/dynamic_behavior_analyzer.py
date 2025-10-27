# src/projectinsight/semantics/dynamic_behavior_analyzer.py
"""
提供基於 LibCST Matchers 的動態行為分析功能。
"""

import logging
from pathlib import Path
from typing import Any

import libcst as cst
import libcst.matchers as m
from libcst.matchers import BaseMatcherNode
from libcst.metadata import (
    FullRepoManager,
    FullyQualifiedNameProvider,
    MetadataWrapper,
    ParentNodeProvider,
    PositionProvider,
    ScopeProvider,
)


class DynamicBehaviorVisitor(m.MatcherDecoratableVisitor):
    """
    一個使用 Matcher 的訪問者，用於根據規則發現動態行為。
    """

    METADATA_DEPENDENCIES = (ScopeProvider, FullyQualifiedNameProvider, ParentNodeProvider, PositionProvider)

    def __init__(self, rules: list[dict[str, Any]], wrapper: MetadataWrapper):
        super().__init__()
        self.wrapper = wrapper
        self.findings: list[dict[str, Any]] = []
        self.matchers: list[tuple[dict, dict, BaseMatcherNode]] = []

        for rule in rules:
            if rule.get("type") != "producer_consumer":
                continue
            for part in ("producer", "consumer"):
                if part in rule:
                    config = rule[part]
                    matcher = self._build_matcher(config)
                    if matcher:
                        self.matchers.append((rule, config, matcher))

    def on_visit(self, node: cst.CSTNode) -> bool:
        """覆寫 on_visit 以檢查節點是否匹配任何規則。"""
        for rule, config, matcher in self.matchers:
            if self.matches(node, matcher):
                self._handle_match(node, rule, config)
        return True

    def _get_enclosing_function_fqn(self, node: cst.CSTNode) -> str:
        """使用 ParentNodeProvider 向上追溯，找到包裹節點的函式 FQN。"""
        current = node
        while current:
            if isinstance(current, (cst.FunctionDef, cst.ClassDef)):
                try:
                    fqns = self.get_metadata(FullyQualifiedNameProvider, current)
                    if fqns:
                        return list(fqns)[0].name
                except Exception:
                    return "unknown.scope.resolution.error"
            try:
                current = self.get_metadata(ParentNodeProvider, current)
            except KeyError:
                break
        return "global.scope"

    def _handle_match(self, node: cst.CSTNode, rule: dict[str, Any], config: dict[str, Any]):
        """處理一個成功的匹配。"""
        correlation_key = rule.get("correlation_key")
        target_fqn = config.get("method_fqn", config.get("match_target"))
        caller_fqn: str
        role = config.get("role")

        if not role:
            logging.warning(f"規則 '{rule.get('rule_name')}' 的部分缺少 'role' 定義，已跳過。")
            return

        match_target = config.get("match_target")
        if match_target == "function_entry":
            caller_fqn = target_fqn
        else:
            caller_fqn = self._get_enclosing_function_fqn(node)

        try:
            position = self.get_metadata(PositionProvider, node)
            line_number = position.start.line
        except Exception:
            line_number = None

        finding = {
            "caller_fqn": caller_fqn,
            "correlation_key": correlation_key,
            "rule_name": rule.get("rule_name"),
            "role": role,
            "line_number": line_number,
            "match_target": match_target,
        }
        if finding not in self.findings:
            self.findings.append(finding)
            logging.info(f"  [{role.capitalize()}發現] 在 {caller_fqn} (行: {line_number}) 發現 '{correlation_key}' 的事件。")

    @staticmethod
    def _build_matcher(config: dict[str, Any]) -> BaseMatcherNode | None:
        match_target = config.get("match_target")
        if match_target == "dict_creation":
            return DynamicBehaviorVisitor._build_dict_matcher(config)
        if match_target == "function_entry":
            return DynamicBehaviorVisitor._build_func_entry_matcher(config)
        return None

    @staticmethod
    def _build_dict_matcher(config: dict[str, Any]) -> BaseMatcherNode | None:
        key = config.get("key_argument")
        value = config.get("value_argument")
        if not key:
            return None

        dict_element_matcher: BaseMatcherNode
        if value:
            dict_element_matcher = m.DictElement(
                key=m.MatchIfTrue(lambda node: isinstance(node, cst.SimpleString) and node.evaluated_value == key),
                value=m.MatchIfTrue(lambda node: isinstance(node, cst.SimpleString) and node.evaluated_value == value),
            )
        else:
            dict_element_matcher = m.DictElement(
                key=m.MatchIfTrue(lambda node: isinstance(node, cst.SimpleString) and node.evaluated_value == key)
            )
        return m.Dict(elements=[m.ZeroOrMore(), dict_element_matcher, m.ZeroOrMore()])

    @staticmethod
    def _build_func_entry_matcher(config: dict[str, Any]) -> BaseMatcherNode | None:
        method_fqn = config.get("method_fqn")
        if not method_fqn:
            return None
        simple_name = method_fqn.split(".")[-1]
        return m.FunctionDef(
            name=m.Name(
                value=simple_name,
                metadata=m.MatchMetadataIfTrue(
                    FullyQualifiedNameProvider,
                    lambda fqns: any(fqn.name == method_fqn for fqn in fqns),
                ),
            )
        )


def analyze_dynamic_behavior(
    py_files: list[Path],
    rules: list[dict[str, Any]],
    project_root: Path,
) -> dict[str, Any]:
    all_findings: list[dict[str, Any]] = []
    logging.info("--- 開始執行分析: 'dynamic_behavior' ---")
    if not rules:
        logging.warning("未定義任何動態行為規則，已跳過。")
        return {"links": []}

    repo_root = str(project_root.resolve())
    file_paths_str = [str(p.resolve()) for p in py_files]
    providers = {FullyQualifiedNameProvider, ScopeProvider, ParentNodeProvider, PositionProvider}
    try:
        repo_manager = FullRepoManager(repo_root, file_paths_str, providers)
        repo_manager.resolve_cache()
    except Exception as e:
        logging.error(f"初始化 LibCST FullRepoManager 時發生嚴重錯誤: {e}")
        return {}

    for file_path_str in file_paths_str:
        try:
            wrapper = repo_manager.get_metadata_wrapper_for_path(file_path_str)
            visitor = DynamicBehaviorVisitor(rules, wrapper)
            wrapper.visit(visitor)
            all_findings.extend(visitor.findings)
        except Exception as e:
            logging.error(f"在 '{file_path_str}' 中分析動態行為時失敗: {e}")

    links = []
    findings_by_rule_key: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
    for f in all_findings:
        key = (f["rule_name"], f["correlation_key"])
        if key not in findings_by_rule_key:
            findings_by_rule_key[key] = {"producer": [], "consumer": []}
        findings_by_rule_key[key][f["role"]].append(f)

    for key, groups in findings_by_rule_key.items():
        for p in groups["producer"]:
            for c in groups["consumer"]:
                links.append({"source": p["caller_fqn"], "target": c["caller_fqn"], "label": p["correlation_key"], "producer_info": p, "consumer_info": c})

    producer_count = sum(len(g["producer"]) for g in findings_by_rule_key.values())
    consumer_count = sum(len(g["consumer"]) for g in findings_by_rule_key.values())
    logging.info(f"動態行為分析完成：發現 {producer_count} 個生產者實例，{consumer_count} 個消費者實例，建立了 {len(links)} 條連結。")
    return {"links": links}
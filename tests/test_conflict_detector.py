"""
规则引擎 — 冲突检测单元测试
覆盖：正常冲突检测、无冲突、规则重复触发、rate_opposite、limit_vs_exempt、days_conflict。
"""

import pytest
from src.engine_rules.conflict_detector import detect_rule_conflicts


class TestDetectRuleConflicts:
    def test_no_conflict_single_rule(self):
        """单条规则不涉及冲突"""
        hit_items = [
            {
                "item_id": "ITEM001",
                "rule_id": "test_rule_001",
                "name": "测试规则",
                "category": "药品",
                "risk_score": 80,
                "matched_condition": "amount > 500",
            }
        ]
        conflicts = detect_rule_conflicts(hit_items)
        assert len(conflicts) == 0

    def test_no_conflict_different_items(self):
        """不同 item_id 的规则不涉及冲突"""
        hit_items = [
            {
                "item_id": "ITEM001",
                "rule_id": "rule_a",
                "name": "规则A",
                "category": "药品",
                "risk_score": 70,
                "matched_condition": "amount > 500",
            },
            {
                "item_id": "ITEM002",
                "rule_id": "rule_b",
                "name": "规则B",
                "category": "耗材",
                "risk_score": 60,
                "matched_condition": "markup_rate > 0.15",
            },
        ]
        conflicts = detect_rule_conflicts(hit_items)
        assert len(conflicts) == 0

    def test_no_conflict_same_category_no_opposite_action(self):
        """同一 category 但无互斥动作"""
        hit_items = [
            {
                "item_id": "ITEM001",
                "rule_id": "rule_a",
                "name": "规则A",
                "category": "药品",
                "risk_score": 70,
                "matched_condition": "amount > 500",
            },
            {
                "item_id": "ITEM001",
                "rule_id": "rule_b",
                "name": "规则B",
                "category": "药品",
                "risk_score": 60,
                "matched_condition": "amount > 1000",
            },
        ]
        conflicts = detect_rule_conflicts(hit_items)
        assert len(conflicts) == 0

    def test_duplicate_rule_triggered(self):
        """同一规则被触发多次 → duplicate 冲突"""
        hit_items = [
            {
                "item_id": "ITEM001",
                "rule_id": "zhongyao_injection_limit",
                "name": "中药注射剂限制",
                "category": "药品",
                "risk_score": 80,
                "matched_condition": "injection_type in [中药注射剂] AND amount > 1000",
            },
            {
                "item_id": "ITEM001",
                "rule_id": "zhongyao_injection_limit",
                "name": "中药注射剂限制",
                "category": "药品",
                "risk_score": 80,
                "matched_condition": "injection_type in [中药注射剂] AND amount > 1000",
            },
        ]
        conflicts = detect_rule_conflicts(hit_items)
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "duplicate"
        assert conflicts[0]["item_id"] == "ITEM001"
        assert len(conflicts[0]["conflicting_rules"]) == 1  # 去重后只剩一条

    def test_rate_opposite_markup_conflict(self):
        """加价率同时触发上限(>)和下限(<)规则 → rate_opposite"""
        hit_items = [
            {
                "item_id": "ITEM001",
                "rule_id": "markup_upper",
                "name": "耗材加价率上限",
                "category": "耗材",
                "risk_score": 75,
                "matched_condition": "material_markup_rate > 0.15",
            },
            {
                "item_id": "ITEM001",
                "rule_id": "markup_lower",
                "name": "耗材加价率下限",
                "category": "耗材",
                "risk_score": 65,
                "matched_condition": "material_markup_rate < 0.10",
            },
        ]
        conflicts = detect_rule_conflicts(hit_items)
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "rate_opposite"
        assert "加价率限制方向矛盾" in conflicts[0]["suggested_resolution"]

    def test_limit_vs_exempt_conflict(self):
        """同时触发限用和豁免规则 → limit_vs_exempt"""
        hit_items = [
            {
                "item_id": "ITEM001",
                "rule_id": "limit_rule",
                "name": "中药注射剂限用规则",
                "category": "药品",
                "risk_score": 85,
                "matched_condition": "injection_type eq 中药注射剂 AND amount > 500",
            },
            {
                "item_id": "ITEM001",
                "rule_id": "exempt_rule",
                "name": "中药注射剂豁免规则",
                "category": "药品",
                "risk_score": 40,
                "matched_condition": "injection_type eq 中药注射剂 AND category eq 急诊",
            },
        ]
        conflicts = detect_rule_conflicts(hit_items)
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "limit_vs_exempt"
        assert "限用规则和豁免规则" in conflicts[0]["suggested_resolution"]

    def test_days_conflict(self):
        """住院天数同时触发上限和下限规则 → days_conflict"""
        hit_items = [
            {
                "item_id": "ITEM001",
                "rule_id": "days_upper",
                "name": "分解住院上限",
                "category": "住院",
                "risk_score": 90,
                "matched_condition": "days_admitted < 3",
            },
            {
                "item_id": "ITEM001",
                "rule_id": "days_lower",
                "name": "住院天数下限",
                "category": "住院",
                "risk_score": 50,
                "matched_condition": "days_admitted > 7",
            },
        ]
        conflicts = detect_rule_conflicts(hit_items)
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "days_conflict"
        assert "住院天数限制矛盾" in conflicts[0]["suggested_resolution"]

    def test_multiple_conflicts_same_item(self):
        """同一费用明细触发多种类型冲突"""
        hit_items = [
            {
                "item_id": "ITEM001",
                "rule_id": "markup_upper",
                "name": "耗材加价率上限",
                "category": "耗材",
                "risk_score": 75,
                "matched_condition": "material_markup_rate > 0.15",
            },
            {
                "item_id": "ITEM001",
                "rule_id": "markup_lower",
                "name": "耗材加价率下限",
                "category": "耗材",
                "risk_score": 65,
                "matched_condition": "material_markup_rate < 0.10",
            },
            {
                "item_id": "ITEM001",
                "rule_id": "zhongyao_limit",
                "name": "中药注射剂限制",
                "category": "药品",
                "risk_score": 80,
                "matched_condition": "injection_type in [中药注射剂] AND amount > 1000",
            },
            {
                "item_id": "ITEM001",
                "rule_id": "zhongyao_limit",
                "name": "中药注射剂限制",
                "category": "药品",
                "risk_score": 80,
                "matched_condition": "injection_type in [中药注射剂] AND amount > 1000",
            },
        ]
        conflicts = detect_rule_conflicts(hit_items)
        assert len(conflicts) == 2  # rate_opposite + duplicate
        conflict_types = {c["conflict_type"] for c in conflicts}
        assert "rate_opposite" in conflict_types
        assert "duplicate" in conflict_types

    def test_empty_hit_items(self):
        """空列表返回空冲突"""
        conflicts = detect_rule_conflicts([])
        assert conflicts == []

    def test_conflict_result_structure(self):
        """验证冲突结果结构完整"""
        hit_items = [
            {
                "item_id": "ITEM001",
                "rule_id": "zhongyao_injection_limit",
                "name": "中药注射剂限制",
                "category": "药品",
                "risk_score": 80,
                "matched_condition": "injection_type in [中药注射剂] AND amount > 1000",
            },
            {
                "item_id": "ITEM001",
                "rule_id": "zhongyao_injection_limit",
                "name": "中药注射剂限制",
                "category": "药品",
                "risk_score": 80,
                "matched_condition": "injection_type in [中药注射剂] AND amount > 1000",
            },
        ]
        conflicts = detect_rule_conflicts(hit_items)
        assert len(conflicts) == 1
        c = conflicts[0]
        assert "item_id" in c
        assert "conflicting_rules" in c
        assert "conflict_type" in c
        assert "suggested_resolution" in c
        assert isinstance(c["conflicting_rules"], list)
        assert len(c["conflicting_rules"]) > 0
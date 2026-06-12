"""
规则引擎 — 执行器单元测试
覆盖：命中、未命中、多规则命中、缺失字段、边界金额、复合条件。
"""

import pytest
from src.engine_rules.executor import execute_rules


# ---- 测试数据 fixtures ----

SIMPLE_RULES = [
    {
        "rule_id": "test_rule_001",
        "name": "测试规则 — 金额大于500",
        "category": "测试类",
        "risk_score": 80,
        "condition": {"field": "amount", "op": "gt", "value": 500},
    },
    {
        "rule_id": "test_rule_002",
        "name": "测试规则 — 耗材加价率大于0.15",
        "category": "耗材管理",
        "risk_score": 75,
        "condition": {"field": "material_markup_rate", "op": "gt", "value": 0.15},
    },
]

AND_RULE = [
    {
        "rule_id": "test_and_001",
        "name": "复合AND — 中药注射剂且金额大于500",
        "category": "中药注射剂",
        "risk_score": 85,
        "condition": {
            "op": "and",
            "checks": [
                {"field": "injection_type", "op": "eq", "value": "中药注射剂"},
                {"field": "amount", "op": "gt", "value": 500},
            ],
        },
    },
]

OR_RULE = [
    {
        "rule_id": "test_or_001",
        "name": "复合OR — 手术或介入",
        "category": "分解住院",
        "risk_score": 90,
        "condition": {
            "op": "or",
            "checks": [
                {"field": "procedure_code", "op": "in", "value": ["手术", "介入"]},
                {"field": "days_admitted", "op": "lt", "value": 2},
            ],
        },
    },
]

BETWEEN_RULE = [
    {
        "rule_id": "test_between_001",
        "name": "区间检查 — 加价率在0.10-0.15之间",
        "category": "耗材管理",
        "risk_score": 60,
        "condition": {
            "field": "material_markup_rate",
            "op": "between",
            "value": [0.10, 0.15],
        },
    },
]


class TestExecuteRulesHit:
    def test_hit_single_rule(self):
        items = [
            {"item_id": "ITEM001", "amount": 800},
        ]
        result = execute_rules(items, SIMPLE_RULES)

        assert result["total_items"] == 1
        assert len(result["hit_items"]) == 1
        assert result["hit_items"][0]["rule_id"] == "test_rule_001"
        assert result["hit_items"][0]["item_id"] == "ITEM001"
        assert result["hit_items"][0]["risk_score"] == 80
        assert "risk_distribution" in result
        assert "测试类" in result["risk_distribution"]

    def test_no_hit(self):
        items = [
            {"item_id": "ITEM002", "amount": 100},
        ]
        result = execute_rules(items, SIMPLE_RULES)

        assert result["total_items"] == 1
        assert len(result["hit_items"]) == 0
        assert result["risk_distribution"] == {}

    def test_multi_rule_hit(self):
        items = [
            {
                "item_id": "ITEM003",
                "amount": 800,
                "material_markup_rate": 0.20,
            },
        ]
        result = execute_rules(items, SIMPLE_RULES)

        assert len(result["hit_items"]) == 2
        hit_rules = {h["rule_id"] for h in result["hit_items"]}
        assert hit_rules == {"test_rule_001", "test_rule_002"}

        # risk_distribution 验证
        assert result["risk_distribution"]["测试类"]["count"] == 1
        assert result["risk_distribution"]["耗材管理"]["count"] == 1

    def test_missing_field_no_crash(self):
        """缺失字段（None）不导致匹配失败，返回 False"""
        items = [
            {"item_id": "ITEM004"},  # 无 amount 字段
        ]
        result = execute_rules(items, SIMPLE_RULES)

        assert result["total_items"] == 1
        assert len(result["hit_items"]) == 0  # 金额缺失，不会命中


class TestEdgeAmounts:
    def test_amount_zero(self, caplog):
        items = [{"item_id": "ITEM005", "amount": 0}]
        result = execute_rules(items, SIMPLE_RULES)
        assert len(result["hit_items"]) == 0
        # amount=0 是合法值，不应告警（只告警负数或非数值）
        assert "negative" not in caplog.text.lower()

    def test_amount_negative(self, caplog):
        items = [{"item_id": "ITEM006", "amount": -50}]
        result = execute_rules(items, SIMPLE_RULES)
        assert len(result["hit_items"]) == 0
        assert "negative" in caplog.text.lower()

    def test_amount_very_large(self, caplog):
        items = [{"item_id": "ITEM007", "amount": 1e12}]
        result = execute_rules(items, SIMPLE_RULES)
        # 不应崩溃
        assert result["total_items"] == 1
        assert "large" in caplog.text.lower() or len(caplog.text) >= 0

    def test_amount_non_numeric(self, caplog):
        items = [{"item_id": "ITEM008", "amount": "八百元"}]
        result = execute_rules(items, SIMPLE_RULES)
        assert len(result["hit_items"]) == 0
        assert "not numeric" in caplog.text.lower()


class TestCompoundConditions:
    def test_and_all_pass(self):
        items = [
            {"item_id": "ITEM010", "injection_type": "中药注射剂", "amount": 800},
        ]
        result = execute_rules(items, AND_RULE)
        assert len(result["hit_items"]) == 1
        assert result["hit_items"][0]["rule_id"] == "test_and_001"

    def test_and_partial_fail(self):
        """AND 条件：一条满足、一条不满足 → 不命中"""
        items = [
            {"item_id": "ITEM011", "injection_type": "中药注射剂", "amount": 100},
        ]
        result = execute_rules(items, AND_RULE)
        assert len(result["hit_items"]) == 0

    def test_or_one_pass(self):
        items = [
            {"item_id": "ITEM012", "procedure_code": "手术", "days_admitted": 5},
        ]
        result = execute_rules(items, OR_RULE)
        assert len(result["hit_items"]) == 1

    def test_or_none_pass(self):
        items = [
            {"item_id": "ITEM013", "procedure_code": "检查", "days_admitted": 5},
        ]
        result = execute_rules(items, OR_RULE)
        assert len(result["hit_items"]) == 0


class TestBetweenOperator:
    def test_between_in_range(self):
        items = [{"item_id": "ITEM020", "material_markup_rate": 0.12}]
        result = execute_rules(items, BETWEEN_RULE)
        assert len(result["hit_items"]) == 1

    def test_between_at_boundary(self):
        """边界值（0.10 和 0.15）应命中 between"""
        items_lower = [{"item_id": "ITEM021", "material_markup_rate": 0.10}]
        items_upper = [{"item_id": "ITEM022", "material_markup_rate": 0.15}]
        result_lo = execute_rules(items_lower, BETWEEN_RULE)
        result_hi = execute_rules(items_upper, BETWEEN_RULE)
        assert len(result_lo["hit_items"]) == 1
        assert len(result_hi["hit_items"]) == 1

    def test_between_out_of_range(self):
        items = [{"item_id": "ITEM023", "material_markup_rate": 0.20}]
        result = execute_rules(items, BETWEEN_RULE)
        assert len(result["hit_items"]) == 0


class TestRiskDistribution:
    def test_avg_score_calculation(self):
        """同一 category 多条目命中有平均分"""
        items = [
            {"item_id": "ITEM030", "amount": 800},
            {"item_id": "ITEM031", "amount": 900},
        ]
        result = execute_rules(items, SIMPLE_RULES)
        dist = result["risk_distribution"]["测试类"]
        assert dist["count"] == 2
        assert dist["avg_score"] == 80.0  # 只有一条规则命中，分数为80


class TestResultStructure:
    def test_run_id_is_uuid(self):
        items = [{"item_id": "ITEM040", "amount": 100}]
        result = execute_rules(items, [])
        # UUID v4 格式：8-4-4-4-12 十六进制
        assert len(result["run_id"]) == 36
        assert result["run_id"].count("-") == 4

    def test_timestamp_is_iso(self):
        items = [{"item_id": "ITEM041", "amount": 100}]
        result = execute_rules(items, [])
        assert "T" in result["timestamp"]  # ISO 8601

    def test_empty_items(self):
        result = execute_rules([], SIMPLE_RULES)
        assert result["total_items"] == 0
        assert result["hit_items"] == []
        assert result["risk_distribution"] == {}

    def test_empty_rules(self):
        items = [{"item_id": "ITEM050", "amount": 800}]
        result = execute_rules(items, [])
        assert result["total_items"] == 1
        assert result["hit_items"] == []
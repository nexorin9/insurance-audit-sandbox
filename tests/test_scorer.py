"""
规则引擎 — 风险评分计算单元测试
"""

import pytest
from src.engine_rules.scorer import (
    calculate_risk_score,
    get_risk_distribution,
    get_top_risk_categories,
    build_run_summary,
)


class TestCalculateRiskScore:
    def test_zero_hit(self):
        assert calculate_risk_score([]) == 0.0

    def test_single_hit(self):
        hit_rules = [{"risk_score": 80}]
        assert calculate_risk_score(hit_rules) == 80.0

    def test_multiple_hits_average(self):
        hit_rules = [{"risk_score": 60}, {"risk_score": 80}, {"risk_score": 100}]
        assert calculate_risk_score(hit_rules) == 80.0

    def test_high_frequency_bonus(self):
        # 同一规则触发多次（rule_id 相同），额外加权 10%
        hit_rules = [
            {"rule_id": "R001", "risk_score": 60},
            {"rule_id": "R001", "risk_score": 60},
        ]
        # 基础分: 60 + bonus: 60 * 0.1 = 66
        assert calculate_risk_score(hit_rules) == 66.0

    def test_capped_at_100(self):
        # 有显式 rule_id 时触发 bonus
        hit_rules = [{"rule_id": "R1", "risk_score": 90}, {"rule_id": "R1", "risk_score": 90}]
        # 基础分 90 + bonus 9 = 99
        assert calculate_risk_score(hit_rules) == 99.0

        # 超限场景：基础分 95 + bonus = 104.5 → cap 100
        hit_rules2 = [{"rule_id": "R2", "risk_score": 95}, {"rule_id": "R2", "risk_score": 95}]
        result = calculate_risk_score(hit_rules2)
        assert result <= 100.0


class TestGetRiskDistribution:
    def test_empty_hit_items(self):
        dist = get_risk_distribution([])
        assert dist == {}

    def test_single_category(self):
        hit_items = [
            {"item_id": "I1", "category": "药品", "risk_score": 70},
            {"item_id": "I2", "category": "药品", "risk_score": 90},
        ]
        dist = get_risk_distribution(hit_items)
        assert dist["药品"]["count"] == 2
        assert dist["药品"]["avg_score"] == 80.0
        assert dist["药品"]["total_score"] == 160.0

    def test_multiple_categories(self):
        hit_items = [
            {"item_id": "I1", "category": "药品", "risk_score": 70},
            {"item_id": "I2", "category": "耗材", "risk_score": 50},
            {"item_id": "I3", "category": "药品", "risk_score": 90},
        ]
        dist = get_risk_distribution(hit_items)
        assert dist["药品"]["count"] == 2
        assert dist["耗材"]["count"] == 1


class TestGetTopRiskCategories:
    def test_empty(self):
        assert get_top_risk_categories([]) == []

    def test_top_n_default(self):
        hit_items = [
            {"item_id": "I1", "category": "耗材", "risk_score": 30, "amount": 100},
            {"item_id": "I2", "category": "药品", "risk_score": 90, "amount": 200},
            {"item_id": "I3", "category": "手术", "risk_score": 70, "amount": 300},
        ]
        top = get_top_risk_categories(hit_items, top_n=3)
        assert len(top) == 3
        # 排序：药品(90) > 手术(70) > 耗材(30)
        assert top[0]["category"] == "药品"
        assert top[0]["avg_score"] == 90.0
        assert top[1]["category"] == "手术"
        assert top[2]["category"] == "耗材"

    def test_top_n_less_than_categories(self):
        hit_items = [
            {"item_id": "I1", "category": "药品", "risk_score": 90},
            {"item_id": "I2", "category": "耗材", "risk_score": 30},
            {"item_id": "I3", "category": "手术", "risk_score": 70},
        ]
        top = get_top_risk_categories(hit_items, top_n=2)
        assert len(top) == 2
        assert top[0]["category"] == "药品"
        assert top[1]["category"] == "手术"

    def test_total_amount_sum(self):
        hit_items = [
            {"item_id": "I1", "category": "药品", "risk_score": 80, "amount": 150.5},
            {"item_id": "I2", "category": "药品", "risk_score": 80, "amount": 249.5},
        ]
        top = get_top_risk_categories(hit_items, top_n=1)
        assert top[0]["total_amount"] == 400.0


class TestBuildRunSummary:
    def test_empty_run(self):
        run_result = {
            "run_id": "R001",
            "timestamp": "2024-01-01T00:00:00Z",
            "rule_set_version": "0.1.0",
            "total_items": 10,
            "hit_items": [],
            "risk_distribution": {},
        }
        summary = build_run_summary(run_result)
        assert summary["hit_count"] == 0
        assert summary["hit_rate"] == 0.0
        assert summary["overall_risk_score"] == 0.0

    def test_full_run(self):
        run_result = {
            "run_id": "R002",
            "timestamp": "2024-01-01T00:00:00Z",
            "rule_set_version": "0.1.0",
            "total_items": 20,
            "hit_items": [
                {"item_id": "I1", "category": "药品", "risk_score": 80, "amount": 100},
                {"item_id": "I2", "category": "药品", "risk_score": 80, "amount": 200},
                {"item_id": "I3", "category": "耗材", "risk_score": 50, "amount": 50},
            ],
            "risk_distribution": {},
        }
        summary = build_run_summary(run_result)
        assert summary["hit_count"] == 3
        assert summary["hit_rate"] == 0.15  # 3/20
        assert summary["overall_risk_score"] == 70.0  # (80+80+50)/3
        assert len(summary["top_risk_categories"]) == 2
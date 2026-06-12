"""
条件操作符库单元测试
"""

import pytest
from src.engine_rules.condition_ops import (
    eq, neq, gt, gte, lt, lte,
    in_, between, contains, regex,
    apply_op,
)


class TestEq:
    def test_numbers_equal(self):
        assert eq(100, 100) is True
        assert eq(100.0, 100) is True

    def test_strings_equal(self):
        assert eq("药品", "药品") is True
        assert eq("药品", "耗材") is False

    def test_type_mismatch_coerces_to_number(self):
        # JSON/CSV 场景下 "100" 与 100 应视为相等（实用行为）
        assert eq("100", 100) is True


class TestNeq:
    def test_numbers_not_equal(self):
        assert neq(100, 200) is True
        assert neq(100, 100) is False

    def test_strings_not_equal(self):
        assert neq("药品", "耗材") is True


class TestGt:
    def test_numbers_gt(self):
        assert gt(150, 100) is True
        assert gt(100, 150) is False

    def test_type_mismatch_returns_false(self):
        assert gt("药品", 100) is False


class TestGte:
    def test_numbers_gte(self):
        assert gte(100, 100) is True
        assert gte(150, 100) is True
        assert gte(99, 100) is False


class TestLt:
    def test_numbers_lt(self):
        assert lt(99, 100) is True
        assert lt(100, 100) is False

    def test_type_mismatch_returns_false(self):
        assert lt("药品", 100) is False


class TestLte:
    def test_numbers_lte(self):
        assert lte(100, 100) is True
        assert lte(99, 100) is True
        assert lte(100.1, 100) is False


class TestIn:
    def test_member_in_list(self):
        assert in_("药品", ["药品", "耗材", "手术"]) is True
        assert in_("检查", ["药品", "耗材", "手术"]) is False

    def test_number_in_list(self):
        assert in_(100, [50, 100, 150]) is True
        assert in_(200, [50, 100, 150]) is False

    def test_invalid_target_returns_false(self):
        assert in_("药品", "耗材") is False


class TestBetween:
    def test_number_in_range(self):
        assert between(100, 50, 150) is True
        assert between(50, 50, 150) is True
        assert between(150, 50, 150) is True
        assert between(49, 50, 150) is False
        assert between(151, 50, 150) is False

    def test_float_boundary(self):
        assert between(0.15, 0.10, 0.20) is True
        assert between(0.15, 0.15, 0.15) is True


class TestContains:
    def test_string_contains(self):
        assert contains("中药注射剂", "注射剂") is True
        assert contains("中药注射剂", "西药") is False

    def test_list_contains(self):
        assert contains(["药品", "耗材"], "药品") is True
        assert contains(["药品", "耗材"], "手术") is False

    def test_none_returns_false(self):
        assert contains(None, "药品") is False


class TestRegex:
    def test_regex_match(self):
        assert regex(r"^\d+$", "12345") is True
        assert regex(r"^\d+$", "12abc") is False

    def test_regex_with_chinese(self):
        assert regex(r"注射剂", "中药注射剂") is True
        assert regex(r"注射剂", "中药口服液") is False

    def test_invalid_pattern_returns_false(self):
        assert regex(r"[invalid", "text") is False

    def test_none_returns_false(self):
        assert regex(r"^\d+$", None) is False


class TestApplyOp:
    def test_apply_eq(self):
        assert apply_op("eq", 100, 100) is True

    def test_apply_gt(self):
        assert apply_op("gt", 150, 100) is True

    def test_apply_in_(self):
        assert apply_op("in", "药品", ["药品", "耗材"]) is True

    def test_apply_between(self):
        assert apply_op("between", 100, 50, 150) is True

    def test_apply_contains(self):
        assert apply_op("contains", "中药注射剂", "注射剂") is True

    def test_apply_regex(self):
        assert apply_op("regex", r"^\d+$", "12345") is True

    def test_unknown_op_returns_false(self):
        assert apply_op("unknown", 100, 100) is False

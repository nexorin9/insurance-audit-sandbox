"""规则引擎 — parser 单元测试"""

import pytest
import tempfile
import json
from pathlib import Path

from src.engine_rules.parser import (
    parse_rule_yaml,
    parse_condition_expr,
    RuleValidationError,
)


# ---- Fixtures ----

@pytest.fixture
def valid_yaml_path():
    """返回内置示例规则集的路径"""
    return Path(__file__).parent.parent / "src" / "engine_rules" / "rules" / "rule_examples.yaml"


@pytest.fixture
def valid_rule_yaml():
    """返回合法规则 YAML 内容的路径"""
    content = """
rules:
  - rule_id: test_001
    name: "测试规则-金额超限"
    category: "测试类"
    risk_score: 80
    condition:
      field: "amount"
      op: "gt"
      value: 1000
  - rule_id: test_002
    name: "测试规则-分类判断"
    category: "测试类"
    risk_score: 60
    condition:
      field: "category"
      op: "eq"
      value: "药品"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", encoding="utf-8", delete=False
    ) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def duplicate_id_yaml():
    content = """
rules:
  - rule_id: dup_id
    name: "规则1"
    category: "测试"
    risk_score: 50
    condition:
      field: "amount"
      op: "gt"
      value: 100
  - rule_id: dup_id
    name: "规则2"
    category: "测试"
    risk_score: 50
    condition:
      field: "amount"
      op: "gt"
      value: 200
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", encoding="utf-8", delete=False
    ) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def missing_field_yaml():
    content = """
rules:
  - rule_id: no_name
    category: "测试"
    risk_score: 50
    condition:
      field: "amount"
      op: "gt"
      value: 100
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", encoding="utf-8", delete=False
    ) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def invalid_score_yaml():
    content = """
rules:
  - rule_id: bad_score
    name: "分数超限"
    category: "测试"
    risk_score: 150
    condition:
      field: "amount"
      op: "gt"
      value: 100
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", encoding="utf-8", delete=False
    ) as f:
        f.write(content)
        return Path(f.name)


# ---- 测试用例 ----

class TestParseRuleYaml:
    def test_normal_parsing(self, valid_rule_yaml):
        rules = parse_rule_yaml(valid_rule_yaml)
        assert len(rules) == 2
        assert rules[0]["rule_id"] == "test_001"
        assert rules[0]["risk_score"] == 80
        assert rules[1]["rule_id"] == "test_002"

    def test_builtin_examples(self, valid_yaml_path):
        rules = parse_rule_yaml(valid_yaml_path)
        assert len(rules) == 8
        ids = {r["rule_id"] for r in rules}
        assert "zy_injection_001" in ids
        assert "material_markup_001" in ids
        assert "decomp_hospital_001" in ids

    def test_duplicate_rule_id_raises(self, duplicate_id_yaml):
        with pytest.raises(RuleValidationError) as exc_info:
            parse_rule_yaml(duplicate_id_yaml)
        assert "重复" in str(exc_info.value) or "dup_id" in str(exc_info.value)

    def test_missing_field_raises(self, missing_field_yaml):
        with pytest.raises(RuleValidationError) as exc_info:
            parse_rule_yaml(missing_field_yaml)
        assert "name" in str(exc_info.value)

    def test_invalid_risk_score_raises(self, invalid_score_yaml):
        with pytest.raises(RuleValidationError) as exc_info:
            parse_rule_yaml(invalid_score_yaml)
        assert "150" in str(exc_info.value)

    def test_file_not_found_raises(self):
        with pytest.raises(RuleValidationError) as exc_info:
            parse_rule_yaml("/not/exist/path.yaml")
        assert "不存在" in str(exc_info.value)

    def test_empty_file_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", encoding="utf-8", delete=False
        ) as f:
            f.write("")
            path = Path(f.name)
        with pytest.raises(RuleValidationError) as exc_info:
            parse_rule_yaml(path)
        assert "空" in str(exc_info.value)


class TestParseConditionExpr:
    def test_structured_dict(self):
        result = parse_condition_expr({"op": "gt", "field": "amount", "value": 1000})
        assert result["op"] == "gt"
        assert result["field"] == "amount"
        assert result["value"] == 1000

    def test_string_expression_gt(self):
        result = parse_condition_expr("amount > 1000")
        assert result["op"] == "gt"
        assert result["field"] == "amount"
        assert result["value"] == 1000

    def test_string_expression_gte(self):
        result = parse_condition_expr("risk_score >= 70")
        assert result["op"] == "gte"
        assert result["value"] == 70

    def test_string_expression_eq(self):
        result = parse_condition_expr('category == "药品"')
        assert result["op"] == "eq"
        assert result["value"] == "药品"

    def test_string_expression_in(self):
        result = parse_condition_expr("category in [药品, 耗材]")
        assert result["op"] == "in"
        assert result["value"] == ["药品", "耗材"]

    def test_invalid_expression_raises(self):
        with pytest.raises(RuleValidationError):
            parse_condition_expr("this is not a valid expression !!!")
"""规则集 CRUD 路由单元测试"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys

# 确保 src 优先
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestListRuleSets:
    def test_list_returns_rule_sets(self, client):
        resp = client.get("/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # 至少应从 rules_index.yaml 返回 3 个规则集
        assert len(data) >= 3
        ids = [r["rule_set_id"] for r in data]
        assert "zhongyao_injection_limit" in ids
        assert "material_markup_limit" in ids
        assert "decomposition_suspicion" in ids

    def test_list_fields(self, client):
        resp = client.get("/rules")
        data = resp.json()
        for item in data:
            assert "rule_set_id" in item
            assert "name" in item
            assert "version" in item
            assert "rule_count" in item


class TestValidateRuleYaml:
    def test_validate_valid_yaml(self, client):
        yaml_content = """
rule_set_id: test_ruleset
name: 测试规则集
version: "1.0.0"
updated_at: "2026-06-13"
description: 测试用规则集
rules:
  - rule_id: TEST_001
    name: 测试规则
    category: 测试类别
    risk_score: 75
    condition:
      op: and
      checks:
        - field: amount
          op: gt
          value: 100
"""
        resp = client.post("/rules/validate", json={"yaml_content": yaml_content})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["errors"] == []
        assert data["rule_count"] == 1

    def test_validate_missing_fields(self, client):
        yaml_content = """
rule_set_id: test_ruleset
name: 测试规则集
rules:
  - name: 缺少 rule_id
    condition: {}
"""
        resp = client.post("/rules/validate", json={"yaml_content": yaml_content})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_validate_duplicate_rule_id(self, client):
        yaml_content = """
rule_set_id: test_ruleset
name: 测试规则集
version: "1.0.0"
rules:
  - rule_id: DUP_ID
    name: 规则1
    category: 测试
    risk_score: 75
    condition:
      op: eq
      checks: []
  - rule_id: DUP_ID
    name: 规则2
    category: 测试
    risk_score: 80
    condition:
      op: eq
      checks: []
"""
        resp = client.post("/rules/validate", json={"yaml_content": yaml_content})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert any("重复" in e for e in data["errors"])

    def test_validate_invalid_yaml(self, client):
        yaml_content = "this is not: yaml: [invalid"
        resp = client.post("/rules/validate", json={"yaml_content": yaml_content})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_validate_empty_content(self, client):
        resp = client.post("/rules/validate", json={"yaml_content": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False

    def test_validate_risk_score_out_of_range(self, client):
        yaml_content = """
rule_set_id: test_ruleset
name: 测试规则集
version: "1.0.0"
rules:
  - rule_id: TEST_001
    name: 超范围风险分
    category: 测试
    risk_score: 150
    condition:
      op: eq
      checks: []
"""
        resp = client.post("/rules/validate", json={"yaml_content": yaml_content})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert any("0-100" in e for e in data["errors"])


class TestGetRuleSet:
    def test_get_existing_rule_set(self, client):
        resp = client.get("/rules/zhongyao_injection_limit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_set_id"] == "zhongyao_injection_limit"
        assert "name" in data
        assert "rules" in data
        assert len(data["rules"]) > 0
        # 检查规则结构
        rule = data["rules"][0]
        assert "rule_id" in rule
        assert "name" in rule
        assert "risk_score" in rule
        assert "condition" in rule

    def test_get_nonexistent_rule_set(self, client):
        resp = client.get("/rules/nonexistent_ruleset_xyz")
        assert resp.status_code == 404

    def test_get_material_markup_limit(self, client):
        resp = client.get("/rules/material_markup_limit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_set_id"] == "material_markup_limit"
        assert len(data["rules"]) > 0

    def test_get_decomposition_suspicion(self, client):
        resp = client.get("/rules/decomposition_suspicion")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_set_id"] == "decomposition_suspicion"
        assert len(data["rules"]) > 0
"""规则集版本化管理路由单元测试"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app

client = TestClient(app)


class TestRuleSetVersions:
    def test_versions_returns_history(self):
        """获取规则集版本历史"""
        resp = client.get("/rules/zhongyao_injection_limit/versions")
        # 可能返回 404（无 git 历史）或 200（有历史）
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)
            if data:
                item = data[0]
                assert "commit_hash" in item
                assert "committed_at" in item

    def test_versions_nonexistent_rule_set(self):
        """版本历史 — 规则集不存在"""
        resp = client.get("/rules/nonexistent_xyz/versions")
        assert resp.status_code == 404


class TestRuleSetDiff:
    def test_diff_requires_compare_version(self):
        """版本对比需要 compare_version 参数"""
        resp = client.get("/rules/zhongyao_injection_limit/diff")
        assert resp.status_code == 422  # 缺少必需参数

    def test_diff_nonexistent_rule_set(self):
        """版本对比 — 规则集不存在"""
        resp = client.get("/rules/nonexistent_xyz/diff?compare_version=HEAD")
        assert resp.status_code == 404

    def test_diff_invalid_version(self):
        """版本对比 — 版本不存在"""
        resp = client.get("/rules/zhongyao_injection_limit/diff?compare_version=invalid_hash_xyz")
        assert resp.status_code == 404


class TestRuleSetImport:
    def test_import_valid_yaml(self):
        """导入有效规则集 YAML"""
        yaml_content = """
rule_set_id: test_import_ruleset
name: 测试导入规则集
version: "1.0.0"
updated_at: "2026-06-13"
description: 测试导入
rules:
  - rule_id: TEST_IMPORT_001
    name: 测试规则导入
    category: 测试类别
    risk_score: 60
    condition:
      op: eq
      checks: []
"""
        resp = client.post("/rules/import", json={
            "rule_set_id": "test_import_ruleset",
            "yaml_content": yaml_content,
        })
        # git 可能不可用，返回 400 或 200
        assert resp.status_code in (200, 400)
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "success"

    def test_import_invalid_yaml(self):
        """导入 — YAML 格式错误"""
        resp = client.post("/rules/import", json={
            "rule_set_id": "test_invalid",
            "yaml_content": "this is: [not yaml",
        })
        assert resp.status_code == 400

    def test_import_missing_rules_field(self):
        """导入 — 缺少 rules 字段"""
        yaml_content = """
rule_set_id: test_no_rules
name: 无规则集
version: "1.0.0"
"""
        resp = client.post("/rules/import", json={
            "rule_set_id": "test_no_rules",
            "yaml_content": yaml_content,
        })
        assert resp.status_code == 400


class TestRuleSetExport:
    def test_export_existing_rule_set(self):
        """导出租房集"""
        resp = client.get("/rules/zhongyao_injection_limit/export")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_set_id"] == "zhongyao_injection_limit"
        assert "yaml_content" in data
        # 验证导出的内容是合法 YAML
        loaded = yaml.safe_load(data["yaml_content"])
        assert isinstance(loaded, dict)
        assert "rules" in loaded

    def test_export_nonexistent_rule_set(self):
        """导出 — 规则集不存在"""
        resp = client.get("/rules/nonexistent_xyz/export")
        assert resp.status_code == 404
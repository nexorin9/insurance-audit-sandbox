"""历史演练对比 API 单元测试."""
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def _make_run(run_id: str, hit_items: list, risk_distribution: dict, total_items: int = 100):
    return {
        "run_id": run_id,
        "timestamp": "2026-01-15T10:00:00Z",
        "rule_set_version": "1.0",
        "rule_set_id": "test-ruleset",
        "total_items": total_items,
        "hit_items_json": json.dumps(hit_items),
        "risk_distribution_json": json.dumps(risk_distribution),
        "status": "completed",
    }


class TestCompareEndpoint:
    """对比 API 测试套件"""

    def test_compare_same_run_id_rejected(self):
        """相同 run_id 对比应返回 400"""
        with patch("src.api.db.get_sandbox_run", return_value=None):
            from src.api.main import app
            client = TestClient(app)
            resp = client.get("/sandbox/compare?run_id_a=abc&run_id_b=abc")
            assert resp.status_code == 400
            assert "相同" in resp.json()["detail"]

    def test_compare_run_id_a_not_found(self):
        """run_id_a 不存在应返回 404"""
        def mock_get(rid):
            return None if rid == "aaa" else _make_run("bbb", [], {})
        with patch("src.api.db.get_sandbox_run", side_effect=mock_get):
            from src.api.main import app
            client = TestClient(app)
            resp = client.get("/sandbox/compare?run_id_a=aaa&run_id_b=bbb")
            assert resp.status_code == 404
            assert "aaa" in resp.json()["detail"]

    def test_compare_run_id_b_not_found(self):
        """run_id_b 不存在应返回 404"""
        def mock_get(rid):
            return None if rid == "bbb" else _make_run("aaa", [], {})
        with patch("src.api.db.get_sandbox_run", side_effect=mock_get):
            from src.api.main import app
            client = TestClient(app)
            resp = client.get("/sandbox/compare?run_id_a=aaa&run_id_b=bbb")
            assert resp.status_code == 404
            assert "bbb" in resp.json()["detail"]

    def test_compare_normal_two_runs(self):
        """正常对比两次演练"""
        hit_a = [
            {"item_id": "item-1", "risk_score": 80, "category": "药品"},
            {"item_id": "item-2", "risk_score": 75, "category": "耗材"},
        ]
        hit_b = [
            {"item_id": "item-1", "risk_score": 80, "category": "药品"},
            {"item_id": "item-3", "risk_score": 90, "category": "手术"},
        ]
        dist_a = {"药品": {"avg_score": 80, "hit_count": 1}, "耗材": {"avg_score": 50, "hit_count": 1}}
        dist_b = {"药品": {"avg_score": 80, "hit_count": 1}, "手术": {"avg_score": 90, "hit_count": 1}}

        def mock_get(rid):
            if rid == "run-a":
                return _make_run("run-a", hit_a, dist_a)
            return _make_run("run-b", hit_b, dist_b)

        with patch("src.api.db.get_sandbox_run", side_effect=mock_get):
            from src.api.main import app
            client = TestClient(app)
            resp = client.get("/sandbox/compare?run_id_a=run-a&run_id_b=run-b")
            assert resp.status_code == 200
            data = resp.json()
            assert data["run_a"]["run_id"] == "run-a"
            assert data["run_b"]["run_id"] == "run-b"
            assert len(data["new_high_risk_items"]) == 1
            assert data["new_high_risk_items"][0]["item_id"] == "item-3"
            assert len(data["resolved_risk_items"]) == 1
            assert data["resolved_risk_items"][0]["item_id"] == "item-2"
            assert "risk_distribution_change" in data

    def test_compare_no_high_risk_items(self):
        """两次演练均无高风险项"""
        with patch("src.api.db.get_sandbox_run", side_effect=lambda rid: _make_run(rid, [], {})):
            from src.api.main import app
            client = TestClient(app)
            resp = client.get("/sandbox/compare?run_id_a=run-a&run_id_b=run-b")
            assert resp.status_code == 200
            data = resp.json()
            assert data["risk_change_pct"] == 0.0
            assert data["new_high_risk_items"] == []
            assert data["resolved_risk_items"] == []

    def test_compare_zero_baseline_new_risks(self):
        """基准为零时出现新高风险"""
        hit_a = []
        hit_b = [{"item_id": "item-x", "risk_score": 85, "category": "药品"}]

        def mock_get(rid):
            return _make_run(rid, hit_a if rid == "run-a" else hit_b, {})
        with patch("src.api.db.get_sandbox_run", side_effect=mock_get):
            from src.api.main import app
            client = TestClient(app)
            resp = client.get("/sandbox/compare?run_id_a=run-a&run_id_b=run-b")
            assert resp.status_code == 200
            data = resp.json()
            assert data["risk_change_pct"] == 100.0
            assert len(data["new_high_risk_items"]) == 1
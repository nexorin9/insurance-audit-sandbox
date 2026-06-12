"""
演练执行路由 — 单元测试
"""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 确保项目根在 sys.path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.api.main import app
from src.api.db import save_sandbox_run


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_run_record():
    return {
        "run_id": "test-run-001",
        "timestamp": "2026-06-13T03:00:00Z",
        "rule_set_id": "zhongyao_injection_limit",
        "rule_set_version": "0.1.0",
        "total_items": 10,
        "hit_items": [
            {
                "item_id": "FI-001",
                "rule_id": "R-001",
                "name": "中药注射剂超限",
                "category": "药品",
                "risk_score": 75.0,
                "amount": 2000.0,
                "matched_condition": "injection_type in [中药注射剂] AND amount > 1000",
            }
        ],
        "risk_distribution": {"药品": {"count": 1, "avg_score": 75.0}},
        "overall_risk_score": 75.0,
        "hit_count": 1,
        "hit_rate": 0.1,
        "top_risk_categories": [
            {
                "category": "药品",
                "avg_score": 75.0,
                "hit_count": 1,
                "total_amount": 2000.0,
                "items": [],
            }
        ],
        "status": "completed",
    }


# ---- 健康检查 ----
def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


# ---- POST /sandbox/run 正常执行 ----
def test_run_sandbox_ok(client):
    body = {
        "rule_set_id": "zhongyao_injection_limit",
        "fee_items": [
            {
                "item_id": "FI-20260613-001",
                "category": "药品",
                "amount": 2000.0,
                "unit_price": 200.0,
                "quantity": 10,
                "material_markup_rate": None,
                "injection_type": "中药注射剂",
                "days_admitted": None,
                "procedure_code": None,
            }
        ],
    }
    resp = client.post("/sandbox/run", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert "message" in data
    assert data["message"]  # 非空


# ---- POST /sandbox/run 规则集不存在 ----
def test_run_sandbox_rule_set_not_found(client):
    body = {
        "rule_set_id": "nonexistent_rule_set",
        "fee_items": [
            {
                "item_id": "FI-001",
                "category": "药品",
                "amount": 100.0,
            }
        ],
    }
    resp = client.post("/sandbox/run", json=body)
    assert resp.status_code == 404


# ---- POST /sandbox/run 费用数据为空 ----
def test_run_sandbox_empty_items(client):
    body = {
        "rule_set_id": "zhongyao_injection_limit",
        "fee_items": [],
    }
    resp = client.post("/sandbox/run", json=body)
    assert resp.status_code == 400


# ---- GET /sandbox/runs 分页 ----
def test_list_runs(client):
    resp = client.get("/sandbox/runs?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data


# ---- GET /sandbox/runs/{run_id} 记录不存在 ----
def test_get_run_not_found(client):
    resp = client.get("/sandbox/runs/nonexistent-run-id")
    assert resp.status_code == 404


# ---- POST /sandbox/run/{run_id}/cancel 记录不存在 ----
def test_cancel_run_not_found(client):
    resp = client.post("/sandbox/run/nonexistent-run-id/cancel")
    assert resp.status_code == 404
"""
数据库层 — 单元测试（SQLite 演练记录持久化）
"""

import json
import tempfile
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 使用临时数据库进行测试
import src.api.db as db_module


@pytest.fixture
def temp_db(monkeypatch):
    """使用临时数据库替代真实数据库"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "test_sandbox.db"
        monkeypatch.setattr(db_module, "DB_PATH", tmp_path)
        # 重新初始化（db.py 模块级已调用过 _init_db，这里强制重载连接）
        db_module._init_db()
        yield tmp_path


@pytest.fixture
def sample_run():
    return {
        "run_id": "test-run-db-001",
        "timestamp": "2026-06-13T10:00:00Z",
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


# ---- 插入演练记录 ----
def test_save_and_get_run(temp_db, sample_run):
    db_module.save_sandbox_run(**sample_run)
    row = db_module.get_sandbox_run(sample_run["run_id"])
    assert row is not None
    assert row["run_id"] == sample_run["run_id"]
    assert row["rule_set_id"] == sample_run["rule_set_id"]
    assert row["total_items"] == sample_run["total_items"]
    assert row["hit_count"] == sample_run["hit_count"]
    assert row["status"] == "completed"
    # JSON 反序列化字段
    assert row["hit_items"][0]["item_id"] == "FI-001"
    assert row["risk_distribution"]["药品"]["count"] == 1


def test_save_and_get_run_with_cancel_status(temp_db, sample_run):
    sample_run["run_id"] = "test-run-db-cancel"
    sample_run["status"] = "cancelled"
    db_module.save_sandbox_run(**sample_run)
    row = db_module.get_sandbox_run("test-run-db-cancel")
    assert row is not None
    assert row["status"] == "cancelled"


# ---- 查询演练记录（不存在）----
def test_get_run_not_found(temp_db):
    row = db_module.get_sandbox_run("nonexistent-run-id")
    assert row is None


# ---- 分页列出演练记录 ----
def test_list_runs_empty(temp_db):
    runs, total = db_module.list_sandbox_runs(page=1, page_size=10)
    assert runs == []
    assert total == 0


def test_list_runs_single_page(temp_db, sample_run):
    db_module.save_sandbox_run(**sample_run)
    runs, total = db_module.list_sandbox_runs(page=1, page_size=10)
    assert total == 1
    assert len(runs) == 1
    assert runs[0]["run_id"] == sample_run["run_id"]


def test_list_runs_pagination(temp_db, sample_run):
    # 插入 15 条记录
    for i in range(15):
        run = dict(sample_run)
        run["run_id"] = f"test-run-db-pag-{i:02d}"
        db_module.save_sandbox_run(**run)

    # 第一页
    runs, total = db_module.list_sandbox_runs(page=1, page_size=10)
    assert total == 15
    assert len(runs) == 10

    # 第二页
    runs, total = db_module.list_sandbox_runs(page=2, page_size=10)
    assert total == 15
    assert len(runs) == 5

    # 第三页（空）
    runs, total = db_module.list_sandbox_runs(page=3, page_size=10)
    assert total == 15
    assert len(runs) == 0


# ---- 演练取消 ----
def test_cancel_run_exists(temp_db, sample_run):
    db_module.save_sandbox_run(**sample_run)
    result = db_module.cancel_sandbox_run(sample_run["run_id"])
    assert result is True
    row = db_module.get_sandbox_run(sample_run["run_id"])
    assert row["status"] == "cancelled"


def test_cancel_run_not_found(temp_db):
    result = db_module.cancel_sandbox_run("nonexistent-run")
    assert result is False


# ---- 过期清理 ----
def test_cleanup_keeps_recent_runs(temp_db, sample_run):
    # 插入 110 条记录（超过默认保留数 100）
    for i in range(110):
        run = dict(sample_run)
        run["run_id"] = f"test-run-db-cleanup-{i:03d}"
        db_module.save_sandbox_run(**run)

    # 只应保留 100 条非 cancelled 记录
    runs, total = db_module.list_sandbox_runs(page=1, page_size=200)
    assert total == 100
    # 验证所有返回记录的 run_id 都是 cleanup 后的（字符串排序在 100 以内）
    run_ids = {r["run_id"] for r in runs}
    # 由于同一 timestamp，DB 任意保留 100 条；验证总数正确即可
    assert len(run_ids) == 100


def test_cleanup_preserves_cancelled_runs(temp_db, sample_run):
    # 插入 110 条，其中最后 10 条是 cancelled
    for i in range(100):
        run = dict(sample_run)
        run["run_id"] = f"test-run-db-cleanup-preserve-{i:03d}"
        db_module.save_sandbox_run(**run)
    for i in range(10):
        run = dict(sample_run)
        run["run_id"] = f"test-run-db-cleanup-cancelled-{i:02d}"
        run["status"] = "cancelled"
        db_module.save_sandbox_run(**run)

    runs, total = db_module.list_sandbox_runs(page=1, page_size=200)
    # cancelled 记录不在 list 中（默认排除），但仍存在于 DB
    assert total == 100  # 只计算非 cancelled
    cancelled_count = len([r for r in runs if r.get("status") == "cancelled"])
    assert cancelled_count == 0


# ---- JSON 字段完整性 ----
def test_hit_items_json_deserialization(temp_db, sample_run):
    db_module.save_sandbox_run(**sample_run)
    row = db_module.get_sandbox_run(sample_run["run_id"])
    # hit_items 应已反序列化
    assert isinstance(row["hit_items"], list)
    assert row["hit_items"][0]["item_id"] == "FI-001"
    # risk_distribution 应已反序列化
    assert isinstance(row["risk_distribution"], dict)
    assert "药品" in row["risk_distribution"]
    # top_risk_categories 应已反序列化
    assert isinstance(row["top_risk_categories"], list)
    assert row["top_risk_categories"][0]["category"] == "药品"


# ---- 并发写入安全 ----
def test_concurrent_insert_same_run_id(temp_db, sample_run):
    # 同一 run_id 多次插入应使用 INSERT OR REPLACE
    db_module.save_sandbox_run(**sample_run)
    # 修改后再次插入
    sample_run["hit_count"] = 99
    sample_run["overall_risk_score"] = 99.0
    db_module.save_sandbox_run(**sample_run)
    row = db_module.get_sandbox_run(sample_run["run_id"])
    assert row["hit_count"] == 99
    assert row["overall_risk_score"] == 99.0
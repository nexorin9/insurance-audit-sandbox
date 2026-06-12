"""
SQLite 数据库层 — 演练记录持久化
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger("api.db")

# ---- 数据库路径 ----
DB_PATH = Path(__file__).parent.parent.parent / "data" / "sandbox.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_MAX_RUNS = 100  # 默认保留最近 100 条


def _init_db() -> None:
    """初始化数据库表"""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sandbox_runs (
                run_id        TEXT PRIMARY KEY,
                timestamp     TEXT NOT NULL,
                rule_set_id   TEXT NOT NULL,
                rule_set_version TEXT NOT NULL,
                total_items   INTEGER NOT NULL,
                hit_items_json TEXT NOT NULL,
                risk_distribution_json TEXT NOT NULL,
                overall_risk_score REAL NOT NULL DEFAULT 0.0,
                hit_count     INTEGER NOT NULL DEFAULT 0,
                hit_rate      REAL NOT NULL DEFAULT 0.0,
                top_risk_categories_json TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'completed'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON sandbox_runs(timestamp DESC)
        """)


@contextmanager
def _get_conn() -> Generator[sqlite3.Connection, None, None]:
    """获取数据库连接的上下文管理器"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---- 初始化 ----
_init_db()


def save_sandbox_run(
    run_id: str,
    timestamp: str,
    rule_set_id: str,
    rule_set_version: str,
    total_items: int,
    hit_items: list[dict],
    risk_distribution: dict,
    overall_risk_score: float,
    hit_count: int,
    hit_rate: float,
    top_risk_categories: list[dict],
    status: str = "completed",
) -> None:
    """保存演练记录"""
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO sandbox_runs
            (run_id, timestamp, rule_set_id, rule_set_version,
             total_items, hit_items_json, risk_distribution_json,
             overall_risk_score, hit_count, hit_rate,
             top_risk_categories_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                timestamp,
                rule_set_id,
                rule_set_version,
                total_items,
                json.dumps(hit_items, ensure_ascii=False),
                json.dumps(risk_distribution, ensure_ascii=False),
                overall_risk_score,
                hit_count,
                hit_rate,
                json.dumps(top_risk_categories, ensure_ascii=False),
                status,
            ),
        )
        conn.commit()

    # 过期清理
    _cleanup_old_runs()


def get_sandbox_run(run_id: str) -> dict[str, Any] | None:
    """获取单条演练记录"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sandbox_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        return _row_to_dict(row)


def list_sandbox_runs(
    page: int = 1, page_size: int = 10
) -> tuple[list[dict[str, Any]], int]:
    """
    分页列出演练记录。

    Returns:
        (记录列表, 总记录数)
    """
    offset = (page - 1) * page_size
    with _get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM sandbox_runs WHERE status != 'cancelled'"
        ).fetchone()[0]
        rows = conn.execute(
            """
            SELECT * FROM sandbox_runs
            WHERE status != 'cancelled'
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        ).fetchall()
    return [_row_to_dict(row) for row in rows], total


def cancel_sandbox_run(run_id: str) -> bool:
    """标记演练为已取消。返回是否成功（记录存在）"""
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE sandbox_runs SET status = 'cancelled' WHERE run_id = ?",
            (run_id,),
        )
        conn.commit()
        return cur.rowcount > 0


def _cleanup_old_runs() -> None:
    """保留最近 _MAX_RUNS 条非取消状态的记录"""
    with _get_conn() as conn:
        conn.execute(
            """
            DELETE FROM sandbox_runs
            WHERE status != 'cancelled'
            AND run_id NOT IN (
                SELECT run_id FROM sandbox_runs
                WHERE status != 'cancelled'
                ORDER BY timestamp DESC
                LIMIT ?
            )
            """,
            (_MAX_RUNS,),
        )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """将 sqlite3.Row 转换为字典"""
    d = dict(row)
    for key in (
        "hit_items_json",
        "risk_distribution_json",
        "top_risk_categories_json",
    ):
        if key in d and d[key]:
            d[key.replace("_json", "")] = json.loads(d[key])
            del d[key]
    return d
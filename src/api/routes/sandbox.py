"""
演练执行路由
POST /sandbox/run   — 执行演练
GET  /sandbox/run/{run_id}  — 获取演练结果
GET  /sandbox/runs         — 演练记录列表（分页）
POST /sandbox/run/{run_id}/cancel — 取消演练
"""

import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..db import (
    cancel_sandbox_run,
    get_sandbox_run,
    list_sandbox_runs,
    save_sandbox_run,
)
from ..models import FeeItem, SandboxRun, SandboxRunCreate
from engine_rules.executor import execute_rules
from engine_rules.parser import parse_rule_yaml
from engine_rules.scorer import build_run_summary
from engine_rules.conflict_detector import detect_rule_conflicts

logger = logging.getLogger("api.routes.sandbox")

# ---- 规则集目录 ----
RULES_DIR = Path(__file__).parent.parent.parent / "engine" / "rules"


class RunResponse(BaseModel):
    """POST /sandbox/run 响应"""
    run_id: str
    message: str


class RunListResponse(BaseModel):
    """GET /sandbox/runs 响应"""
    runs: list[SandboxRun]
    total: int
    page: int
    page_size: int
    total_pages: int


class CancelResponse(BaseModel):
    """POST /sandbox/run/{run_id}/cancel 响应"""
    run_id: str
    cancelled: bool
    message: str


class ConflictResponse(BaseModel):
    """GET /sandbox/run/{run_id}/conflicts 响应"""
    run_id: str
    conflict_count: int
    conflicts: list[dict]


router = APIRouter(prefix="/sandbox", tags=["演练"])


def _load_rules(rule_set_id: str) -> list[dict]:
    """加载指定规则集，返回规则列表"""
    yaml_file = RULES_DIR / f"{rule_set_id}.yaml"
    if not yaml_file.exists():
        raise HTTPException(status_code=404, detail=f"规则集 {rule_set_id} 不存在")
    return parse_rule_yaml(yaml_file)


def _fee_items_to_dict(items: list[FeeItem]) -> list[dict]:
    """FeeItem 列表转换为普通 dict 列表"""
    return [item.model_dump() for item in items]


# ---- 执行演练 ----
@router.post("/run", response_model=RunResponse)
async def run_sandbox(body: SandboxRunCreate):
    """执行飞检规则演练。

    加载指定规则集，对费用明细逐条执行规则匹配，计算风险评分，
    持久化演练记录并返回 run_id。

    演练流程：加载规则集 → 逐条匹配 → 风险评分 → 持久化 → 返回结果。

    Args:
        body: 包含 rule_set_id 和 fee_items 的演练请求。

    Returns:
        RunResponse: 包含 run_id 和执行摘要信息。

    Raises:
        400: fee_items 为空。
        404: 规则集不存在或加载失败。
    """
    rule_set_id = body.rule_set_id
    fee_items = body.fee_items

    if not fee_items:
        raise HTTPException(status_code=400, detail="费用数据不能为空")

    # 加载规则集
    try:
        rules = _load_rules(rule_set_id)
    except Exception as e:
        logger.warning("加载规则集 %s 失败: %s", rule_set_id, e)
        raise HTTPException(status_code=404, detail=f"规则集 {rule_set_id} 加载失败: {e}")

    # 转换为 dict
    items_dict = _fee_items_to_dict(fee_items)

    # 执行规则引擎
    run_result = execute_rules(items_dict, rules)

    # 计算汇总
    summary = build_run_summary(run_result)

    # 持久化
    try:
        save_sandbox_run(
            run_id=summary["run_id"],
            timestamp=summary["timestamp"],
            rule_set_id=rule_set_id,
            rule_set_version=summary["rule_set_version"],
            total_items=summary["total_items"],
            hit_items=run_result["hit_items"],
            risk_distribution=run_result["risk_distribution"],
            overall_risk_score=summary["overall_risk_score"],
            hit_count=summary["hit_count"],
            hit_rate=summary["hit_rate"],
            top_risk_categories=summary["top_risk_categories"],
        )
    except Exception as e:
        logger.error("保存演练记录失败 run_id=%s: %s", summary["run_id"], e)
        # 降级：仍返回结果，只是不持久化
        pass

    logger.info(
        "演练执行完成 run_id=%s rule_set_id=%s total=%d hit=%d",
        summary["run_id"], rule_set_id, summary["total_items"], summary["hit_count"],
    )

    return RunResponse(
        run_id=summary["run_id"],
        message=f"演练执行完成，命中 {summary['hit_count']} 条，共 {summary['total_items']} 条费用明细",
    )


# ---- 获取演练结果 ----
@router.get("/run/{run_id}", response_model=SandboxRun)
async def get_run(run_id: str):
    """获取指定演练的完整执行结果。

    从 SQLite 数据库读取持久化的演练记录，返回统计摘要及风险分布。

    Args:
        run_id: 演练记录唯一ID（UUID）。

    Returns:
        SandboxRun: 包含演练统计、高风险项数量、风险分布等完整信息。

    Raises:
        404: 演练记录不存在。
    """
    record = get_sandbox_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"演练记录 {run_id} 不存在")

    return SandboxRun(
        run_id=record["run_id"],
        timestamp=record["timestamp"],
        rule_set_version=record["rule_set_version"],
        total_items=record["total_items"],
        hit_count=record["hit_count"],
        hit_rate=record["hit_rate"],
        overall_risk_score=record["overall_risk_score"],
        risk_distribution=record["risk_distribution"],
        top_risk_categories=record["top_risk_categories"],
    )


# ---- 演练记录列表 ----
@router.get("/runs", response_model=RunListResponse)
async def list_runs(page: int = 1, page_size: int = 10):
    """列出演练记录（分页）。

    按执行时间倒序返回演练摘要列表。

    Args:
        page: 页码，从 1 开始，默认 1。
        page_size: 每页记录数，范围 1~100，默认 10。

    Returns:
        RunListResponse: 包含演练记录列表、总数、页码信息。
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    runs, total = list_sandbox_runs(page=page, page_size=page_size)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return RunListResponse(
        runs=[
            SandboxRun(
                run_id=r["run_id"],
                timestamp=r["timestamp"],
                rule_set_version=r["rule_set_version"],
                total_items=r["total_items"],
                hit_count=r["hit_count"],
                hit_rate=r["hit_rate"],
                overall_risk_score=r["overall_risk_score"],
                risk_distribution=r["risk_distribution"],
                top_risk_categories=r["top_risk_categories"],
            )
            for r in runs
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---- 取消演练 ----
@router.post("/run/{run_id}/cancel", response_model=CancelResponse)
async def cancel_run(run_id: str):
    """标记指定演练为已取消状态。

    取消后的演练仍保留记录，但无法生成报告。

    Args:
        run_id: 演练记录唯一ID。

    Returns:
        CancelResponse: cancelled=true 表示标记成功。

    Raises:
        404: 演练记录不存在。
    """
    cancelled = cancel_sandbox_run(run_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail=f"演练记录 {run_id} 不存在")

    logger.info("演练已取消 run_id=%s", run_id)
    return CancelResponse(
        run_id=run_id,
        cancelled=True,
        message="演练已标记为取消",
    )


# ---- 冲突检测 ----
@router.get("/run/{run_id}/conflicts", response_model=ConflictResponse)
async def get_run_conflicts(run_id: str):
    """检测指定演练中同一费用明细触发多条互斥规则的场景。

    冲突类型包括：同一费用触发同类 action 相反的规则、同一字段多次矛盾判定等。

    Args:
        run_id: 演练记录唯一ID。

    Returns:
        ConflictResponse: 包含冲突数量及详细冲突清单。

    Raises:
        404: 演练记录不存在。
    """
    record = get_sandbox_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"演练记录 {run_id} 不存在")

    hit_items = record.get("hit_items", [])
    conflicts = detect_rule_conflicts(hit_items)

    logger.info("冲突检测完成 run_id=%s conflict_count=%d", run_id, len(conflicts))
    return ConflictResponse(
        run_id=run_id,
        conflict_count=len(conflicts),
        conflicts=conflicts,
    )
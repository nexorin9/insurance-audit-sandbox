"""历史演练对比 API 路由 — GET /sandbox/compare."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


@router.get("/compare")
async def compare_runs(
    run_id_a: str = Query(
        ...,
        description="第一次（基准）演练的 run_id",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    ),
    run_id_b: str = Query(
        ...,
        description="第二次（对比）演练的 run_id",
        examples=["660e8400-e29b-41d4-a716-446655440001"],
    ),
):
    """对比两次演练结果，输出风险变化趋势。

    分析两次演练的高风险项变化、风险分布变化，并计算风险变化百分比。
    适用于评估整改效果或监测风险趋势。

    Args:
        run_id_a: 基准演练的 ID。
        run_id_b: 对比演练的 ID。

    Returns:
        包含 run_a/run_b 基本信息、risk_change_pct、
        新增高风险项、已缓解高风险项、风险分布变化。

    Raises:
        400: 两次演练 ID 相同。
        404: 指定演练记录不存在。
    """
    from src.api.db import get_sandbox_run

    if run_id_a == run_id_b:
        raise HTTPException(status_code=400, detail="两次演练 ID 相同，请使用不同的演练记录进行对比")

    run_a = get_sandbox_run(run_id_a)
    run_b = get_sandbox_run(run_id_b)

    if run_a is None:
        raise HTTPException(status_code=404, detail=f"演练记录 {run_id_a} 不存在")
    if run_b is None:
        raise HTTPException(status_code=404, detail=f"演练记录 {run_id_b} 不存在")

    # 解析 JSON 字段
    import json

    hit_items_a = json.loads(run_a.get("hit_items_json", "[]"))
    hit_items_b = json.loads(run_b.get("hit_items_json", "[]"))
    risk_dist_a = json.loads(run_a.get("risk_distribution_json", "{}"))
    risk_dist_b = json.loads(run_b.get("risk_distribution_json", "{}"))

    # 高风险项阈值
    HIGH_RISK_THRESHOLD = 70

    def extract_high_risk_item_ids(hit_items: list) -> set:
        return {
            item["item_id"]
            for item in hit_items
            if item.get("risk_score", 0) >= HIGH_RISK_THRESHOLD
        }

    high_risk_a = extract_high_risk_item_ids(hit_items_a)
    high_risk_b = extract_high_risk_item_ids(hit_items_b)

    # 新增高风险项：在 B 中但不在 A 中
    new_high_risk_items = [
        item for item in hit_items_b
        if item["item_id"] in high_risk_b and item["item_id"] not in high_risk_a
    ]

    # 已缓解高风险项：在 A 中但不在 B 中
    resolved_risk_items = [
        item for item in hit_items_a
        if item["item_id"] in high_risk_a and item["item_id"] not in high_risk_b
    ]

    # 风险变化百分比（基于高风险项数量）
    count_a = len(high_risk_a)
    count_b = len(high_risk_b)
    if count_a > 0:
        risk_change_pct = ((count_b - count_a) / count_a) * 100
    else:
        risk_change_pct = 100.0 if count_b > 0 else 0.0

    # 风险分布变化
    def calc_category_stats(risk_dist: dict) -> dict:
        return {
            cat: {"avg_score": data.get("avg_score", 0), "hit_count": data.get("hit_count", 0)}
            for cat, data in risk_dist.items()
        }

    stats_a = calc_category_stats(risk_dist_a)
    stats_b = calc_category_stats(risk_dist_b)

    all_categories = set(stats_a.keys()) | set(stats_b.keys())
    risk_distribution_change = {}
    for cat in all_categories:
        before = stats_a.get(cat, {"avg_score": 0, "hit_count": 0})
        after = stats_b.get(cat, {"avg_score": 0, "hit_count": 0})
        risk_distribution_change[cat] = {
            "before_avg_score": before["avg_score"],
            "after_avg_score": after["avg_score"],
            "score_change": after["avg_score"] - before["avg_score"],
            "before_hit_count": before["hit_count"],
            "after_hit_count": after["hit_count"],
            "hit_count_change": after["hit_count"] - before["hit_count"],
        }

    return {
        "run_a": {
            "run_id": run_id_a,
            "timestamp": run_a.get("timestamp"),
            "rule_set_version": run_a.get("rule_set_version"),
            "total_items": run_a.get("total_items"),
            "high_risk_count": len(high_risk_a),
        },
        "run_b": {
            "run_id": run_id_b,
            "timestamp": run_b.get("timestamp"),
            "rule_set_version": run_b.get("rule_set_version"),
            "total_items": run_b.get("total_items"),
            "high_risk_count": len(high_risk_b),
        },
        "risk_change_pct": round(risk_change_pct, 2),
        "new_high_risk_items": new_high_risk_items,
        "resolved_risk_items": resolved_risk_items,
        "risk_distribution_change": risk_distribution_change,
    }
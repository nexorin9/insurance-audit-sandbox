"""
规则引擎 — 风险评分计算
根据命中规则计算费用明细风险评分，生成风险分布统计与 TOP 高风险类别。
"""

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


def calculate_risk_score(hit_rules: list[dict], item: dict | None = None) -> float:
    """
    根据命中规则列表计算单条费用明细的风险评分（0-100）。

    Args:
        hit_rules: 该费用明细命中的规则列表，每条须含 risk_score
        item: 费用明细（可选，用于未来扩展加权因子）

    Returns:
        风险评分（0-100，浮点数，保留两位小数）
    """
    if not hit_rules:
        return 0.0

    # 基础分：命中规则 risk_score 的平均值
    base_scores = [r.get("risk_score", 0) for r in hit_rules]
    base_score = sum(base_scores) / len(base_scores)

    # 加权分：统计不同规则 ID 的出现次数，高频规则（>1次）额外加权 10%
    rule_counts: dict[str, int] = defaultdict(int)
    for rule in hit_rules:
        rule_id = rule.get("rule_id", "")
        rule_counts[rule_id] += 1

    bonus = 0.0
    for rule_id, count in rule_counts.items():
        # 仅对显式 rule_id（非空）的高频触发加 bonus
        if count > 1 and rule_id:
            score = 0
            for r in hit_rules:
                if r.get("rule_id", "") == rule_id:
                    score = r.get("risk_score", 0)
                    break
            bonus += score * 0.1

    total = base_score + bonus
    return round(min(total, 100.0), 2)


def get_risk_distribution(hit_items: list[dict]) -> dict[str, dict[str, Any]]:
    """
    按类别统计命中次数与平均风险分数。

    Args:
        hit_items: executor.execute_rules() 返回的 hit_items 列表

    Returns:
        风险分布字典：
        {
            category: {
                "count": int,
                "avg_score": float,
                "total_score": float,
                "items": list[dict]  # 该类别的命中条目（不含 risk_distribution 内部数据）
            }
        }
    """
    distribution: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "total_score": 0.0, "items": []}
    )

    for item in hit_items:
        cat = item.get("category", "unknown")
        score = item.get("risk_score", 0)
        distribution[cat]["count"] += 1
        distribution[cat]["total_score"] += score
        distribution[cat]["items"].append(item)

    # 计算平均分并整理输出结构
    result = {}
    for cat, stats in distribution.items():
        count = stats["count"]
        total = stats["total_score"]
        result[cat] = {
            "count": count,
            "avg_score": round(total / count, 2) if count > 0 else 0.0,
            "total_score": round(total, 2),
            "items": stats["items"],
        }

    return result


def get_top_risk_categories(
    hit_items: list[dict], top_n: int = 5
) -> list[dict[str, Any]]:
    """
    提取 TOP N 高风险类别。

    Args:
        hit_items: executor.execute_rules() 返回的 hit_items 列表
        top_n: 返回条数，默认 5

    Returns:
        TOP 高风险类别列表，每条含：
        {
            "category": str,
            "avg_score": float,
            "hit_count": int,
            "total_amount": float,
            "items": list[dict]  # 该类别下所有命中条目（不含内部统计字段）
        }
    """
    dist = get_risk_distribution(hit_items)

    # 按 avg_score 降序排序
    sorted_cats = sorted(
        dist.items(),
        key=lambda x: (x[1]["avg_score"], x[1]["count"]),
        reverse=True,
    )

    top = []
    for cat, stats in sorted_cats[:top_n]:
        # 计算该类别下所有条目的总金额
        total_amount = sum(
            (item.get("amount") or 0)
            for item in stats["items"]
            if item.get("amount") is not None
        )

        top.append({
            "category": cat,
            "avg_score": stats["avg_score"],
            "hit_count": stats["count"],
            "total_amount": round(total_amount, 2),
            "items": stats["items"],
        })

    return top


def build_run_summary(run_result: dict) -> dict[str, Any]:
    """
    根据 executor 的完整运行结果构建汇总报告。

    Args:
        run_result: executor.execute_rules() 返回的完整结果字典

    Returns:
        汇总字典，含：
        {
            "run_id": str,
            "timestamp": str,
            "rule_set_version": str,
            "total_items": int,
            "hit_count": int,
            "hit_rate": float,
            "overall_risk_score": float,  # 所有命中条目的平均风险分
            "risk_distribution": dict,
            "top_risk_categories": list[dict]
        }
    """
    hit_items = run_result.get("hit_items", [])
    total_items = run_result.get("total_items", 0)

    hit_count = len(hit_items)
    hit_rate = round(hit_count / total_items, 4) if total_items > 0 else 0.0

    # 整体风险分：所有命中条目的 risk_score 平均值
    if hit_items:
        overall = round(
            sum(item.get("risk_score", 0) for item in hit_items) / hit_count, 2
        )
    else:
        overall = 0.0

    dist = get_risk_distribution(hit_items)
    top = get_top_risk_categories(hit_items, top_n=5)

    return {
        "run_id": run_result.get("run_id", ""),
        "timestamp": run_result.get("timestamp", ""),
        "rule_set_version": run_result.get("rule_set_version", ""),
        "total_items": total_items,
        "hit_count": hit_count,
        "hit_rate": hit_rate,
        "overall_risk_score": overall,
        "risk_distribution": dist,
        "top_risk_categories": top,
    }
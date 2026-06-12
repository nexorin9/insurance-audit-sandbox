"""
规则引擎 — 规则执行器
遍历费用明细，对每条记录执行规则集，输出命中结果。
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .condition_ops import apply_op

logger = logging.getLogger(__name__)


# ---- 费用字段白名单（用于警告未知字段）----
KNOWN_FIELDS = {
    "item_id", "category", "amount", "unit_price", "quantity",
    "material_markup_rate", "injection_type", "days_admitted",
    "procedure_code", "readmission_flag",
}


def execute_rules(items: list[dict], rules: list[dict]) -> dict:
    """
    对费用明细集合执行规则集。

    Args:
        items: 费用明细列表，每条须含 item_id
        rules: 结构化规则列表（来自 parser.parse_rule_yaml）

    Returns:
        执行结果字典：
        {
            run_id: str,
            timestamp: str (ISO 8601),
            rule_set_version: str,
            total_items: int,
            hit_items: list[dict],
            risk_distribution: dict[category -> {count, avg_score}]
        }
    """
    run_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    hit_items: list[dict] = []
    risk_distribution: dict[str, dict] = {}

    for item in items:
        # 未知字段警告
        for field in item:
            if field not in KNOWN_FIELDS:
                logger.warning(
                    "run_id=%s | item_id=%s | unknown field %r (value=%r)",
                    run_id, item.get("item_id"), field, item.get(field),
                )

        # 边界金额检查
        amount = item.get("amount")
        if amount is not None:
            if not isinstance(amount, (int, float)):
                logger.warning(
                    "run_id=%s | item_id=%s | amount is not numeric: %r",
                    run_id, item.get("item_id"), amount,
                )
            elif amount < 0:
                logger.warning(
                    "run_id=%s | item_id=%s | amount is negative: %s",
                    run_id, item.get("item_id"), amount,
                )

        for rule in rules:
            hit, matched_condition = _evaluate_rule(rule, item, run_id)
            if hit:
                hit_item = {
                    "item_id": item.get("item_id"),
                    "rule_id": rule["rule_id"],
                    "name": rule["name"],
                    "category": rule["category"],
                    "risk_score": rule["risk_score"],
                    "amount": amount,
                    "matched_condition": matched_condition,
                }
                hit_items.append(hit_item)

                cat = rule["category"]
                if cat not in risk_distribution:
                    risk_distribution[cat] = {"count": 0, "total_score": 0}
                risk_distribution[cat]["count"] += 1
                risk_distribution[cat]["total_score"] += rule["risk_score"]

    # 计算各类别平均风险分
    for cat, stats in risk_distribution.items():
        if stats["count"] > 0:
            stats["avg_score"] = round(stats["total_score"] / stats["count"], 2)
        else:
            stats["avg_score"] = 0.0
        del stats["total_score"]  # 只保留 count 和 avg_score

    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "rule_set_version": "0.1.0",
        "total_items": len(items),
        "hit_items": hit_items,
        "risk_distribution": risk_distribution,
    }


def _evaluate_rule(rule: dict, item: dict, run_id: str) -> tuple[bool, str]:
    """
    对单条费用明细评估单条规则。

    Returns:
        (是否命中, matched_condition 描述字符串)
    """
    condition = rule.get("condition")

    # ---- 复合条件：op="and"/"or" + checks[] ----
    if isinstance(condition, dict) and "checks" in condition:
        checks = condition["checks"]
        logic_op = condition.get("op", "and")
        results: list[bool] = []

        for check in checks:
            sub_hit, sub_desc = _evaluate_single_check(check, item, run_id)
            results.append(sub_hit)

        if logic_op == "and":
            hit = all(results)
        elif logic_op == "or":
            hit = any(results)
        else:
            logger.warning("run_id=%s | rule_id=%s | unknown logic op %s, treating as and",
                           run_id, rule["rule_id"], logic_op)
            hit = all(results)

        matched_condition = f"{logic_op.upper()}(" + ", ".join(
            f"{c['field']} {c['op']} {c['value']}" for c in checks
        ) + ")"

        return hit, matched_condition

    # ---- 简单条件：field + op + value ----
    if isinstance(condition, dict):
        hit, matched_condition = _evaluate_single_check(condition, item, run_id)
        return hit, matched_condition

    # ---- 字符串表达式（直接透传，不解析）----
    if isinstance(condition, str):
        # 不支持直接执行字符串表达式，记录并返回 False
        logger.warning(
            "run_id=%s | rule_id=%s | string condition not supported: %s",
            run_id, rule["rule_id"], condition,
        )
        return False, condition

    # 未知格式
    logger.warning(
        "run_id=%s | rule_id=%s | unknown condition type: %s",
        run_id, rule["rule_id"], type(condition).__name__,
    )
    return False, ""


def _evaluate_single_check(check: dict, item: dict, run_id: str) -> tuple[bool, str]:
    """
    评估单个检查条件（field + op + value）。

    Returns:
        (是否命中, 条件描述字符串)
    """
    field = check.get("field")
    op = check.get("op")
    value = check.get("value")

    if not field or not op:
        logger.warning(
            "run_id=%s | check missing field/op: %s",
            run_id, check,
        )
        return False, ""

    field_value = item.get(field)

    # 缺失字段 → 视为 False，不抛异常
    if field_value is None:
        desc = f"{field} {op} {value} [field missing]"
        return False, desc

    # ---- 根据操作符类型分发参数 ----
    if op == "in":
        # value 是列表
        hit = apply_op(op, field_value, value)
    elif op == "between":
        # value 是 [lo, hi]
        if isinstance(value, (list, tuple)) and len(value) == 2:
            lo, hi = value[0], value[1]
            hit = apply_op(op, field_value, lo, hi)
        else:
            logger.warning(
                "run_id=%s | between op requires [lo, hi] list, got %s",
                run_id, value,
            )
            hit = False
    elif op == "contains":
        # value 是单个值（needle）
        hit = apply_op(op, field_value, value)
    elif op == "regex":
        # pattern 在 value，text 是 field_value
        hit = apply_op(op, value, field_value)
    else:
        # eq/neq/gt/gte/lt/lte: (a, b)
        hit = apply_op(op, field_value, value)

    desc = f"{field} {op} {value}"
    return hit, desc
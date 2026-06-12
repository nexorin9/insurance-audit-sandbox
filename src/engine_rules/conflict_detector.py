"""
规则冲突检测
检测同一费用明细触发多条互斥规则的场景，生成冲突清单。
"""

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


# ---- 互斥规则定义（category 内 action 相反的规则组）----
# 格式：category -> list of (rule_id 前缀模式, 互斥描述)
# 互斥类型：
#   - "limit_vs_exempt": 限用 vs 豁免（同一药品既有限制又有豁免）
#   - "rate_opposite": 加价率限制方向相反（同时要求加价率 > X 且 < Y）
#   - "duplicate": 同一规则被触发多次
#   - "days_conflict": 住院天数限制矛盾（同时要求 < X 且 > Y）

MUTUALLY_EXCLUSIVE_RULES: dict[str, list[tuple[str, str]]] = {
    # 药品类：中药注射剂限制规则内部冲突
    "药品": [
        ("zhongyao_injection_limit", "limit_vs_exempt"),
        ("material_markup_limit", "rate_opposite"),
    ],
    # 耗材类：加价率矛盾
    "耗材": [
        ("material_markup_limit", "rate_opposite"),
    ],
    # 住院类：分解住院相关规则内部冲突
    "住院": [
        ("decomposition_suspicion", "days_conflict"),
    ],
}


def detect_rule_conflicts(hit_items: list[dict]) -> list[dict[str, Any]]:
    """
    检测命中规则列表中的冲突。

    Args:
        hit_items: executor.execute_rules() 返回的 hit_items 列表
                   每条须含：item_id, rule_id, name, category, risk_score

    Returns:
        冲突清单列表，每条含：
        {
            "item_id": str,
            "conflicting_rules": list[dict],   # 冲突的规则列表
            "conflict_type": str,              # 冲突类型
            "suggested_resolution": str,       # 建议处理方式
        }
    """
    conflicts: list[dict[str, Any]] = []

    # ---- 按 item_id 分组 ----
    items_by_id: dict[str, list[dict]] = defaultdict(list)
    for item in hit_items:
        item_id = item.get("item_id")
        if item_id:
            items_by_id[item_id].append(item)

    for item_id, rules in items_by_id.items():
        if len(rules) < 2:
            continue  # 单规则不涉及冲突

        # ---- 检测同一 category 内的互斥规则 ----
        rules_by_category: dict[str, list[dict]] = defaultdict(list)
        for rule in rules:
            cat = rule.get("category", "unknown")
            rules_by_category[cat].append(rule)

        for cat, cat_rules in rules_by_category.items():
            if len(cat_rules) < 2:
                continue

            # 检测 duplicate（同 rule_id 被触发多次）
            rule_id_counts: dict[str, int] = defaultdict(int)
            for rule in cat_rules:
                rule_id_counts[rule.get("rule_id", "")] += 1

            duplicates = {
                rid: cnt for rid, cnt in rule_id_counts.items()
                if cnt > 1 and rid
            }
            if duplicates:
                conflicts.append({
                    "item_id": item_id,
                    "conflicting_rules": _dedup_rules([r for r in cat_rules if duplicates.get(r.get("rule_id", ""), 0) > 0]),
                    "conflict_type": "duplicate",
                    "suggested_resolution": "同一规则被多次触发，请检查费用明细是否符合该规则条件，或该规则是否存在重复条件判断",
                })

            # 检测 rate_opposite（同一 category 内加价率方向相反）
            markup_rules = [r for r in cat_rules if "markup" in r.get("rule_id", "").lower() or "markup" in r.get("name", "").lower()]
            if len(markup_rules) >= 2:
                # 提取所有含 markup_rate 相关条件描述
                markup_strs = [r.get("matched_condition", "") for r in markup_rules]
                # 如果同时包含 > 和 < 方向的条件，视为冲突
                has_gt = any(">" in s for s in markup_strs)
                has_lt = any("<" in s for s in markup_strs)
                if has_gt and has_lt:
                    conflicts.append({
                        "item_id": item_id,
                        "conflicting_rules": markup_rules,
                        "conflict_type": "rate_opposite",
                        "suggested_resolution": "加价率限制方向矛盾（同时触发上限和下限规则），建议确认费用明细加价率是否在合规范围内",
                    })

            # 检测 limit_vs_exempt（限用 vs 豁免）
            # 通过规则名判断：含"限制"vs含"豁免"或"除外"
            limit_rules = [r for r in cat_rules if "限制" in r.get("name", "") or "限用" in r.get("name", "")]
            exempt_rules = [r for r in cat_rules if "豁免" in r.get("name", "") or "除外" in r.get("name", "")]
            if limit_rules and exempt_rules:
                conflicts.append({
                    "item_id": item_id,
                    "conflicting_rules": limit_rules + exempt_rules,
                    "conflict_type": "limit_vs_exempt",
                    "suggested_resolution": "费用明细同时触发限用规则和豁免规则，请确认费用明细的实际使用场景是否符合院内医保政策",
                })

            # 检测 days_conflict（住院天数矛盾）
            days_rules = [r for r in cat_rules if "days" in r.get("matched_condition", "").lower() or "住院" in r.get("name", "")]
            if len(days_rules) >= 2:
                days_strs = [r.get("matched_condition", "") for r in days_rules]
                has_gt = any(">" in s for s in days_strs)
                has_lt = any("<" in s for s in days_strs)
                if has_gt and has_lt:
                    conflicts.append({
                        "item_id": item_id,
                        "conflicting_rules": days_rules,
                        "conflict_type": "days_conflict",
                        "suggested_resolution": "住院天数限制矛盾（同时触发上限和下限规则），建议确认患者实际住院天数是否符合分解住院认定标准",
                    })

    return conflicts


def _dedup_rules(rules: list[dict]) -> list[dict]:
    """去重规则列表（按 rule_id）"""
    seen: set[str] = set()
    result = []
    for r in rules:
        rid = r.get("rule_id", "")
        if rid not in seen:
            seen.add(rid)
            result.append(r)
    return result